import openpyxl
from xlsx_writer import write_xlsx

SAMPLE_DATA = {
    "grade": 1,
    "subject": "공통수학1",
    "credit": 4,
    "writer": "정요한",
    "teachers": "김은상, 장재욱, 정요한",
    "midterm": {"selective": 80, "essay": 10, "short": 10, "ratio": 30},
    "final": {"selective": 80, "essay": 10, "short": 10, "ratio": 30},
    "performance_items": [
        {"type": "서논술형", "title": "단원별 핵심 개념 구조화를 통해 단계별 문제 해결하기", "month": "3~7", "ratio": 15},
        {"type": "서논술형", "title": "수학 과제 탐구를 통한 실생활 문제 수학적으로 표현하기", "month": "4,6", "ratio": 25},
    ],
    "grading_method": "추정분할",
    "split_scores": {"A/B": 39, "B/C": 38, "C/D": 37, "D/E": 36, "E/I": 35},
}


def test_write_xlsx_fills_header_and_ratio_cells(tmp_path):
    output = tmp_path / "out.xlsx"
    write_xlsx(SAMPLE_DATA, str(output))

    wb = openpyxl.load_workbook(output)
    sheet = wb["★계획★(여기에 작성 요망)"]

    assert sheet["A6"].value == 1
    assert sheet["B6"].value == "공통수학1"
    assert sheet["C6"].value == 4
    assert sheet["D6"].value == "정요한"
    assert sheet["E6"].value == "김은상, 장재욱, 정요한"
    assert sheet["F6"].value == 80
    assert sheet["G6"].value == 10
    assert sheet["J6"].value == 30
    assert sheet["Q3"].value == "서논술형"
    assert sheet["Q4"].value == "단원별 핵심 개념 구조화를 통해 단계별 문제 해결하기"
    assert sheet["Q5"].value == "3~7"
    assert sheet["Q6"].value == 15
    assert sheet["R6"].value == 25
    assert sheet["AA6"].value == "추정분할"
    assert sheet["AB6"].value == 39
    assert sheet["AF6"].value == 35


def test_write_xlsx_raises_when_more_than_9_performance_items(tmp_path):
    data = dict(SAMPLE_DATA, performance_items=[{"type": "서논술형", "title": f"항목{i}", "month": "3", "ratio": 1} for i in range(10)])
    output = tmp_path / "out.xlsx"
    try:
        write_xlsx(data, str(output))
        assert False, "should have raised"
    except ValueError as e:
        assert "9" in str(e)
