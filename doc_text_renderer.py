import html

DEFAULT_ABSENTEE_POLICY = (
    "◦ 미응시, 미제출한 경우 [기본점수-1점]을 부여한다.\n"
    "◦ 평가 당일 개인적인 사유로 인한 결석이나 공결, 전입 등으로 인하여 결과물을 제출하지 못했을 경우 "
    "수행평가 기회를 1회 부여한다. 이때 부여되는 수행평가에 불참할 경우 [기본점수-1점]을 부여한다.\n"
    "◦ 전입생의 전입교 수행평가 점수 반영 여부는 동교과 교사들 간의 협의를 통해 진행한다.\n"
    "◦ 특수학생인 경우, 학업성적관리규정에 의거하여 특수학생의 특수성과 상황에 따른 합리적인 배려를 제공하며, "
    "그 예는 아래와 같다.\n"
    " * 학생의 특수성으로 인해 추가적인 시간이 필요하다고 판단되거나 학생이 요청할 경우, 평가 시간을 최대 1.5배 부여한다.\n"
    " * 학생이 특수성에 구애받지 않고 신체적, 심리적으로 안정된 상태에서 평가에 임할 수 있도록 특수교사와의 협의 또는 "
    "필요에 따라 학교 내 별도의 환경을 제공한다."
)

DEFAULT_PLAGIARISM_POLICY = (
    "학업성적관리규정 제16조 3항('수행평가를 할 때 표절 행위가 발생하지 않도록 사전 교육을 충분히 실시하고, "
    "처리기준은 교과별 평가 계획에 명시한다.')에 의거하여, 표절 행위가 발생한 경우 [기본점수-1점]을 부여한다."
)


def _esc(value) -> str:
    return html.escape(str(value)) if value not in (None, "") else ""


def _esc_multiline(value) -> str:
    """줄바꿈을 <br>로 바꿔 렌더한다.

    성취기준/수업방법/평가방법처럼 프론트엔드가 **배열**로 보내는 값도 그대로
    들어온다 -- 예전에는 str(list)가 그대로 이스케이프돼 문서에
    "['[10공수1-01-01] ...', '...']" 같은 파이썬 repr 이 찍혔다. 배열은 항목마다
    한 줄로 펼친다.
    """
    if isinstance(value, (list, tuple)):
        return "<br>".join(_esc(v) for v in value if v not in (None, ""))
    return _esc(value).replace("\n", "<br>")


def _section(title: str, body_html: str) -> str:
    return f'<section class="doc-section"><h2>{_esc(title)}</h2>{body_html}</section>'


def _esc_ml(value) -> str:
    """성취수준처럼 원문 문단이 여러 줄인 값을 표 칸에 넣을 때 쓴다 — 이스케이프한 뒤
    개행을 <br>로 바꿔, 고시 원문의 문단 구분이 표 안에서 사라지지 않게 한다."""
    return _esc(value).replace(chr(10), "<br>")


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


def _monthly_plan_section(payload: dict) -> str:
    rows = [row for row in payload.get("units_by_month") or [] if row.get("month")]
    if not rows:
        return _section("1. 교수학습 운영 계획", "<p>(입력된 월별 계획이 없습니다)</p>")
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
        "1. 교수학습 운영 계획",
        f"<table class='doc-table'><thead>{header}</thead><tbody>{body_rows}</tbody></table>",
    )


