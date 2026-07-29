import html


def _esc(value) -> str:
    return html.escape(str(value)) if value not in (None, "") else ""


def _esc_multiline(value) -> str:
    return _esc(value).replace("\n", "<br>")


def _section(title: str, body_html: str) -> str:
    return f'<section class="doc-section"><h2>{_esc(title)}</h2>{body_html}</section>'


def _list(items) -> str:
    lis = "".join(f"<li>{_esc(item)}</li>" for item in (items or []) if item)
    return f"<ul>{lis}</ul>" if lis else "<p>(내용 없음)</p>"


def _cover_section(payload: dict) -> str:
    rows = [
        ("적용 교육과정", f"{_esc(payload.get('revision'))}개정"),
        ("학년 / 과목 / 학점", f"{_esc(payload.get('grade'))}학년 · {_esc(payload.get('subject'))} · {_esc(payload.get('credit'))}학점"),
        ("학기 / 과목유형", f"{_esc(payload.get('semester'))} · {_esc(payload.get('subject_type'))}"),
        ("작성자 / 담당교사", f"{_esc(payload.get('writer'))} / {_esc(payload.get('teachers'))}"),
    ]
    body = "<table class='doc-table'><tbody>" + "".join(
        f"<tr><th>{label}</th><td>{value}</td></tr>" for label, value in rows
    ) + "</tbody></table>"
    return _section("표지 정보", body)


def _grading_scheme_section(payload: dict) -> str:
    return _section("성적 산출 방식", _list(payload.get("grading_scheme")))


def _eval_purpose_section(subject_json: dict) -> str:
    return _section("평가 목적", _list(subject_json.get("eval_purpose")))


def _eval_direction_section(subject_json: dict) -> str:
    return _section("평가 방향", _list(subject_json.get("eval_direction")))


def _monthly_plan_section(payload: dict) -> str:
    rows = [row for row in payload.get("units_by_month") or [] if row.get("month")]
    if not rows:
        return _section("월별 교수학습 운영 계획", "<p>(입력된 월별 계획이 없습니다)</p>")
    header = (
        "<tr><th>월</th><th>주(시수)</th><th>단원명</th><th>성취기준</th>"
        "<th>수업방법</th><th>평가방법</th><th>사회정서교육</th></tr>"
    )
    body_rows = "".join(
        "<tr>"
        f"<td>{_esc(r.get('month'))}</td>"
        f"<td>{_esc_multiline(r.get('weeks'))}</td>"
        f"<td>{_esc(r.get('unit'))}</td>"
        f"<td>{_esc_multiline(r.get('standards'))}</td>"
        f"<td>{_esc_multiline(r.get('method'))}</td>"
        f"<td>{_esc_multiline(r.get('eval'))}</td>"
        f"<td>{_esc_multiline(r.get('sel'))}</td>"
        "</tr>"
        for r in rows
    )
    return _section(
        "월별 교수학습 운영 계획",
        f"<table class='doc-table'><thead>{header}</thead><tbody>{body_rows}</tbody></table>",
    )


def _minimum_achievement_section(subject_json: dict) -> str:
    overall = subject_json.get("minimum_achievement_overall")
    items = subject_json.get("minimum_achievement") or []
    if not overall and not items:
        return _section("최소 성취수준 보장 지도", "<p>(콘텐츠 라이브러리에 없는 과목입니다)</p>")

    parts = [f"<p>{_esc(overall)}</p>"] if overall else []
    trait_labels = [("지식·이해", "지식이해"), ("과정·기능", "과정기능"), ("가치·태도", "가치태도")]
    for item in items:
        traits = item.get("최소능력수행특성") or {}
        trait_rows = "".join(
            f"<tr><th>{label}</th><td>{_esc(traits.get(key))}</td></tr>" for label, key in trait_labels
        )
        parts.append(
            f"<h3>{_esc(item.get('영역'))}</h3>"
            f"{_list(item.get('성취기준별성취수준E'))}"
            f"<table class='doc-table'><tbody>{trait_rows}</tbody></table>"
        )
    return _section("최소 성취수준 보장 지도", "".join(parts))


def _achievement_levels_section(subject_json: dict) -> str:
    levels = subject_json.get("achievement_levels") or {}
    if not levels:
        return _section("성취수준(A~E)", "<p>(콘텐츠 라이브러리에 없는 과목입니다)</p>")
    grades = ["A", "B", "C", "D", "E"]
    header = "<tr><th>구분</th>" + "".join(f"<th>{g}</th>" for g in grades) + "</tr>"
    trait_labels = [("지식·이해", "지식이해"), ("과정·기능", "과정기능"), ("가치·태도", "가치태도")]
    body_rows = "".join(
        "<tr>"
        + f"<th>{label}</th>"
        + "".join(f"<td>{_esc((levels.get(g) or {}).get(key))}</td>" for g in grades)
        + "</tr>"
        for label, key in trait_labels
    )
    return _section(
        "성취수준(A~E)", f"<table class='doc-table'><thead>{header}</thead><tbody>{body_rows}</tbody></table>"
    )


