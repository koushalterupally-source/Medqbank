import base64, io, re, json, os, sys, html
import pytesseract
from PIL import Image

OPT_RE = re.compile(r'^\s*[\(]?([a-dA-D])[\)\.]\s*')

def data_url_to_img(u):
    hdr, b64 = u.split(',', 1)
    return Image.open(io.BytesIO(base64.b64decode(b64))).convert('RGB')

def ocr_lines(img, scale=2):
    """Return list of line dicts with text + bbox, OCR'd on an upscaled copy (coords back in original scale)."""
    big = img.resize((img.width*scale, img.height*scale), Image.LANCZOS)
    d = pytesseract.image_to_data(big, output_type=pytesseract.Output.DICT)
    from collections import defaultdict
    groups = defaultdict(list)
    for i in range(len(d['text'])):
        t = d['text'][i]
        if not t.strip():
            continue
        key = (d['block_num'][i], d['par_num'][i], d['line_num'][i])
        groups[key].append((d['left'][i], d['top'][i], d['width'][i], d['height'][i], t, int(d['conf'][i])))
    lines = []
    for ws in groups.values():
        ws.sort(key=lambda w: w[0])
        top = min(w[1] for w in ws)/scale; bot = max(w[1]+w[3] for w in ws)/scale
        left = min(w[0] for w in ws)/scale; right = max(w[0]+w[2] for w in ws)/scale
        text = ' '.join(w[4] for w in ws)
        conf = sum(max(w[5],0) for w in ws)/len(ws)
        lines.append({'top':top,'bot':bot,'left':left,'right':right,'text':text,'conf':conf})
    lines.sort(key=lambda l: l['top'])
    return lines

def content_bbox(img, y0, y1, ink_thresh=200):
    """Fast bbox of dark content within vertical band [y0,y1] using PIL. Return (l,t,r,b) or None."""
    from PIL import ImageFilter
    W,H = img.size
    y0 = max(0,int(y0)); y1 = min(H,int(y1))
    if y1-y0 <= 0:
        return None
    band = img.convert('L').crop((0,y0,W,y1))
    # ink mask: dark pixels -> 255
    mask = band.point(lambda p: 255 if p < ink_thresh else 0)
    # despeckle to drop stray single pixels/antialias noise
    mask = mask.filter(ImageFilter.MedianFilter(3))
    bbox = mask.getbbox()
    if not bbox:
        return None
    l,t,r,b = bbox
    return (max(0,l-8), max(0,t+y0-8), min(W,r+8), min(H,b+y0+8))

def parse_question_image(img):
    """Return dict: stem(text), options(list up to 4 text), figure_bbox or None."""
    lines = ocr_lines(img)
    # locate header
    hdr_idx = next((i for i,l in enumerate(lines) if re.match(r'^\s*Question\s*\d+', l['text'], re.I)), -1)
    start = hdr_idx+1 if hdr_idx>=0 else 0
    # option lines: those matching a)/b)/c)/d)
    opt_idxs = [i for i,l in enumerate(lines) if OPT_RE.match(l['text'])]
    opt_start = opt_idxs[0] if opt_idxs else len(lines)
    opt_y = lines[opt_start]['top'] if opt_idxs else img.height
    # stem lines: contiguous well-aligned text after header, before figure/options
    stem_lines = []
    if start < len(lines):
        base_left = lines[start]['left']
        med_h = 18
        prev_bot = None
        for l in lines[start:opt_start]:
            gap_ok = prev_bot is None or (l['top']-prev_bot) <= 1.9*med_h
            align_ok = abs(l['left']-base_left) <= 45
            texty = l['conf']>=55 and len(re.sub(r'[^A-Za-z]','',l['text']))>=3
            if gap_ok and align_ok and texty:
                stem_lines.append(l); prev_bot = l['bot']
            else:
                break
    stem_bot = stem_lines[-1]['bot'] if stem_lines else (lines[start]['top'] if start<len(lines) else 0)
    stem = ' '.join(l['text'] for l in stem_lines).strip()
    # options text (strip label prefix, force order)
    options = []
    for i in opt_idxs[:4]:
        options.append(OPT_RE.sub('', lines[i]['text']).strip())
    # figure detection: content between stem_bot and opt_y that isn't the stem
    fig = None
    band_top = stem_bot + 6
    band_bot = opt_y - 6
    if band_bot - band_top > 25:
        fig = content_bbox(img, band_top, band_bot)
    return {'stem':stem,'options':options,'figure':fig,'n_opts':len(options)}

if __name__ == '__main__':
    img = data_url_to_img(open('/tmp/claude-0/-home-user-Medqbank/2fb0de8b-c54a-5792-bf95-e53b5184420f/scratchpad/q1_url.txt').read())
    print(parse_question_image(img))
