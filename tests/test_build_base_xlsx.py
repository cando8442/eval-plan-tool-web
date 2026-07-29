import openpyxl
from scripts.build_base_xlsx import build


def test_base_xlsx_has_blank_data_cells_but_keeps_formulas(tmp_path):
    output = tmp_path / "base_planning_table.xlsx"
    build(source="templates_src/source_common_math1.xlsx", output=str(output))

    wb = openpyxl.load_workbook(output)
    sheet = wb["★계획★(여기에 작성 요망)"]

    assert sheet["B6"].value is None  # 과목명 비어있어야 함
    assert sheet["Q4"].value is None  # 수행평가 영역명 비어있어야 함
    assert sheet["AA6"].value is None  # 성취평가방식 비어있어야 함
    assert sheet["I6"].value == "=SUM(F6:H6)"  # 합계 수식은 유지
    assert sheet["AG6"].value.startswith("=(J6*G6/100)")  # 검증용 수식 유지
    assert sheet["C10"].value.startswith("=IF(")  # 경고 메시지 수식 유지
