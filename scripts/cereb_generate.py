import html as htmlmod, re, json, os, sys
sys.path.insert(0, '/home/user/Medqbank/scripts')
from cereb_parse import extract_tests

UP = '/root/.claude/uploads/2fb0de8b-c54a-5792-bf95-e53b5184420f'
OUT = '/home/user/Medqbank/android/app/src/main/assets/cereb'

# upload filename -> (output json filename, subject display name, slug)
MAP = [
    ('d25b3e1c-CEREB_Anatomy.html',                 'anatomy.json',                      'Anatomy'),
    ('73871979-CEREB_Anesthesia.html',              'anesthesia.json',                   'Anesthesia'),
    ('49156533-CEREB_Biochemistry.html',            'biochemistry.json',                 'Biochemistry'),
    ('17c63732-CEREB_Dermatology.html',             'dermatology.json',                  'Dermatology'),
    ('86244489-CEREB_ENT_1.html',                   'ent.json',                          'ENT'),
    ('b9b728d5-CEREB_Forensic_Medicine_1.html',     'forensic_medicine.json',            'Forensic Medicine'),
    ('708e5a4c-CEREB_Medicine.html',                'medicine.json',                     'Medicine'),
    ('44aceae8-CEREB_Microbiology_1.html',          'microbiology.json',                 'Microbiology'),
    ('0c5b337b-CEREB_Obstetrics__Gynecology_1.html','obstetrics_gynaecology.json',       'Obstetrics & Gynaecology'),
    ('c31cbf3b-CEREB_Ophthalmology_1.html',         'ophthalmology.json',                'Ophthalmology'),
    ('beeb267f-CEREB_BTR.html',                     'best_of_the_rest.json',             'Best of the Rest'),
    ('5b08f8c4-CEREB_BTRs.html',                    'best_of_the_rest_subject_wise.json','Best of the Rest (Subject-wise)'),
    ('7e5f9b53-CEREB_Grand_Tests_1.html',           'grand_tests.json',                  'Grand Tests'),
    ('3da1315c-cereb_g_t.html',                     'grand_tests_2.json',                'Grand Tests 2'),
    ('c4a07717-CEREB_previous_year_tests_1.html',   'previous_year_tests.json',          'Previous Year Tests'),
]

def esc(t):
    if t is None: return ''
    return (t.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'))

def img_html(urls, cls):
    if not urls: return ''
    parts = ''.join(
        f'<img src="{htmlmod.escape(u, quote=True)}" alt="figure" loading="lazy">'
        for u in urls if u)
    if not parts: return ''
    return f'<div class="{cls}">{parts}</div>'

REF_RE = re.compile(r'Ref(?:erence)?\s*[:\-]\s*(.+?)(?:</li>|</p>|$)', re.I | re.S)

def build_question(q, qid, subject, subtopic):
    text = (q.get('text') or '').strip()
    qhtml = esc(text)
    qimgs = q.get('question_images') or []
    if qimgs:
        qhtml += img_html(qimgs, 'q-images')
    opts = q.get('options') or []
    options = [esc((o.get('text') or '').strip()) for o in opts]
    correct = next((i for i, o in enumerate(opts) if o.get('correct')), 0)
    # explanation
    short = esc((q.get('correct_answer') or '').strip())
    detail = (q.get('explanation') or '').strip()   # already HTML
    eimgs = q.get('explanation_images') or []
    if eimgs:
        detail += img_html(eimgs, 'exp-images')
    exp = {}
    if short: exp['short'] = short
    if detail: exp['detail'] = detail
    m = REF_RE.search(q.get('explanation') or '')
    if m:
        ref = re.sub(r'<[^>]+>', '', m.group(1)).strip()
        if ref and len(ref) < 400:
            exp['ref'] = ref
    return {
        'id': qid,
        'subject': subject,
        'subtopic': subtopic,
        'exam': 'CEREB',
        'question': qhtml,
        'options': options,
        'correct': correct,
        'explanation': exp,
    }

def slugify(name):
    return re.sub(r'[^a-z0-9]+', '_', name.lower()).strip('_')

def main():
    manifest_subjects = []
    for src, outname, subject in MAP:
        tests = extract_tests(os.path.join(UP, src))
        slug = outname[:-5]
        questions = []
        subtopics = []
        qi = 0
        for tname, qs in tests:
            subtopics.append({'name': tname, 'count': len(qs)})
            for q in qs:
                qid = f'cereb_{slug}_{qi}'
                questions.append(build_question(q, qid, subject, tname))
                qi += 1
        # sort subtopics by name for stable manifest display
        subtopics_sorted = sorted(subtopics, key=lambda s: s['name'])
        with open(os.path.join(OUT, outname), 'w', encoding='utf-8') as fh:
            json.dump(questions, fh, ensure_ascii=False, separators=(',', ':'))
        manifest_subjects.append({
            'name': subject,
            'file': f'cereb/{outname}',
            'total': len(questions),
            'subtopics': subtopics_sorted,
        })
        nimg = sum(1 for q in questions if 'q-images' in q['question'])
        print(f"{outname:38s} {len(questions):5d} Qs, {len(subtopics):3d} subtopics, {nimg} with images")
    # write partial manifest data for merge step
    with open('/home/user/Medqbank/scripts/generated_manifest.json', 'w') as fh:
        json.dump(manifest_subjects, fh, ensure_ascii=False)
    print('DONE. Generated', len(manifest_subjects), 'subject files.')

if __name__ == '__main__':
    main()
