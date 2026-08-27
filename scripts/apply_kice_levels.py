# -*- coding: utf-8 -*-
# 콘텐츠 라이브러리의 성취기준/성취수준을 KICE 성취수준 PDF 원문으로 채우는 반영 도구.
# 웹앱 런타임에서는 쓰이지 않는다(오프라인 1회성). 사용법은 아래 docstring 참고.
#
#   python scripts/parse_kice_levels.py <성취기준별시작> <끝> <영역별시작> <끝> <out.json> [PDF경로]
#   python scripts/apply_kice_levels.py <out.json> <과목명> [교과군]
#
# 과목을 추가할 때 자간 깨짐/어절 붙음 후보가 보고되면, 진짜 오류만
# REPAIRS/PHRASE_FIXES에 명시적으로 넣을 것. 자동 교정은 원문을 훼손한다.
"""parse_levels.py가 뽑아낸 성취기준/성취수준 원문을 콘텐츠 라이브러리 과목 JSON에
반영한다. 과목별로 하드코딩하지 않고 파싱 결과만으로 채운다.

사용법:  python apply_levels.py <parsed.json> <과목명> [교과군]
"""
import io, json, sys, collections, os, re

WEB = r'C:\Users\cando\projects\eval_plan_tool\web'
GRADES = ["A", "B", "C", "D", "E"]
TRAITS = ["지식이해", "과정기능", "가치태도"]
ROMAN = ["Ⅰ", "Ⅱ", "Ⅲ", "Ⅳ", "Ⅴ", "Ⅵ", "Ⅶ", "Ⅷ", "Ⅸ", "Ⅹ"]

SOURCE_NOTE = (
    "성취기준과 성취수준(성취기준별·영역별·학기 단위·최소 성취수준)은 한국교육과정평가원 "
    "「2022 개정 교육과정에 따른 고등학교 과학과 선택과목 성취수준」의 '{subject}' 절 "
    "원문을 그대로 옮긴 것이다(PDF 표에서 자동 추출한 뒤, 양쪽 정렬로 벌어진 자간과 "
    "줄바꿈으로 끊긴 어절만 복원했고 문장은 손대지 않았다). '학기 단위 성취수준'은 원문에 "
    "과목 단위 표가 없어 세 범주별로 영역별 성취수준 원문을 영역 라벨과 함께 이어붙인 "
    "것이다. 월별 진도·수업방법·평가방법·수행평가 예시 과제와 루브릭·분할점수·평가의 "
    "목적과 방향은 원문이 없는 교사 재량 영역이라 예시값이므로 실제 제출 전 수정이 필요하다."
)


def unit_label(idx, name):
    return "%s. %s" % (ROMAN[idx], name)


