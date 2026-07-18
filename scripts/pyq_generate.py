import sys, html as htmlmod, re, json, io, base64, time
sys.path.insert(0,'/home/user/Medqbank/scripts')
from cereb_parse import extract_questions
from pyq_ocr import data_url_to_img, parse_question_image, content_bbox, ocr_lines, OPT_RE
from PIL import Image

def esc(t):
    # Source option/explanation text sometimes already contains HTML entities --
    # occasionally even double-escaped ones baked in by the original exporter
    # (e.g. "&amp;gt;150" for what should just be ">150"). Decode repeatedly until
    # it stabilizes so any level of pre-existing escaping is fully unwound before
    # a single clean re-escape; plain text has nothing to decode so this is a
    # no-op for it, and it terminates immediately once nothing changes.
    t = t or ''
    while True:
        unescaped = htmlmod.unescape(t)
        if unescaped == t:
            break
        t = unescaped
    return t.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

COMMON_WORDS = set('the and of to in is was for that with as are this be or an '
                    'which but not all have had one what when he she it his her '
                    'at from by on can may these into also more most such'.split())

def ocr_quality_ok(text):
    """Heuristic: does this OCR'd text read like real English, or is it garbled?
    Genuine prose has a healthy density of very common short words; character-level
    OCR corruption mangles those too, so a garbled passage's density is near zero."""
    words = re.findall(r"[a-zA-Z']+", text.lower())
    if len(words) < 12:
        return False
    common_hits = sum(1 for w in words if w in COMMON_WORDS)
    return common_hits / len(words) > 0.10

def strip_option_prefix(t):
    """Some source option 'text' fields carry a duplicated/garbled label prefix
    baked in by the original exporter (e.g. "a b) It arises...", "Cc) It gives
    rise...", "I d) Acute pancreatitis...") where the real content starts right
    after it. Strip a leading 1-2 char prefix ending in ')' -- deliberately NOT
    '.', since a period there collides with genuine content like genus
    abbreviations ("E.coli", "M. tuberculosis") which must never be truncated."""
    return re.sub(r'^\s*[A-Za-z]\s*\S?\)\s*', '', t)

def strip_trailing_watermark(t):
    """Drop a bare reference/slide number stuck onto the end of option text
    (a source-image watermark bleeding into the last option), without touching
    options that are legitimately numeric."""
    m = re.match(r'^(.*\D)\s+\d{3,6}$', t)
    if m and len(m.group(1).strip()) >= 3:
        return m.group(1).strip()
    return t

def clean_explanation(text):
    """Tidy an OCR'd / HTML explanation: drop the 'Solution to Question N:' style
    boilerplate prefix (matched structurally so it survives OCR garbling of the
    word 'Solution'), dedupe repeated lines, collapse blank runs."""
    if not text:
        return ''
    t = re.sub(r'^.{0,30}?Question\s*\d+\s*[:.]?\s*(<br>)?', '', text, flags=re.I)
    t = re.sub(r'^\s*(Explanation|Answer)\s*[:\-.]?\s*(<br>)?', '', t, flags=re.I)
    parts = re.split(r'(?:<br>\s*)+', t)
    out = []
    for p in parts:
        p = p.strip()
        # strip a stray leading curly-quote/bullet OCR artifact (source slides used
        # bullet glyphs that tesseract frequently misreads as a leading quote mark)
        p = re.sub(r"^[‘’“”'\"]\s*", '', p)
        if not p:
            continue
        # drop bare reference/slide numbers baked into the source images as a watermark
        if re.fullmatch(r'\d{2,6}', p):
            continue
        if out and out[-1].lower() == p.lower():   # skip consecutive duplicate lines
            continue
        out.append(p)
    return '<br>'.join(out)

def crop_stem_figure(img, lines):
    """Crop the original question image to keep header-less stem + figure,
    dropping the baked-in options strip. Falls back to the full image if the
    crop would be suspicious (guarantees no lost context)."""
    W, H = img.size
    hdr = next((l for l in lines if re.match(r'^\s*Question\s*\d+', l['text'], re.I)), None)
    optlines = [l for l in lines if OPT_RE.match(l['text'])]
    opt = optlines[0] if optlines else None
    top = int(hdr['bot'] + 4) if hdr else 0
    bot = int(opt['top'] - 4) if (opt and opt['top'] > 0.35 * H) else H
    if bot - top < 0.25 * H:          # crop looks wrong -> keep whole image
        top, bot = 0, H
    return img.crop((0, max(0, top), W, min(H, bot))), optlines

def strip_tags(h):
    h = re.sub(r'<span[^>]*>.*?</span>', '', h, count=1, flags=re.DOTALL)  # drop badge
    h = re.sub(r'<br\s*/?>', ' ', h)
    h = re.sub(r'<[^>]+>', '', h)
    return htmlmod.unescape(h).strip()

