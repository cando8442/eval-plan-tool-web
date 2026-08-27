"""KICE「2022 개정 교육과정에 따른 고등학교 과학과 선택과목 성취수준」PDF에서
한 과목의 '성취기준별 성취수준'과 '영역별 성취수준'을 뽑아낸다.

PDF 표를 텍스트로 추출하면 셀 내용이 위에서 아래로 한 줄씩 늘어서므로,
아래 규칙으로 되짚는다.
  - 성취기준별: `[12세포01-01] 본문` 뒤에 A~E가 각각 줄머리에 오는 형태
  - 영역별:     영역명 뒤에 A~E, 각 등급 안에서 지식･이해/과정･기능/가치･태도

양쪽 정렬 때문에 PDF가 글자 사이에 공백을 끼워 넣은 구간("말 할  수  있 다 .")은
자동으로 못 고치므로 suspicious 목록으로 뽑아 사람이 확인하게 한다.
"""
import io, json, re, sys, collections

PDF = None  # 명령줄 6번째 인자로 지정, 없으면 아래 기본값
DEFAULT_PDF = r'C:\Users\cando\OneDrive\바탕 화면\평가기준_과학과.pdf'
GRADES = ["A", "B", "C", "D", "E"]
TRAIT_MAP = {"지식･이해": "지식이해", "지식·이해": "지식이해",
             "과정･기능": "과정기능", "과정·기능": "과정기능",
             "가치･태도": "가치태도", "가치·태도": "가치태도"}

DROP_PATTERNS = [
    r'^성취기준[ ]*성취기준별 성취수준$',
    r'^[Ⅰ-ⅿ]+[.]?[ ]*[가-힣0-9]+ 성취수준$',
    r'^2022 개정 교육과정에 따른',
    r'^고등학교 과학과 선택과목 성취수준$',
    r'^\d{1,4}$',                          # 쪽번호
    r'^[\u2160-\u217f]+\.?\s',             # 러닝 헤더 (ⅩⅠ. 세포와 물질대사)
    r'^교육과정 성취기준\s*성취기준별 성취수준$',
    r'^영역\s*영역별 성취수준$',
    r'^\d 성취기준별 성취수준$',
    r'^\d 영역별 성취수준$',
]
DROP_RE = [re.compile(p) for p in DROP_PATTERNS]
AREA_RE = re.compile(r'^\((\d)\)\s*(.+)$')
CODE_RE = re.compile(r'\[((?:10|12)[\uac00-\ud7a3]{2,3}\d?(?:-\d{2})?\d{0,2}-\d{2})\]')
LEVEL_RE = re.compile(r'^([A-E])(?:\s+(.*))?$')
# 등급 문자 뒤에 공백 없이 본문이 붙는 판(예: "DD NA의 구조와…")을 위한 보조 패턴
LEVEL_TIGHT_RE = re.compile(r'^([A-E])(\S.*)$')
INQUIRY_HEAD_RE = re.compile(r'^<\s*탐\s*구\s*활\s*동\s*>')


def page_lines(pdf, lo, hi):
    from pypdf import PdfReader
    r = PdfReader(pdf)
    out = []
    for i in range(lo, hi + 1):
        for raw in (r.pages[i - 1].extract_text() or '').split('\n'):
            # 오른쪽 공백은 남긴다 - 이 PDF는 줄 끝 공백 유무로 어절 경계를 표시한다.
            line = raw.rstrip('\r').lstrip()
            if not line.strip():
                continue
            if any(rx.match(line) for rx in DROP_RE):
                continue
            out.append(line)
    return out


def join_lines(parts):
    """PDF 줄바꿈으로 끊긴 조각을 잇는다. 이 문서는 어절 경계에서 줄이 바뀔 때만
    줄 끝에 공백을 남기므로, 그 공백이 없으면 어절 중간이라 보고 붙여 쓴다."""
    out = ''
    for raw in parts:
        if raw is None:
            continue
        piece = raw.lstrip()
        if not piece.strip():
            continue
        if not out:
            out = piece
            continue
        boundary = out.endswith(' ') or out.rstrip()[-1] in '.,;:)' or piece[0] in '<[('
        out = out.rstrip() + (' ' if boundary else '') + piece
    return re.sub(r'[ 	]+', ' ', out).strip()


# 양쪽 정렬로 글자 사이가 벌어진 구간(공백 제거형) -> 정상 표기.
# 이 문서의 서술어는 정형화돼 있어 항목이 과목 간에 대부분 재사용된다.
REPAIRS = {
    "말할수있다": "말할 수 있다",
    "설명할수있다": "설명할 수 있다",
    "추론할수있다": "추론할 수 있다",
    "구분할수있다": "구분할 수 있다",
    "제작할수있다": "제작할 수 있다",
    "수행할수있다": "제작할 수 있다",
    "를조사할수있다": "를 조사할 수 있다",
    "에대해소통할수있다": "에 대해 소통할 수 있다",
    "여협력적으로소통할수있다": "여 협력적으로 소통할 수 있다",
    "대해흥미와호기심을가진다": "대해 흥미와 호기심을 가진다",
    "에대한흥미와호기심을가진다": "에 대한 흥미와 호기심을 가진다",
    "로다각적인접근을시도한다": "로 다각적인 접근을 시도한다",
    "체유전양상의차이를설명할수있다": "체 유전 양상의 차이를 설명할 수 있다",
    "학문분야와직업을설명할수있다": "학문 분야와 직업을 설명할 수 있다",
    "할수있다": "할 수 있다",
    "대한흥미와호기심을가진다": "대한 흥미와 호기심을 가진다",
    "대해소통할수있다": "대해 소통할 수 있다",
    "문분야와직업을설명할수있다": "문 분야와 직업을 설명할 수 있다",
    "유전양상의차이를": "유전 양상의 차이를",
    "협력적으로소통할수있다": "협력적으로 소통할 수 있다",
    "흥미와호기심을가진다": "흥미와 호기심을 가진다",
    "접근을시도한다": "접근을 시도한다",
    "관심을가진다": "관심을 가진다",
    "흥미를가진다": "흥미를 가진다",
    "인식할수": "인식할 수",
    "설계할수": "설계할 수",
    "판단할수": "판단할 수",
    "해석할수": "해석할 수",
    "예측하고": "예측하고",
    "측정하고비교할수": "측정하고 비교할 수",
    "조사하고발표할수": "조사하고 발표할 수",
    "사례와연관지어": "사례와 연관지어",
    "부터기후변화가수생태": "부터 기후변화가 수생태",
    "알고이와관련된일상생활": "알고, 이와 관련된 일상생활",
    "알고,이와관련된일상생활": "알고, 이와 관련된 일상생활",
    "느낄수있다": "느낄 수 있다",
    "느낄수있": "느낄 수 있",
    "맞게시각자": "맞게 시각 자",
    "제시하고,심층순환이밀도": "제시하고, 심층 순환이 밀도",
    "수있음과반": "수 있음과 반",
    "알고,양적관": "알고, 양적 관",
    "형성되며모든": "형성되며 모든",
    "알고,전기분": "알고, 전기분",
    "따라구분할수있고": "따라 구분할 수 있고",
    "서제시할수": "서 제시할 수",
    "제시하고발표할수": "제시하고 발표할 수",
    "측정할수": "측정할 수",
    "갖고에너지문": "갖고, 에너지 문",
    "과학이필요": "과학이 필요",
    "수행하여유도전": "수행하여 유도 전",
    "안전성과환경친화": "안전성과 환경 친화",
    "해결하기위한": "해결하기 위한",
    "갖고,에너지문": "갖고, 에너지 문",
    "표현하고공유할수": "표현하고 공유할 수",
    "표현할수": "표현할 수",
    "다양한도": "다양한 도",
    "분해실험하기탐구활": "분해 실험하기 탐구활",
    "관련지어설명할수": "관련지어 설명할 수",
    "도출하고해석할수": "도출하고 해석할 수",
    "조사할수": "조사할 수",
    "추론할수": "추론할 수",
    "설명할수": "설명할 수",
    "제작할수": "제작할 수",
    "수행할수": "수행할 수",
    "구분하여": "구분하여",
    "제작하고": "제작하고",
    "종류와특성을": "종류와 특성을",
    "도출하고해석할": "도출하고 해석할",
}



