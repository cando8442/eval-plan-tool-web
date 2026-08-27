# -*- coding: utf-8 -*-
"""교육부 고시 제2022-33호 별책 PDF 추출 텍스트에서 과목별 성취기준을 파싱한다.

PDF 텍스트는 pdfminer 로 뽑은 것이라 (1) 어절 사이가 두 칸 공백이고 (2) 한 문장이
여러 줄에 걸쳐 끊겨 있으며 (3) 쪽번호와 머리글("과학과  교육과정", "선택  중심
교육과정 – 진로 선택 과목 -")이 본문 사이에 섞여 있다. 그래서 먼저 머리글/쪽번호를
털어낸 뒤 줄을 이어 붙이고, 그 위에서 성취기준 코드를 기준으로 잘라낸다.
"""
import re

# 성취기준 코드: [12유전01-01], [10통과1-01-01] 처럼 영역-일련번호가 2단 또는 3단이다.
CODE_RE = re.compile(r"\[(\d+[가-힣]+\d?)-?(\d{2})-(\d{2})\]")
CODE_TOKEN = re.compile(r"\[\d+[가-힣]+\d?-?\d{2}-\d{2}\]")

_DROP_LINE = re.compile(
    r"^\s*(?:\d{1,3}|[가-힣]+과\s+교육과정|선택\s+중심\s+교육과정.*|공통\s+교육과정.*|"
    r"[가-힣]+과\s+교육과정\s*$)\s*$"
)


def clean(text: str) -> str:
    """쪽번호·머리글 줄을 버리고 줄을 이어 붙인다.

    PDF 는 한 줄이 넘칠 때 단어 중간에서 그냥 끊는다("...유전 형" / "질의 ..."). 이때
    끊긴 줄은 끝에 공백이 없고, 어절 경계에서 끊긴 줄은 끝에 공백이 남는다. 그래서
    줄을 이어 붙일 때 공백을 새로 넣지 않고 원래 줄 끝 공백만 살려야 "유전 형질의"가
    "유전 형 질의"로 깨지지 않는다.
    """
    out = []
    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        if _DROP_LINE.match(stripped):
            continue
        trailing = " " if line != line.rstrip() else ""
        out.append(stripped + trailing)
    return re.sub(r"\s+", " ", "".join(out))


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def parse_standards(raw_text: str) -> dict:
    """{코드접두사: {"areas": [(영역번호, 영역명)], "standards": [(코드, 문장)]}} 반환.

    성취기준 본문은 "나. 성취기준" 아래에서 줄머리에 [코드]로 시작하고, 해설은
    "• [코드]" 로 시작한다. 그래서 불릿이 붙은 코드는 건너뛴다.
    """
    text = clean(raw_text)

    # "나. 성취기준" ~ 다음 "나. 성취기준" 또는 문서 끝까지를 과목 블록으로 본다.
    blocks = []
    marks = [m.start() for m in re.finditer(r"나\.\s*성취기준", text)]
    for i, start in enumerate(marks):
        end = marks[i + 1] if i + 1 < len(marks) else len(text)
        blocks.append(text[start:end])

    result = {}
    for block in blocks:
        # 해설/고려사항 구역은 성취기준 원문이 아니므로 각 영역에서 잘라낸다.
        # 영역 헤더 "(1) 영역명" 위치를 찾는다.
        areas = []
        for m in re.finditer(r"\((\d)\)\s*([가-힣A-Za-z0-9·⋅\s]{2,30}?)\s*(?=\[\d)", block):
            areas.append((int(m.group(1)), _norm(m.group(2)), m.start()))

        for m in re.finditer(CODE_TOKEN, block):
            code = m.group(0)
            before = block[max(0, m.start() - 2) : m.start()]
            if "•" in before:  # 성취기준 해설 항목
                continue
            # 본문 속 상호참조(예: '문학'([12문학01-02])에서 ...)는 성취기준 목록이
            # 아니라 해설 문장이다. 이걸 성취기준으로 잘못 주우면 뒤따르는 해설 문단이
            # 통째로 본문으로 붙는다.
            if before.endswith("("):
                continue
            # 코드 다음부터, 다음 코드/탐구활동/해설 헤더 전까지가 문장이다.
            rest = block[m.end() :]
            stop = re.search(r"(?:\[\d+[가-힣]|<탐구|\(가\)\s*성취기준|\(나\)\s*성취기준|나\.\s*성취기준)", rest)
            body = rest[: stop.start()] if stop else rest
            body = _norm(body)
            # 실제 성취기준 문장은 길어야 200자 안쪽이다. 이보다 길면 해설/고려 사항이
            # 딸려 붙은 것이므로 후보에서 버린다.
            if len(body) > 300:
                continue
            if not body.endswith("."):
                # 다음 토큰까지 붙어 잘린 경우가 아니면 그대로 둔다.
                body = body.rstrip(" •")
            pm = CODE_RE.match(code)
            prefix = pm.group(1)
            area_no = int(pm.group(2)) if pm.group(2) else 0
            entry = result.setdefault(prefix, {"areas": {}, "standards": []})
            entry["standards"].append((code, body, area_no))

        for no, name, pos in areas:
            # 이 영역 헤더 뒤 첫 코드의 접두사에 영역명을 붙인다.
            m = CODE_TOKEN.search(block, pos)
            if not m:
                continue
            pm = CODE_RE.match(m.group(0))
            prefix = pm.group(1)
            if prefix in result:
                result[prefix]["areas"][no] = name

    # 중복 제거 + 코드순 정렬
    for prefix, entry in result.items():
        seen = {}
        for code, body, area_no in entry["standards"]:
            if code not in seen or len(body) > len(seen[code][0]):
                seen[code] = (body, area_no)
        entry["standards"] = [(c, seen[c][0], seen[c][1]) for c in sorted(seen)]
    return result


if __name__ == "__main__":
    import sys

    data = parse_standards(open(sys.argv[1], encoding="utf-8").read())
    want = sys.argv[2] if len(sys.argv) > 2 else None
    for prefix, entry in sorted(data.items()):
        if want and prefix != want:
            continue
        print(f"### {prefix}  ({len(entry['standards'])}개)  영역={entry['areas']}")
        for code, body, area_no in entry["standards"]:
            print(f"  {code} {body}")
