import openpyxl

SHEET_NAME = "★계획★(여기에 작성 요망)"
PERFORMANCE_COLS = ["Q", "R", "S", "T", "U", "V", "W", "X", "Y"]
SPLIT_SCORE_COLS = {"A/B": "AB6", "B/C": "AC6", "C/D": "AD6", "D/E": "AE6", "E/I": "AF6"}


def write_xlsx(data: dict, output_path: str, base_path: str = "templates_src/base_planning_table.xlsx") -> None:
    performance_items = data["performance_items"]
    if len(performance_items) > 9:
        raise ValueError("수행평가 항목은 최대 9개까지 지원합니다.")

    wb = openpyxl.load_workbook(base_path)
    sheet = wb[SHEET_NAME]

    sheet["A6"] = data["grade"]
    sheet["B6"] = data["subject"]
    sheet["C6"] = data["credit"]
    sheet["D6"] = data["writer"]
    sheet["E6"] = data["teachers"]

    midterm_cells = {"selective": "F6", "essay": "G6", "short": "H6", "ratio": "J6"}
    for key, cell in midterm_cells.items():
        if data["midterm"].get(key) not in (None, ""):
            sheet[cell] = data["midterm"][key]

    final_cells = {"selective": "K6", "essay": "L6", "short": "M6", "ratio": "O6"}
    for key, cell in final_cells.items():
        if data["final"].get(key) not in (None, ""):
            sheet[cell] = data["final"][key]

    for col, item in zip(PERFORMANCE_COLS, performance_items):
        # 항목을 만들어두고 일부 칸만 채운 채 생성하는 경우가 흔하다 -- 없는 키에
        # KeyError 를 내지 말고 빈 칸으로 남긴다(엑셀에서 직접 채우면 된다).
        sheet[f"{col}3"] = item.get("type")
        sheet[f"{col}4"] = item.get("title")
        sheet[f"{col}5"] = item.get("month")
        sheet[f"{col}6"] = item.get("ratio")

    sheet["AA6"] = data["grading_method"]
    for key, cell in SPLIT_SCORE_COLS.items():
        if key in data["split_scores"]:
            sheet[cell] = data["split_scores"][key]

    wb.save(output_path)
