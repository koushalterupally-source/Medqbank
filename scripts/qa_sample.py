"""Draw a stratified random sample of questions across all PYQ subjects for manual QA."""
import json, random, glob, os, re, sys

random.seed(42)
BASE = '/home/user/Medqbank/android/app/src/main/assets/pyq'
N = 50

def main():
    all_q = []
    for f in sorted(glob.glob(os.path.join(BASE, '*.json'))):
        if f.endswith('manifest.json'):
            continue
        subj = os.path.basename(f)
        d = json.load(open(f))
        for q in d:
            all_q.append(q)
    print(f'Total pool: {len(all_q)} questions', file=sys.stderr)
    sample = random.sample(all_q, N)
    # classify
    for q in sample:
        q['_type'] = 'image' if 'q-images' in q['question'] else 'text'
    img_n = sum(1 for q in sample if q['_type'] == 'image')
    print(f'Sample: {N} total, {img_n} image-type, {N-img_n} text-type', file=sys.stderr)
    json.dump(sample, open('/tmp/claude-0/-home-user-Medqbank/2fb0de8b-c54a-5792-bf95-e53b5184420f/scratchpad/qa_sample.json', 'w'), ensure_ascii=False)

if __name__ == '__main__':
    main()
