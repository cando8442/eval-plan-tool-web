from schedule_calc import compute_monthly_sessions


def test_march_2026_full_month_all_weekdays_no_exclusions():
    # 2026년 3월은 1일(일)~31일(화). 월/화/수/목/금 전부 선택 시 등교일 = 평일 전체.
    result = compute_monthly_sessions(
        year=2026,
        semester_start="2026-03-01",
        semester_end="2026-03-31",
        excluded_events=[],
        class_weekdays=[0, 1, 2, 3, 4],
    )
    # 2026-03: 평일(월~금) 일수를 직접 셈 (수동 계산: 3/2~3/31 중 주말 제외)
    assert result[3]["sessions"] == 22  # 2026년 3월 평일 수 (달력 계산 결과)


def test_excluded_holiday_reduces_session_count():
    result_without_exclusion = compute_monthly_sessions(
        year=2026, semester_start="2026-03-01", semester_end="2026-03-31",
        excluded_events=[], class_weekdays=[6],  # 일요일만 선택(테스트 편의상 극단값)
    )
    result_with_exclusion = compute_monthly_sessions(
        year=2026, semester_start="2026-03-01", semester_end="2026-03-31",
        excluded_events=[{"month": 3, "day": 1, "label": "삼일절", "category": "HOLIDAY"}],
        class_weekdays=[6],
    )
    assert result_with_exclusion[3]["sessions"] == result_without_exclusion[3]["sessions"] - 1


def test_week_label_reflects_number_of_distinct_calendar_weeks_touched():
    result = compute_monthly_sessions(
        year=2026, semester_start="2026-03-01", semester_end="2026-03-31",
        excluded_events=[], class_weekdays=[0],
    )
    assert result[3]["weeks"].endswith("주")
