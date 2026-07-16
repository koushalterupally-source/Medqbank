import sys, html as htmlmod, re, json, io, base64, time
sys.path.insert(0,'/home/user/Medqbank/scripts')
from cereb_parse import extract_questions
from pyq_ocr import data_url_to_img, parse_question_image, content_bbox
from PIL import Image

def esc(t):
    return (t or '').replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')

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
        options = [esc((o.get('text') or '').strip()) for o in opts_data]
        if stem:
            question_html = esc(stem)
        elif qimgs:
            # rare: options are text but the stem lives in an image -> OCR/keep it
            img = data_url_to_img(qimgs[0])
            r = parse_question_image(img)
            question_html = esc(r['stem'].strip())
            if r['figure']:
                crop = img.crop(r['figure'])
                if crop.width > 40 and crop.height > 40:
                    question_html += fig_html(img_to_datauri(crop))
        if not question_html.strip():
            question_html = '<em>Question text was not included in the source. Pick the correct option below.</em>'
    elif qimgs:
        # IMAGE-TYPE: OCR stem, crop figure, options -> buttons
        img = data_url_to_img(qimgs[0])
        r = parse_question_image(img)
        stem = r['stem'].strip()
        # options: OCR text for phrase options; for "identify the labelled structure"
        # questions the options are just the labels A/B/C/D, so force position letters.
        ocr_opts = [o.strip() for o in r['options']]
        multichar = [o for o in ocr_opts if len(o) > 2]
        if len(multichar) >= len(opts_data) - 1 and len(ocr_opts) >= len(opts_data):
            for i in range(len(opts_data)):
                txt = ocr_opts[i] if i < len(ocr_opts) and ocr_opts[i] else chr(65 + i)
                options.append(esc(txt))
        else:
            options = [chr(65 + i) for i in range(len(opts_data))]
        parts = []
        if stem and stem.lower() not in ('maxillary sinus',):  # avoid obvious figure-label-only stems
            parts.append(esc(stem))
        if r['figure']:
            crop = img.crop(r['figure'])
            # ignore tiny/degenerate crops
            if crop.width > 40 and crop.height > 40:
                parts.append(fig_html(img_to_datauri(crop)))
        question_html = ''.join(parts) or '(See figure)'
    else:
        stem = strip_tags(qsrc.get('text',''))
        question_html = esc(stem)
        options = [esc((o.get('text') or '').strip()) or chr(65+i) for i,o in enumerate(opts_data)]

    # explanation: prefer text; else OCR explanation image to text; keep image if figure-heavy
    exp = {}
    etxt = strip_tags(qsrc.get('explanation','')) if qsrc.get('explanation') else ''
    eimgs = qsrc.get('explanation_images') or []
    ca = (qsrc.get('correct_answer') or '').strip()
    if ca:
        exp['short'] = f"Ans: {esc(ca)}"
    if etxt:
        exp['detail'] = esc(etxt)
    elif eimgs:
        try:
            eimg = data_url_to_img(eimgs[0])
            import pytesseract
            otext = pytesseract.image_to_string(eimg).strip()
            otext = re.sub(r'\n{2,}','\n', otext)
            if len(re.sub(r'[^A-Za-z]','',otext)) > 30:
                exp['detail'] = esc(otext).replace('\n','<br>')
            else:
                exp['detail'] = fig_html(img_to_datauri(eimg))
        except Exception:
            pass

    return {
        'id': qid, 'subject': subject, 'subtopic': subtopic, 'exam': 'PYQ',
        'year': subtopic, 'question': question_html, 'options': options,
        'correct': correct, 'explanation': exp,
    }

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
    for ti, sd in enumerate(srcdocs):
        tname = htmlmod.unescape(testnames[ti]) if ti < len(testnames) else f'Test {ti+1}'
        qs = extract_questions(htmlmod.unescape(sd))
        for qi, q in enumerate(qs):
            slug = re.sub(r'[^a-z0-9]+','_',subject.lower()).strip('_')
            qid = f'pyq_{slug}_{ti}_{qi}'
            out.append(build(q, subject, tname, qid))
    return out

if __name__ == '__main__':
    t0=time.time()
    data = process_file('/root/.claude/uploads/2fb0de8b-c54a-5792-bf95-e53b5184420f/af242e5f-ENT_PYQs1.html', 'ENT')
    json.dump(data, open('/tmp/claude-0/-home-user-Medqbank/2fb0de8b-c54a-5792-bf95-e53b5184420f/scratchpad/ent_pyqs.json','w'), ensure_ascii=False)
    withfig=sum(1 for q in data if 'q-images' in q['question'])
    print(f'ENT PYQ: {len(data)} questions, {withfig} with figures, {time.time()-t0:.0f}s')
