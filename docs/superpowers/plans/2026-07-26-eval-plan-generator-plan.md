# 평가계획서 자동 생성 도구 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 로컬 Flask 웹앱에서 교사가 폼을 채우면, 실제 한글(.hwp) 파일과 엑셀(.xlsx) 평가계획서를 동시에 생성한다. 학사일정 hwp를 업로드하면 월별 수업 주·차시도 자동 계산해 폼에 채워준다.

**Architecture:** Flask 로컬 서버(`app.py`) + 콘텐츠 라이브러리(과목별 JSON) + 토큰치환 방식 hwp 생성(pyhwpx `find_replace_all`) + openpyxl xlsx 생성 + hwp5proc 기반 학사일정 파서. 상세 배경은 `docs/superpowers/specs/2026-07-26-eval-plan-generator-design.md` 참고.

**Tech Stack:** Python 3.14, Flask, openpyxl, pyhwpx(+pywin32, Windows 전용), pytest. hwp 텍스트 검증용 CLI: `hwp5proc`(pyhwp 패키지, `pip install pyhwp`로 설치됨 — 이미 이 PC의 `C:\Users\cando\AppData\Local\Python\pythoncore-3.14-64\Scripts\hwp5proc.exe`에 존재).

## Global Constraints

- 이 도구는 **한글 프로그램이 설치·실행 가능한 Windows PC에서만** 동작한다 (pyhwpx가 `HWPFrame.HwpObject` COM 객체를 통해 실제 한글을 조작하기 때문).
- 결과물(.hwp, .xlsx)은 `C:\Users\cando\평가계획서_출력\`에만 저장한다. Drive 자동 업로드는 하지 않는다.
- MVP 범위: 2022개정 수학교과군, 수행평가 항목 최대 4개, 콘텐츠 라이브러리는 공통수학1부터 시작(다른 과목은 이후 같은 JSON 스키마로 추가).
- 모든 자동 생성 값(월별 단원 분배, 분할점수 예시, 학사일정 파싱 결과)은 **교사가 검토·수정 가능한 초안**이지 확정값이 아니다 — UI 문구에서 "자동" 대신 "참고 초안"으로 표현한다.
- pyhwp의 `hwp5txt`는 표 셀 내용을 추출하지 못한다. hwp 표 내용 검증에는 반드시 `hwp5proc xml` + 정규식으로 `<Text>` 요소를 뽑아 확인할 것.

---

### Task 1: 프로젝트 스캐폴딩

**Files:**
- Create: `requirements.txt`
- Create: `.gitignore`
- Create: `app.py`
- Test: `tests/test_app.py`

**Interfaces:**
- Produces: Flask app 객체 `app` (`app.py`에서 `from flask import Flask; app = Flask(__name__)`), 이후 모든 task가 여기에 라우트를 추가함

- [ ] **Step 1: requirements.txt 작성**

```
flask==3.1.0
openpyxl==3.1.5
pyhwpx==1.7.2
pywin32==312
pytest==8.3.3
```

- [ ] **Step 2: .gitignore 작성**

```
__pycache__/
*.pyc
.venv/
평가계획서_출력/
*.egg-info/
```

- [ ] **Step 3: 가상환경 생성 및 설치**

Run: `cd C:\Users\cando\eval_plan_tool && python -m venv .venv && .venv\Scripts\pip install -r requirements.txt`

- [ ] **Step 4: app.py에 헬스체크 라우트 작성**

```python
from flask import Flask

app = Flask(__name__)