# 자간이 벌어져 쪼개진 약어. 이 문서에 나오는 것만 다룬다.
ACRONYMS = ['mRNA', 'DNA', 'RNA', 'ATP', 'PCR', 'NGS', 'LMO', 'GMO', 'pH']
# 홀로 설 수 없는 조사 - 앞 어절에 붙여야 한다.
ORPHAN_PARTICLES = ['로', '을', '를', '은', '는', '의', '에']
# 줄 이음에서 앞 어절에 잘못 붙는 서술어 - 띄어 써야 한다.
GLUED_PREDICATES = ['가진다', '인식한다', '시도한다', '지닌다', '느낀다', '중시한다',
                    '기여한다', '즐긴다', '체험한다', '이해한다', '소통한다', '제시한다']


# 원문의 명백한 오타. 고친 것만 여기 남긴다.
TYPOS = {'이떄': '이때'}


def fix_tokens(s):
    """약어 분리, 조사 고아, 서술어 붙음을 되돌린다."""
    for a in ACRONYMS:
        pat = r'\s*'.join(list(a))
        s = re.sub(pat, a, s)
    for pcl in ORPHAN_PARTICLES:
        s = re.sub(r'(?<=[\uac00-\ud7a3])\s+' + pcl + r'(?=[\s.,])', pcl, s)
    for pred in GLUED_PREDICATES:
        s = re.sub(r'(?<=[을를이가])' + pred, ' ' + pred, s)
    # 괄호 뒤에 떨어져 나온 조사도 붙인다: '(LMO) 가' -> '(LMO)가'
    s = re.sub('(?<=[)]) +(가|이|은|는|을|를|의|에|와|과)(?=[ .,])', lambda m: m.group(1), s)
    for stem in VERB_SPLIT_STEMS:
        s = s.replace(stem + ' 할 수 ', stem + '할 수 ')
        s = s.replace(stem + ' 하고', stem + '하고')
        s = s.replace(stem + ' 하여', stem + '하여')
        s = s.replace(stem + ' 한다', stem + '한다')
    for bad, good in TYPOS.items():
        s = s.replace(bad, good)
    return re.sub(r'[ \t]+', ' ', s).strip()

# run 경계로는 잡히지 않는 자간 구간(앞뒤에 2글자 어절이 섞인 경우)을
# 문구 단위로 되돌린다. 과목을 추가할 때마다 여기에 쌓인다.
# 좁은 표 칸에서 서술어가 갈라져 나오는 판: '설명 할 수' -> '설명할 수'.
# 앞이 조사 없는 한자어 명사일 때만이라 '~을 할 수 있다'와 겹치지 않는다.
VERB_SPLIT_STEMS = ['설명', '말', '추론', '조사', '제작', '구분', '비교', '수행', '소통', '분석', '표현', '적용', '판단', '예측', '평가', '제시', '탐구', '관찰', '측정', '해석', '설계', '도출', '활용', '발표', '토론', '인식', '파악']

PHRASE_FIXES = {
    "수송 과 정의 종 류 와 특 징을": "수송 과정의 종류와 특징을",
    "구성하는원소들이": "구성하는 원소들이",
    "일상생활에서활용되는": "일상생활에서 활용되는",
    "일상생활의문제해결에": "일상생활의 문제해결에",
    "특 징 및 생 태 계 에 서 일 어 나 는 물 질 의 순 환 과 에 너 지 의 흐 름 을 비 교 하 여 설 명 할": "특징 및 생태계에서 일어나는 물질의 순환과 에너지의 흐름을 비교하여 설명할",
}


def repair_spacing(s):
    """양쪽 정렬로 글자 사이가 벌어진 구간을 REPAIRS 표로 되돌린다.

    run 경계가 앞뒤로 밀릴 수 있으므로 run 안의 모든 연속 구간을 긴 것부터
    사전과 맞춰본다."""
    # 자간 복원 전에 공백을 먼저 한 칸으로 줄인다 - 원문은 벌어진 구간에 두 칸을
    # 섞어 쓰기 때문에, 축약을 나중에 하면 사전 매칭이 통째로 빗나간다.
    s = re.sub('[ ' + chr(9) + ']+', ' ', s)
    for bad, good in PHRASE_FIXES.items():
        s = s.replace(bad, good)
    for run in find_suspicious(s):
        toks = run.split(' ')
        n = len(toks)
        done = False
        for size in range(n, 2, -1):
            for start in range(0, n - size + 1):
                win = toks[start:start + size]
                key = ''.join(win).rstrip('.,')
                if key in REPAIRS:
                    tail = ''.join(win)[len(key):]
                    s = s.replace(' '.join(win), REPAIRS[key] + tail)
                    done = True
                    break
            if done:
                break
    return fix_tokens(re.sub('\s+([.,])', lambda m: m.group(1), s))


def despace(s):
    return re.sub(r'\s+', ' ', s).strip()


def find_suspicious(s):
    """양쪽 정렬로 글자 사이가 벌어진 구간(한글 1글자 토큰 4개 이상 연속)을 찾는다."""
    hits, run = [], []
    for t in s.split(' '):
        core = t.rstrip('.,')
        if len(core) == 1 and '\uac00' <= core <= '\ud7a3':
            run.append(t)
            continue
        if len(run) >= 4:
            hits.append(' '.join(run))
        run = []
    if len(run) >= 4:
        hits.append(' '.join(run))
    return hits


def next_grade(mode):
    if mode in (None, 'inquiry'):
        return 'A'
    if mode == 'text':
        return 'A'
    idx = GRADES.index(mode) if mode in GRADES else -1
    return GRADES[idx + 1] if 0 <= idx < len(GRADES) - 1 else None


def parse_standards(lines):
    """성취기준별 성취수준 -> [{unit, standards:[{code,text,inquiry,levels}]}]"""
    areas = []
    cur_area = None
    cur_std = None
    bucket = []
    mode = None   # 'text' | 'inquiry' | 'A'~'E'

    def flush():
        nonlocal bucket, cur_std, mode
        if mode is not None and bucket and (cur_std is not None or mode == 'area_inquiry'):
            val = join_lines(bucket)
            if mode == 'text':
                cur_std['text'] = val
            elif mode == 'area_inquiry':
                for piece in re.split(r'[ ]*[•·][ ]*', val):
                    piece = piece.strip().strip('[]')
                    if piece:
                        cur_area.setdefault('inquiry', []).append(despace(piece))
            elif mode == 'inquiry':
                for piece in re.split(r'\s*[\u2022\u00b7]\s*', val):
                    piece = piece.strip()
                    if piece:
                        cur_std['inquiry'].append(despace(piece).strip('[]'))
            else:
                cur_std['levels'][mode] = val
        bucket = []

    for line in lines:
        m_area = AREA_RE.match(line)
        if m_area and not CODE_RE.search(line):
            flush()
            mode, cur_std = None, None
            cur_area = {"unit": despace(m_area.group(2)), "standards": []}
            areas.append(cur_area)
            continue
        m_code = CODE_RE.search(line)
        if m_code and line.lstrip().startswith('['):
            flush()
            cur_std = {"code": m_code.group(1), "text": "", "inquiry": [],
                       "levels": collections.OrderedDict()}
            if cur_area is None:
                cur_area = {"unit": "(영역 미상)", "standards": []}
                areas.append(cur_area)
            cur_area["standards"].append(cur_std)
            mode, bucket = 'text', [line]
            continue
        if INQUIRY_HEAD_RE.match(line):
            # 진행 중인 등급 텍스트를 먼저 확정해야 A~E가 다 찼는지 판단할 수 있다.
            flush()
            # 이 문서군에는 탐구 활동을 성취기준별이 아니라 영역 끝에 한꺼번에
            # 싣는 판이 있다. A~E가 이미 다 찬 뒤에 나오면 영역 목록으로 본다.
            area_level = (cur_std is not None
                          and all(g in cur_std['levels'] for g in GRADES))
            mode = 'area_inquiry' if area_level else 'inquiry'
            bucket = []
            tail = INQUIRY_HEAD_RE.sub('', line).strip()
            if tail:
                bucket = [tail]
            continue
        m_lv = LEVEL_RE.match(line)
        if m_lv and cur_std is not None:
            flush()
            mode = m_lv.group(1)
            bucket = [m_lv.group(2)] if m_lv.group(2) else []
            continue
        # '...설명할 수 있다.D'처럼 다음 등급 문자가 앞 문장 끝에 붙어 나오는 판.
        # (원문에서 그 등급 칸이 비어 있을 때 이렇게 붙는다.)
        if cur_std is not None and mode in GRADES:
            tail_m = re.match('^(.+[.가-힣])[ ]*([A-E])$', line.rstrip())
            if tail_m and next_grade(mode) == tail_m.group(2):
                bucket.append(tail_m.group(1))
                flush()
                mode, bucket = tail_m.group(2), []
                continue
        if cur_std is not None:
            nxt = next_grade(mode)
            m_t = LEVEL_TIGHT_RE.match(line)
            if nxt and m_t and m_t.group(1) == nxt and nxt not in cur_std['levels']:
                flush()
                mode = nxt
                bucket = [m_t.group(2)]
                continue
        bucket.append(line)
    flush()
    for a in areas:
        for st in a["standards"]:
            st["text"] = repair_spacing(st["text"])
            st["inquiry"] = [repair_spacing(x) for x in st["inquiry"]]
            for g in list(st["levels"]):
                st["levels"][g] = repair_spacing(st["levels"][g])
    return areas


