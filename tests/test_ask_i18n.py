import pytest

from app.interpretation.language import Catalog

KEYS = (
    "area.career",
    "area.relationships",
    "area.finances",
    "area.home",
    "ask.coverage.uncovered_title",
    "ask.coverage.uncovered_body",
    "ask.coverage.suggestion",
    "error.ask_question_invalid",
    "error.ask_quota_exhausted",
    "error.ask_disabled",
)


@pytest.mark.parametrize("lang", ["en", "hi", "mr"])
def test_ask_keys_exist_in_every_language(lang) -> None:
    catalog = Catalog("i18n")
    for key in KEYS:
        assert catalog.get(key, lang).strip()


def test_quota_copy_names_the_weekly_reset_without_the_old_allowance() -> None:
    catalog = Catalog("i18n")
    text = catalog.get("error.ask_quota_exhausted", "en")
    assert "Monday" in text
    assert "three" not in text.lower()


def test_uncovered_body_formats_area_list() -> None:
    catalog = Catalog("i18n")
    text = catalog.format("ask.coverage.uncovered_body", "en", areas="Career, Finances")
    assert "Career, Finances" in text
