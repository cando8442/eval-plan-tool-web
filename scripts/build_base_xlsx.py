import openpyxl

SHEET_NAME = "★계획★(여기에 작성 요망)"

# I6, N6, Z6, AG6는 수식이라 건드리지 않음. A9:C14 경고 수식도 그대로 둠.
CELLS_TO_CLEAR = (
    ["A6", "B6", "C6", "D6", "E6", "F6", "G6", "H6", "J6", "K6", "L6", "M6", "O6", "AA6"]
    + [f"AB6"] + [f"AC6"] + [f"AD6"] + [f"AE6"] + [f"AF6"]
)
COLS_Q_TO_Y = ["Q", "R", "S", "T", "U", "V", "W", "X", "Y"]
for row in (3, 4, 5, 6):
    for col in COLS_Q_TO_Y:
        CELLS_TO_CLEAR.append(f"{col}{row}")


def build(source: str, output: str) -> None:
    wb = openpyxl.load_workbook(source)
    sheet = wb[SHEET_NAME]
    for cell in CELLS_TO_CLEAR:
        sheet[cell] = None
    wb.save(output)


if __name__ == "__main__":
    build("templates_src/source_common_math1.xlsx", "templates_src/base_planning_table.xlsx")
