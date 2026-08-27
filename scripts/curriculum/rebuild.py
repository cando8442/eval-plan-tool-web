# -*- coding: utf-8 -*-
"""콘텐츠 라이브러리의 units_by_month 를 교육과정 원문 성취기준으로 다시 만든다.

2022 개정 교육과정 과목은 한 학기 완결이므로, 과목의 성취기준 전체가 한 학기
(월별 계획 5행) 안에 모두 들어가야 한다. 기존 파일들은 영역당 2개씩만 뽑은 3개월치
예시라, 성취기준 상당수가 아예 UI에 뜨지 않았다.

프론트엔드(static/form.js MAX_MONTHLY_ROWS)가 월별 계획을 5행으로 제한하고,
라이브러리의 월을 "학기 진행 순서상 몇 번째 달인가"로 위치 매칭하므로 월 수는 정확히
5개여야 한다. 또 units_by_month 는 sorted(key=int) 로 정렬되므로 2학기 과목은
9~1월이 아니라 8~12월로 적어야 순서가 뒤집히지 않는다(공통수학2가 쓰는 방식).
"""
import json
import io
import re

ROMAN = {1: "Ⅰ", 2: "Ⅱ", 3: "Ⅲ", 4: "Ⅳ", 5: "Ⅴ", 6: "Ⅵ"}

FIRST_SEMESTER = ["3", "4", "5", "6", "7"]
SECOND_SEMESTER = ["8", "9", "10", "11", "12"]

# 한 학기 5개월 예시 배분(4학점 기준 약 68차시). 중간고사는 넷째 달 직전,
# 기말고사는 마지막 달에 둔다 -- 실제 시수는 학사일정 분석 결과로 덮어쓰인다.
MONTH_SHAPE = [
    {"week_hours": "1~4주 (16)", "exam": None},
    {"week_hours": "1~4주 (13)", "exam": "5주: 중간고사"},
    {"week_hours": "1~4주 (16)", "exam": None},
    {"week_hours": "1~5주 (16)", "exam": None},
    {"week_hours": "1주 기말고사, 2~4주 (8)", "exam": "1주: 기말고사"},
]


def split_into_months(standards, n_months=5):
    """성취기준 목록을 n_months 개 구간으로 나눈다.

    두 가지를 동시에 만족해야 한다. (1) 각 달의 성취기준 수가 고르게 -- 한 달에 1개,
    다른 달에 5개씩 몰리면 예시 계획으로 못 쓴다. (2) 가능하면 영역 경계에서 끊기 --
    한 달 안에 여러 영역이 섞이면 단원명이 길어지고 수업 흐름과도 어긋난다.

    구간 수가 5, 성취기준이 20개 미만이라 완전 탐색(DP)으로 최적 분할을 고른다.
    비용 = 균등 편차 제곱합 + 영역 경계가 아닌 지점에서 끊을 때의 벌점.
    """
    n = len(standards)
    if n <= n_months:
        # 성취기준이 달 수보다 적으면 한 달에 하나씩 넣고 나머지는 비운다.
        return [[s] for s in standards] + [[] for _ in range(n_months - n)]

    boundaries = {i for i in range(1, n) if standards[i][2] != standards[i - 1][2]}
    avg = n / n_months
    BOUNDARY_PENALTY = 1.5

    from functools import lru_cache

    @lru_cache(maxsize=None)
    def best(start, slots):
        """standards[start:] 를 slots 개 구간으로 나눌 때의 (비용, 컷 목록)."""
        if slots == 1:
            size = n - start
            return ((size - avg) ** 2, ())
        result = None
        # 각 구간은 최소 1개는 가져가야 하고, 뒤 구간에도 1개씩은 남겨야 한다.
        for cut in range(start + 1, n - slots + 2):
            size = cut - start
            cost = (size - avg) ** 2
            if cut not in boundaries:
                cost += BOUNDARY_PENALTY
            sub_cost, sub_cuts = best(cut, slots - 1)
            total = cost + sub_cost
            if result is None or total < result[0]:
                result = (total, (cut,) + sub_cuts)
        return result

    _, cuts = best(0, n_months)
    bounds = [0] + list(cuts) + [n]
    return [standards[bounds[i] : bounds[i + 1]] for i in range(n_months)]


def unit_name(bucket, areas, fallback=""):
    """그 달의 단원명. 고시문 영역명을 그대로 쓰고, 영역 구분이 없는 과목은 과목명을 쓴다.

    국어 선택 과목처럼 고시문이 영역을 나누지 않는 과목(성취기준이 전부 01-xx)은
    단원 구분이 원문에 없다. 없는 단원명을 지어내면 이 라이브러리가 처음에 성취기준을
    지어내 틀렸던 것과 같은 문제가 되므로, 과목명을 넣고 교사가 채우게 둔다.
    """
    names = []
    for _, _, area_no in bucket:
        official = areas.get(area_no)
        if official:
            label = f"{ROMAN.get(area_no, area_no)}. {official}"
        else:
            label = fallback
        if label and label not in names:
            names.append(label)
    return " / ".join(names)


def rebuild_units(subject_json, parsed, semester=1, fallback_unit=""):
    standards = parsed["standards"]
    areas = parsed["areas"]
    months = FIRST_SEMESTER if semester == 1 else SECOND_SEMESTER
    buckets = split_into_months(standards, len(months))

    old = subject_json.get("units_by_month") or {}
    old_rows = [old[k] for k in sorted(old, key=int)]

    def carry(idx, key, default):
        """기존 파일에 있던 수업방법/평가방법을 살려 쓴다(달 수가 늘었으므로 순환)."""
        if not old_rows:
            return default
        return old_rows[idx % len(old_rows)].get(key) or default

    new = {}
    for i, month in enumerate(months):
        bucket = buckets[i]
        shape = MONTH_SHAPE[i]
        new[month] = {
            "week_hours": shape["week_hours"],
            "unit": unit_name(bucket, areas, fallback_unit),
            "standards": [f"{code} {body}" for code, body, _ in bucket],
            "teaching_methods": carry(i, "teaching_methods", ["강의식 수업", "주제탐구학습"]),
            "eval_methods": carry(i, "eval_methods", ["교사관찰", "형성평가"]),
            "sel": carry(i, "sel", None) if i < len(old_rows) else None,
            "exam": shape["exam"],
        }
    return new


def fix_codes(obj, old_prefix, new_prefix):
    """minimum_achievement 등에 남은 옛 코드 접두사를 원문 접두사로 바꾼다."""
    dumped = json.dumps(obj, ensure_ascii=False)
    dumped = dumped.replace(old_prefix, new_prefix)
    return json.loads(dumped)