def main():
    parsed_path, subject = sys.argv[1], sys.argv[2]
    category = sys.argv[3] if len(sys.argv) > 3 else "과학과"
    path = os.path.join(WEB, "subjects", "2022", category, subject + ".json")

    P = json.load(io.open(parsed_path, encoding='utf-8'))
    with io.open(path, encoding='utf-8') as f:
        d = json.load(f, object_pairs_hook=collections.OrderedDict)

    areas = P["areas"]
    labels = [unit_label(i, a["unit"]) for i, a in enumerate(areas)]
    area_lv = {a["unit"]: a["levels"] for a in P["area_levels"]}

    # 성취기준 원문 (영역별 그룹)
    d["all_standards"] = [
        collections.OrderedDict([
            ("unit", labels[i]),
            ("standards", [s["text"] for s in a["standards"]]),
            # 이 문서군에는 탐구 활동을 성취기준별이 아니라 영역 끝에 묶어 싣는 판이 있다.
            ("inquiry", a.get("inquiry") or []),
        ]) for i, a in enumerate(areas)
    ]

    # 성취기준별 성취수준 + 탐구 활동
    d["standard_achievement_levels"] = [
        collections.OrderedDict([
            ("code", s["code"]),
            ("inquiry", s["inquiry"]),
            ("levels", collections.OrderedDict((g, s["levels"].get(g, "")) for g in GRADES)),
        ]) for a in areas for s in a["standards"]
    ]

    # 영역별 성취수준
    d["area_achievement_levels"] = [
        collections.OrderedDict([
            ("unit", labels[i]),
            ("levels", collections.OrderedDict(
                (g, collections.OrderedDict(
                    (t, (area_lv.get(a["unit"], {}).get(g) or {}).get(t, "")) for t in TRAITS))
                for g in GRADES)),
        ]) for i, a in enumerate(areas)
    ]

    # 학기 단위 성취수준 (범주 x A~E) — 영역별 원문을 영역 라벨과 함께 결합
    d["achievement_levels"] = collections.OrderedDict(
        (g, collections.OrderedDict(
            (t, "\n".join(
                "[%s] %s" % (labels[i], (area_lv.get(a["unit"], {}).get(g) or {}).get(t, ""))
                for i, a in enumerate(areas)
                if (area_lv.get(a["unit"], {}).get(g) or {}).get(t)))
            for t in TRAITS))
        for g in GRADES)

    # 최소 성취수준 진술문 — E수준 원문
    # 코드는 12<과목약칭><영역2자리>-<일련2자리> 형태. 약칭 길이가 과목마다 달라
    # 자릿수로 자르면 안 되고 정규식으로 쪼개야 한다.
    # 코드 체계가 둘이다: 진로선택 '12유전01-01'과 공통 '10통과1-01-01'.
    # 자릿수로 자르면 안 되고 정규식으로 쪼갠다. sep은 영역 번호 앞 하이픈 유무.
    CODE_RE = re.compile(r'^((?:10|12)[가-힣]+(?:\d(?=-))?)(-?)(\d{2})-(\d{2})$')

    def split_code(code):
        m = CODE_RE.match(code)
        if m:
            return m.group(1), m.group(2), m.group(3), m.group(4)
        return code[:5], '', code[5:7], code[8:]

    code_prefix, code_sep = split_code(areas[0]["standards"][0]["code"])[:2]
    d["minimum_achievement"] = []
    for i, a in enumerate(areas):
        e = area_lv.get(a["unit"], {}).get("E") or {}
        area_no = (split_code(a["standards"][0]["code"])[2]
                   if a["standards"] else "%02d" % (i + 1))
        d["minimum_achievement"].append(collections.OrderedDict([
            ("영역", "[%s%s%s] %s" % (code_prefix, code_sep, area_no, a["unit"])),
            ("영역별성취수준E", " ".join(
                e[t].replace("\n", " ") for t in TRAITS if e.get(t))),
            ("성취기준별성취수준E", [
                "%s-%s %s" % (split_code(s["code"])[2], split_code(s["code"])[3],
                              s["levels"].get("E", "")) for s in a["standards"]]),
            ("최소능력수행특성", collections.OrderedDict((t, e.get(t, "")) for t in TRAITS)),
        ]))
    d["minimum_achievement_overall"] = " ".join(
        (area_lv.get(a["unit"], {}).get("E") or {}).get("지식이해", "").replace("\n", " ")
        for a in areas).strip()

    # 월별 계획표의 성취기준도 원문으로 맞춘다(단원명이 영역과 일치하는 행만).
    by_label = {labels[i]: [s["text"] for s in a["standards"]] for i, a in enumerate(areas)}
    matched = 0
    for month, info in (d.get("units_by_month") or {}).items():
        unit = info.get("unit")
        if unit in by_label:
            info["standards"] = list(by_label[unit])
            matched += 1
        else:
            plain = re.sub(r'^[\u2160-\u217f]+\.\s*', '', unit or '')
            hit = [L for L in by_label if L.endswith(plain)] if plain else []
            if hit:
                info["unit"] = hit[0]
                info["standards"] = list(by_label[hit[0]])
                matched += 1

    # 단원명 표기가 원문과 달라 못 붙은 행은 순서로 맞춘다(월 수와 영역 수가 같을 때만).
    months = list((d.get('units_by_month') or {}).keys())
    if matched < len(areas) and len(months) == len(areas):
        for idx, m in enumerate(sorted(months, key=lambda x: int(x))):
            info = d['units_by_month'][m]
            info['unit'] = labels[idx]
            info['standards'] = list(by_label[labels[idx]])
        matched = len(areas)

    d["source_note"] = SOURCE_NOTE.format(subject=subject)

    with io.open(path, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
        f.write('\n')

    # 원문에서 아예 비어 있는 등급 칸이 있는 과목이 있다(예: 통합과학2 03-01의 B/D).
    empty = [(x["code"], g) for x in d["standard_achievement_levels"]
             for g in GRADES if not x["levels"][g]]
    empty_area = [(x["unit"], g, t) for x in d["area_achievement_levels"]
                  for g in GRADES for t in TRAITS if not x["levels"][g][t]]
    print(path)
    print('  영역:', labels)
    print('  성취기준:', len(d["standard_achievement_levels"]),
          '| 성취기준별 성취수준 빈칸:', empty or '없음')
    print('  영역별 성취수준 빈칸:', empty_area or '없음')
    print('  탐구 활동:',
          sum(len(x["inquiry"]) for x in d["standard_achievement_levels"]), '건(성취기준별) +',
          sum(len(g.get("inquiry") or []) for g in d["all_standards"]), '건(영역별)')
    print('  월별 계획표 성취기준 갱신:', matched, '행 /',
          len(d.get("units_by_month") or {}))


if __name__ == '__main__':
    main()
