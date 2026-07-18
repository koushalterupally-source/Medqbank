"""Remove CEREB 'match the following' questions whose entire content lived in a
now-dead cerebellum S3 image. These are unanswerable: the two columns (or the
labeled diagram) are gone, and the answer options are bare letter-number
pairings (e.g. 'A-2, B-1, C-5, D-3') that can't be reasoned about without the
figure. Match questions that keep both Column A and Column B fully in text
(no dead image) are answerable and are left untouched.
"""
import json, glob, re, os

DEAD_IMG = 'cerebellum-web-static.s3.amazonaws.com'
CEREB_DIR = os.path.join(os.path.dirname(__file__), '..',
                         'android/app/src/main/assets/cereb')


def is_match(qt):
    return bool(re.search(r'match (the|each|these|following)', qt, re.I))


def is_dead_match(q):
    """Unanswerable: a match-style question that depends on a dead figure."""
    qt = q.get('question', '')
    return is_match(qt) and DEAD_IMG in qt


def rebuild_manifest():
    manifest_path = os.path.join(CEREB_DIR, 'manifest.json')
    manifest = json.load(open(manifest_path))
    for subj in manifest['subjects']:
        fname = os.path.basename(subj['file'])
        path = os.path.join(CEREB_DIR, fname)
        # Some manifest subjects have no data file on disk (pre-existing gap);
        # leave those entries exactly as they are rather than error out.
        if not os.path.exists(path):
            continue
        data = json.load(open(path))
        subj['total'] = len(data)
        counts = {}
        for q in data:
            st = q.get('subtopic', 'General')
            counts[st] = counts.get(st, 0) + 1
        # keep only subtopics that still have questions, preserve alpha order
        subj['subtopics'] = [{'name': n, 'count': counts[n]}
                             for n in sorted(counts)]
    json.dump(manifest, open(manifest_path, 'w'), ensure_ascii=False, indent=1)


def main():
    files = sorted(glob.glob(os.path.join(CEREB_DIR, '*.json')))
    total_removed = 0
    for f in files:
        if os.path.basename(f) == 'manifest.json':
            continue
        data = json.load(open(f))
        kept = [q for q in data if not (isinstance(q, dict) and is_dead_match(q))]
        removed = len(data) - len(kept)
        if removed:
            json.dump(kept, open(f, 'w'), ensure_ascii=False, indent=1)
            total_removed += removed
            print(f'{os.path.basename(f)}: removed {removed}, kept {len(kept)}')
    print(f'\nTotal removed: {total_removed}')
    rebuild_manifest()
    print('Manifest rebuilt.')


if __name__ == '__main__':
    main()