def _minimum_achievement_block(subject_json: dict) -> str:
    """"나. 최소 성취수준 진술문" -- _eval_operation_section 안에 h4로 들어간다."""
    overall = subject_json.get("minimum_achievement_overall")
    items = subject_json.get("minimum_achievement") or []
    if not overall and not items:
        body = "<p>(콘텐츠 라이브러리에 없는 과목입니다)</p>"
    else:
        parts = [f"<p>{_esc(overall)}</p>"] if overall else []
        trait_labels = [("지식·이해", "지식이해"), ("과정·기능", "과정기능"), ("가치·태도", "가치태도")]
        for item in items:
            traits = item.get("최소능력수행특성") or {}
            # 범주별 최소 능력 수행 특성은 영역별 성취수준이 있는 과목에만 존재한다.
            trait_table = ""
            if traits:
                trait_rows = "".join(
                    f"<tr><th>{label}</th><td>{_esc_ml(traits.get(key))}</td></tr>"
                    for label, key in trait_labels
                )
                trait_table = f"<table class='doc-table'><tbody>{trait_rows}</tbody></table>"
            parts.append(
                f"<h5>{_esc(item.get('영역'))}</h5>"
                f"{_list(item.get('성취기준별성취수준E'))}"
                f"{trait_table}"
            )
        body = "".join(parts)
    return f"<h4>나. 최소 성취수준 진술문</h4>{body}"


def _achievement_levels_block(subject_json: dict) -> str:
    """"가. 학기 단위 성취수준" -- _eval_operation_section 안에 h4로 들어간다."""
    levels = subject_json.get("achievement_levels") or {}
    if not levels:
        body = "<p>(콘텐츠 라이브러리에 없는 과목입니다)</p>"
    else:
        grades = ["A", "B", "C", "D", "E"]
        header = "<tr><th>구분</th>" + "".join(f"<th>{g}</th>" for g in grades) + "</tr>"
        trait_labels = [("지식·이해", "지식이해"), ("과정·기능", "과정기능"), ("가치·태도", "가치태도")]
        # 성취수준 문서에 '영역별 성취수준' 절이 없는 과목(국어과 선택과목 등)은
        # 범주(지식·이해/과정·기능/가치·태도) 구분이 원문에 없다. 그런 과목은
        # 등급별 진술을 한 줄짜리 표로 그린다.
        if any(isinstance(v, str) for v in levels.values()):
            body_rows = (
                "<tr><th>성취수준</th>"
                + "".join(f"<td>{_esc_ml(levels.get(g))}</td>" for g in grades)
                + "</tr>"
            )
        else:
            body_rows = "".join(
                "<tr>"
                + f"<th>{label}</th>"
                + "".join(f"<td>{_esc_ml((levels.get(g) or {}).get(key))}</td>" for g in grades)
                + "</tr>"
                for label, key in trait_labels
            )
        body = f"<table class='doc-table'><thead>{header}</thead><tbody>{body_rows}</tbody></table>"
    return f"<h4>가. 학기 단위 성취수준</h4>{body}"


def _eval_operation_section(subject_json: dict) -> str:
    """"2. 평가 운영 계획" -- 평가목적/방향/성취평가제 적용을 실제 문서 번호 체계
    (1./2./3., 3. 안에 가./나.)로 묶는다. 원본 hwp 예시(templates_src/source_common_math1.hwp)를
    hwp5proc로 직접 추출해 확인한 제목·번호 그대로다."""
    body = (
        f"<h3>1. 평가 목적</h3>{_list(subject_json.get('eval_purpose'))}"
        f"<h3>2. 평가 방향 및 방침</h3>{_list(subject_json.get('eval_direction'))}"
        f"<h3>3. 성취평가제 적용</h3>"
        f"{_achievement_levels_block(subject_json)}"
        f"{_minimum_achievement_block(subject_json)}"
    )
    return _section("2. 평가 운영 계획", body)


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

    return _section("4. 평가 영역 및 반영 비율", table + method_html)


