# -*- coding: utf-8 -*-
"""교육과정 고시문 PDF에서 과목별 성취기준을 뽑아 콘텐츠 라이브러리에 반영한다.

배경
----
이 라이브러리의 과목 JSON은 원래 성취기준을 영역당 2개씩만 뽑아 3개월치로 적어둔
"재구성 초안"이었다. 2022 개정 교육과정 과목은 한 학기 완결이므로 성취기준 전체가
한 학기 월별 계획(5행) 안에 들어가야 하는데, 절반 이상이 UI에 아예 뜨지 않았고
성취기준 코드 접두사가 틀린 과목도 있었다.

사용법
------
1. 교육부 고시 제2022-33호 해당 별책 PDF를 내려받는다(국가교육과정정보센터
   https://ncic.re.kr 교육과정 자료실).
2. 텍스트를 뽑는다:  python -m scripts.curriculum.apply_from_pdf --extract 별책9.pdf sci.txt
3. 어떤 과목이 잡히는지 확인한다: python -m scripts.curriculum.apply_from_pdf --list sci.txt
4. 매핑 파일(JSON)을 만든다. {"과목파일명": ["원문코드접두사", 학기]} 형태다.
5. 반영한다:
     python -m scripts.curriculum.apply_from_pdf \\
         --text sci.txt --dir "subjects/2022/과학과" --map map.json \\
         --document "교육부 고시 제2022-33호 [별책 9] 과학과 교육과정" --write

--write 없이 돌리면 무엇이 바뀌는지만 보여준다(드라이런).
"""
import argparse
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scripts.curriculum.parse_curriculum import parse_standards
from scripts.curriculum.rebuild import rebuild_units, fix_codes

NOTE = (
    "성취기준(총 {n}개)과 영역명·성취기준 코드는 {doc} 원문을 파싱해 그대로 옮겼다. "
    "2022 개정 교육과정 과목은 한 학기 완결이므로 월별 계획 5개월에 성취기준 전체를 "
    "배치했다(월·시수는 예시이며 학사일정 분석 결과로 덮어쓰인다). 성취수준(A~E)·"
    "최소 성취수준 진술문·수행평가 예시는 고시문에 없는 내용(한국교육과정평가원 "
    "성취수준 자료 소관)이라 재구성본이므로 실제 제출 전 검토·보완이 필요하다."
)
NOTE_NO_AREAS = (
    " 이 과목은 고시문이 성취기준을 영역으로 나누지 않으므로(성취기준이 모두 01-xx) "
    "단원명이 원문에 없다. 없는 단원명을 지어내지 않고 과목명을 넣어 두었으니 "
    "교사가 수업 순서에 맞게 채워야 한다."
)

CODE_PREFIX = re.compile(r"\[(\d+[가-힣]+\d?)-?\d{2}-\d{2}\]")


def extract(pdf_path: str, out_path: str) -> None:
    from pdfminer.high_level import extract_text

    text = extract_text(pdf_path)
    io.open(out_path, "w", encoding="utf-8").write(text)
    print(f"{out_path}: {len(text)}자")


def apply(text_path: str, subject_dir: str, mapping: dict, document: str, write: bool) -> int:
    parsed_all = parse_standards(io.open(text_path, encoding="utf-8").read())
    problems = 0

    for name, (prefix, semester) in mapping.items():
        path = os.path.join(subject_dir, f"{name}.json")
        if not os.path.isfile(path):
            print(f"!! 파일 없음: {path}")
            problems += 1
            continue
        parsed = parsed_all.get(prefix)
        if not parsed:
            print(f"!! 원문에서 못 찾음: {name} ({prefix})")
            problems += 1
            continue

        data = json.load(io.open(path, encoding="utf-8"))

        # 기존 파일이 쓰던 코드 접두사가 원문과 다르면 바로잡는다.
        blob = json.dumps(data, ensure_ascii=False)
        old_prefixes = {p for p in CODE_PREFIX.findall(blob) if p != prefix}
        for old in old_prefixes:
            data = fix_codes(data, old, prefix)

        has_areas = bool(parsed["areas"])
        data["units_by_month"] = rebuild_units(data, parsed, semester, fallback_unit=name)
        data["source_note"] = NOTE.format(n=len(parsed["standards"]), doc=document) + (
            "" if has_areas else NOTE_NO_AREAS
        )
        data["standards_source"] = {
            "verified": True,
            "document": document,
            "standards_count": len(parsed["standards"]),
        }

        official = {f"{code} {body}" for code, body, _ in parsed["standards"]}
        months = sorted(data["units_by_month"], key=int)
        for task in data.get("performance_task_examples") or []:
            month = str(task.get("month") or "")
            if month not in data["units_by_month"]:
                month = months[-1]
                task["month"] = month
            existing = task.get("standards") or []
            if existing and all(x in official for x in existing):
                continue  # 이미 원문 성취기준을 정확히 가리키고 있다
            task["standards"] = list(data["units_by_month"][month]["standards"])
            task["curriculum_area"] = data["units_by_month"][month]["unit"]

        sizes = [len(data["units_by_month"][m]["standards"]) for m in months]
        print(
            f"{name:20s} {prefix:8s} {len(parsed['standards']):2d}개 {str(sizes):16s} "
            f"영역={'원문' if has_areas else '없음(과목명)'} 코드교정:{sorted(old_prefixes) or '-'}"
        )
        if write:
            with io.open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                f.write("\n")

    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--extract", nargs=2, metavar=("PDF", "OUT"), help="PDF에서 텍스트 추출")
    ap.add_argument("--list", metavar="TEXT", help="추출된 텍스트에서 잡히는 과목 코드 목록")
    ap.add_argument("--text", help="추출된 교육과정 텍스트")
    ap.add_argument("--dir", help="과목 JSON 디렉터리 (예: subjects/2022/과학과)")
    ap.add_argument("--map", help='{"과목명": ["코드접두사", 학기]} 매핑 JSON 경로')
    ap.add_argument("--document", help="근거 문서명 (source_note/standards_source 에 기록)")
    ap.add_argument("--write", action="store_true", help="실제로 저장 (없으면 드라이런)")
    args = ap.parse_args()

    if args.extract:
        extract(*args.extract)
        return 0

    if args.list:
        data = parse_standards(io.open(args.list, encoding="utf-8").read())
        for prefix, entry in sorted(data.items()):
            print(f"{prefix:10s} {len(entry['standards']):3d}개  영역={entry['areas']}")
        return 0

    if not (args.text and args.dir and args.map and args.document):
        ap.error("--text, --dir, --map, --document 가 모두 필요하다")

    mapping = json.load(io.open(args.map, encoding="utf-8"))
    problems = apply(args.text, args.dir, mapping, args.document, args.write)
    print("\n저장 완료" if args.write else "\n[드라이런] --write 를 붙이면 저장한다")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
