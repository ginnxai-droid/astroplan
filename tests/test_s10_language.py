import pytest

from app.interpretation.errors import MissingI18nKeyError
from app.interpretation.guardrails import verify_text
from app.interpretation.language import Catalog

pytestmark = pytest.mark.s10


def test_all_templates_tooltips_and_errors_pass_guardrails() -> None:
    cat = Catalog("i18n")
    for lang in ("en", "hi", "mr"):
        glossary = cat.glossary(lang)
        assert len(glossary) >= 16
        for val in glossary.values():
            verify_text(val, languages=(lang,))
        verify_text(cat.get("yoga.hamsa.simple", lang), languages=(lang,))
        verify_text(cat.get("trust.professional_advice_disclaimer", lang), languages=(lang,))


def test_missing_key_raises() -> None:
    with pytest.raises(MissingI18nKeyError):
        Catalog("i18n").get("does_not_exist.simple", "en")