@app.get("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    app.run(debug=True, port=5000)
```

- [ ] **Step 5: 실패하는 테스트 작성**

```python
# tests/test_app.py
from app import app


def test_health_endpoint():
    client = app.test_client()
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok"}
```

- [ ] **Step 6: 테스트 실행해 통과 확인**

Run: `.venv\Scripts\pytest tests/test_app.py -v`
Expected: PASS (Step 4에서 이미 구현했으므로 바로 통과 — 이 프로젝트는 인프라 태스크라 실패 확인 단계를 생략함)

- [ ] **Step 7: 커밋**

```bash
git add requirements.txt .gitignore app.py tests/test_app.py
git commit -m "Scaffold Flask app with health check route"
```

---

### Task 2: 콘텐츠 라이브러리 로더 (`content_library.py`)

**Files:**
- Create: `content_library.py`
- Test: `tests/test_content_library.py`
- Test fixture: `tests/fixtures/subjects/2022/테스트과목/테스트과목.json`

**Interfaces:**
- Consumes: 없음 (순수 파일 시스템 접근)
- Produces: `load_subject(revision: str, category: str, subject: str, base_dir: str = "subjects") -> dict | None` — JSON 파일이 있으면 dict, 없으면 `None` 리턴 (예외를 던지지 않음 — 폼에서 "라이브러리 없음, 직접 입력" 분기로 쓰기 위함)

- [ ] **Step 1: 테스트 픽스처 작성**

```bash
mkdir -p tests/fixtures/subjects/2022/테스트과목
```

```json
// tests/fixtures/subjects/2022/테스트과목/테스트과목.json
{
  "subject": "테스트과목",
  "revision": "2022",
  "track": "공통과목",
  "eval_purpose": ["가. 테스트 목적"],
  "eval_direction": ["가. 테스트 방향"]
}
```

- [ ] **Step 2: 실패하는 테스트 작성**

```python
# tests/test_content_library.py
from content_library import load_subject


def test_load_existing_subject_returns_dict():
    result = load_subject("2022", "테스트과목", "테스트과목", base_dir="tests/fixtures/subjects")
    assert result is not None
    assert result["subject"] == "테스트과목"
    assert result["eval_purpose"] == ["가. 테스트 목적"]


def test_load_missing_subject_returns_none():
    result = load_subject("2022", "테스트과목", "존재안함", base_dir="tests/fixtures/subjects")
    assert result is None
```

- [ ] **Step 3: 테스트 실행해 실패 확인**

Run: `.venv\Scripts\pytest tests/test_content_library.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'content_library'`

- [ ] **Step 4: content_library.py 구현**

```python
import json
import os
from typing import Optional


def load_subject(revision: str, category: str, subject: str, base_dir: str = "subjects") -> Optional[dict]:
    path = os.path.join(base_dir, revision, category, f"{subject}.json")
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)
```

- [ ] **Step 5: 테스트 실행해 통과 확인**

Run: `.venv\Scripts\pytest tests/test_content_library.py -v`
Expected: PASS (2 passed)

- [ ] **Step 6: 커밋**

```bash
git add content_library.py tests/test_content_library.py tests/fixtures/subjects
git commit -m "Add content library loader for subject JSON files"
```

---

### Task 3: 검증 로직 (`validation.py`) — 원본 엑셀 IF수식 재현

**Files:**
- Create: `validation.py`
- Test: `tests/test_validation.py`

**Interfaces:**
- Consumes: 없음
- Produces: `validate_plan(grade: int, credit: int, midterm_essay_ratio: float, midterm_total_ratio: float, final_essay_ratio: float, final_total_ratio: float, performance_items: list[dict], grading_method: str, split_scores: dict) -> list[str]`
  - `performance_items`: `[{"type": "서논술형", "ratio": 15.0}, ...]` (`type`은 원본 표의 "유형선택" 값, `ratio`는 "학기말반영비율(%)")
  - `split_scores`: `{"A/B": 39, "B/C": 38, "C/D": 37, "D/E": 36, "E/I": 35}` 처럼 있는 것만 키로 넣은 dict (없는 등급은 키 자체가 없음)
  - 반환값: 경고 메시지 문자열 리스트 (원본 엑셀 A9~C14 영역의 4개 검증 메시지와 1:1 대응, 문제 없으면 빈 리스트)

원본 수식 근거 (`templates_src/source_common_math1.xlsx`의 `★계획★(여기에 작성 요망)` 시트 C10~C14, `$A$6`=학년, `$C$6`=학점수, `$Z$6`=수행평가 반영비율 합, `$AG$6`=서논술형(정기+수행) 반영비율 합):
- C10: `학년<>3 AND 학점<=2 AND Z6<20` → 수행평가 총비율 20% 미만 경고
- C11: `학년<>3 AND 학점>=3 AND AG6<30` → 서논술형(정기+수행) 30% 미만 경고
- C12: `학년<>3 AND 학점>=3 AND Z6<40` → 수행평가 총비율 40% 미만 경고
- C13: `성취평가방식(grading_method) 미입력` 경고
- C14: `Z6<>0 AND (A/B, B/C, C/D 중 하나라도 없음)` → 분할점수 미입력 경고 (D/E, E/I는 원본 수식에서도 검사 대상이 아님 — 그대로 재현)

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/test_validation.py
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
```

- [ ] **Step 2: 테스트 실행해 실패 확인**

Run: `.venv\Scripts\pytest tests/test_validation.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'validation'`

- [ ] **Step 3: validation.py 구현**

```python
def validate_plan(
    grade: int,
    credit: int,
    midterm_essay_ratio: float,
    midterm_total_ratio: float,
    final_essay_ratio: float,
    final_total_ratio: float,
    performance_items: list[dict],
    grading_method: str,
    split_scores: dict,
) -> list[str]:
    warnings: list[str] = []

    performance_ratio_sum = sum(item["ratio"] for item in performance_items)
    essay_ratio_sum = (
        (midterm_total_ratio * midterm_essay_ratio / 100)
        + (final_total_ratio * final_essay_ratio / 100)
        + sum(item["ratio"] for item in performance_items if item["type"] == "서논술형")
    )

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
```

- [ ] **Step 4: 테스트 실행해 통과 확인**

Run: `.venv\Scripts\pytest tests/test_validation.py -v`
Expected: PASS (8 passed)

- [ ] **Step 5: 커밋**

```bash
git add validation.py tests/test_validation.py
git commit -m "Add validation module replicating the original xlsx IF-formula rules"
```

---

### Task 4: 베이스 xlsx 템플릿 빌드 스크립트

**Files:**
- Create: `scripts/build_base_xlsx.py`
- Test: `tests/test_build_base_xlsx.py`

**Interfaces:**
- Consumes: `templates_src/source_common_math1.xlsx` (이미 프로젝트에 있음, 실제 제출된 예시 파일)
- Produces: `templates_src/base_planning_table.xlsx` — `★계획★(여기에 작성 요망)` 시트의 데이터 셀(A6:E6, F6:H6, J6, K6:M6, O6, Q3:Y6, AA6:AF6)만 비우고 나머지(라벨, I6/N6/Z6/AG6 수식, A9:C14 검증 수식, 다른 시트)는 그대로 유지한 파일

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/test_build_base_xlsx.py
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
```

- [ ] **Step 2: 테스트 실행해 실패 확인**

Run: `.venv\Scripts\pytest tests/test_build_base_xlsx.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.build_base_xlsx'`

- [ ] **Step 3: `scripts/__init__.py` 빈 파일 생성 후 build_base_xlsx.py 구현**

```bash
mkdir -p scripts && touch scripts/__init__.py
```

```python
# scripts/build_base_xlsx.py
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
```

- [ ] **Step 4: 테스트 실행해 통과 확인**

Run: `.venv\Scripts\pytest tests/test_build_base_xlsx.py -v`
Expected: PASS

- [ ] **Step 5: 실제로 base_planning_table.xlsx 생성해서 커밋할 산출물로 확보**

Run: `.venv\Scripts\python scripts/build_base_xlsx.py`
Expected: `templates_src/base_planning_table.xlsx` 생성됨

- [ ] **Step 6: 커밋**

```bash
git add scripts/__init__.py scripts/build_base_xlsx.py tests/test_build_base_xlsx.py templates_src/base_planning_table.xlsx
git commit -m "Add build script that blanks the xlsx template's data cells"
```

---

### Task 5: xlsx_writer.py

