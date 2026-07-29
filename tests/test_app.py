# tests/test_app.py
import os

from app import app


def test_health_endpoint():
    client = app.test_client()
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok"}


def test_subjects_endpoint_lists_2022_math_subjects():
    client = app.test_client()
    resp = client.get("/api/subjects?revision=2022&category=수학")
    assert resp.status_code == 200
    subjects = resp.get_json()["subjects"]
    assert "공통수학1" in subjects
    assert "공통수학2" in subjects


def test_subjects_endpoint_lists_2015_math_subjects():
    client = app.test_client()
    resp = client.get("/api/subjects?revision=2015&category=수학")
    assert resp.status_code == 200
    subjects = resp.get_json()["subjects"]
    for name in ["기하", "미적분", "확률과통계", "인공지능수학", "수학과제탐구"]:
        assert name in subjects


def test_subjects_endpoint_lists_2022_korean_subjects():
    client = app.test_client()
    resp = client.get("/api/subjects?revision=2022&category=국어")
    assert resp.status_code == 200
    subjects = resp.get_json()["subjects"]
    for name in [
        "공통국어1", "공통국어2", "화법과언어", "독서와 작문",
        "문학", "문학과 영상", "주제 탐구 독서", "독서 토론과 글쓰기",
    ]:
        assert name in subjects


def test_subjects_endpoint_lists_2022_english_subjects():
    client = app.test_client()
    resp = client.get("/api/subjects?revision=2022&category=영어")
    assert resp.status_code == 200
    subjects = resp.get_json()["subjects"]
    for name in [
        "공통영어1", "공통영어2", "영어Ⅰ", "영어Ⅱ",
        "영어 독해와 작문", "영어 발표와 토론", "영미 문학 읽기",
    ]:
        assert name in subjects


def test_subjects_endpoint_lists_2022_korean_history_subjects():
    client = app.test_client()
    resp = client.get("/api/subjects?revision=2022&category=한국사")
    assert resp.status_code == 200
    subjects = resp.get_json()["subjects"]
    assert "한국사1" in subjects
    assert "한국사2" in subjects


def test_subjects_endpoint_lists_2022_social_studies_subjects():
    client = app.test_client()
    resp = client.get("/api/subjects?revision=2022&category=사회과")
    assert resp.status_code == 200
    subjects = resp.get_json()["subjects"]
    for name in [
        "통합사회1", "통합사회2", "사회와 문화", "세계시민과 지리",
        "현대사회와 윤리", "세계사",
    ]:
        assert name in subjects


def test_subjects_endpoint_lists_2022_science_subjects():
    client = app.test_client()
    resp = client.get("/api/subjects?revision=2022&category=과학과")
    assert resp.status_code == 200
    subjects = resp.get_json()["subjects"]
    assert "통합과학1" in subjects
    assert "통합과학2" in subjects


def test_subjects_endpoint_returns_empty_for_unregistered_category():
    client = app.test_client()
    resp = client.get("/api/subjects?revision=2015&category=국어")
    assert resp.status_code == 200
    assert resp.get_json()["subjects"] == []


def test_generate_endpoint_creates_xlsx_and_doc_preview(tmp_path, monkeypatch):
    monkeypatch.setattr("app.OUTPUT_DIR", str(tmp_path))
    client = app.test_client()

    payload = {
        "grade": 1, "subject": "공통수학1", "credit": 4,
        "writer": "정요한", "teachers": "김은상, 장재욱, 정요한",
        "revision": "2022", "category": "수학", "semester": "1학기", "subject_type": "공통과목",
        "midterm": {"selective": 80, "essay": 10, "short": 10, "ratio": 30},
        "final": {"selective": 80, "essay": 10, "short": 10, "ratio": 30},
        "performance_items": [
            {"type": "서논술형", "title": "단원별 핵심 개념 구조화를 통해 단계별 문제 해결하기", "month": "3~7", "ratio": 15},
            {"type": "서논술형", "title": "수학 과제 탐구를 통한 실생활 문제 수학적으로 표현하기", "month": "4,6", "ratio": 25},
        ],
        "grading_method": "추정분할",
        "split_scores": {"A/B": 39, "B/C": 38, "C/D": 37, "D/E": 36, "E/I": 35},
        "units_by_month": [],
    }
    resp = client.post("/api/generate", json=payload)
    assert resp.status_code == 200
    data = resp.get_json()
    relative_path = data["xlsx_download_url"].removeprefix("/api/download/")
    assert os.path.isfile(os.path.join(str(tmp_path), *relative_path.split("/")))
    assert data["warnings"] == []
    assert "단원별 핵심 개념 구조화를 통해 단계별 문제 해결하기" in data["doc_html"]
    assert data["xlsx_download_url"].endswith(f"/{data['xlsx_filename']}")


