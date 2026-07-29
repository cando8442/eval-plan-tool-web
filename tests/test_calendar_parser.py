import subprocess

import pytest

import calendar_parser
from calendar_parser import parse_calendar

FIXTURE = "tests/fixtures/academic_calendar_2026.hwp"
HWP5PROC = r"C:\Users\cando\AppData\Local\Python\pythoncore-3.14-64\Scripts\hwp5proc.exe"


def test_parse_calendar_finds_march_1_holiday():
    events = parse_calendar(FIXTURE, hwp5proc_path=HWP5PROC)
    march_1 = [e for e in events if e["month"] == 3 and e["day"] == 1]
    assert any(e["label"] == "삼일절" and e["category"] == "HOLIDAY" for e in march_1)


def test_parse_calendar_finds_midterm_exam_period_in_april():
    events = parse_calendar(FIXTURE, hwp5proc_path=HWP5PROC)
    exam_days = sorted(e["day"] for e in events if e["month"] == 4 and e["category"] == "EXAM")
    assert exam_days == [22, 23, 24, 27, 28]


def test_parse_calendar_finds_discretionary_holiday_in_may():
    events = parse_calendar(FIXTURE, hwp5proc_path=HWP5PROC)
    may_no_class = [e for e in events if e["month"] == 5 and e["category"] == "NO_CLASS"]
    assert any(e["day"] == 1 for e in may_no_class)
    assert any(e["day"] == 4 for e in may_no_class)


def test_parse_calendar_raises_when_hwp5proc_fails(monkeypatch):
    """hwp5proc.exe가 실패(nonzero returncode)하면, 빈 이벤트 목록을 조용히 반환하는 대신
    (실제로 공휴일이 없는 것과 구분이 안 되므로) 명확한 예외를 내야 한다."""

    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(args=args, returncode=1, stdout="", stderr="hwp5proc: invalid file")

    monkeypatch.setattr(calendar_parser.subprocess, "run", fake_run)

    with pytest.raises(RuntimeError, match="hwp5proc"):
        parse_calendar(FIXTURE, hwp5proc_path=HWP5PROC)
