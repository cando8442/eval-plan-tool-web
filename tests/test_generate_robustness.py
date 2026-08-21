"""
/api/generate 가 마지막 단계에서 조용히 죽지 않는지 확인하는 회귀 테스트.

2026-08-21 버그: 마법사 5단계에서 "문 서 생 성"을 눌러도 아무 반응이 없거나
500 HTML이 돌아와 프론트엔드가 response.json()에서 다시 터졌다. 서버 쪽 몫은
(1) 비어 있는 수치 입력(ratio/credit 미입력)에도 500이 아니라 정상 응답을 주는 것,
(2) 그래도 예외가 나면 HTML이 아니라 message 필드를 가진 JSON을 주는 것이다.
"""
import json

import pytest

from app import app


BASE_PAYLOAD = {
    "grade": 1,
    "subject": "공통수학1",
    "credit": 4,
    "writer": "홍길동",
    "teachers": "홍길동",
    "revision": "2022",
    "semester": "1학기",
    "subject_type": "공통과목",
    "grading_scheme": ["석차등급"],
    "category": "수학",
    "midterm": {"selective": 70, "essay": 30, "short": 0, "ratio": 30},
    "final": {"selective": 70, "essay": 30, "short": 0, "ratio": 30},
    "performance_items": [{"type": "논술형", "title": "A", "month": "4", "ratio": 40}],
    "grading_method": "고정분할",
    "split_scores": {},
    "units_by_month": [{"month": "3", "unit": "다항식", "standards": [], "sessions": 16}],
}


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _post(client, payload):
    return client.post("/api/generate", data=json.dumps(payload), content_type="application/json")


def test_performance_ratio_missing_does_not_500(client):
    payload = json.loads(json.dumps(BASE_PAYLOAD))
    payload["performance_items"] = [{"type": "논술형", "title": "A", "month": "4", "ratio": None}]
    resp = _post(client, payload)
    assert resp.status_code == 200, resp.get_data(as_text=True)[:500]


def test_performance_ratio_key_absent_does_not_500(client):
    payload = json.loads(json.dumps(BASE_PAYLOAD))
    payload["performance_items"] = [{"type": "논술형", "title": "A", "month": "4"}]
    resp = _post(client, payload)
    assert resp.status_code == 200, resp.get_data(as_text=True)[:500]


def test_credit_missing_does_not_500(client):
    payload = json.loads(json.dumps(BASE_PAYLOAD))
    payload["credit"] = None
    resp = _post(client, payload)
    assert resp.status_code == 200, resp.get_data(as_text=True)[:500]


def test_unexpected_error_returns_json_not_html(client):
    """어떤 이유로든 실패하더라도 프론트엔드가 response.json()으로 읽을 수 있어야 한다."""
    resp = _post(client, {"grade": 1})  # 필수 키가 통째로 빠진 요청
    assert resp.status_code >= 400
    assert resp.mimetype == "application/json", resp.get_data(as_text=True)[:300]
    assert "message" in resp.get_json()


def test_list_fields_render_as_html_not_python_repr(client):
    """성취기준/수업방법 등 배열 값이 문서에 ['...'] 파이썬 repr 로 새어나오면 안 된다."""
    payload = json.loads(json.dumps(BASE_PAYLOAD))
    payload["units_by_month"] = [{
        "month": "3", "unit": "다항식",
        "standards": ["[10공수1-01-01] 다항식의 사칙연산", "[10공수1-01-02] 항등식과 나머지정리"],
        "method": ["강의식 수업", "모둠협력수업"],
        "eval": ["퀴즈"],
    }]
    resp = _post(client, payload)
    assert resp.status_code == 200
    doc = resp.get_json()["doc_html"]
    assert "&#x27;]" not in doc and "[&#x27;" not in doc, "파이썬 리스트 repr 이 문서에 새어나옴"
    assert "[10공수1-01-01] 다항식의 사칙연산<br>[10공수1-01-02] 항등식과 나머지정리" in doc