def parse_area_levels(lines, area_names):
    """영역별 성취수준 -> [{unit, levels:{A:{지식이해,과정기능,가치태도}}}]"""
    by_unit = collections.OrderedDict()
    cur_unit = cur_grade = cur_trait = None
    bucket = []
    squish = lambda s: re.sub(r'\s+', '', s)
    plain_names = {squish(n) for n in area_names}
    trait_plain = {squish(k): v for k, v in TRAIT_MAP.items()}

    def flush():
        nonlocal bucket
        if cur_unit and cur_grade and cur_trait and bucket:
            g = by_unit.setdefault(cur_unit, collections.OrderedDict()) \
                       .setdefault(cur_grade, collections.OrderedDict())
            val = join_lines(bucket)
            g[cur_trait] = (g[cur_trait] + '\n' + val) if g.get(cur_trait) else val
        bucket = []

    for line in lines:
        m_area = AREA_RE.match(line)
        if m_area:
            name = despace(m_area.group(2))
            # 표 첫 칸에 '(1) 융합과학 / 탐구의 이해'처럼 번호까지 붙은 영역명이
            # 줄바꿈된 채 되풀이되는 판이 있다. 현재 영역명의 조각이면 넘긴다.
            if cur_unit and squish(name) and squish(name) in squish(cur_unit):
                continue
            flush()
            cur_unit = name
            cur_grade = cur_trait = None
            continue
        sq = squish(line)
        if sq in plain_names:              # 표 첫 칸에 반복되는 영역명
            continue
        if cur_unit and sq and sq in squish(cur_unit) and len(sq) < len(squish(cur_unit)):
            continue                       # 줄바꿈으로 쪼개진 영역명 조각
        if sq in trait_plain:
            flush()
            cur_trait = trait_plain[sq]
            continue
        # '생명시스템의 / 구성 A'처럼 영역명이 줄바꿈으로 쪼개져 등급 문자와
        # 한 줄에 붙어 나오는 판이 있다. 앞부분이 영역명 조각이면 등급으로 본다.
        m_split = re.match('^(.*)([A-E])$', sq)
        if m_split and cur_unit:
            head, letter = m_split.group(1), m_split.group(2)
            if head and head in squish(cur_unit):
                flush()
                cur_grade, cur_trait = letter, None
                continue
        m_lv = LEVEL_RE.match(line)
        if m_lv:
            flush()
            cur_grade, cur_trait = m_lv.group(1), None
            rest = m_lv.group(2)
            if rest and squish(rest) in trait_plain:
                cur_trait = trait_plain[squish(rest)]
            elif rest:
                for lab, key in trait_plain.items():
                    if squish(rest).startswith(lab):
                        cur_trait = key
                        bucket = [squish(rest)[len(lab):]]
                        break
            continue
        matched = False
        for lab, key in trait_plain.items():
            if sq.startswith(lab):
                flush()
                cur_trait = key
                tail = line.strip()[len(lab):].strip() if line.strip().startswith(lab) else sq[len(lab):]
                bucket = [tail] if tail else []
                matched = True
                break
        # '...실천한다.E'처럼 다음 등급 문자가 앞 문장 끝에 붙어 나오는 판.
        tail_m = re.match('^(.+[.가-힣])[ ]*([A-E])$', line.rstrip())
        if tail_m and cur_grade and next_grade(cur_grade) == tail_m.group(2):
            bucket.append(tail_m.group(1))
            flush()
            cur_grade, cur_trait = tail_m.group(2), None
            continue
        if not matched:
            bucket.append(line)
    flush()

    for gr in by_unit.values():
        for tr in gr.values():
            for t in list(tr):
                joined = chr(10).join(repair_spacing(x) for x in tr[t].split(chr(10)))
                # 영역별 성취수준은 셀 안에서 문장 단위로 문단이 나뉘어 있다.
                tr[t] = re.sub(r'(?<=다\.)[ \t]+(?=\S)', chr(10), joined)
    return [{"unit": u,
             "levels": collections.OrderedDict((g, gr.get(g, {})) for g in GRADES)}
            for u, gr in by_unit.items()]


def find_glued(s):
    """줄 이음에서 두 어절이 붙어버린 후보(지나치게 긴 한글 덩어리)를 찾는다."""
    out = []
    for t in s.split(' '):
        core = t.strip('.,()[]')
        if len(core) >= 7 and all('가' <= c <= '힣' for c in core):
            out.append(core)
    return out


def restore_glued(tok, corpus):
    """같은 글자열이 문서 어딘가에 띄어 쓰여 있으면 그 표기를 쓴다."""
    text, nospace, index = corpus
    best, start = None, 0
    while True:
        at = nospace.find(tok, start)
        if at < 0:
            break
        start = at + 1
        cand = text[index[at]:index[at + len(tok) - 1] + 1]
        if '|' in cand or chr(10) in cand:
            continue
        if best is None or cand.count(' ') > best.count(' '):
            best = cand
    return best if best and best.count(' ') > 0 else None


def build_corpus(areas, area_levels):
    """과목 전체 텍스트를 모아 공백 제거 색인을 만든다.

    같은 문구가 문서 안 여러 곳에 나오는데, 좁은 칸에서만 자간이 벌어진다.
    그래서 깨진 구간의 공백을 지운 형태로 색인을 뒤져 정상 표기를 되찾을 수 있다.
    """
    chunks = []
    for a in areas:
        for s in a['standards']:
            chunks.append(s['text'])
            chunks.extend(s['levels'].values())
            chunks.extend(s.get('inquiry') or [])
        chunks.extend(a.get('inquiry') or [])
    for a in area_levels:
        for tr in a['levels'].values():
            chunks.extend(tr.values())
    text = ' | '.join(chunks)
    nospace, index = [], []
    for pos, ch in enumerate(text):
        if not ch.isspace():
            nospace.append(ch)
            index.append(pos)
    return text, ''.join(nospace), index


def restore_from_corpus(run, corpus):
    """깨진 구간과 같은 글자열을 문서에서 찾아, 공백이 가장 적은 표기를 고른다."""
    text, nospace, index = corpus
    key = run.replace(' ', '')
    if len(key) < 4:
        return None
    best, start = None, 0
    while True:
        at = nospace.find(key, start)
        if at < 0:
            break
        start = at + 1
        cand = text[index[at]:index[at + len(key) - 1] + 1]
        if '|' in cand:
            continue
        if best is None or cand.count(' ') < best.count(' '):
            best = cand
    return best if best and best.count(' ') < run.count(' ') else None


