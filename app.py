import os
import re
import tempfile
import uuid

from flask import Flask, jsonify, render_template, request, send_from_directory

from calendar_parser import parse_calendar
from content_library import list_subjects, load_subject
from doc_text_renderer import render_plan_html
from schedule_calc import compute_monthly_sessions
from validation import validate_plan
from xlsx_writer import write_xlsx

app = Flask(__name__)

# 배포 환경(Render 등)의 임시 디스크에도, 로컬 실행에도 그대로 동작하도록 OS
# 임시 디렉터리 아래에 둔다 -- Windows 전용 절대경로였던 이전 기본값은 서버에서
# 동작하지 않는다.
OUTPUT_DIR = os.environ.get("EVAL_PLAN_OUTPUT_DIR", os.path.join(tempfile.gettempdir(), "eval_plan_tool_output"))
_REQUEST_ID_RE = re.compile(r"^[0-9a-f]{32}$")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/reference")
def reference():
    """
    콘텐츠 라이브러리(subjects/*.json)의 units_by_month를 그대로 돌려준다. 월별 계획표
    UI에서 교육과정 성취기준 체크박스 후보를 채우는 데 쓴다 — 과목이 라이브러리에 없으면
    빈 dict를 돌려주고, 프론트엔드는 "기타(직접입력)"만 안내한다.
    """
    revision = request.args.get("revision", "2022")
    category = request.args.get("category", "")
    subject = request.args.get("subject", "")
    loaded_subject = load_subject(revision, category, subject) if subject and category else None
    units_by_month = (loaded_subject or {}).get("units_by_month", {})
    return jsonify({"units_by_month": units_by_month})


@app.get("/api/subjects")
def subjects():
    """
    콘텐츠 라이브러리(subjects/{revision}/{category}/*.json)에 등록된 과목명 목록을
    돌려준다. 과목명 입력란 옆 드롭다운이 적용 교육과정을 바꿀 때마다 이걸 호출해
    "이 교육과정에 실제로 등록된 과목"을 보여준다 — 등록 안 된 과목은 여전히 직접
    입력할 수 있다.
    """
    revision = request.args.get("revision", "2022")
    category = request.args.get("category", "수학")
    return jsonify({"subjects": list_subjects(revision, category)})


@app.post("/api/calendar/upload")
def calendar_upload():
    uploaded = request.files["calendar"]
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    # 공개 배포 환경에서는 여러 사용자가 동시에 업로드할 수 있어, 고정 파일명이면
    # 서로의 학사일정 파일을 덮어쓸 수 있다 -- 요청마다 고유한 임시 파일을 쓰고
    # 파싱 후 바로 지운다(파싱 결과만 필요하고 원본 파일은 남길 이유가 없음).
    tmp_path = os.path.join(OUTPUT_DIR, f"_uploaded_calendar_{uuid.uuid4().hex}.hwp")
    uploaded.save(tmp_path)
    try:
        events = parse_calendar(tmp_path)
    finally:
        os.remove(tmp_path)
    return jsonify({"events": events})


@app.post("/api/calendar/compute")
def calendar_compute():
    """
    /api/calendar/upload가 돌려준 후보(events) 중 교사가 화면에서 확인/수정해 확정한
    excluded_events만 받아서, 실제 월별 주·차시를 계산해 돌려준다.
    이 라우트가 Task 9의 compute_monthly_sessions를 실제로 호출하는 유일한 지점이다.
    """
    payload = request.get_json()
    result = compute_monthly_sessions(
        year=payload["year"],
        semester_start=payload["semester_start"],
        semester_end=payload["semester_end"],
        excluded_events=payload["excluded_events"],
        class_weekdays=payload["class_weekdays"],
    )
    return jsonify({"monthly_sessions": result})


@app.post("/api/generate")
def generate():
    payload = request.get_json()
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    performance_ratios = [{"type": p["type"], "ratio": p["ratio"]} for p in payload["performance_items"]]
    warnings = validate_plan(
        grade=payload["grade"],
        credit=payload["credit"],
        midterm_essay_ratio=payload["midterm"]["essay"],
        midterm_total_ratio=payload["midterm"]["ratio"],
        final_essay_ratio=payload["final"]["essay"],
        final_total_ratio=payload["final"]["ratio"],
        performance_items=performance_ratios,
        grading_method=payload["grading_method"],
        split_scores=payload["split_scores"],
    )

    # 공개 배포 환경에서는 파일명이 과목명에서만 나오면(예: "평가계획표(공통수학1).xlsx")
    # 서로 다른 사용자가 같은 파일명을 만들어 덮어쓰거나, 다운로드 URL을 추측해
    # 남이 생성한 파일을 열람할 수 있다 -- 요청마다 무작위 하위 디렉터리를 둔다.
    request_id = uuid.uuid4().hex
    request_dir = os.path.join(OUTPUT_DIR, request_id)
    os.makedirs(request_dir, exist_ok=True)

    safe_subject = payload["subject"].replace("/", "_")
    xlsx_filename = f"평가계획표({safe_subject}).xlsx"
    xlsx_path = os.path.join(request_dir, xlsx_filename)

    write_xlsx(payload, xlsx_path)

    loaded_subject = load_subject(payload["revision"], payload["category"], payload["subject"])
    if loaded_subject is None:
        warnings.append(
            f"'{payload['subject']}' 과목은 콘텐츠 라이브러리에 없습니다. "
            "아래 미리보기의 서술형 내용(평가목적/방향/성취수준 등)이 비어 있으니 "
            "직접 작성해주세요."
        )
    subject_json = loaded_subject or {}
    doc_html = render_plan_html(payload, subject_json)

    return jsonify(
        {
            "xlsx_filename": xlsx_filename,
            "xlsx_download_url": f"/api/download/{request_id}/{xlsx_filename}",
            "doc_html": doc_html,
            "warnings": warnings,
        }
    )


@app.get("/api/download/<request_id>/<path:filename>")
def download(request_id, filename):
    if not _REQUEST_ID_RE.match(request_id):
        return jsonify({"message": "invalid request id"}), 404
    return send_from_directory(os.path.join(OUTPUT_DIR, request_id), filename, as_attachment=True)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
