import sys, os, json, time
os.environ['OMP_THREAD_LIMIT'] = '1'   # let the process pool own the parallelism
sys.path.insert(0, '/home/user/Medqbank/scripts')
from multiprocessing import Pool
from pyq_generate import process_file

HTML='/tmp/claude-0/-home-user-Medqbank/2fb0de8b-c54a-5792-bf95-e53b5184420f/scratchpad/pyqsrc/html'
OUT='/home/user/Medqbank/android/app/src/main/assets/pyq'
LOG='/tmp/claude-0/-home-user-Medqbank/2fb0de8b-c54a-5792-bf95-e53b5184420f/scratchpad/batch.log'

# (html file, display subject, output json)
JOBS = [
  ('Anaesthesia_PYQs.html',     'Anaesthesia',                    'anaesthesia.json'),
  ('Anatomy_PYQs.html',         'Anatomy',                        'anatomy.json'),
  ('Biochemistry_PYQs.html',    'Biochemistry',                   'biochemistry.json'),
  ('Dermatology_PYQs.html',     'Dermatology',                    'dermatology.json'),
  ('ENT_PYQs.html',             'ENT',                            'ent.json'),
  ('Forensic_Medicine_PYQs.html','Forensic Medicine',             'forensic_medicine.json'),
  ('Medicine_PYQs.html',        'Medicine',                       'medicine.json'),
  ('Microbiology_PYQs.html',    'Microbiology',                   'microbiology.json'),
  ('OBG_PYQs.html',             'Obstetrics & Gynaecology',       'obstetrics_gynaecology.json'),
  ('Ophthalmology_PYQs.html',   'Ophthalmology',                  'ophthalmology.json'),
  ('Orthopaedics_PYQs.html',    'Orthopaedics',                   'orthopaedics.json'),
  ('PSM_PYQs.html',             'Preventive & Social Medicine',   'preventive_social_medicine.json'),
  ('Pathology_PYQs.html',       'Pathology',                      'pathology.json'),
  ('Pharmacology_PYQs.html',    'Pharmacology',                   'pharmacology.json'),
  ('Physiology_PYQs.html',      'Physiology',                     'physiology.json'),
  ('Psychiatry_PYQs.html',      'Psychiatry',                     'psychiatry.json'),
  ('Radiology_PYQs.html',       'Radiology',                      'radiology.json'),
  ('Surgery_PYQs.html',         'Surgery',                        'surgery.json'),
]

def work(job):
    fn, subj, out = job
    t0 = time.time()
    data = process_file(os.path.join(HTML, fn), subj)
    json.dump(data, open(os.path.join(OUT, out), 'w'), ensure_ascii=False)
    figs = sum(1 for q in data if 'q-images' in q['question'])
    subs = {}
    for q in data:
        subs[q['subtopic']] = subs.get(q['subtopic'], 0) + 1
    entry = {'name': subj, 'file': f'pyq/{out}', 'total': len(data),
             'subtopics': [{'name': k, 'count': v} for k, v in subs.items()]}
    with open(LOG, 'a') as lg:
        lg.write(f'{subj}: {len(data)} Qs, {figs} figs, {time.time()-t0:.0f}s\n')
    return entry

if __name__ == '__main__':
    open(LOG, 'w').close()
    t0 = time.time()
    with Pool(6) as p:
        entries = p.map(work, JOBS)
    entries.sort(key=lambda e: e['name'])
    json.dump({'subjects': entries}, open(os.path.join(OUT, 'manifest.json'), 'w'),
              ensure_ascii=False, indent=1)
    tot = sum(e['total'] for e in entries)
    with open(LOG, 'a') as lg:
        lg.write(f'ALL DONE: {tot} questions across {len(entries)} subjects, {time.time()-t0:.0f}s\n')
