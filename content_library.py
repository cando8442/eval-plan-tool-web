import json
import os
from typing import Optional

# 기본값은 이 파일(content_library.py)의 실제 위치를 기준으로 계산한다 (CWD 기준이
# 아님). CWD 기준 상대경로("subjects")를 쓰면, 저장소 루트가 아닌 다른 디렉터리에서
# 이 모듈을 import/실행할 때(예: tokens.py의 모듈 임포트 시점 최상위 호출) 조용히
# None을 반환하고, 그 None이 이후 AttributeError 같은 뜻 모를 오류로 번진다.
_DEFAULT_SUBJECTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "subjects")


_DIGIT_TO_ROMAN = {"1": "Ⅰ", "2": "Ⅱ", "3": "Ⅲ"}
_ROMAN_TO_DIGIT = {v: k for k, v in _DIGIT_TO_ROMAN.items()}


def _numeral_variant(subject: str) -> Optional[str]:
    """과목명 끝 글자가 아라비아 숫자(1/2/3)면 로마 숫자(Ⅰ/Ⅱ/Ⅲ)로, 로마 숫자면
    아라비아 숫자로 바꾼 변형을 돌려준다. "미적분1"을 타이핑해도 실제 파일명이
    "미적분Ⅰ.json"인 과목을 찾을 수 있도록 하기 위함 -- 사용자가 키보드로 치기 쉬운
    아라비아 숫자와, 교육과정 공식 표기인 로마 숫자 사이의 표기 차이를 흡수한다."""
    if not subject:
        return None
    last = subject[-1]
    if last in _DIGIT_TO_ROMAN:
        return subject[:-1] + _DIGIT_TO_ROMAN[last]
    if last in _ROMAN_TO_DIGIT:
        return subject[:-1] + _ROMAN_TO_DIGIT[last]
    return None


def load_subject(revision: str, category: str, subject: str, base_dir: str = _DEFAULT_SUBJECTS_DIR) -> Optional[dict]:
    path = os.path.join(base_dir, revision, category, f"{subject}.json")
    if not os.path.isfile(path):
        variant = _numeral_variant(subject)
        if variant is None:
            return None
        path = os.path.join(base_dir, revision, category, f"{variant}.json")
        if not os.path.isfile(path):
            return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def list_subjects(revision: str, category: str, base_dir: str = _DEFAULT_SUBJECTS_DIR) -> list[str]:
    dir_path = os.path.join(base_dir, revision, category)
    if not os.path.isdir(dir_path):
        return []
    names = [f[: -len(".json")] for f in os.listdir(dir_path) if f.endswith(".json")]
    return sorted(names)