**Files:**
- Create: `xlsx_writer.py`
- Test: `tests/test_xlsx_writer.py`

**Interfaces:**
- Consumes: `templates_src/base_planning_table.xlsx` (Task 4 산출물)
- Produces: `write_xlsx(data: dict, output_path: str, base_path: str = "templates_src/base_planning_table.xlsx") -> None`
  - `data` 스키마: `{"grade": 1, "subject": "공통수학1", "credit": 4, "writer": "정요한", "teachers": "김은상, 장재욱, 정요한", "midterm": {"selective": 80, "essay": 10, "short": 10, "ratio": 30}, "final": {"selective": 80, "essay": 10, "short": 10, "ratio": 30}, "performance_items": [{"type": "서논술형", "title": "...", "month": "3~7", "ratio": 15}, ...], "grading_method": "추정분할", "split_scores": {"A/B": 39, "B/C": 38, "C/D": 37, "D/E": 36, "E/I": 35}}`
  - `data["writer"]`는 Task 6 설계 노트에서 언급한, hwp에는 없고 xlsx에만 있는 "작성자" 필드

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/test_xlsx_writer.py
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
```

- [ ] **Step 2: 테스트 실행해 실패 확인**

Run: `.venv\Scripts\pytest tests/test_xlsx_writer.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'xlsx_writer'`

- [ ] **Step 3: xlsx_writer.py 구현**

```python
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

    sheet["F6"] = data["midterm"]["selective"]
    sheet["G6"] = data["midterm"]["essay"]
    sheet["H6"] = data["midterm"]["short"]
    sheet["J6"] = data["midterm"]["ratio"]

    sheet["K6"] = data["final"]["selective"]
    sheet["L6"] = data["final"]["essay"]
    sheet["M6"] = data["final"]["short"]
    sheet["O6"] = data["final"]["ratio"]

    for col, item in zip(PERFORMANCE_COLS, performance_items):
        sheet[f"{col}3"] = item["type"]
        sheet[f"{col}4"] = item["title"]
        sheet[f"{col}5"] = item["month"]
        sheet[f"{col}6"] = item["ratio"]

    sheet["AA6"] = data["grading_method"]
    for key, cell in SPLIT_SCORE_COLS.items():
        if key in data["split_scores"]:
            sheet[cell] = data["split_scores"][key]

    wb.save(output_path)
```

- [ ] **Step 4: 테스트 실행해 통과 확인**

Run: `.venv\Scripts\pytest tests/test_xlsx_writer.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: 커밋**

```bash
git add xlsx_writer.py tests/test_xlsx_writer.py
git commit -m "Add xlsx_writer that fills the planning table from form data"
```

---

### Task 6: 베이스 hwp 토큰 템플릿 빌드 스크립트

**Files:**
- Create: `scripts/build_base_hwp.py`
- Test: `tests/test_build_base_hwp.py` (실제 한글 프로그램 필요 — Windows+한글 설치 환경에서만 실행)

**Interfaces:**
- Consumes: `templates_src/source_common_math1.hwp` (실제 예시 파일, 원문은 이번 세션에서 `hwp5proc xml`로 이미 전량 확인함)
- Produces: `templates_src/base.hwp` — 아래 원문 텍스트가 전부 `{{TOKEN}}`으로 치환된 파일. 이 스크립트는 pyhwpx의 `find_replace_all(원문, 토큰)`만 반복 호출 — 표 셀 좌표 탐색은 전혀 쓰지 않음(2026-07-26 스파이크로 이 방식이 표 안 텍스트에도 동작함을 검증함).

이 스크립트가 정의하는 `TOKEN_MAP`(원문 → 토큰)이 이후 Task 7의 `hwp_writer.py`가 값을 채워 넣는 유일한 계약이다. 헤더 필드용 토큰과, `subjects/2022/수학/공통수학1.json`의 실제 값을 원문으로 삼은 콘텐츠 토큰으로 나뉜다.

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/test_build_base_hwp.py
"""
이 테스트는 실제 한글 프로그램(HWPFrame.HwpObject COM)이 설치된 Windows에서만 통과한다.
CI에서는 스킵하고, 로컬에서 수동으로 1회 실행해 templates_src/base.hwp를 만든 뒤 커밋한다.
"""
import re
import subprocess
import sys

from scripts.build_base_hwp import build

HWP5PROC = r"C:\Users\cando\AppData\Local\Python\pythoncore-3.14-64\Scripts\hwp5proc.exe"


def _extract_texts(hwp_path: str) -> list[str]:
    xml = subprocess.run([HWP5PROC, "xml", hwp_path], capture_output=True, text=True, encoding="utf-8").stdout
    return re.findall(r"<Text[^>]*>(.*?)</Text>", xml, re.S)


def test_build_base_hwp_replaces_teacher_name_with_token(tmp_path):
    output = tmp_path / "base.hwp"
    build(source="templates_src/source_common_math1.hwp", output=str(output))

    texts = _extract_texts(str(output))
    joined = " ".join(texts)
    assert "{{TEACHERS}}" in joined
    assert "김은상, 장재욱, 정요한" not in joined


def test_build_base_hwp_replaces_subject_name_with_token(tmp_path):
    output = tmp_path / "base.hwp"
    build(source="templates_src/source_common_math1.hwp", output=str(output))

    texts = _extract_texts(str(output))
    joined = " ".join(texts)
    assert "{{SUBJECT}}" in joined
```

- [ ] **Step 2: 테스트 실행해 실패 확인**

Run: `.venv\Scripts\pytest tests/test_build_base_hwp.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.build_base_hwp'`

- [ ] **Step 3: build_base_hwp.py 구현**

