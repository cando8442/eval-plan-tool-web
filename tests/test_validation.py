from validation import validate_plan


def _base_kwargs(**overrides):
    kwargs = dict(
        grade=1,
        credit=4,
        midterm_essay_ratio=10.0,
        midterm_total_ratio=30.0,
        final_essay_ratio=10.0,
        final_total_ratio=30.0,
        performance_items=[
            {"type": "서논술형", "ratio": 15.0},
            {"type": "서논술형", "ratio": 25.0},
        ],
        grading_method="추정분할",
        split_scores={"A/B": 39, "B/C": 38, "C/D": 37, "D/E": 36, "E/I": 35},
    )
    kwargs.update(overrides)
    return kwargs


def test_valid_plan_returns_no_warnings():
    warnings = validate_plan(**_base_kwargs())
    assert warnings == []


def test_credit_le_2_requires_performance_ratio_20_percent():
    warnings = validate_plan(**_base_kwargs(credit=2, performance_items=[{"type": "서논술형", "ratio": 15.0}]))
    assert any("수행평가 총비율" in w and "20%" in w for w in warnings)


def test_credit_ge_3_requires_essay_ratio_30_percent():
    kwargs = _base_kwargs(credit=3, midterm_essay_ratio=0.0, final_essay_ratio=0.0,
                           performance_items=[{"type": "실험실습", "ratio": 40.0}])
    warnings = validate_plan(**kwargs)
    assert any("서논술형" in w and "30%" in w for w in warnings)


def test_credit_ge_3_requires_performance_ratio_40_percent():
    kwargs = _base_kwargs(credit=3, performance_items=[{"type": "서논술형", "ratio": 30.0}])
    warnings = validate_plan(**kwargs)
    assert any("수행평가 총비율" in w and "40%" in w for w in warnings)


def test_grade_3_is_exempt_from_all_ratio_checks():
    kwargs = _base_kwargs(grade=3, credit=2, performance_items=[])
    warnings = validate_plan(**kwargs)
    assert warnings == []


def test_missing_grading_method_warns():
    warnings = validate_plan(**_base_kwargs(grading_method=""))
    assert any("성취평가 방식" in w for w in warnings)


def test_missing_split_score_warns_when_performance_ratio_nonzero():
    warnings = validate_plan(**_base_kwargs(split_scores={"A/B": 39}))
    assert any("수행평가 성취기준 점수" in w for w in warnings)


def test_no_split_score_warning_when_performance_ratio_zero():
    warnings = validate_plan(**_base_kwargs(performance_items=[], split_scores={}))
    assert not any("수행평가 성취기준 점수" in w for w in warnings)


def test_grade_3_is_exempt_from_credit_3_ratio_checks():
    """Regression test: grade 3 must exempt from C11 and C12 (credit >= 3 checks).

    Uses credit=3 with low essay/performance ratios that would normally trigger
    C11 (essay_ratio_sum < 30) and C12 (performance_ratio_sum < 40) warnings.
    The grade=3 exemption should suppress both.
    """
    kwargs = _base_kwargs(
        grade=3,
        credit=3,
        midterm_essay_ratio=0.0,
        final_essay_ratio=0.0,
        performance_items=[{"type": "실험실습", "ratio": 20.0}],  # Only 20%, below 30% essay and 40% performance
    )
    warnings = validate_plan(**kwargs)
    assert warnings == []


def test_split_scores_only_requires_abc_not_de():
    """Regression test: split_scores checks only require A/B, B/C, C/D (not D/E or E/I).

    D/E and E/I are deliberately not checked in the original Excel formula.
    This test protects against someone "fixing" this later by mistake.
    """
    kwargs = _base_kwargs(
        split_scores={"A/B": 39, "B/C": 38, "C/D": 37}  # D/E and E/I omitted
    )
    warnings = validate_plan(**kwargs)
    assert not any("수행평가 성취기준 점수" in w for w in warnings)