def test_download_endpoint_serves_generated_xlsx(tmp_path, monkeypatch):
    monkeypatch.setattr("app.OUTPUT_DIR", str(tmp_path))
    client = app.test_client()

    payload = {
        "grade": 1, "subject": "공통수학1", "credit": 4,
        "writer": "정요한", "teachers": "김은상, 장재욱, 정요한",
        "revision": "2022", "category": "수학", "semester": "1학기", "subject_type": "공통과목",
        "midterm": {"selective": 80, "essay": 10, "short": 10, "ratio": 30},
        "final": {"selective": 80, "essay": 10, "short": 10, "ratio": 30},
        "performance_items": [],
        "grading_method": "추정분할",
        "split_scores": {"A/B": 39, "B/C": 38, "C/D": 37, "D/E": 36, "E/I": 35},
        "units_by_month": [],
    }
    resp = client.post("/api/generate", json=payload)
    data = resp.get_json()

    download_resp = client.get(data["xlsx_download_url"])
    assert download_resp.status_code == 200
    assert download_resp.mimetype == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def test_download_endpoint_rejects_non_uuid_request_id(tmp_path, monkeypatch):
    """request_id는 항상 uuid4().hex로만 만들어지므로, 그 형식이 아닌 값(경로 순회 시도
    포함)은 파일 존재 여부와 무관하게 404여야 한다 — 공개 배포 환경에서 다른 사용자의
    출력 디렉터리를 추측/순회해 접근하지 못하도록 막는 방어선이다."""
    monkeypatch.setattr("app.OUTPUT_DIR", str(tmp_path))
    client = app.test_client()

    resp = client.get("/api/download/../secrets/whatever.xlsx")
    assert resp.status_code == 404


def test_generate_endpoint_warns_when_subject_not_in_content_library(tmp_path, monkeypatch):
    """콘텐츠 라이브러리에 없는 과목명을 제출하면, xlsx/미리보기는 (서술형 내용이 빈 채)
    생성되지만 warnings에 명확한 안내 문구가 포함되어야 한다 — 그렇지 않으면 사용자가
    아무 신호 없이 불완전한 문서를 받게 된다."""
    monkeypatch.setattr("app.OUTPUT_DIR", str(tmp_path))
    client = app.test_client()

    payload = {
        "grade": 1, "subject": "존재하지않는과목", "credit": 4,
        "writer": "정요한", "teachers": "김은상, 장재욱, 정요한",
        "revision": "2022", "category": "수학", "semester": "1학기", "subject_type": "공통과목",
        "midterm": {"selective": 80, "essay": 10, "short": 10, "ratio": 30},
        "final": {"selective": 80, "essay": 10, "short": 10, "ratio": 30},
        "performance_items": [
            {"type": "서논술형", "title": "단원별 핵심 개념 구조화를 통해 단계별 문제 해결하기", "month": "3~7", "ratio": 15},
            {"type": "서논술형", "title": "수학 과제 탐구를 통한 실생활 문제 수학적으로 표현하기", "month": "4,6", "ratio": 25},
        ],
        "grading_method": "추정분할",
        "split_scores": {"A/B": 39, "B/C": 38, "C/D": 37, "D/E": 36, "E/I": 35},
        "units_by_month": [],
    }
    resp = client.post("/api/generate", json=payload)
    assert resp.status_code == 200
    data = resp.get_json()
    relative_path = data["xlsx_download_url"].removeprefix("/api/download/")
    assert os.path.isfile(os.path.join(str(tmp_path), *relative_path.split("/")))
    assert any("콘텐츠 라이브러리에 없습니다" in w for w in data["warnings"])


def test_calendar_compute_endpoint_returns_monthly_sessions():
    client = app.test_client()
    payload = {
        "year": 2026,
        "semester_start": "2026-03-01",
        "semester_end": "2026-03-31",
        "excluded_events": [{"month": 3, "day": 1, "label": "삼일절", "category": "HOLIDAY"}],
        "class_weekdays": [0, 1, 2, 3, 4],
    }
    resp = client.post("/api/calendar/compute", json=payload)
    assert resp.status_code == 200
    data = resp.get_json()
    assert 3 in data["monthly_sessions"] or "3" in data["monthly_sessions"]
