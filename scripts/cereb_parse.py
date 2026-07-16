import html, re, json, os

def extract_tests(path):
    """Return list of (testName, questions_list) from a CEREB combined HTML."""
    raw = open(path, encoding='utf-8', errors='replace').read()
    # map testId -> name from nav buttons
    names = {}
    for m in re.finditer(r"showTest\('(test\d+)'\)\">([^<]+)</button>", raw):
        names[m.group(1)] = m.group(2).strip()
    out = []
    # iterate over each iframe container: <div id="testN" ...> ... srcdoc="..."></iframe>
    for m in re.finditer(r'<div id="(test\d+)"[^>]*>.*?srcdoc="(.*?)"></iframe>', raw, re.DOTALL):
        tid = m.group(1)
        name = names.get(tid, tid)
        dec = html.unescape(m.group(2))
        qs = extract_questions(dec)
        out.append((name, qs))
    return out

def extract_questions(js):
    """Find `questions = [ ... ];` real array (skip the initial `questions = [];`)."""
    # find all occurrences of 'questions = ['
    idxs = [mm.start() for mm in re.finditer(r'questions\s*=\s*\[', js)]
    best = []
    for start in idxs:
        br = js.index('[', start)
        arr = _match_array(js, br)
        if arr is None:
            continue
        try:
            data = json.loads(arr)
        except Exception:
            continue
        if isinstance(data, list) and len(data) > len(best):
            best = data
    return best

def _match_array(s, i):
    """i points at '['. Return substring of the balanced array, respecting strings."""
    depth = 0
    instr = False
    esc = False
    for j in range(i, len(s)):
        c = s[j]
        if instr:
            if esc:
                esc = False
            elif c == '\\':
                esc = True
            elif c == '"':
                instr = False
        else:
            if c == '"':
                instr = True
            elif c == '[':
                depth += 1
            elif c == ']':
                depth -= 1
                if depth == 0:
                    return s[i:j+1]
    return None

if __name__ == '__main__':
    import sys
    UP = '/root/.claude/uploads/2fb0de8b-c54a-5792-bf95-e53b5184420f'
    for f in sorted(os.listdir(UP)):
        if not f.endswith('.html'):
            continue
        tests = extract_tests(os.path.join(UP, f))
        total = sum(len(q) for _, q in tests)
        withimg = sum(1 for _, qs in tests for q in qs if q.get('question_images'))
        empty_text = sum(1 for _, qs in tests for q in qs if not (q.get('text') or '').strip())
        print(f"{f:52s} tests={len(tests):3d} Qs={total:5d} q_with_img={withimg:5d} empty_text={empty_text}")