```python
# scripts/build_base_hwp.py
from pyhwpx import Hwp

# 원문(2026 실제 제출본, 공통수학1)과 토큰의 매핑.
# 순서 중요: 더 긴/더 구체적인 문자열을 먼저 치환해야 짧은 문자열이 먼저 걸려 깨지는 걸 방지함.
TOKEN_MAP: list[tuple[str, str]] = [
    # 헤더
    ("김은상, 장재욱, 정요한", "{{TEACHERS}}"),
    ("공통수학1", "{{SUBJECT}}"),
    # 평가 목적/방향 (문단, 표 밖 본문)
    (
        "가. 학생의 변화와 성장에 대한 자료를 다각도로 수집하여 적절한 피드백을 제공한다.\n"
        "나. 학생의 성취기준 도달 정도를 파악하고 성취수준을 점검한다.\n"
        "다. 다양한 유형의 평가를 활용하여 학습 목표의 효과적인 달성을 도모한다.",
        "{{EVAL_PURPOSE}}",
    ),
    (
        "가. 공통수학1의 개별적인 수학적 사실이나 공식의 단순 암기 여부보다는, 수학적 교과 역량(문제 해결, 추론, "
        "의사소통, 연결, 정보 처리) 함양과 핵심 아이디어에 대한 깊이 있는 이해를 중심으로 평가한다.",
        "{{EVAL_DIRECTION}}",
    ),
]


def build(source: str, output: str) -> None:
    hwp = Hwp(visible=False)
    try:
        hwp.open(source)
        for original, token in TOKEN_MAP:
            hwp.find_replace_all(original, token)
        hwp.save_as(output)
    finally:
        hwp.quit()


if __name__ == "__main__":
    build("templates_src/source_common_math1.hwp", "templates_src/base.hwp")
```

**참고**: 위 `TOKEN_MAP`은 헤더 2개 + 평가목적/방향 앞부분만 예시로 채워둔 최소 버전이다. "나/다/라/마" 문단, 월별 표 30개 셀, 성취수준 표, 최소성취수준 표, 수행평가 세부계획 2블록(교육과정영역/평가과제/성취기준/기본점수/결시자정책/표절정책/채점기준), 분할점수 표까지 전부 같은 패턴(`(원문, 토큰)` 튜플 추가)으로 채워야 완전해진다 — 원문은 `subjects/2022/수학/공통수학1.json`에 이미 다 들어있으니, 이 JSON을 순회하며 `TOKEN_MAP`을 조립하는 헬퍼(`_token_map_from_subject_json()`)를 추가하는 후속 작업으로 이어가는 것을 권장한다(Task 7에서 이어감).

- [ ] **Step 4: 테스트 실행해 통과 확인 (실제 한글 프로그램 필요)**

Run: `.venv\Scripts\pytest tests/test_build_base_hwp.py -v`
Expected: PASS (2 passed) — 실패하면 한글 프로그램이 다른 문서를 편집 중이거나 팝업이 떠 있는지 확인 (pyhwpx는 열려있는 한글 인스턴스와 충돌할 수 있음, 실행 전 한글 프로그램을 모두 닫을 것)

- [ ] **Step 5: 실제 base.hwp 생성해 커밋할 산출물로 확보**

Run: `.venv\Scripts\python scripts/build_base_hwp.py`
Expected: `templates_src/base.hwp` 생성됨

- [ ] **Step 6: 커밋**

```bash
git add scripts/build_base_hwp.py tests/test_build_base_hwp.py templates_src/base.hwp
git commit -m "Add build script that tokenizes the hwp template via find_replace_all"
```

---

### Task 7: TOKEN_MAP을 공통수학1.json 전체로 확장 + hwp_writer.py

**Files:**
- Modify: `scripts/build_base_hwp.py`
- Create: `tokens.py`
- Create: `hwp_writer.py`
- Test: `tests/test_tokens.py`
- Test: `tests/test_hwp_writer.py` (한글 프로그램 필요)

**Interfaces:**
- Consumes: `subjects/2022/수학/공통수학1.json` (Task 완료된 콘텐츠), `templates_src/base.hwp` (Task 6 산출물)
- Produces:
  - `tokens.py`: `build_token_map(subject_json: dict) -> dict[str, str]` — 콘텐츠 라이브러리 JSON 하나를 받아 `{"{{EVAL_PURPOSE}}": "가. ...\n나. ...", ...}` 형태의 토큰→값 dict를 만듦 (원문 문자열은 몰라도 됨 — 이건 런타임에 값을 "채우는" 쪽이라 원문 걱정 없이 그냥 토큰:값 매핑만 하면 됨)
  - `hwp_writer.py`: `write_hwp(token_values: dict, output_path: str, base_path: str = "templates_src/base.hwp") -> None`

- [ ] **Step 1: tokens.py에 대한 실패하는 테스트 작성**

```python
# tests/test_tokens.py
from tokens import build_token_map

SAMPLE_SUBJECT = {
    "eval_purpose": ["가. 목적1", "나. 목적2"],
    "eval_direction": ["가. 방향1", "나. 방향2"],
}


def test_build_token_map_joins_purpose_and_direction_with_newlines():
    tokens = build_token_map(SAMPLE_SUBJECT)
    assert tokens["{{EVAL_PURPOSE}}"] == "가. 목적1\n나. 목적2"
    assert tokens["{{EVAL_DIRECTION}}"] == "가. 방향1\n나. 방향2"


def test_build_token_map_includes_header_overrides():
    tokens = build_token_map(SAMPLE_SUBJECT, subject_name="공통수학1", teachers="김은상, 장재욱, 정요한")
    assert tokens["{{SUBJECT}}"] == "공통수학1"
    assert tokens["{{TEACHERS}}"] == "김은상, 장재욱, 정요한"
```

- [ ] **Step 2: 테스트 실행해 실패 확인**

Run: `.venv\Scripts\pytest tests/test_tokens.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tokens'`

- [ ] **Step 3: tokens.py 구현**

```python
def build_token_map(subject_json: dict, subject_name: str = "", teachers: str = "") -> dict[str, str]:
    tokens: dict[str, str] = {}

    if subject_name:
        tokens["{{SUBJECT}}"] = subject_name
    if teachers:
        tokens["{{TEACHERS}}"] = teachers

    if "eval_purpose" in subject_json:
        tokens["{{EVAL_PURPOSE}}"] = "\n".join(subject_json["eval_purpose"])
    if "eval_direction" in subject_json:
        tokens["{{EVAL_DIRECTION}}"] = "\n".join(subject_json["eval_direction"])

    return tokens
```

