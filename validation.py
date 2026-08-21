def validate_plan(
    grade: int,
    credit: int,
    midterm_essay_ratio: float | None,
    midterm_total_ratio: float | None,
    final_essay_ratio: float | None,
    final_total_ratio: float | None,
    performance_items: list[dict],
    grading_method: str,
    split_scores: dict,
) -> list[str]:
    """
    midterm/final의 네 비율 인자는 선택 입력(None 가능) — 폼에서 반영비율을 빈칸으로
    두고 생성할 수 있게 되어(교사가 나중에 hwp에서 직접 채우는 워크플로 지원), 검증
    계산에서는 미입력을 0으로 취급한다.
    """
    warnings: list[str] = []

    midterm_essay_ratio = midterm_essay_ratio or 0
    midterm_total_ratio = midterm_total_ratio or 0
    final_essay_ratio = final_essay_ratio or 0
    final_total_ratio = final_total_ratio or 0

    # 수행평가 반영비율/학점도 미입력(None)이거나 키 자체가 없을 수 있다 -- 예전에는
    # 여기서 TypeError/KeyError 가 나면서 /api/generate 가 통째로 500이 됐고, 프론트엔드는
    # 그 HTML을 response.json()으로 읽다 또 터져 "생성 실패: SyntaxError"만 보였다.
    # 검증 계산에서는 미입력을 0으로 취급한다(경고 문구로 사용자에게 알린다).
    def _ratio_of(item: dict) -> float:
        return item.get("ratio") or 0

    performance_ratio_sum = sum(_ratio_of(item) for item in performance_items)
    essay_ratio_sum = (
        (midterm_total_ratio * midterm_essay_ratio / 100)
        + (final_total_ratio * final_essay_ratio / 100)
        + sum(_ratio_of(item) for item in performance_items if item.get("type") == "서논술형")
    )

    credit = credit or 0
    is_exempt = grade == 3

    if not is_exempt and credit <= 2 and performance_ratio_sum < 20:
        warnings.append(
            f"2학점 이하인 과목은 반드시 [수행평가 총비율]이 20%이상이 되어야 하는데 "
            f"현재 {performance_ratio_sum}%입니다."
        )

    if not is_exempt and credit >= 3 and essay_ratio_sum < 30:
        warnings.append(
            f"3학점 이상인 과목은 반드시 [지필평가의 서논술형+수행평가의 서논술형]이 30%이상이 되어야 하는데 "
            f"현재 {essay_ratio_sum}%입니다."
        )

    if not is_exempt and credit >= 3 and performance_ratio_sum < 40:
        warnings.append(
            f"3단위 이상인 과목은 반드시 [수행평가 총비율]이 40%이상이 되어야 하는데 "
            f"현재 {performance_ratio_sum}%입니다."
        )

    if not grading_method:
        warnings.append("[성취평가 방식]을 입력해 주세요.")

    if performance_ratio_sum != 0:
        required_keys = ("A/B", "B/C", "C/D")
        if any(not split_scores.get(k) for k in required_keys):
            warnings.append("맨 우측부분의 [수행평가 성취기준 점수]를 입력(A/B~C/D)해 주세요.")

    return warnings
