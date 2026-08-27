# -*- coding: utf-8 -*-
"""KICE 성취수준 PDF에서 과목별 '성취기준별 성취수준'/'영역별 성취수준' 쪽 범위를 찾는다.

각 과목 절은 항상 1 성취기준별 성취수준 -> 2 영역별 성취수준 -> 3 예시 평가 도구
순서라, 이 세 표지의 쪽 번호로 구간을 자른다. 과목명은 러닝 헤더(예: 'Ⅲ세계시민과
지리 성취수준')에서 뽑고, 못 뽑으면 성취기준 코드 약칭으로 대신한다.

사용법:  python scan_sections.py <PDF경로> <out.json>
"""
import io, json, re, sys

# 표지 문구에 띄어쓰기 흔들림이 있다(예: 여행지리는 '3 예시 평가도구').
MARKS = [(re.compile(r'1\s*성취기준별\s*성취수준'), 'std'),
         (re.compile(r'2\s*영역별\s*성취수준'), 'area'),
         (re.compile(r'3\s*예시\s*평가\s*도구'), 'tool')]
TITLE_RE = re.compile(r'^[Ⅰ-ⅿXIV]+\s*(.+?)\s*성취수준$')
CODE_RE = re.compile(r'\[(?:10|12)([가-힣]{2,3})\d')


def subject_from_page(text):
    for line in text.split('\n'):
        m = TITLE_RE.match(line.strip())
        if m and m.group(1).strip():
            return m.group(1).strip()
    m = CODE_RE.search(text)
    return '(코드 %s)' % m.group(1) if m else '(미상)'


def main():
    from pypdf import PdfReader
    pdf, out = sys.argv[1], sys.argv[2]
    r = PdfReader(pdf)

    # 쪽마다 어떤 표지가 있는지 모은다(한 쪽에 둘 이상 있을 수 있어 리스트로).
    marks = []
    for i, page in enumerate(r.pages):
        t = page.extract_text() or ''
        kinds = [kind for rx, kind in MARKS if rx.search(t)]
        if kinds:
            marks.append((i + 1, kinds, t))

    starts = [m for m in marks if 'std' in m[1]]
    sections = []
    for idx, (p_std, _, text) in enumerate(starts):
        # 다음 과목이 시작하기 전까지만 뒤진다 - 안 그러면 표지를 놓친 과목이
        # 다음 과목의 쪽을 끌어와 구간이 통째로 어긋난다.
        limit = starts[idx + 1][0] if idx + 1 < len(starts) else len(r.pages) + 1
        area = [p for p, k, _ in marks if p_std <= p < limit and 'area' in k]
        tool = [p for p, k, _ in marks if p_std <= p < limit and 'tool' in k]
        if not area or not tool:
            print('  [건너뜀] %d쪽 - 영역별/예시 표지를 못 찾음' % p_std)
            continue
        sections.append({
            'subject': subject_from_page(text),
            'std': [p_std, area[0] - 1],
            'area': [area[0], tool[0] - 1],
        })

    with io.open(out, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(sections, f, ensure_ascii=False, indent=1)

    print(pdf, '->', out, '(%d쪽, %d과목)' % (len(r.pages), len(sections)))
    for s in sections:
        print('  %-28s 성취기준별 %s  영역별 %s' % (s['subject'], s['std'], s['area']))


if __name__ == '__main__':
    main()
