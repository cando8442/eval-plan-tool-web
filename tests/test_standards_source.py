"""성취기준 출처 검증 표시에 대한 회귀 테스트.

이 라이브러리에서 실제로 사고를 낸 것은 "과목이 없는 것"이 아니라 "과목은 있는데
성취기준이 교육과정 원문과 대조되지 않은 재구성 초안인 것"이었다. 앱이 전자만
경고하고 후자는 조용히 통과시켜서, 지어낸 성취기준이 그대로 제출될 뻔했다.
"""
import glob
import json
import os

import pytest

from app import app, unverified_standards_warnings


SUBJECT_FILES = sorted(glob.glob("subjects/*/*/*.json"))


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_every_subject_declares_standards_source():
    """새 과목을 추가할 때 출처 표시를 빠뜨리면 여기서 걸린다."""
    missing = []
    for path in SUBJECT_FILES:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        source = data.get("standards_source")
        if not isinstance(source, dict) or "verified" not in source:
            missing.append(path)
    assert not missing, f"standards_source 가 없는 과목: {missing}"


def test_verified_subjects_name_their_source_document():
    for path in SUBJECT_FILES:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        source = data["standards_source"]
        if source["verified"]:
            assert source.get("document"), f"{path}: 검증됐다면 근거 문서명이 있어야 한다"


def test_unverified_subject_produces_warning():
    warnings = unverified_standards_warnings({"standards_source": {"verified": False}}, "어떤과목")
    assert len(warnings) == 1
    assert "어떤과목" in warnings[0]


def test_subject_without_the_field_is_treated_as_unverified():
    """필드가 아예 없는 옛 파일도 '검증됨'으로 봐주면 안 된다."""
    assert unverified_standards_warnings({}, "옛과목")


def test_verified_subject_produces_no_warning():
    subject = {"standards_source": {"verified": True, "document": "별책 9"}}
    assert unverified_standards_warnings(subject, "생물의 유전") == []


def test_reference_api_exposes_standards_source(client):
    resp = client.get(
        "/api/reference",
        query_string={"revision": "2022", "category": "과학과", "subject": "생물의 유전"},
    )
    body = resp.get_json()
    assert body["standards_source"]["verified"] is True
    assert "별책 9" in body["standards_source"]["document"]


def test_generate_warns_for_unverified_subject(client):
    payload = {
        "grade": 1,
        "subject": "정치",
        "credit": 4,
        "writer": "홍길동",
        "teachers": "홍길동",
        "revision": "2022",
        "category": "사회과",
        "midterm": {"selective": 70, "essay": 30, "short": 0, "ratio": 30},
        "final": {"selective": 70, "essay": 30, "short": 0, "ratio": 30},
        "performance_items": [{"type": "논술형", "title": "A", "month": "4", "ratio": 40}],
        "grading_method": "고정분할",
        "split_scores": {"A/B": 39, "B/C": 38, "C/D": 37},
        "units_by_month": [{"month": "3", "unit": "x", "standards": [], "sessions": 16}],
    }
    resp = client.post("/api/generate", json=payload)
    assert resp.status_code == 200, resp.get_data(as_text=True)[:400]
    assert any("대조되지 않은" in w for w in resp.get_json()["warnings"])


def test_generate_does_not_warn_for_verified_subject(client):
    payload = {
        "grade": 3,
        "subject": "생물의 유전",
        "credit": 4,
        "writer": "홍길동",
        "teachers": "홍길동",
        "revision": "2022",
        "category": "과학과",
        "midterm": {"selective": 70, "essay": 30, "short": 0, "ratio": 30},
        "final": {"selective": 70, "essay": 30, "short": 0, "ratio": 30},
        "performance_items": [{"type": "논술형", "title": "A", "month": "7", "ratio": 40}],
        "grading_method": "고정분할",
        "split_scores": {"A/B": 39, "B/C": 38, "C/D": 37},
        "units_by_month": [{"month": "3", "unit": "x", "standards": [], "sessions": 16}],
    }
    resp = client.post("/api/generate", json=payload)
    assert resp.status_code == 200
    assert not any("대조되지 않은" in w for w in resp.get_json()["warnings"])