def img_to_datauri(img, maxw=680, q=72):
    if img.width > maxw:
        img = img.resize((maxw, round(img.height*maxw/img.width)), Image.LANCZOS)
    buf = io.BytesIO(); img.convert('RGB').save(buf, 'JPEG', quality=q, optimize=True)
    return 'data:image/jpeg;base64,'+base64.b64encode(buf.getvalue()).decode()

def fig_html(datauri):
    return f'<div class="q-images"><img src="{datauri}" alt="figure" loading="lazy"></div>'

def correct_index(opts):
    return next((i for i,o in enumerate(opts) if o.get('correct')), 0)

def build(qsrc, subject, subtopic, qid):
    opts_data = qsrc.get('options') or []
    has_text_opts = any((o.get('text') or '').strip() for o in opts_data)
    correct = correct_index(opts_data)
    qimgs = qsrc.get('question_images') or []
    question_html = ''
    options = []

    if has_text_opts:
        # TEXT-TYPE: real text already present
        stem = strip_tags(qsrc.get('text',''))
        options = [esc(strip_trailing_watermark(strip_option_prefix((o.get('text') or '').strip())))
                   for o in opts_data]
        if stem:
            question_html = esc(stem)
        elif qimgs:
            # rare: options are text but the stem lives in an image -> OCR it, but
            # OCR of a stem-only image can be badly garbled (character-level errors
            # that still look like words), so verify it reads like real English
            # before trusting it; otherwise show the image itself so nothing false
            # or unreadable is presented as the question.
            img = data_url_to_img(qimgs[0])
            lines = ocr_lines(img)
            hdr_idx = next((i for i, l in enumerate(lines)
                             if re.match(r'^\s*Question\s*\d+', l['text'], re.I)), -1)
            if hdr_idx == -1 and lines:
                # OCR sometimes mangles "Question N:" badly enough to miss the
                # strict match above; a short first line that doesn't read like
                # real prose is almost always that garbled header bleeding into
                # the stem, not real content -- skip it too rather than let the
                # garbage leak into the question text.
                first = lines[0]['text'].strip()
                if len(first) <= 25 and not ocr_quality_ok(first):
                    hdr_idx = 0
            stem_lines = lines[hdr_idx + 1:] if hdr_idx >= 0 else lines
            opt_idx = next((i for i, l in enumerate(stem_lines) if OPT_RE.match(l['text'])),
                            len(stem_lines))
            ocr_stem = ' '.join(l['text'] for l in stem_lines[:opt_idx]).strip()
            if len(ocr_stem) >= 15 and ocr_quality_ok(ocr_stem):
                question_html = esc(ocr_stem)
            else:
                question_html = fig_html(img_to_datauri(img, maxw=680, q=70))
        if not question_html.strip():
            question_html = '<em>Question text was not included in the source. Pick the correct option below.</em>'
    elif qimgs:
        # IMAGE-TYPE: the whole question (stem + options + any figure) is baked into
        # one image. OCR is used to try to recover clean phrase options as tappable
        # buttons and to crop off the redundant options strip, but a cropped/lettered
        # result is only trusted when confident; otherwise the FULL original image is
        # shown so a bad crop or missed option line can never silently lose content.
        img = data_url_to_img(qimgs[0])
        lines = ocr_lines(img)
        crop, optlines = crop_stem_figure(img, lines)
        ocr_opts = [strip_trailing_watermark(OPT_RE.sub('', l['text']).strip())
                    for l in optlines[:len(opts_data)]]
        multichar = [o for o in ocr_opts if len(o) > 2]
        confident = (len(ocr_opts) >= len(opts_data)
                     and len(multichar) >= len(opts_data) - 1)
        use_crop = confident and crop.height >= 0.35 * img.height
        shown = crop if use_crop else img
        question_html = fig_html(img_to_datauri(shown, maxw=680, q=70))
        if confident:
            options = [esc(ocr_opts[i]) if ocr_opts[i] else chr(65 + i)
                       for i in range(len(opts_data))]
        else:
            options = [chr(65 + i) for i in range(len(opts_data))]
            # Low OCR confidence forces a bare-letter fallback for the tappable
            # buttons, which can mask the SAME "references a list that's never
            # shown" problem seen elsewhere: e.g. baked-in options "a) 1 and 2"
            # / "b) 1 and 4" referencing numbered statements that don't appear
            # anywhere. Check the raw (pre-fallback) OCR text for that pattern
            # even though it wasn't confident enough to use as button labels.
            combo_hits = sum(1 for o in ocr_opts if _is_combo_code(o))
            if combo_hits >= 2:
                options = ['__UNANSWERABLE__'] * len(opts_data)
    else:
        stem = strip_tags(qsrc.get('text',''))
        question_html = esc(stem)
        options = [esc(strip_trailing_watermark(strip_option_prefix((o.get('text') or '').strip())))
                   or chr(65 + i) for i, o in enumerate(opts_data)]

    # explanation: prefer text; else OCR explanation image to text; keep image if figure-heavy
    exp = {}
    etxt = strip_tags(qsrc.get('explanation','')) if qsrc.get('explanation') else ''
    eimgs = qsrc.get('explanation_images') or []
    ca = (qsrc.get('correct_answer') or '').strip()
    if ca:
        exp['short'] = f"Ans: {esc(ca)}"
    if etxt:
        exp['detail'] = clean_explanation(esc(etxt))
    elif eimgs:
        try:
            eimg = data_url_to_img(eimgs[0])
            import pytesseract
            otext = pytesseract.image_to_string(eimg).strip()
            otext = re.sub(r'\n{2,}', '\n', otext)
            if ocr_quality_ok(otext):
                exp['detail'] = clean_explanation(esc(otext).replace('\n', '<br>'))
            else:
                exp['detail'] = fig_html(img_to_datauri(eimg))
        except Exception:
            pass

    return {
        'id': qid, 'subject': subject, 'subtopic': subtopic, 'exam': 'PYQ',
        'year': subtopic, 'question': question_html, 'options': options,
        'correct': correct, 'explanation': exp,
    }

