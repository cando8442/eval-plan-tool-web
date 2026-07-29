import re
import subprocess

CATEGORY_KEYWORDS = {
    "EXAM": ["중간고사", "기말고사"],
    "NO_CLASS": ["재량휴업일", "방학식", "개학", "시업식", "종업식"],
    "HOLIDAY": ["대체공휴일", "삼일절", "어린이날", "현충일", "광복절", "개천절", "한글날", "추석", "설날", "부처님"],
}

MONTH_HEADER_RE = re.compile(r"^\d{1,2}$")
DAY_NUMBER_RE = re.compile(r"^\d{1,2}$")


def _classify(label: str) -> str:
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(keyword in label for keyword in keywords):
            return category
    return "NOTE"


def _extract_texts(hwp_path: str, hwp5proc_path: str) -> list[str]:
    result = subprocess.run(
        [hwp5proc_path, "xml", hwp_path],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if result.returncode != 0:
        stderr_summary = (result.stderr or "").strip() or "(no stderr output)"
        raise RuntimeError(
            f"hwp5proc.exe failed (exit code {result.returncode}) while parsing "
            f"calendar file '{hwp_path}'. This means the calendar could NOT be read "
            "-- an empty event list here would silently look like 'no holidays' "
            f"instead of a real failure. hwp5proc stderr: {stderr_summary}"
        )
    return re.findall(r"<Text[^>]*>(.*?)</Text>", result.stdout, re.S)


def parse_calendar(hwp_path: str, hwp5proc_path: str = os.environ.get("HWP5PROC_PATH", "hwp5proc")) -> list[dict]:
    import html

    texts = [html.unescape(t) for t in _extract_texts(hwp_path, hwp5proc_path)]
    stripped_texts = [t.strip() for t in texts]
    events: list[dict] = []

    current_month = None
    current_day = None
    pending_label_parts: list[str] = []
    last_day_seen = 0

    def flush_label():
        nonlocal pending_label_parts
        if current_month is not None and current_day is not None and pending_label_parts:
            label = "".join(pending_label_parts).strip()
            if label:
                events.append({
                    "month": current_month,
                    "day": current_day,
                    "label": label,
                    "category": _classify(label),
                })
        pending_label_parts = []

    i = 0
    n = len(stripped_texts)
    while i < n:
        stripped = stripped_texts[i]

        if MONTH_HEADER_RE.match(stripped) and 1 <= int(stripped) <= 12:
            # 월 헤더 후보(1~12 숫자만 있는 토큰)는 바로 뒤에 등교일수 "(N)"
            # 표기가 붙어있을 때만 확정한다. 그냥 1~12일자를 가리키는 숫자와
            # 겹치므로(예: 4월 중 "4"), 다음 토큰이 "("로 시작하는지로 구분한다.
            next_token = stripped_texts[i + 1] if i + 1 < n else ""
            if next_token.startswith("("):
                flush_label()
                current_month = int(stripped)
                current_day = None
                last_day_seen = 0
                # 등교일수 표기는 한 토큰("(21)")일 수도 있고, 줄바꿈으로 인해
                # 여러 토큰("(19/", "20)")으로 쪼개질 수도 있다 — ")"가 나올
                # 때까지 건너뛴다.
                j = i + 1
                while j < n and ")" not in stripped_texts[j]:
                    j += 1
                i = j + 1
                continue

        if DAY_NUMBER_RE.match(stripped) and current_month is not None:
            day_value = int(stripped)
            # 일자는 월 안에서 항상 증가(1일부터 말일까지, 최대 31)한다 —
            # 감소하거나 31을 넘으면 새 일자가 아니라 본문/여백 속 숫자(예:
            # "~13)", 학기 전환 여백의 "수업일수 95일" 등)로 간주한다.
            if last_day_seen < day_value <= 31:
                flush_label()
                current_day = day_value
                last_day_seen = day_value
                i += 1
                continue

        if current_month is not None and current_day is not None:
            pending_label_parts.append(stripped)

        i += 1

    flush_label()
    return events
