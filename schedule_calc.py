from datetime import date, timedelta


def compute_monthly_sessions(
    year: int,
    semester_start: str,
    semester_end: str,
    excluded_events: list[dict],
    class_weekdays: list[int],
) -> dict[int, dict]:
    start = date.fromisoformat(semester_start)
    end = date.fromisoformat(semester_end)

    excluded_dates = {
        date(year, e["month"], e["day"]) for e in excluded_events
    }

    by_month: dict[int, list[date]] = {}
    current = start
    while current <= end:
        if current.weekday() in class_weekdays and current not in excluded_dates:
            by_month.setdefault(current.month, []).append(current)
        current += timedelta(days=1)

    result: dict[int, dict] = {}
    for month, days in by_month.items():
        week_numbers = sorted({(d.day - 1) // 7 + 1 for d in days})
        if len(week_numbers) == 1:
            weeks_label = f"{week_numbers[0]}주"
        else:
            weeks_label = f"{week_numbers[0]}~{week_numbers[-1]}주"
        result[month] = {"weeks": weeks_label, "sessions": len(days)}

    return result