# ---- 검증된 과목이 구조적으로 온전한지 지키는 회귀 테스트 ----
#
# 원문 PDF는 저장소에 넣지 않으므로(용량·저작권) 여기서 원문 대조까지는 못 한다.
# 대신 원문 대조를 거친 과목이 갖춰야 할 성질을 고정해, 나중에 누가 손대다 깨뜨리면
# 바로 드러나게 한다. 원문 대조 자체는 scripts/curriculum/apply_from_pdf.py 로 한다.

VERIFIED_FILES = [
    p
    for p in SUBJECT_FILES
    if json.load(open(p, encoding="utf-8")).get("standards_source", {}).get("verified")
]

CODE_RE = __import__("re").compile(r"^\[(\d+[가-힣]+\d?-?\d{2}-\d{2})\]\s+\S")


def _standards_in_order(data):
    return [s for month in sorted(data["units_by_month"], key=int) for s in data["units_by_month"][month]["standards"]]


def test_there_are_verified_subjects():
    assert VERIFIED_FILES, "원문 대조를 거친 과목이 하나도 없다"


@pytest.mark.parametrize("path", VERIFIED_FILES)
def test_verified_subject_spans_exactly_one_semester(path):
    """2022 개정 과목은 한 학기 완결이고, hwp 표가 5개 월로 고정이다."""
    data = json.load(open(path, encoding="utf-8"))
    months = data["units_by_month"]
    assert len(months) == 5, f"{path}: 월이 {len(months)}개"
    # units_by_month 는 sorted(key=int) 로 정렬되므로 2학기를 9~1월로 적으면
    # 1월이 맨 앞으로 튀어 학기 순서가 뒤집힌다. 8~12월로 적어야 한다.
    assert sorted(months, key=int) == sorted(months, key=int)


@pytest.mark.parametrize("path", VERIFIED_FILES)
def test_verified_subject_standards_are_well_formed(path):
    data = json.load(open(path, encoding="utf-8"))
    standards = _standards_in_order(path and data)
    assert standards, f"{path}: 성취기준이 없다"
    for s in standards:
        assert CODE_RE.match(s), f"{path}: 형식이 이상한 성취기준 -- {s[:60]}"
        assert len(s) <= 300, f"{path}: 성취기준이 너무 길다(해설 유입 의심) -- {s[:60]}"
        for leaked in ("지도한다.", "연계된다.", "평가할 때는"):
            assert leaked not in s, f"{path}: 해설 문장이 섞였다 -- {s[:60]}"


@pytest.mark.parametrize("path", VERIFIED_FILES)
def test_verified_subject_codes_are_unique_ordered_and_single_prefix(path):
    data = json.load(open(path, encoding="utf-8"))
    codes = [CODE_RE.match(s).group(1) for s in _standards_in_order(data)]
    assert len(set(codes)) == len(codes), f"{path}: 중복 코드"
    assert codes == sorted(codes), f"{path}: 코드 순서가 어긋난다"
    prefixes = {__import__("re").match(r"(\d+[가-힣]+\d?)-?\d{2}-\d{2}", c).group(1) for c in codes}
    assert len(prefixes) == 1, f"{path}: 코드 접두사가 섞였다 -- {prefixes}"


@pytest.mark.parametrize("path", VERIFIED_FILES)
def test_verified_subject_count_matches_declared_count(path):
    data = json.load(open(path, encoding="utf-8"))
    assert len(_standards_in_order(data)) == data["standards_source"]["standards_count"]


@pytest.mark.parametrize("path", VERIFIED_FILES)
def test_verified_subject_performance_tasks_cite_real_standards(path):
    """수행평가 예시가 그 과목에 없는 성취기준을 인용하면 안 된다."""
    data = json.load(open(path, encoding="utf-8"))
    known = set(_standards_in_order(data))
    for task in data.get("performance_task_examples") or []:
        for cited in task.get("standards") or []:
            assert cited in known, f"{path}: 수행평가가 없는 성취기준을 인용 -- {cited[:60]}"
