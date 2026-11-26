from datetime import date

import pytest

from app.interpretation.ask import (
    AskLexiconError,
    classify_question,
    infer_target_date,
    is_present_time_question,
    iso_week_start,
    load_area_lexicon,
)


@pytest.fixture(scope="module")
def lexicon():
    return load_area_lexicon("rules/ask_lexicon.yaml")


@pytest.mark.parametrize(
    ("question", "area", "term"),
    [
        ("Will I change jobs before mid-2027?", "career", "job"),
        ("Shall I startup a new business?", "career", "startup"),
        ("Should I ask for a promotion this year?", "career", "promotion"),
        ("Will I marry in the next two years?", "relationships", "marry"),
        ("Should I take a loan this year?", "finances", "loan"),
        ("Is this a good year to move home?", "home", "home"),
    ],
)
def test_routes_english_questions(lexicon, question, area, term) -> None:
    routed, matched = classify_question(question, lexicon)
    assert routed == area
    assert term in matched


def test_routes_hindi_and_marathi(lexicon) -> None:
    assert classify_question("क्या मेरी नौकरी बदलेगी?", lexicon)[0] == "career"
    assert classify_question("माझं घर कधी बदलेल?", lexicon)[0] == "home"


def test_unmapped_area_abstains(lexicon) -> None:
    assert classify_question("How is my health in 2027?", lexicon) == (None, [])


def test_vehicle_routes_to_others(lexicon) -> None:
    routed, matched = classify_question("When will I buy my first car?", lexicon)
    assert routed == "others"
    assert "car" in matched
    assert classify_question("How is my career?", lexicon)[0] == "career"


def test_negation_is_not_understood_and_routes_to_the_named_area(lexicon) -> None:
    # Documented v1 limitation: the router sees the noun, not the negation.
    assert classify_question("I am not worried about money, will my loan clear?", lexicon)[0] == (
        "finances"
    )


def test_compound_tie_abstains(lexicon) -> None:
    assert classify_question("Should I move for a new job?", lexicon) == (None, [])


def test_present_cue_detection(lexicon) -> None:
    assert is_present_time_question("What should I focus on today?", lexicon)
    assert not is_present_time_question("Will I change jobs in 2028?", lexicon)


def test_target_year_inference_and_clamping() -> None:
    today = date(2026, 11, 17)
    assert infer_target_date("Will I change jobs before mid-2027?", today=today) == (
        date(2027, 1, 15)
    )
    assert infer_target_date("Anything for 2026 or 2027?", today=today) is None
    assert infer_target_date("What about 2035?", today=today) == date(2029, 11, 17)
    assert infer_target_date("Will I change jobs?", today=today) is None


def test_target_year_inference_survives_leap_day() -> None:
    assert infer_target_date("2027", today=date(2028, 2, 29)) == date(2028, 2, 29)


def test_iso_week_start_is_monday() -> None:
    assert iso_week_start(date(2026, 11, 17)) == date(2026, 11, 16)


def test_loader_rejects_incomplete_lexicon(tmp_path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("career: [job]\npresent_cues: [today]\n", encoding="utf-8")
    with pytest.raises(AskLexiconError):
        load_area_lexicon(bad)