- [ ] **Step 4: 테스트 실행해 통과 확인**

Run: `.venv\Scripts\pytest tests/test_tokens.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: hwp_writer.py에 대한 실패하는 테스트 작성**

```python
# tests/test_hwp_writer.py
"""실제 한글 프로그램이 필요한 통합 테스트."""
import re
import subprocess

from hwp_writer import write_hwp

HWP5PROC = r"C:\Users\cando\AppData\Local\Python\pythoncore-3.14-64\Scripts\hwp5proc.exe"


def _extract_texts(hwp_path: str) -> list[str]:
    xml = subprocess.run([HWP5PROC, "xml", hwp_path], capture_output=True, text=True, encoding="utf-8").stdout
    return re.findall(r"<Text[^>]*>(.*?)</Text>", xml, re.S)


def test_write_hwp_fills_subject_and_teachers(tmp_path):
    output = tmp_path / "result.hwp"
    write_hwp({"{{SUBJECT}}": "대수", "{{TEACHERS}}": "홍길동"}, str(output))

    joined = " ".join(_extract_texts(str(output)))
    assert "대수" in joined
    assert "홍길동" in joined
    assert "{{SUBJECT}}" not in joined
    assert "{{TEACHERS}}" not in joined
```

- [ ] **Step 6: 테스트 실행해 실패 확인**

Run: `.venv\Scripts\pytest tests/test_hwp_writer.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'hwp_writer'`

- [ ] **Step 7: hwp_writer.py 구현**

```python
from pyhwpx import Hwp


def write_hwp(token_values: dict[str, str], output_path: str, base_path: str = "templates_src/base.hwp") -> None:
    hwp = Hwp(visible=False)
    try:
        hwp.open(base_path)
        for token, value in token_values.items():
            hwp.find_replace_all(token, value)
        hwp.save_as(output_path)
    finally:
        hwp.quit()
```

- [ ] **Step 8: 테스트 실행해 통과 확인 (한글 프로그램 필요, 실행 전 한글 프로그램 모두 닫을 것)**

Run: `.venv\Scripts\pytest tests/test_hwp_writer.py -v`
Expected: PASS

- [ ] **Step 9: build_base_hwp.py의 TOKEN_MAP을 공통수학1.json 전체로 확장**

`scripts/build_base_hwp.py`에 아래 내용을 추가해, 지금까지 헤더 2개 + 평가목적/방향 일부만 있던 `TOKEN_MAP`을 JSON의 모든 서술형 필드(월별 단원·성취기준, 성취수준 A~E, 최소성취수준, 수행평가 2블록의 모든 하위 필드, 분할점수)로 확장한다. `content_library.load_subject`로 JSON을 불러와 그 값을 그대로 원문으로 사용(원문은 실제 파일에서 나온 값과 100% 동일하므로 `find_replace_all`이 반드시 매치함):

```python
# scripts/build_base_hwp.py 상단에 추가
import sys
sys.path.insert(0, ".")
from content_library import load_subject


def _token_map_from_common_math1() -> list[tuple[str, str]]:
    subject = load_subject("2022", "수학", "공통수학1")
    pairs: list[tuple[str, str]] = []

    for grade, levels in subject["achievement_levels"].items():
        pairs.append((levels["지식이해"], f"{{{{ACHV_{grade}_지식이해}}}}"))
        pairs.append((levels["과정기능"], f"{{{{ACHV_{grade}_과정기능}}}}"))
        pairs.append((levels["가치태도"], f"{{{{ACHV_{grade}_가치태도}}}}"))

    pairs.append((subject["minimum_achievement_overall"], "{{MIN_ACHV_OVERALL}}"))

    for i, task in enumerate(subject["performance_task_examples"], start=1):
        pairs.append((task["task"], f"{{{{TASK_{i}_DESC}}}}"))
        pairs.append((task["absentee_policy"], f"{{{{TASK_{i}_ABSENTEE}}}}"))
        pairs.append((task["plagiarism_policy"], f"{{{{TASK_{i}_PLAGIARISM}}}}"))

    return pairs


