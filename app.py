import os
import re
import shutil
import tempfile
import time
import uuid

import logging
import traceback

from flask import Flask, jsonify, render_template, request, send_from_directory
from werkzeug.exceptions import HTTPException

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
OUTPUT_RETENTION_SECONDS = 24 * 60 * 60  # 개인정보처리방침 제4조와 동일한 보관기간(24시간)


def _cleanup_old_outputs():
    """
    생성된 xlsx(작성자 성명 등 포함)를 서버 디스크에 무기한 남기지 않도록,
    보관기간(24시간)이 지난 요청 디렉터리를 정리한다. 별도 백그라운드
    스케줄러 없이 다음 /api/generate 호출 시점에 기회적으로 청소한다 --
    Render 무료 플랜은 상시 실행되는 워커를 별도로 둘 수 없어, 방침에도
    "생성 후 24시간이 지나면 다음 요청 처리 시점에 삭제"로 정확히 적는다.
    """
    if not os.path.isdir(OUTPUT_DIR):
        return
    cutoff = time.time() - OUTPUT_RETENTION_SECONDS
    for name in os.listdir(OUTPUT_DIR):
        path = os.path.join(OUTPUT_DIR, name)
        if not os.path.isdir(path):
            continue
        try:
            if os.path.getmtime(path) < cutoff:
                shutil.rmtree(path, ignore_errors=True)
        except OSError:
            continue


# 정적 리소스(폼 스크립트/스타일시트)만 자체 도메인에서 불러오고, 인라인
# script/style이나 외부 출처 로드가 전혀 없는 앱이라 최소한의 CSP로 XSS 표면을
# 원천 차단할 수 있다. 나머지 헤더도 dorms-check 보안 트랙 기준(클릭재킹/MIME
# 스니핑/리퍼러 유출/불필요한 브라우저 권한 차단)에 맞춰 전 응답에 적용한다.
@app.after_request
def set_security_headers(response):
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; "
        "style-src 'self' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data:; object-src 'none'; base-uri 'self'; "
        "form-action 'self'; frame-ancestors 'none'"
    )
    response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    return response


# 프론트엔드(static/form.js)는 모든 API 응답을 response.json()으로 읽는다 -- 기본
# Flask 오류 페이지는 HTML이라, 서버에서 예외가 나면 브라우저 쪽에서 JSON 파싱이
# 다시 터지면서 사용자에게는 "생성 실패: SyntaxError ..." 같은 뜻 모를 문구만
# 남았다. /api/* 에서는 항상 message 필드를 가진 JSON 을 돌려주고, 진짜 원인은
# 서버 로그(Render 대시보드)에 트레이스백으로 남긴다.
@app.errorhandler(Exception)
def handle_any_error(error):
    status = error.code if isinstance(error, HTTPException) else 500
    if not request.path.startswith("/api/"):
        return error if isinstance(error, HTTPException) else ("Internal Server Error", 500)
    if status >= 500:
        app.logger.error("%s %s 처리 중 오류: %s", request.method, request.path, traceback.format_exc())
        message = "서버에서 문서를 만드는 중 오류가 발생했습니다. 입력값을 확인하고 다시 시도해주세요."
    else:
        message = getattr(error, "description", str(error))
    return jsonify({"message": message}), status


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/privacy")
def privacy():
    return render_template("privacy.html")


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
    _cleanup_old_outputs()

    performance_items = payload.get("performance_items") or []
    performance_ratios = [{"type": p.get("type"), "ratio": p.get("ratio")} for p in performance_items]
    midterm = payload.get("midterm") or {}
    final = payload.get("final") or {}
    warnings = validate_plan(
        grade=payload.get("grade"),
        credit=payload.get("credit"),
        midterm_essay_ratio=midterm.get("essay"),
        midterm_total_ratio=midterm.get("ratio"),
        final_essay_ratio=final.get("essay"),
        final_total_ratio=final.get("ratio"),
        performance_items=performance_ratios,
        grading_method=payload.get("grading_method"),
        split_scores=payload.get("split_scores") or {},
    )

    # 공개 배포 환경에서는 파일명이 과목명에서만 나오면(예: "평가계획표(공통수학1).xlsx")
    # 서로 다른 사용자가 같은 파일명을 만들어 덮어쓰거나, 다운로드 URL을 추측해
    # 남이 생성한 파일을 열람할 수 있다 -- 요청마다 무작위 하위 디렉터리를 둔다.
    request_id = uuid.uuid4().hex
    request_dir = os.path.join(OUTPUT_DIR, request_id)
    os.makedirs(request_dir, exist_ok=True)

    safe_subject = (payload.get("subject") or "과목미입력").replace("/", "_")
    xlsx_filename = f"평가계획표({safe_subject}).xlsx"
    xlsx_path = os.path.join(request_dir, xlsx_filename)

    write_xlsx(payload, xlsx_path)

    loaded_subject = load_subject(
        payload.get("revision") or "2022", payload.get("category") or "", payload.get("subject") or ""
    )
    if loaded_subject is None:
        warnings.append(
            f"'{payload.get('subject')}' 과목은 콘텐츠 라이브러리에 없습니다. "
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