def _ratio_section(payload: dict) -> str:
    midterm = payload.get("midterm") or {}
    final = payload.get("final") or {}
    items = payload.get("performance_items") or []
    rows = [("중간고사", midterm.get("ratio")), ("기말고사", final.get("ratio"))] + [
        (item.get("title") or f"수행평가({item.get('type', '')})", item.get("ratio")) for item in items
    ]
    body = "".join(
        f"<tr><th>{_esc(label)}</th>"
        f"<td>{_esc(ratio) + '%' if ratio is not None else '(미입력)'}</td></tr>"
        for label, ratio in rows
    )
    table = f"<table class='doc-table'><tbody>{body}</tbody></table>"
    method_html = f"<p>성취평가 방식: {_esc(payload.get('grading_method'))}</p>"

    scores_html = ""
    split_scores = payload.get("split_scores") or {}
    if payload.get("grading_method") == "추정분할" and split_scores:
        header = "<tr>" + "".join(f"<th>{_esc(k)}</th>" for k in split_scores) + "</tr>"
        vals = "<tr>" + "".join(f"<td>{_esc(v)}</td>" for v in split_scores.values()) + "</tr>"
        scores_html = (
            f"<h3>분할점수(추정분할)</h3><table class='doc-table'><thead>{header}</thead>"
            f"<tbody>{vals}</tbody></table>"
        )

    return _section("평가영역 및 반영비율", table + method_html + scores_html)


def _performance_items_section(payload: dict) -> str:
    items = payload.get("performance_items") or []
    if not items:
        return _section("수행평가 세부계획", "<p>(입력된 수행평가 항목이 없습니다)</p>")

    parts = []
    for idx, item in enumerate(items, start=1):
        base_score = item.get("base_score")
        info_rows = [
            ("유형", item.get("type")),
            (
                "반영비율 / 배점 / 기본점수",
                f"{item.get('ratio', '')}% / {item.get('score', '')}점 / "
                f"{base_score if base_score is not None else '(미입력)'}",
            ),
            ("적용 시기(월)", item.get("month")),
            ("교육과정 영역", item.get("curriculum_area")),
            ("평가 과제", item.get("task")),
        ]
        info_table = "<table class='doc-table'><tbody>" + "".join(
            f"<tr><th>{_esc(label)}</th><td>{_esc_multiline(value)}</td></tr>" for label, value in info_rows
        ) + "</tbody></table>"

        rubric = item.get("rubric") or []
        rubric_html = "<p>(채점기준 미입력)</p>"
        if rubric:
            header = "<tr><th>영역</th><th>척도</th><th>채점기준</th><th>배점</th></tr>"
            rows = "".join(
                "<tr>"
                f"<td>{_esc(r.get('영역'))}</td><td>{_esc(r.get('척도'))}</td>"
                f"<td>{_esc(r.get('채점기준'))}</td><td>{_esc(r.get('배점'))}</td>"
                "</tr>"
                for r in rubric
            )
            rubric_html = f"<table class='doc-table'><thead>{header}</thead><tbody>{rows}</tbody></table>"

        parts.append(
            f"<h3>{idx}. {_esc(item.get('title') or '(제목 미입력)')}</h3>"
            f"{info_table}<h4>성취기준</h4>{_list(item.get('standards'))}"
            f"<h4>채점기준표</h4>{rubric_html}"
        )
    return _section("수행평가 세부계획", "".join(parts))


def render_plan_html(payload: dict, subject_json: dict | None) -> str:
    """평가계획서 hwp에 들어가던 내용을 구글독스 붙여넣기용 HTML로 렌더링한다.

    hwp COM 자동화(pyhwpx)를 대체하는 경로 -- 표/문단 구조는 유지하되 원본 hwp
    서식과 동일하지는 않다. 사용자가 이 결과를 그대로 복사해 구글독스에 붙여넣고
    다듬는 것을 전제로 한다.
    """
    subject_json = subject_json or {}
    sections = [
        _cover_section(payload),
        _grading_scheme_section(payload),
        _eval_purpose_section(subject_json),
        _eval_direction_section(subject_json),
        _monthly_plan_section(payload),
        _minimum_achievement_section(subject_json),
        _achievement_levels_section(subject_json),
        _ratio_section(payload),
        _performance_items_section(payload),
    ]
    title = f"<h1>{_esc(payload.get('semester'))} {_esc(payload.get('subject'))} 교수학습 및 평가 계획서</h1>"
    return f'<div class="doc-render">{title}{"".join(sections)}</div>'