TOKEN_MAP.extend(_token_map_from_common_math1())
```

**주의**: 위 확장 코드는 긴 서술형 문단(성취수준, 최소성취수준, 결시자정책 등)만 다룬다. 월별 표의 30개 개별 셀, 수행평가 표의 채점기준(표 형태), 분할점수 표는 텍스트가 표 구조 안에 촘촘히 붙어있어 `find_replace_all`로 통째로 바꾸면 표의 행/열 개수 자체가 안 맞을 위험이 있다 — 이 부분은 Task 6에서 검증한 것처럼 표 셀 하나하나를 `find_replace_all`로 원문 그대로 치환하되(표를 늘리거나 줄이지 않고 원래 있던 셀 값만 텍스트로 교체), 실제 실행 후 반드시 `hwp5proc xml`로 표 개수가 원본과 같은지 확인하는 수동 검증 단계를 다음 Task 11에서 거친다.

- [ ] **Step 10: base.hwp 재생성**

Run: `.venv\Scripts\python scripts/build_base_hwp.py`

- [ ] **Step 11: 커밋**

```bash
git add tokens.py hwp_writer.py scripts/build_base_hwp.py tests/test_tokens.py tests/test_hwp_writer.py templates_src/base.hwp
git commit -m "Expand hwp tokenization to cover full content-library fields; add hwp_writer"
```

---

### Task 8: 학사일정 hwp 파서 (`calendar_parser.py`)

**Files:**
- Create: `calendar_parser.py`
- Test: `tests/test_calendar_parser.py`
- Fixture (이미 있음): `tests/fixtures/academic_calendar_2026.hwp` (서울세종고 2026학년도 학사일정, 교사용 원본)

**Interfaces:**
- Consumes: 없음 (hwp5proc CLI 서브프로세스만 사용)
- Produces: `parse_calendar(hwp_path: str, hwp5proc_path: str = r"C:\Users\cando\AppData\Local\Python\pythoncore-3.14-64\Scripts\hwp5proc.exe") -> list[dict]`
  - 반환값 예: `[{"month": 3, "day": 1, "label": "삼일절", "category": "HOLIDAY"}, {"month": 3, "day": 22, "label": "중간고사", "category": "EXAM"}, ...]`
  - `category`는 `HOLIDAY`(공휴일/대체공휴일) / `EXAM`(중간·기말고사) / `NO_CLASS`(재량휴업일/방학식/개학) / `NOTE`(그 외 특이사항, 자동 제외 대상 아님 — 교사가 직접 판단)
  - 이 함수는 **후보를 뽑아줄 뿐** 확정하지 않는다 — Task 10 폼에서 교사가 이 리스트를 보고 삭제/추가한다

원본 구조 확인(2026-07-26, 실제 파일 `academic_calendar_2026.hwp`를 hwp5proc xml로 추출해 검증함): 표는 `월(정수) → (등교일수) → 1,2,3...31(일자, 월 안에서 오름차순 반복) → 각 일자 뒤에 0개 이상의 이벤트 텍스트`로 이어지는 순수 텍스트 스트림이다. 요일은 이 파일에서 굳이 읽어낼 필요가 없다 — `datetime.date(2026, month, day).weekday()`로 실제 달력 계산을 하면 되므로, 파서는 "몇 월 며칠에 무슨 라벨이 붙어있는가"만 뽑으면 충분하다.

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/test_calendar_parser.py
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
```

- [ ] **Step 2: 테스트 실행해 실패 확인**

Run: `.venv\Scripts\pytest tests/test_calendar_parser.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'calendar_parser'`

- [ ] **Step 3: calendar_parser.py 구현**

```python
import re
import subprocess

CATEGORY_KEYWORDS = {
    "EXAM": ["중간고사", "기말고사"],
    "NO_CLASS": ["재량휴업일", "방학식", "개학", "시업식", "종업식"],
    "HOLIDAY": ["대체공휴일", "삼일절", "어린이날", "현충일", "광복절", "개천절", "한글날", "추석", "설날", "부처님"],
}

MONTH_HEADER_RE = re.compile(r"^\d{1,2}$")
DAY_COUNT_RE = re.compile(r"^\(\d+\)$")
DAY_NUMBER_RE = re.compile(r"^\d{1,2}$")


def _classify(label: str) -> str:
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(keyword in label for keyword in keywords):
            return category
    return "NOTE"


def _extract_texts(hwp_path: str, hwp5proc_path: str) -> list[str]:
    result = subprocess.run(
        [hwp5proc_path, "xml", hwp_path],
        capture_output=True, text=True, encoding="utf-8",
    )
    return re.findall(r"<Text[^>]*>(.*?)</Text>", result.stdout, re.S)


def parse_calendar(hwp_path: str, hwp5proc_path: str = r"C:\Users\cando\AppData\Local\Python\pythoncore-3.14-64\Scripts\hwp5proc.exe") -> list[dict]:
    import html

    texts = [html.unescape(t) for t in _extract_texts(hwp_path, hwp5proc_path)]
    events: list[dict] = []

    current_month = None
    current_day = None
    pending_label_parts: list[str] = []
    expecting_day_count = False
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

    for text in texts:
        stripped = text.strip()

        if expecting_day_count and DAY_COUNT_RE.match(stripped):
            expecting_day_count = False
            continue

        if MONTH_HEADER_RE.match(stripped) and 1 <= int(stripped) <= 12 and not expecting_day_count:
            # 월 헤더 후보. 다음 토큰이 (N) 패턴이면 확정.
            candidate_month = int(stripped)
            flush_label()
            current_month = candidate_month
            current_day = None
            last_day_seen = 0
            expecting_day_count = True
            continue

        if DAY_NUMBER_RE.match(stripped) and current_month is not None:
            day_value = int(stripped)
            # 일자는 월 안에서 항상 증가(1일부터 말일까지) — 감소하면 새 일자가 아니라 본문 속 숫자로 간주.
            if day_value > last_day_seen or (last_day_seen >= 28 and day_value == 1):
                flush_label()
                current_day = day_value
                last_day_seen = day_value
                continue

        if current_month is not None and current_day is not None:
            pending_label_parts.append(stripped)

    flush_label()
    return events
```

- [ ] **Step 4: 테스트 실행해 통과 확인**

Run: `.venv\Scripts\pytest tests/test_calendar_parser.py -v`
Expected: PASS (3 passed). 만약 실패하면 `academic_calendar_2026.hwp`를 `hwp5proc xml`로 직접 열어 3월/4월/5월 구간의 실제 텍스트 순서를 다시 확인하고 정규식/상태머신을 조정할 것 — 이 파서는 실제 파일 1개로만 검증된 휴리스틱이라 학교가 다르거나 서식이 바뀌면 깨질 수 있음(설계 문서의 리스크 항목 참고).

- [ ] **Step 5: 커밋**

```bash
git add calendar_parser.py tests/test_calendar_parser.py
git commit -m "Add academic calendar hwp parser using real 2026 fixture"
```

---

### Task 9: 월별 주·차시 계산 (`schedule_calc.py`)

**Files:**
- Create: `schedule_calc.py`
- Test: `tests/test_schedule_calc.py`

