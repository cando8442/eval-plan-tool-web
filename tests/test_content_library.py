from content_library import list_subjects, load_subject


def test_load_existing_subject_returns_dict():
    result = load_subject("2022", "테스트과목", "테스트과목", base_dir="tests/fixtures/subjects")
    assert result is not None
    assert result["subject"] == "테스트과목"
    assert result["eval_purpose"] == ["가. 테스트 목적"]


def test_load_missing_subject_returns_none():
    result = load_subject("2022", "테스트과목", "존재안함", base_dir="tests/fixtures/subjects")
    assert result is None


def test_list_subjects_returns_registered_names():
    result = list_subjects("2022", "테스트과목", base_dir="tests/fixtures/subjects")
    assert result == ["테스트과목"]


def test_list_subjects_returns_empty_for_missing_category():
    result = list_subjects("2015", "테스트과목", base_dir="tests/fixtures/subjects")
    assert result == []


def test_load_subject_falls_back_to_roman_numeral_variant():
    # 실제 라이브러리 파일은 "미적분Ⅰ.json"(로마 숫자)이지만, 사용자가 키보드로 치기
    # 쉬운 아라비아 숫자 "미적분1"을 입력해도 같은 과목을 찾아야 한다.
    result = load_subject("2022", "수학", "미적분1")
    assert result is not None
    assert result["subject"] == "미적분Ⅰ"


def test_load_subject_falls_back_to_digit_variant():
    result = load_subject("2022", "테스트과목", "테스트과목Ⅰ", base_dir="tests/fixtures/subjects")
    assert result is None  # 폴백 대상 파일("테스트과목1.json")도 없으면 여전히 None