def _split_scores_section(payload: dict) -> str:
    """"6. 수행평가 성취 수준" -- 문서 맨 아래, 추정분할 과목만 있는 섹션(실제
    성취수준별 분할점수표). 원본 hwp 안내문구: "고정분할 과목은 기재하지 마시고
    6번 항목 자체를 삭제해주세요" -- 그래서 고정분할이거나 값이 없으면 섹션
    자체를 아예 비운다(빈 제목만 남기지 않음)."""
    split_scores = payload.get("split_scores") or {}
    if payload.get("grading_method") != "추정분할" or not split_scores:
        return ""
    header = "<tr><th>성취수준</th>" + "".join(f"<th>{_esc(k)}</th>" for k in split_scores) + "</tr>"
    vals = "<tr><th>성취수준별 분할점수</th>" + "".join(f"<td>{_esc(v)}</td>" for v in split_scores.values()) + "</tr>"
    table = f"<table class='doc-table'><thead>{header}</thead><tbody>{vals}</tbody></table>"
    return _section("6. 수행평가 성취 수준", table)


def _performance_items_section(payload: dict, subject_json: dict) -> str:
    items = payload.get("performance_items") or []
    if not items:
        return _section("5. 수행평가 세부 계획", "<p>(입력된 수행평가 항목이 없습니다)</p>")

    library_items = subject_json.get("performance_task_examples") or []

    parts = []
    for idx, item in enumerate(items):
        lib = library_items[idx] if idx < len(library_items) else {}
        base_score = item.get("base_score")
        if base_score is None:
            base_score = lib.get("base_score")
        task = item.get("task") or lib.get("task")
        curriculum_area = item.get("curriculum_area") or lib.get("curriculum_area")
        absentee_policy = lib.get("absentee_policy") or DEFAULT_ABSENTEE_POLICY
        plagiarism_policy = lib.get("plagiarism_policy") or DEFAULT_PLAGIARISM_POLICY

        info_rows = [
            ("유형", item.get("type")),
            (
                "반영비율 / 배점 / 기본점수",
                f"{item.get('ratio', '')}% / {item.get('score', '')}점 / "
                f"{base_score if base_score is not None else '(미입력)'}",
            ),
            ("적용 시기(월)", item.get("month")),
            ("교육과정 영역", curriculum_area),
            ("평가 과제", task),
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
            f"<h3>({idx + 1}) {_esc(item.get('title') or '(제목 미입력)')}</h3>"
            f"{info_table}"
            f"<h4>성취기준</h4>{_list(item.get('standards'))}"
            f"<h4>결시자 및 학적변동자·특수학생 평가방법</h4><p>{_esc_multiline(absentee_policy)}</p>"
            f"<h4>표절 행위 발생 시 처리기준</h4><p>{_esc_multiline(plagiarism_policy)}</p>"
            f"<h4>채점기준표</h4>{rubric_html}"
        )
    return _section("5. 수행평가 세부 계획", "".join(parts))


def render_plan_html(payload: dict, subject_json: dict | None) -> str:
    """평가계획서 hwp에 들어가던 내용을 구글독스 붙여넣기용 HTML로 렌더링한다.

    hwp COM 자동화(pyhwpx)를 대체하는 경로 -- 표/문단 구조는 유지하되 원본 hwp
    서식과 동일하지는 않다. 사용자가 이 결과를 그대로 복사해 구글독스에 붙여넣고
    다듬는 것을 전제로 한다. 섹션 제목/번호(1. 교수학습 운영 계획, 2. 평가 운영
    계획[1./2./3., 3.의 가./나.], 4. 평가 영역 및 반영 비율, 5. 수행평가 세부
    계획)는 실제 제출 서식(templates_src/source_common_math1.hwp)에서 그대로
    가져왔다.
    """
    subject_json = subject_json or {}
    sections = [
        _cover_section(payload),
        _grading_scheme_section(payload),
        _monthly_plan_section(payload),
        _eval_operation_section(subject_json),
        _ratio_section(payload),
        _performance_items_section(payload, subject_json),
        _split_scores_section(payload),
    ]
    title = f"<h1>{_esc(payload.get('semester'))} {_esc(payload.get('subject'))} 교수학습 및 평가 계획서</h1>"
    return f'<div class="doc-render">{title}{"".join(sections)}</div>'