**Interfaces:**
- Consumes: `calendar_parser.parse_calendar()`의 출력 형식(`{"month": int, "day": int, "label": str, "category": str}`의 리스트)을 그대로 받음
- Produces: `compute_monthly_sessions(year: int, semester_start: str, semester_end: str, excluded_events: list[dict], class_weekdays: list[int]) -> dict[int, dict]`
  - `semester_start`/`semester_end`: `"2026-03-02"` 형식 문자열
  - `class_weekdays`: `[0, 2, 3, 4]` 처럼 `datetime.date.weekday()` 값(월=0~일=6)의 리스트 — 4단위면 보통 4개
  - `excluded_events`: `parse_calendar()` 출력 중 교사가 "제외"로 확정한 것만 (category가 EXAM/NO_CLASS/HOLIDAY인 항목들, 교사가 확인 후 넘어온 리스트)
  - 반환값: `{3: {"weeks": "1~4주", "sessions": 16}, 4: {...}, ...}` — 원본 템플릿의 "1~4주 (16)" 표기와 맞춤

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/test_schedule_calc.py
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
```

- [ ] **Step 2: 테스트 실행해 실패 확인**

Run: `.venv\Scripts\pytest tests/test_schedule_calc.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'schedule_calc'`

- [ ] **Step 3: schedule_calc.py 구현**

```python
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
```

- [ ] **Step 4: 테스트 실행해 통과 확인**

Run: `.venv\Scripts\pytest tests/test_schedule_calc.py -v`
Expected: PASS (3 passed). `test_march_2026_full_month_all_weekdays_no_exclusions`의 22가 실제로 맞는지는 `python -c "import calendar; print(sum(1 for d in range(1,32) if __import__('datetime').date(2026,3,d).weekday()<5))"`로 먼저 확인하고, 다르면 테스트의 기댓값을 실제 계산값으로 고칠 것(달력 사실이므로 구현이 아니라 테스트 기댓값이 틀렸을 가능성).

- [ ] **Step 5: 커밋**

```bash
git add schedule_calc.py tests/test_schedule_calc.py
git commit -m "Add pure date-arithmetic monthly session count calculator"
```

---

### Task 10: Flask 폼 배선 (`app.py` 확장 + `templates/index.html`)

**Files:**
- Modify: `app.py`
- Create: `templates/index.html`
- Create: `static/form.js`
- Test: `tests/test_app.py` (확장)

**Interfaces:**
- Consumes: Task 2~9의 `load_subject`, `validate_plan`, `write_xlsx`, `write_hwp`, `build_token_map`, `parse_calendar`, `compute_monthly_sessions` 전부
- Produces: 라우트 `GET /` (폼), `POST /api/calendar/upload` (학사일정 업로드 → 후보 이벤트 JSON), `POST /api/calendar/compute` (교사가 확정한 제외일 목록 → 월별 주·차시 JSON, `compute_monthly_sessions`를 실제로 호출하는 지점), `POST /api/generate` (폼 데이터 → hwp+xlsx 생성, 결과 경로 JSON 리턴)

- [ ] **Step 1: 실패하는 테스트 작성 (엔드투엔드, 실제 한글 프로그램 필요)**

```python
# tests/test_app.py 에 추가
import os
from app import app


def test_generate_endpoint_creates_hwp_and_xlsx(tmp_path, monkeypatch):
    monkeypatch.setattr("app.OUTPUT_DIR", str(tmp_path))
    client = app.test_client()

    payload = {
        "grade": 1, "subject": "공통수학1", "credit": 4,
        "writer": "정요한", "teachers": "김은상, 장재욱, 정요한",
        "revision": "2022", "category": "수학",
        "midterm": {"selective": 80, "essay": 10, "short": 10, "ratio": 30},
        "final": {"selective": 80, "essay": 10, "short": 10, "ratio": 30},
        "performance_items": [
            {"type": "서논술형", "title": "단원별 핵심 개념 구조화를 통해 단계별 문제 해결하기", "month": "3~7", "ratio": 15},
            {"type": "서논술형", "title": "수학 과제 탐구를 통한 실생활 문제 수학적으로 표현하기", "month": "4,6", "ratio": 25},
        ],
        "grading_method": "추정분할",
        "split_scores": {"A/B": 39, "B/C": 38, "C/D": 37, "D/E": 36, "E/I": 35},
    }
    resp = client.post("/api/generate", json=payload)
    assert resp.status_code == 200
    data = resp.get_json()
    assert os.path.isfile(data["xlsx_path"])
    assert os.path.isfile(data["hwp_path"])
    assert data["warnings"] == []


def test_calendar_compute_endpoint_returns_monthly_sessions():
    client = app.test_client()
    payload = {
        "year": 2026,
        "semester_start": "2026-03-01",
        "semester_end": "2026-03-31",
        "excluded_events": [{"month": 3, "day": 1, "label": "삼일절", "category": "HOLIDAY"}],
        "class_weekdays": [0, 1, 2, 3, 4],
    }
    resp = client.post("/api/calendar/compute", json=payload)
    assert resp.status_code == 200
    data = resp.get_json()
    assert 3 in data["monthly_sessions"] or "3" in data["monthly_sessions"]
```

- [ ] **Step 2: 테스트 실행해 실패 확인**

Run: `.venv\Scripts\pytest tests/test_app.py::test_generate_endpoint_creates_hwp_and_xlsx -v`
Expected: FAIL with `AttributeError` 또는 404 (라우트 없음)

- [ ] **Step 3: app.py에 라우트 구현**

```python
# app.py에 추가
import os
from flask import Flask, jsonify, render_template, request

from content_library import load_subject
from validation import validate_plan
from xlsx_writer import write_xlsx
from hwp_writer import write_hwp
from tokens import build_token_map
from calendar_parser import parse_calendar
from schedule_calc import compute_monthly_sessions

OUTPUT_DIR = r"C:\Users\cando\평가계획서_출력"


@app.get("/")
def index():
    return render_template("index.html")


@app.post("/api/calendar/upload")
def calendar_upload():
    uploaded = request.files["calendar"]
    tmp_path = os.path.join(OUTPUT_DIR, "_uploaded_calendar.hwp")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    uploaded.save(tmp_path)
    events = parse_calendar(tmp_path)
    return jsonify({"events": events})


