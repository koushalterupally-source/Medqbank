import re

BOT_TAG_RE = re.compile(r'^@[\w_]+$')
LABEL_ONLY_RE = re.compile(r'^(Explanation|Educational Objective|Ref|Option\s*[A-D])\s*[:.]?$', re.I)


def _substantial(text):
    """Is this bullet a real informative sentence, or just a label/keyword fragment
    the source's own content generator left behind (e.g. 'Option A.' or a bare
    noun phrase like 'anterior relation')?"""
    t = text.strip()
    if not t:
        return False
    if LABEL_ONLY_RE.match(t):
        return False
    if BOT_TAG_RE.match(t):
        return False
    # genuine sentences in this dataset are consistently multi-word and reasonably
    # long; bare keyword-fragment bullets are short noun phrases with few words
    words = t.split()
    if len(t) < 25 or len(words) < 4:
        return False
    return True


def _filter_bullets(raw_lines):
    """Shared bullet-list cleanup: drop label-only/keyword-fragment/bot-tag lines,
    then drop near-duplicates (one line's text fully contained in another's)."""
    kept_text = []
    kept_raw = []
    for raw in raw_lines:
        text = re.sub(r'^[•➤]\s*', '', raw).strip()
        if not _substantial(text):
            continue
        key = re.sub(r'^[:\s]+', '', text.lower())
        # source sometimes splits "Ref : X" and ": X" across two separate bullets;
        # treat one contained in the other as the same fragment
        if any(key in k or k in key for k in kept_text):
            continue
        kept_text.append(key)
        kept_raw.append(re.sub(r'^[•➤]\s*', '', raw))
    return kept_raw


def clean_cereb_explanation(html):
    """Strip the source's own duplicated bullet-fragment noise: each real sentence
    is consistently followed by a label-only repeat and a run of bare keyword
    fragments extracted from that same sentence, and some sentences are printed
    twice in full. Keep only substantial, deduplicated bullets; drop stray bot
    signature tags (e.g. '@dams_new_robot').

    Source explanations come in two formats: some wrap bullets in real <ul><li>
    HTML, others are plain text with '•'-prefixed lines joined by bare '\\n'
    (which HTML collapses into an unreadable run-on paragraph when rendered) --
    both are handled and normalized to real markup.
    """
    if not html:
        return html

    def clean_list(m):
        items = re.findall(r'<li>(.*?)</li>', m.group(0), re.DOTALL)
        kept = _filter_bullets(items)
        if not kept:
            return ''
        tag = 'ul' if '<ul>' in m.group(0) else 'ol'
        return f'<{tag}>' + ''.join(f'<li>{k}</li>' for k in kept) + f'</{tag}>'

    if '<ul>' in html or '<ol>' in html:
        html = re.sub(r'<(ul|ol)>.*?</\1>', clean_list, html, flags=re.DOTALL)
    elif '\n' in html and ('•' in html or '➤' in html):
        # plain-text bullet format with no HTML list markup at all
        lines = [l for l in html.split('\n') if l.strip()]
        kept = _filter_bullets(lines)
        html = '<br>'.join(kept)

    # a stray bot-signature tag can appear regardless of which format above matched
    # (or in explanations with neither list format at all)
    html = re.sub(r'<p>\s*@[\w_]+\s*</p>', '', html)
    html = re.sub(r'(^|<br>)\s*@[\w_]+\s*(?=<br>|$)', r'\1', html)
    html = re.sub(r'^@[\w_]+$', '', html.strip())

    # normalize a stray space before an ordinal suffix ("4 th" -> "4th")
    html = re.sub(r'(\d)\s+(st|nd|rd|th)\b', r'\1\2', html, flags=re.I)
    return html.strip()


if __name__ == '__main__':
    import json
    d = json.load(open('/home/user/Medqbank/android/app/src/main/assets/cereb/anatomy.json'))
    q = next(q for q in d if 'Duodenum' in q['explanation'].get('detail', '') and 'Vishram' in q['explanation'].get('detail', ''))
    print("=== HTML-list format BEFORE ===")
    print(q['explanation']['detail'][:400])
    print("\n=== HTML-list format AFTER ===")
    print(clean_cereb_explanation(q['explanation']['detail']))

    d2 = json.load(open('/home/user/Medqbank/android/app/src/main/assets/cereb/pathology.json'))
    q2 = next(q for q in d2 if 'Fat deposits' in q['explanation'].get('detail', ''))
    print("\n=== plain-text bullet format BEFORE ===")
    print(repr(q2['explanation']['detail'][:150]))
    print("\n=== plain-text bullet format AFTER ===")
    print(clean_cereb_explanation(q2['explanation']['detail']))