def corpus_repair(areas, area_levels):
    """자간이 벌어진 채 남은 구간을 문서 안의 정상 표기로 되돌린다."""
    corpus = build_corpus(areas, area_levels)
    fixed = 0

    def fix(s):
        nonlocal fixed
        for run in find_suspicious(s):
            good = restore_from_corpus(run, corpus)
            if good:
                s = s.replace(run, good)
                fixed += 1
        # 어절 붙음은 자동으로 고치지 않는다. 원문이 실제로 붙여 쓴 말
        # (예: '유전자편집기술')까지 쪼개 버려 원문을 훼손하기 때문이다.
        # 탐지 결과는 보고만 하고, 진짜 오류는 PHRASE_FIXES에 명시한다.
        return s

    for a in areas:
        for s in a['standards']:
            s['text'] = fix(s['text'])
            s['inquiry'] = [fix(x) for x in s['inquiry']]
            for g in list(s['levels']):
                s['levels'][g] = fix(s['levels'][g])
        if a.get('inquiry'):
            a['inquiry'] = [fix(x) for x in a['inquiry']]
    for a in area_levels:
        for g in list(a['levels']):
            for t in list(a['levels'][g]):
                a['levels'][g][t] = chr(10).join(
                    fix(x) for x in a['levels'][g][t].split(chr(10)))
    return fixed