def _is_combo_code(o):
    """A 'select which combination' style option that only makes sense if a
    numbered/lettered list of items was given elsewhere -- plain number
    combinations ("1,2" / "2,3,4 are correct"), match-pair codes ("1-D, 2-C,
    3-B, 4-A"), or roman-numeral combinations ("ii,iii"). Requires an actual
    separator (comma/dash/'and') so a genuine single short answer (a lab
    value, a dosage, an age, "C1", "B") is never mistaken for one."""
    o = o.strip()
    if not o or len(o) > 25:
        return False
    if not re.search(r'[,\-]|\band\b', o, re.I):
        return False
    residual = re.sub(r'and|are|correct|only|is|[A-DivxIVX\d\-,\s]', '', o, flags=re.I)
    return residual == '' and bool(re.search(r'[ivx\d]', o, re.I))

def is_unanswerable(built_q):
    """Some source questions reference a numbered/lettered list of items in
    their options (e.g. "1,2" / "1-D, 2-C, 3-B, 4-A" / "ii,iii") but the
    actual list of what those items *are* was never captured anywhere in the
    export -- not in the stem, not as an image, nothing recoverable. These
    are genuinely unanswerable as they exist in the source and are excluded
    rather than shipped as an unsolvable trick question. A 3-of-4 majority is
    enough (rather than requiring all 4) so one option mangled by OCR beyond
    recognition doesn't let an otherwise-obvious case slip through."""
    opts = built_q['options']
    if opts and opts[0] == '__UNANSWERABLE__':
        return True  # flagged inline in build() from pre-fallback OCR text
    if len(opts) < 3:
        return False
    if sum(1 for o in opts if _is_combo_code(o)) < len(opts) - 1:
        return False
    stem_text = re.sub(r'<[^>]+>', ' ', built_q['question'])
    return not re.search(r'\b[1I]\s*[.)]\s*\w', stem_text)

def process_file(path, subject):
    raw = open(path, encoding='utf-8', errors='replace').read()
    h2s = [htmlmod.unescape(re.sub(r'<[^>]+>','',m)).strip() for m in re.findall(r'<h2[^>]*>(.*?)</h2>', raw, re.DOTALL)]
    srcdocs = re.findall(r'srcdoc="(.*?)"></iframe>', raw, re.DOTALL)
    n = len(srcdocs)
    if len(h2s) == n:
        testnames = h2s                       # all headings are test names
    elif len(h2s) == n + 1:
        testnames = h2s[1:]                   # first heading is a page title
    else:
        testnames = [f'Test {i+1}' for i in range(n)]
    out = []
    skipped = 0
    for ti, sd in enumerate(srcdocs):
        tname = htmlmod.unescape(testnames[ti]) if ti < len(testnames) else f'Test {ti+1}'
        qs = extract_questions(htmlmod.unescape(sd))
        for qi, q in enumerate(qs):
            slug = re.sub(r'[^a-z0-9]+','_',subject.lower()).strip('_')
            qid = f'pyq_{slug}_{ti}_{qi}'
            built = build(q, subject, tname, qid)
            if is_unanswerable(built):
                skipped += 1
                continue
            out.append(built)
    if skipped:
        print(f'  ({subject}: skipped {skipped} unanswerable questions -- referenced a numbered list never captured in the source)')
    return out

if __name__ == '__main__':
    t0=time.time()
    data = process_file('/root/.claude/uploads/2fb0de8b-c54a-5792-bf95-e53b5184420f/af242e5f-ENT_PYQs1.html', 'ENT')
    json.dump(data, open('/tmp/claude-0/-home-user-Medqbank/2fb0de8b-c54a-5792-bf95-e53b5184420f/scratchpad/ent_pyqs.json','w'), ensure_ascii=False)
    withfig=sum(1 for q in data if 'q-images' in q['question'])
    print(f'ENT PYQ: {len(data)} questions, {withfig} with figures, {time.time()-t0:.0f}s')