@app.post("/api/calendar/compute")
def calendar_compute():
    """
    /api/calendar/upload가 돌려준 후보(events) 중 교사가 화면에서 확인/수정해 확정한
    excluded_events만 받아서, 실제 월별 주·차시를 계산해 돌려준다.
    이 라우트가 Task 9의 compute_monthly_sessions를 실제로 호출하는 유일한 지점이다.
    """
    payload = request.get_json()
    result = compute_monthly_sessions(
        year=payload["year"],
        semester_start=payload["semester_start"],
        semester_end=payload["semester_end"],
        excluded_events=payload["excluded_events"],
        class_weekdays=payload["class_weekdays"],
    )
    return jsonify({"monthly_sessions": result})


@app.post("/api/generate")
def generate():
    payload = request.get_json()
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    performance_ratios = [{"type": p["type"], "ratio": p["ratio"]} for p in payload["performance_items"]]
    warnings = validate_plan(
        grade=payload["grade"],
        credit=payload["credit"],
        midterm_essay_ratio=payload["midterm"]["essay"],
        midterm_total_ratio=payload["midterm"]["ratio"],
        final_essay_ratio=payload["final"]["essay"],
        final_total_ratio=payload["final"]["ratio"],
        performance_items=performance_ratios,
        grading_method=payload["grading_method"],
        split_scores=payload["split_scores"],
    )

    safe_subject = payload["subject"].replace("/", "_")
    xlsx_path = os.path.join(OUTPUT_DIR, f"평가계획표({safe_subject}).xlsx")
    hwp_path = os.path.join(OUTPUT_DIR, f"교수학습및평가계획서({safe_subject}).hwp")

    write_xlsx(payload, xlsx_path)

    subject_json = load_subject(payload["revision"], payload["category"], payload["subject"]) or {}
    token_values = build_token_map(subject_json, subject_name=payload["subject"], teachers=payload["teachers"])
    write_hwp(token_values, hwp_path)

    return jsonify({"xlsx_path": xlsx_path, "hwp_path": hwp_path, "warnings": warnings})
```

- [ ] **Step 4: 최소 templates/index.html 작성 (폼 골격 — 실제 UX 다듬기는 이후 반복 작업)**

```html
<!-- templates/index.html -->
<!doctype html>
<html lang="ko">
<head><meta charset="utf-8"><title>평가계획서 생성기</title></head>
<body>
  <h1>평가계획서 생성기</h1>
  <form id="plan-form">
    <label>학년 <input type="number" name="grade" required></label>
    <label>과목명 <input type="text" name="subject" required></label>
    <label>학점 <input type="number" name="credit" required></label>
    <label>작성자 <input type="text" name="writer" required></label>
    <label>전체 교사명단 <input type="text" name="teachers" required></label>
    <button type="submit">생성</button>
  </form>
  <div id="result"></div>
  <script src="/static/form.js"></script>
</body>
</html>
```

```javascript
// static/form.js
document.getElementById("plan-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  // 이 골격은 헤더 필드(학년/과목명/학점/작성자/교사명단)만 다룬다.
  // 월별 표·반영비율 그리드·수행평가 블록·학사일정 업로드 UI는 별도 후속 계획(Task 11 참고)에서 추가한다.
  alert("폼 UI는 후속 계획에서 완성합니다.");
});
```

- [ ] **Step 5: 테스트 실행해 통과 확인 (한글 프로그램 필요)**

Run: `.venv\Scripts\pytest tests/test_app.py -v`
Expected: PASS

- [ ] **Step 6: 커밋**

```bash
git add app.py templates/index.html static/form.js tests/test_app.py
git commit -m "Wire Flask routes for calendar upload and hwp/xlsx generation"
```

---

### Task 11: 수동 엔드투엔드 검증 (자동화 불가 — 반드시 사람이 확인)

**Files:** 없음 (검증 절차)

- [ ] **Step 1**: `.venv\Scripts\python app.py` 실행 후 브라우저에서 `http://localhost:5000` 접속해 폼이 뜨는지 확인
- [ ] **Step 2**: Task 10 테스트와 동일한 공통수학1 데이터로 `/api/generate` 호출 (curl 또는 브라우저 개발자도구 fetch로) → `평가계획서_출력` 폴더에 생성된 `.hwp`를 **실제로 한글 프로그램에서 열어** 원본과 표 구조(행/열 개수)가 같은지, 토큰이 전부 실제 값으로 치환됐는지 육안 확인
- [ ] **Step 3**: 같은 폴더의 `.xlsx`를 엑셀에서 열어 A9:C14의 4개 검증 메시지 셀이 (정상 입력 시) 전부 빈칸으로 나오는지 확인
- [ ] **Step 4**: 의도적으로 학점을 2로 바꿔 다시 생성 → 수행평가 총비율 20% 미만 경고가 `/api/generate` 응답의 `warnings`에도, 엑셀 A10/C10 셀에도 동시에 뜨는지 확인(두 검증 로직이 어긋나지 않는지가 핵심)
- [ ] **Step 5**: `tests/fixtures/academic_calendar_2026.hwp`를 `/api/calendar/upload`로 업로드해 반환된 `events`가 3월 삼일절·4월 중간고사 등 실제 항목을 담고 있는지 확인 → 그중 일부를 `excluded_events`로 골라 `/api/calendar/compute`에 학기 시작/종료일과 수업요일(예: 4단위면 `[0,1,2,3]`)을 함께 보내 `monthly_sessions`가 그럴듯한 값(월별 15~20 사이)으로 나오는지 확인
- [ ] **Step 6**: 이 6단계가 모두 통과하면 이 계획의 MVP가 완료된 것 — 이후는 (a) 다른 수학 과목 JSON 추가, (b) 폼 UI 완성(월별 표, 반영비율 그리드, 수행평가 블록 반복 입력, 학사일정 업로드 연동), (c) TOKEN_MAP의 표 안 나머지 필드(월별표 30칸, 채점기준표, 분할점수표) 전부 채우기 — 이 세 가지를 후속 계획으로 별도 작성할 것을 권장함