def main():
    global PDF
    PDF = sys.argv[6] if len(sys.argv) > 6 else DEFAULT_PDF
    std_lo, std_hi, area_lo, area_hi, out = (
        int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), sys.argv[5])
    areas = parse_standards(page_lines(PDF, std_lo, std_hi))
    area_names = [a["unit"] for a in areas]
    area_levels = parse_area_levels(page_lines(PDF, area_lo, area_hi), area_names)

    # 최종 보정 패스 - 위 단계에서 놓친 자간 구간을 한 번 더 훑는다.
    for a in areas:
        for s in a['standards']:
            s['text'] = repair_spacing(s['text'])
            s['inquiry'] = [repair_spacing(x) for x in s['inquiry']]
            for g in list(s['levels']):
                s['levels'][g] = repair_spacing(s['levels'][g])
    for a in area_levels:
        for g in list(a['levels']):
            for t in list(a['levels'][g]):
                a['levels'][g][t] = chr(10).join(
                    repair_spacing(x) for x in a['levels'][g][t].split(chr(10)))

    # 사전으로 못 고친 구간은 문서 자체에서 정상 표기를 찾아 되돌린다.
    n_fixed = corpus_repair(areas, area_levels)

    suspicious = []
    for a in areas:
        for s in a["standards"]:
            for txt in [s["text"]] + list(s["levels"].values()):
                suspicious += find_suspicious(txt)
    for a in area_levels:
        for tr in a["levels"].values():
            for v in tr.values():
                suspicious += find_suspicious(v)

    glued = []
    for a in areas:
        for s in a['standards']:
            for txt in [s['text']] + list(s['levels'].values()):
                glued += find_glued(txt)
    for a in area_levels:
        for tr in a['levels'].values():
            for v in tr.values():
                glued += find_glued(v)

    data = {"areas": areas, "area_levels": area_levels,
            "suspicious": sorted(set(suspicious)),
            "glued": sorted(set(glued))}
    with io.open(out, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print('영역:', area_names)
    total = 0
    for a in areas:
        for s in a["standards"]:
            total += 1
            missing = [g for g in GRADES if not s["levels"].get(g)]
            extra = [k for k in s["levels"] if k not in GRADES]
            flag = (' MISSING=%s' % missing if missing else '') + \
                   (' EXTRA=%s' % extra if extra else '')
            print('  %s  본문%3d자  탐구%s%s' % (s["code"], len(s["text"]), s["inquiry"] or '-', flag))
    print('성취기준 합계:', total)
    print('영역별 성취수준:')
    for a in area_levels:
        for g in GRADES:
            tr = a["levels"].get(g) or {}
            miss = [t for t in ("지식이해", "과정기능", "가치태도") if not tr.get(t)]
            print('   %-18s %s %s %s' % (a["unit"], g,
                  {t: len(v) for t, v in tr.items()},
                  ('MISSING=%s' % miss) if miss else ''))
    print('자간 깨짐 후보:', len(data["suspicious"]), '| 문서 대조로 복원:', n_fixed)
    print('어절 붙음 후보:', len(data['glued']))
    for g in data['glued']:
        print('   ~', g)
    for s in data["suspicious"]:
        print('   !', s)


if __name__ == '__main__':
    main()
"""KICE「2022 개정 교육과정에 따른 고등학교 과학과 선택과목 성취수준」PDF에서
한 과목의 '성취기준별 성취수준'과 '영역별 성취수준'을 뽑아낸다.

PDF 표를 텍스트로 추출하면 셀 내용이 위에서 아래로 한 줄씩 늘어서므로,
아래 규칙으로 되짚는다.
  - 성취기준별: `[12세포01-01] 본문` 뒤에 A~E가 각각 줄머리에 오는 형태
  - 영역별:     영역명 뒤에 A~E, 각 등급 안에서 지식･이해/과정･기능/가치･태도

양쪽 정렬 때문에 PDF가 글자 사이에 공백을 끼워 넣은 구간("말 할  수  있 다 .")은
자동으로 못 고치므로 suspicious 목록으로 뽑아 사람이 확인하게 한다.
"""
import io, json, re, sys, collections

PDF = None  # 명령줄 6번째 인자로 지정, 없으면 아래 기본값
DEFAULT_PDF = r'C:\Users\cando\OneDrive\바탕 화면\평가기준_과학과.pdf'
GRADES = ["A", "B", "C", "D", "E"]
TRAIT_MAP = {"지식･이해": "지식이해", "지식·이해": "지식이해",
             "과정･기능": "과정기능", "과정·기능": "과정기능",
             "가치･태도": "가치태도", "가치·태도": "가치태도"}

DROP_PATTERNS = [
    r'^성취기준[ ]*성취기준별 성취수준$',
    r'^[Ⅰ-ⅿ]+[.]?[ ]*[가-힣0-9]+ 성취수준$',
    r'^2022 개정 교육과정에 따른',
    r'^고등학교 과학과 선택과목 성취수준$',
    r'^\d{1,4}$',                          # 쪽번호
    r'^[\u2160-\u217f]+\.?\s',             # 러닝 헤더 (ⅩⅠ. 세포와 물질대사)
    r'^교육과정 성취기준\s*성취기준별 성취수준$',
    r'^영역\s*영역별 성취수준$',
    r'^\d 성취기준별 성취수준$',
    r'^\d 영역별 성취수준$',
]
DROP_RE = [re.compile(p) for p in DROP_PATTERNS]
AREA_RE = re.compile(r'^\((\d)\)\s*(.+)$')
CODE_RE = re.compile(r'\[((?:10|12)[\uac00-\ud7a3]{2,3}\d?(?:-\d{2})?\d{0,2}-\d{2})\]')
LEVEL_RE = re.compile(r'^([A-E])(?:\s+(.*))?$')
# 등급 문자 뒤에 공백 없이 본문이 붙는 판(예: "DD NA의 구조와…")을 위한 보조 패턴
LEVEL_TIGHT_RE = re.compile(r'^([A-E])(\S.*)$')
INQUIRY_HEAD_RE = re.compile(r'^<\s*탐\s*구\s*활\s*동\s*>')


def page_lines(pdf, lo, hi):
    from pypdf import PdfReader
    r = PdfReader(pdf)
    out = []
    for i in range(lo, hi + 1):
        for raw in (r.pages[i - 1].extract_text() or '').split('\n'):
            # 오른쪽 공백은 남긴다 - 이 PDF는 줄 끝 공백 유무로 어절 경계를 표시한다.
            line = raw.rstrip('\r').lstrip()
            if not line.strip():
                continue
            if any(rx.match(line) for rx in DROP_RE):
                continue
            out.append(line)
    return out


def join_lines(parts):
    """PDF 줄바꿈으로 끊긴 조각을 잇는다. 이 문서는 어절 경계에서 줄이 바뀔 때만
    줄 끝에 공백을 남기므로, 그 공백이 없으면 어절 중간이라 보고 붙여 쓴다."""
    out = ''
    for raw in parts:
        if raw is None:
            continue
        piece = raw.lstrip()
        if not piece.strip():
            continue
        if not out:
            out = piece
            continue
        boundary = out.endswith(' ') or out.rstrip()[-1] in '.,;:)' or piece[0] in '<[('
        out = out.rstrip() + (' ' if boundary else '') + piece
    return re.sub(r'[ 	]+', ' ', out).strip()


# 양쪽 정렬로 글자 사이가 벌어진 구간(공백 제거형) -> 정상 표기.
# 이 문서의 서술어는 정형화돼 있어 항목이 과목 간에 대부분 재사용된다.
REPAIRS = {
    "말할수있다": "말할 수 있다",
    "설명할수있다": "설명할 수 있다",
    "추론할수있다": "추론할 수 있다",
    "구분할수있다": "구분할 수 있다",
    "제작할수있다": "제작할 수 있다",
    "수행할수있다": "제작할 수 있다",
    "를조사할수있다": "를 조사할 수 있다",
    "에대해소통할수있다": "에 대해 소통할 수 있다",
    "여협력적으로소통할수있다": "여 협력적으로 소통할 수 있다",
    "대해흥미와호기심을가진다": "대해 흥미와 호기심을 가진다",
    "에대한흥미와호기심을가진다": "에 대한 흥미와 호기심을 가진다",
    "로다각적인접근을시도한다": "로 다각적인 접근을 시도한다",
    "체유전양상의차이를설명할수있다": "체 유전 양상의 차이를 설명할 수 있다",
    "학문분야와직업을설명할수있다": "학문 분야와 직업을 설명할 수 있다",
    "할수있다": "할 수 있다",
    "대한흥미와호기심을가진다": "대한 흥미와 호기심을 가진다",
    "대해소통할수있다": "대해 소통할 수 있다",
    "문분야와직업을설명할수있다": "문 분야와 직업을 설명할 수 있다",
    "유전양상의차이를": "유전 양상의 차이를",
    "협력적으로소통할수있다": "협력적으로 소통할 수 있다",
    "흥미와호기심을가진다": "흥미와 호기심을 가진다",
    "접근을시도한다": "접근을 시도한다",
    "관심을가진다": "관심을 가진다",
    "흥미를가진다": "흥미를 가진다",
    "인식할수": "인식할 수",
    "설계할수": "설계할 수",
    "판단할수": "판단할 수",
    "해석할수": "해석할 수",
    "예측하고": "예측하고",
    "측정하고비교할수": "측정하고 비교할 수",
    "조사하고발표할수": "조사하고 발표할 수",
    "사례와연관지어": "사례와 연관지어",
    "부터기후변화가수생태": "부터 기후변화가 수생태",
    "알고이와관련된일상생활": "알고, 이와 관련된 일상생활",
    "알고,이와관련된일상생활": "알고, 이와 관련된 일상생활",
    "느낄수있다": "느낄 수 있다",
    "느낄수있": "느낄 수 있",
    "맞게시각자": "맞게 시각 자",
    "제시하고,심층순환이밀도": "제시하고, 심층 순환이 밀도",
    "수있음과반": "수 있음과 반",
    "알고,양적관": "알고, 양적 관",
    "형성되며모든": "형성되며 모든",
    "알고,전기분": "알고, 전기분",
    "따라구분할수있고": "따라 구분할 수 있고",
    "서제시할수": "서 제시할 수",
    "제시하고발표할수": "제시하고 발표할 수",
    "측정할수": "측정할 수",
    "갖고에너지문": "갖고, 에너지 문",
    "과학이필요": "과학이 필요",
    "수행하여유도전": "수행하여 유도 전",
    "안전성과환경친화": "안전성과 환경 친화",
    "해결하기위한": "해결하기 위한",
    "갖고,에너지문": "갖고, 에너지 문",
    "표현하고공유할수": "표현하고 공유할 수",
    "표현할수": "표현할 수",
    "다양한도": "다양한 도",
    "분해실험하기탐구활": "분해 실험하기 탐구활",
    "관련지어설명할수": "관련지어 설명할 수",
    "도출하고해석할수": "도출하고 해석할 수",
    "조사할수": "조사할 수",
    "추론할수": "추론할 수",
    "설명할수": "설명할 수",
    "제작할수": "제작할 수",
    "수행할수": "수행할 수",
    "구분하여": "구분하여",
    "제작하고": "제작하고",
    "종류와특성을": "종류와 특성을",
    "도출하고해석할": "도출하고 해석할",
}



# 자간이 벌어져 쪼개진 약어. 이 문서에 나오는 것만 다룬다.
ACRONYMS = ['mRNA', 'DNA', 'RNA', 'ATP', 'PCR', 'NGS', 'LMO', 'GMO', 'pH']
# 홀로 설 수 없는 조사 - 앞 어절에 붙여야 한다.
ORPHAN_PARTICLES = ['로', '을', '를', '은', '는', '의', '에']
# 줄 이음에서 앞 어절에 잘못 붙는 서술어 - 띄어 써야 한다.
GLUED_PREDICATES = ['가진다', '인식한다', '시도한다', '지닌다', '느낀다', '중시한다',
                    '기여한다', '즐긴다', '체험한다', '이해한다', '소통한다', '제시한다']


# 원문의 명백한 오타. 고친 것만 여기 남긴다.
TYPOS = {'이떄': '이때'}


def fix_tokens(s):
    """약어 분리, 조사 고아, 서술어 붙음을 되돌린다."""
    for a in ACRONYMS:
        pat = r'\s*'.join(list(a))
        s = re.sub(pat, a, s)
    for pcl in ORPHAN_PARTICLES:
        s = re.sub(r'(?<=[\uac00-\ud7a3])\s+' + pcl + r'(?=[\s.,])', pcl, s)
    for pred in GLUED_PREDICATES:
        s = re.sub(r'(?<=[을를이가])' + pred, ' ' + pred, s)
    # 괄호 뒤에 떨어져 나온 조사도 붙인다: '(LMO) 가' -> '(LMO)가'
    s = re.sub('(?<=[)]) +(가|이|은|는|을|를|의|에|와|과)(?=[ .,])', lambda m: m.group(1), s)
    for stem in VERB_SPLIT_STEMS:
        s = s.replace(stem + ' 할 수 ', stem + '할 수 ')
        s = s.replace(stem + ' 하고', stem + '하고')
        s = s.replace(stem + ' 하여', stem + '하여')
        s = s.replace(stem + ' 한다', stem + '한다')
    for bad, good in TYPOS.items():
        s = s.replace(bad, good)
    return re.sub(r'[ \t]+', ' ', s).strip()

# run 경계로는 잡히지 않는 자간 구간(앞뒤에 2글자 어절이 섞인 경우)을
# 문구 단위로 되돌린다. 과목을 추가할 때마다 여기에 쌓인다.
# 좁은 표 칸에서 서술어가 갈라져 나오는 판: '설명 할 수' -> '설명할 수'.
# 앞이 조사 없는 한자어 명사일 때만이라 '~을 할 수 있다'와 겹치지 않는다.
VERB_SPLIT_STEMS = ['설명', '말', '추론', '조사', '제작', '구분', '비교', '수행', '소통', '분석', '표현', '적용', '판단', '예측', '평가', '제시', '탐구', '관찰', '측정', '해석', '설계', '도출', '활용', '발표', '토론', '인식', '파악']

PHRASE_FIXES = {
    "수송 과 정의 종 류 와 특 징을": "수송 과정의 종류와 특징을",
    "구성하는원소들이": "구성하는 원소들이",
    "일상생활에서활용되는": "일상생활에서 활용되는",
    "일상생활의문제해결에": "일상생활의 문제해결에",
    "특 징 및 생 태 계 에 서 일 어 나 는 물 질 의 순 환 과 에 너 지 의 흐 름 을 비 교 하 여 설 명 할": "특징 및 생태계에서 일어나는 물질의 순환과 에너지의 흐름을 비교하여 설명할",
}


def repair_spacing(s):
    """양쪽 정렬로 글자 사이가 벌어진 구간을 REPAIRS 표로 되돌린다.

    run 경계가 앞뒤로 밀릴 수 있으므로 run 안의 모든 연속 구간을 긴 것부터
    사전과 맞춰본다."""
    # 자간 복원 전에 공백을 먼저 한 칸으로 줄인다 - 원문은 벌어진 구간에 두 칸을
    # 섞어 쓰기 때문에, 축약을 나중에 하면 사전 매칭이 통째로 빗나간다.
    s = re.sub('[ ' + chr(9) + ']+', ' ', s)
    for bad, good in PHRASE_FIXES.items():
        s = s.replace(bad, good)
    for run in find_suspicious(s):
        toks = run.split(' ')
        n = len(toks)
        done = False
        for size in range(n, 2, -1):
            for start in range(0, n - size + 1):
                win = toks[start:start + size]
                key = ''.join(win).rstrip('.,')
                if key in REPAIRS:
                    tail = ''.join(win)[len(key):]
                    s = s.replace(' '.join(win), REPAIRS[key] + tail)
                    done = True
                    break
            if done:
                break
    return fix_tokens(re.sub('\s+([.,])', lambda m: m.group(1), s))


def despace(s):
    return re.sub(r'\s+', ' ', s).strip()


def find_suspicious(s):
    """양쪽 정렬로 글자 사이가 벌어진 구간(한글 1글자 토큰 4개 이상 연속)을 찾는다."""
    hits, run = [], []
    for t in s.split(' '):
        core = t.rstrip('.,')
        if len(core) == 1 and '\uac00' <= core <= '\ud7a3':
            run.append(t)
            continue
        if len(run) >= 4:
            hits.append(' '.join(run))
        run = []
    if len(run) >= 4:
        hits.append(' '.join(run))
    return hits


def next_grade(mode):
    if mode in (None, 'inquiry'):
        return 'A'
    if mode == 'text':
        return 'A'
    idx = GRADES.index(mode) if mode in GRADES else -1
    return GRADES[idx + 1] if 0 <= idx < len(GRADES) - 1 else None


def parse_standards(lines):
    """성취기준별 성취수준 -> [{unit, standards:[{code,text,inquiry,levels}]}]"""
    areas = []
    cur_area = None
    cur_std = None
    bucket = []
    mode = None   # 'text' | 'inquiry' | 'A'~'E'

    def flush():
        nonlocal bucket, cur_std, mode
        if mode is not None and bucket and (cur_std is not None or mode == 'area_inquiry'):
            val = join_lines(bucket)
            if mode == 'text':
                cur_std['text'] = val
            elif mode == 'area_inquiry':
                for piece in re.split(r'[ ]*[•·][ ]*', val):
                    piece = piece.strip().strip('[]')
                    if piece:
                        cur_area.setdefault('inquiry', []).append(despace(piece))
            elif mode == 'inquiry':
                for piece in re.split(r'\s*[\u2022\u00b7]\s*', val):
                    piece = piece.strip()
                    if piece:
                        cur_std['inquiry'].append(despace(piece).strip('[]'))
            else:
                cur_std['levels'][mode] = val
        bucket = []

    for line in lines:
        m_area = AREA_RE.match(line)
        if m_area and not CODE_RE.search(line):
            flush()
            mode, cur_std = None, None
            cur_area = {"unit": despace(m_area.group(2)), "standards": []}
            areas.append(cur_area)
            continue
        m_code = CODE_RE.search(line)
        if m_code and line.lstrip().startswith('['):
            flush()
            cur_std = {"code": m_code.group(1), "text": "", "inquiry": [],
                       "levels": collections.OrderedDict()}
            if cur_area is None:
                cur_area = {"unit": "(영역 미상)", "standards": []}
                areas.append(cur_area)
            cur_area["standards"].append(cur_std)
            mode, bucket = 'text', [line]
            continue
        if INQUIRY_HEAD_RE.match(line):
            # 진행 중인 등급 텍스트를 먼저 확정해야 A~E가 다 찼는지 판단할 수 있다.
            flush()
            # 이 문서군에는 탐구 활동을 성취기준별이 아니라 영역 끝에 한꺼번에
            # 싣는 판이 있다. A~E가 이미 다 찬 뒤에 나오면 영역 목록으로 본다.
            area_level = (cur_std is not None
                          and all(g in cur_std['levels'] for g in GRADES))
            mode = 'area_inquiry' if area_level else 'inquiry'
            bucket = []
            tail = INQUIRY_HEAD_RE.sub('', line).strip()
            if tail:
                bucket = [tail]
            continue
        m_lv = LEVEL_RE.match(line)
        if m_lv and cur_std is not None:
            flush()
            mode = m_lv.group(1)
            bucket = [m_lv.group(2)] if m_lv.group(2) else []
            continue
        # '...설명할 수 있다.D'처럼 다음 등급 문자가 앞 문장 끝에 붙어 나오는 판.
        # (원문에서 그 등급 칸이 비어 있을 때 이렇게 붙는다.)
        if cur_std is not None and mode in GRADES:
            tail_m = re.match('^(.+[.가-힣])[ ]*([A-E])$', line.rstrip())
            if tail_m and next_grade(mode) == tail_m.group(2):
                bucket.append(tail_m.group(1))
                flush()
                mode, bucket = tail_m.group(2), []
                continue
        if cur_std is not None:
            nxt = next_grade(mode)
            m_t = LEVEL_TIGHT_RE.match(line)
            if nxt and m_t and m_t.group(1) == nxt and nxt not in cur_std['levels']:
                flush()
                mode = nxt
                bucket = [m_t.group(2)]
                continue
        bucket.append(line)
    flush()
    for a in areas:
        for st in a["standards"]:
            st["text"] = repair_spacing(st["text"])
            st["inquiry"] = [repair_spacing(x) for x in st["inquiry"]]
            for g in list(st["levels"]):
                st["levels"][g] = repair_spacing(st["levels"][g])
    return areas


def is_table_head(line):
    """셀 끝에 딸려 온 표 머리(영역명)인지 본다.

    성취수준 본문은 언제나 '~다.'로 끝난다. 짧고 마침표로 끝나지 않는 끝줄은
    내용이 아니라 다음 영역의 표 머리다."""
    t = line.strip()
    return 0 < len(t) <= 20 and not t.endswith(('.', '다', '음', '함'))


def parse_area_levels(lines, area_names, boundary='header'):
    """영역별 성취수준 -> [{unit, levels:{A:{지식이해,과정기능,가치태도}}}]

    boundary='header': '(n) 영역명' 헤더에서 영역을 바꾼다(대부분의 과목).
    boundary='grade': 등급이 A로 돌아올 때 바꾼다. 헤더가 쪽 맨 위로 밀려 나와
    앞 영역의 남은 등급보다 먼저 오는 판(통합사회)에서 쓴다."""
    by_unit = collections.OrderedDict()
    cur_unit = cur_grade = cur_trait = None
    header_names = []      # '(n) 영역명' 헤더를 나온 순서대로 모은다
    area_idx = -1          # 등급이 A로 돌아올 때마다 다음 영역으로 넘어간다
    pending_name = None    # 'pending' 모드에서 전환을 미뤄 둔 영역명
    bucket = []
    squish = lambda s: re.sub(r'\s+', '', s)
    plain_names = {squish(n) for n in area_names}
    trait_plain = {squish(k): v for k, v in TRAIT_MAP.items()}

    def start_area_if_A(letter):
        """등급이 A로 돌아오면 다음 영역이 시작된 것으로 본다."""
        nonlocal area_idx, cur_unit, pending_name
        if boundary == 'pending':
            # 헤더가 앞 영역의 남은 등급보다 먼저 오면 전환을 미뤄 뒀다가 여기서 바꾼다.
            # 반대로 헤더가 A보다 늦게 오는 판도 있어(사회과 마지막 영역), 같은 영역에서
            # A가 다시 나오면 헤더를 기다리지 않고 다음 영역으로 넘어간다.
            already_A = bool((by_unit.get(cur_unit) or {}).get('A'))
            if letter == 'A' and (pending_name or already_A) or (
                    pending_name and cur_grade and letter <= cur_grade):
                flush()
                if pending_name:
                    cur_unit = pending_name
                    pending_name = None
                else:
                    used = list(by_unit)
                    nxt = [x for x in header_names if x not in used]
                    cur_unit = nxt[0] if nxt else '(영역 %d)' % (len(used) + 1)
        if boundary == 'grade' and letter == 'A':
            flush()
            area_idx += 1
            cur_unit = (header_names[area_idx] if area_idx < len(header_names)
                        else '(영역 %d)' % (area_idx + 1))
        return letter

    def flush():
        nonlocal bucket
        if cur_unit and cur_grade and cur_trait and bucket:
            g = by_unit.setdefault(cur_unit, collections.OrderedDict()) \
                       .setdefault(cur_grade, collections.OrderedDict())
            val = join_lines(bucket)
            g[cur_trait] = (g[cur_trait] + '\n' + val) if g.get(cur_trait) else val
        bucket = []

    for line in lines:
        m_area = AREA_RE.match(line)
        if m_area:
            name = despace(m_area.group(2))
            if boundary == 'pending':
                # 헤더가 쪽 맨 위로 밀려 나와 앞 영역의 남은 등급보다 먼저 오는
                # 판이 있다. 바로 바꾸지 말고 다음 등급까지 전환을 미룬다.
                # 표 첫 칸에도 '(3) 지속가능한 / 세계를 위한 / 생태전환'처럼 번호째
                # 되풀이된다. 이미 보류 중인 이름의 조각이면 덮어쓰지 않는다.
                sqn = squish(name)
                same_as_cur = cur_unit and sqn == squish(cur_unit)
                frag_of_pending = pending_name and sqn in squish(pending_name)
                if sqn and not same_as_cur and not frag_of_pending:
                    pending_name = name
                continue
            if boundary == 'grade':
                # 헤더는 이름만 모아 둔다. 경계는 등급 A 재등장으로 잡는다.
                if squish(name) and not any(squish(name) == squish(x) for x in header_names):
                    header_names.append(name)
                continue
            # 표 첫 칸에 '(1) 융합과학 / 탐구의 이해'처럼 번호까지 붙은 영역명이
            # 줄바꿈된 채 되풀이되는 판이 있다. 현재 영역명의 조각이면 넘긴다.
            if cur_unit and squish(name) and squish(name) in squish(cur_unit):
                continue
            flush()
            cur_unit = name
            cur_grade = cur_trait = None
            continue
            flush()
            cur_unit = name
            cur_grade = cur_trait = None
            continue
        sq = squish(line)
        if sq in plain_names:              # 표 첫 칸에 반복되는 영역명
            continue
        near = [x for x in (cur_unit, pending_name) if x]
        if sq and any(sq in squish(x) and len(sq) < len(squish(x)) for x in near):
            continue                       # 줄바꿈으로 쪼개진 영역명 조각
        if sq in trait_plain:
            flush()
            cur_trait = trait_plain[sq]
            continue
        # '생명시스템의 / 구성 A'처럼 영역명이 줄바꿈으로 쪼개져 등급 문자와
        # 한 줄에 붙어 나오는 판이 있다. 앞부분이 영역명 조각이면 등급으로 본다.
        m_split = re.match('^(.*)([A-E])$', sq)
        if m_split:
            head, letter = m_split.group(1), m_split.group(2)
            # 앞부분이 현재 영역명이나 아직 전환하지 않은 영역명의 조각이면 등급으로 본다.
            near = [x for x in (cur_unit, pending_name) if x]
            if head and any(head in squish(x) for x in near):
                flush()
                cur_grade, cur_trait = start_area_if_A(letter), None
                continue
        m_lv = LEVEL_RE.match(line)
        if m_lv:
            flush()
            cur_grade, cur_trait = start_area_if_A(m_lv.group(1)), None
            rest = m_lv.group(2)
            if rest and squish(rest) in trait_plain:
                cur_trait = trait_plain[squish(rest)]
            elif rest:
                for lab, key in trait_plain.items():
                    if squish(rest).startswith(lab):
                        cur_trait = key
                        bucket = [squish(rest)[len(lab):]]
                        break
            continue
        matched = False
        for lab, key in trait_plain.items():
            if sq.startswith(lab):
                flush()
                cur_trait = key
                tail = line.strip()[len(lab):].strip() if line.strip().startswith(lab) else sq[len(lab):]
                bucket = [tail] if tail else []
                matched = True
                break
        # '...실천한다.E'처럼 다음 등급 문자가 앞 문장 끝에 붙어 나오는 판.
        tail_m = re.match('^(.+[.가-힣])[ ]*([A-E])$', line.rstrip())
        if tail_m and cur_grade and next_grade(cur_grade) == tail_m.group(2):
            bucket.append(tail_m.group(1))
            flush()
            cur_grade, cur_trait = tail_m.group(2), None
            continue
        if not matched:
            bucket.append(line)
    flush()

    # 표 첫 칸의 영역명이 앞 셀 끝에 딸려 들어오는 판이 있다. 셀 끝줄이
    # 영역명과 똑같으면 떼어 낸다(내용이 아니라 표 머리이므로).
    known = {squish(x) for x in list(by_unit) + list(area_names) + header_names if x}
    for gr in by_unit.values():
        for tr in gr.values():
            for t in list(tr):
                parts = tr[t].split(chr(10))
                while len(parts) > 1 and (squish(parts[-1]) in known or is_table_head(parts[-1])):
                    parts.pop()
                tr[t] = chr(10).join(parts)

    for gr in by_unit.values():
        for tr in gr.values():
            for t in list(tr):
                joined = chr(10).join(repair_spacing(x) for x in tr[t].split(chr(10)))
                # 영역별 성취수준은 셀 안에서 문장 단위로 문단이 나뉘어 있다.
                tr[t] = re.sub(r'(?<=다\.)[ \t]+(?=\S)', chr(10), joined)
    return [{"unit": u,
             "levels": collections.OrderedDict((g, gr.get(g, {})) for g in GRADES)}
            for u, gr in by_unit.items()]


def find_glued(s):
    """줄 이음에서 두 어절이 붙어버린 후보(지나치게 긴 한글 덩어리)를 찾는다."""
    out = []
    for t in s.split(' '):
        core = t.strip('.,()[]')
        if len(core) >= 7 and all('가' <= c <= '힣' for c in core):
            out.append(core)
    return out


def restore_glued(tok, corpus):
    """같은 글자열이 문서 어딘가에 띄어 쓰여 있으면 그 표기를 쓴다."""
    text, nospace, index = corpus
    best, start = None, 0
    while True:
        at = nospace.find(tok, start)
        if at < 0:
            break
        start = at + 1
        cand = text[index[at]:index[at + len(tok) - 1] + 1]
        if '|' in cand or chr(10) in cand:
            continue
        if best is None or cand.count(' ') > best.count(' '):
            best = cand
    return best if best and best.count(' ') > 0 else None


def build_corpus(areas, area_levels):
    """과목 전체 텍스트를 모아 공백 제거 색인을 만든다.

    같은 문구가 문서 안 여러 곳에 나오는데, 좁은 칸에서만 자간이 벌어진다.
    그래서 깨진 구간의 공백을 지운 형태로 색인을 뒤져 정상 표기를 되찾을 수 있다.
    """
    chunks = []
    for a in areas:
        for s in a['standards']:
            chunks.append(s['text'])
            chunks.extend(s['levels'].values())
            chunks.extend(s.get('inquiry') or [])
        chunks.extend(a.get('inquiry') or [])
    for a in area_levels:
        for tr in a['levels'].values():
            chunks.extend(tr.values())
    text = ' | '.join(chunks)
    nospace, index = [], []
    for pos, ch in enumerate(text):
        if not ch.isspace():
            nospace.append(ch)
            index.append(pos)
    return text, ''.join(nospace), index


def restore_from_corpus(run, corpus):
    """깨진 구간과 같은 글자열을 문서에서 찾아, 공백이 가장 적은 표기를 고른다."""
    text, nospace, index = corpus
    key = run.replace(' ', '')
    if len(key) < 4:
        return None
    best, start = None, 0
    while True:
        at = nospace.find(key, start)
        if at < 0:
            break
        start = at + 1
        cand = text[index[at]:index[at + len(key) - 1] + 1]
        if '|' in cand:
            continue
        if best is None or cand.count(' ') < best.count(' '):
            best = cand
    return best if best and best.count(' ') < run.count(' ') else None


def corpus_repair(areas, area_levels):
    """자간이 벌어진 채 남은 구간을 문서 안의 정상 표기로 되돌린다."""
    corpus = build_corpus(areas, area_levels)
    fixed = 0

    def fix(s):
        nonlocal fixed
        for run in find_suspicious(s):
            good = restore_from_corpus(run, corpus)
            if good:
                s = s.replace(run, good)
                fixed += 1
        # 어절 붙음은 자동으로 고치지 않는다. 원문이 실제로 붙여 쓴 말
        # (예: '유전자편집기술')까지 쪼개 버려 원문을 훼손하기 때문이다.
        # 탐지 결과는 보고만 하고, 진짜 오류는 PHRASE_FIXES에 명시한다.
        return s

    for a in areas:
        for s in a['standards']:
            s['text'] = fix(s['text'])
            s['inquiry'] = [fix(x) for x in s['inquiry']]
            for g in list(s['levels']):
                s['levels'][g] = fix(s['levels'][g])
        if a.get('inquiry'):
            a['inquiry'] = [fix(x) for x in a['inquiry']]
    for a in area_levels:
        for g in list(a['levels']):
            for t in list(a['levels'][g]):
                a['levels'][g][t] = chr(10).join(
                    fix(x) for x in a['levels'][g][t].split(chr(10)))
    return fixed


AREA_NO_RE = re.compile(r'^(?:10|12)[가-힣]+\d?-?(\d{2})-\d{2}$')


def regroup_by_code(areas, area_levels):
    """성취기준 코드의 영역 번호로 영역을 다시 나눈다.

    통합사회처럼 성취기준별 표에 '(1) 영역명' 헤더가 없는 과목이 있다. 이때는
    영역 경계를 코드로 잡고, 영역명은 영역별 성취수준 쪽에서 순서대로 가져온다.
    """
    buckets = collections.OrderedDict()
    for a in areas:
        for s in a['standards']:
            m = AREA_NO_RE.match(s['code'])
            if not m:
                return areas, False
            buckets.setdefault(m.group(1), []).append(s)
    if len(buckets) != len(area_levels):
        return areas, False
    inquiry = [x for a in areas for x in (a.get('inquiry') or [])]
    out = []
    for (no, stds), lv in zip(buckets.items(), area_levels):
        out.append({'unit': lv['unit'], 'standards': stds})
    if inquiry:
        out[-1]['inquiry'] = inquiry
    return out, True


def main():
    global PDF
    PDF = sys.argv[6] if len(sys.argv) > 6 else DEFAULT_PDF
    std_lo, std_hi, area_lo, area_hi, out = (
        int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), sys.argv[5])
    areas = parse_standards(page_lines(PDF, std_lo, std_hi))
    area_names = [a["unit"] for a in areas]
    lvl_lines = page_lines(PDF, area_lo, area_hi)

    def blanks(res):
        return sum(1 for a in res for g in GRADES
                   for t in ('지식이해', '과정기능', '가치태도')
                   if not (a['levels'].get(g) or {}).get(t))

    # 헤더 기준이 기본이지만, 헤더가 쪽 맨 위로 밀려 나오는 문서(통합사회)에서는
    # 빈칸이 무더기로 생긴다. 두 방식을 다 돌려 빈칸이 적은 쪽을 쓴다.
    # 성취기준 코드의 영역 번호 개수가 정답이다(01-.., 02-.. 등).
    expected = len({AREA_NO_RE.match(s['code']).group(1)
                    for a in areas for s in a['standards']
                    if AREA_NO_RE.match(s['code'])})

    def score(res):
        # 영역 수가 맞는 쪽이 먼저, 그다음 빈칸이 적은 쪽.
        return (0 if expected and len(res) == expected else 1, blanks(res))

    cands = [('헤더 보류', parse_area_levels(lvl_lines, area_names, boundary='pending')),
             ('헤더', parse_area_levels(lvl_lines, area_names)),
             ('등급 A 재등장', parse_area_levels(lvl_lines, area_names, boundary='grade'))]
    cands.sort(key=lambda x: score(x[1]))
    pick, area_levels = cands[0]
    if pick != '헤더 보류':
        print('영역 경계: %s 기준 채택 (영역 %d/%d, 빈칸 %d)'
              % (pick, len(area_levels), expected, blanks(area_levels)))
    elif score(area_levels)[0]:
        print('경고: 영역 수가 성취기준 코드와 다름 (%d != %d)' % (len(area_levels), expected))

    # 최종 보정 패스 - 위 단계에서 놓친 자간 구간을 한 번 더 훑는다.
    for a in areas:
        for s in a['standards']:
            s['text'] = repair_spacing(s['text'])
            s['inquiry'] = [repair_spacing(x) for x in s['inquiry']]
            for g in list(s['levels']):
                s['levels'][g] = repair_spacing(s['levels'][g])
    for a in area_levels:
        for g in list(a['levels']):
            for t in list(a['levels'][g]):
                a['levels'][g][t] = chr(10).join(
                    repair_spacing(x) for x in a['levels'][g][t].split(chr(10)))

    # 성취기준별 표에 영역 헤더가 없는 과목(통합사회 등)은 코드로 영역을 다시 나눈다.
    su = [a['unit'] for a in areas]
    au = [a['unit'] for a in area_levels]
    if su != au:
        areas, changed = regroup_by_code(areas, area_levels)
        if changed:
            print('영역 재구성: 코드 기준으로 다시 나눔 ->', [a['unit'] for a in areas])
            area_names = [a['unit'] for a in areas]

    # 사전으로 못 고친 구간은 문서 자체에서 정상 표기를 찾아 되돌린다.
    n_fixed = corpus_repair(areas, area_levels)

    suspicious = []
    for a in areas:
        for s in a["standards"]:
            for txt in [s["text"]] + list(s["levels"].values()):
                suspicious += find_suspicious(txt)
    for a in area_levels:
        for tr in a["levels"].values():
            for v in tr.values():
                suspicious += find_suspicious(v)

    glued = []
    for a in areas:
        for s in a['standards']:
            for txt in [s['text']] + list(s['levels'].values()):
                glued += find_glued(txt)
    for a in area_levels:
        for tr in a['levels'].values():
            for v in tr.values():
                glued += find_glued(v)

    data = {"areas": areas, "area_levels": area_levels,
            "suspicious": sorted(set(suspicious)),
            "glued": sorted(set(glued))}
    with io.open(out, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print('영역:', area_names)
    total = 0
    for a in areas:
        for s in a["standards"]:
            total += 1
            missing = [g for g in GRADES if not s["levels"].get(g)]
            extra = [k for k in s["levels"] if k not in GRADES]
            flag = (' MISSING=%s' % missing if missing else '') + \
                   (' EXTRA=%s' % extra if extra else '')
            print('  %s  본문%3d자  탐구%s%s' % (s["code"], len(s["text"]), s["inquiry"] or '-', flag))
    print('성취기준 합계:', total)
    print('영역별 성취수준:')
    for a in area_levels:
        for g in GRADES:
            tr = a["levels"].get(g) or {}
            miss = [t for t in ("지식이해", "과정기능", "가치태도") if not tr.get(t)]
            print('   %-18s %s %s %s' % (a["unit"], g,
                  {t: len(v) for t, v in tr.items()},
                  ('MISSING=%s' % miss) if miss else ''))
    print('자간 깨짐 후보:', len(data["suspicious"]), '| 문서 대조로 복원:', n_fixed)
    print('어절 붙음 후보:', len(data['glued']))
    for g in data['glued']:
        print('   ~', g)
    for s in data["suspicious"]:
        print('   !', s)


if __name__ == '__main__':
    main()
