from app.interpretation.language import Catalog
from app.interpretation.terms import gloss


def test_hindi_and_marathi_terms_lead_with_the_vernacular_name() -> None:
    assert gloss("Pisces", "mr") == "मीन (Pisces)"
    assert gloss("Aries", "mr") == "मेष (Aries)"
    assert gloss("Aries", "hi") == "मेष (Aries)"
    assert gloss("Libra", "mr") == "तूळ (Libra)"
    assert gloss("Libra", "hi") == "तुला (Libra)"
    assert gloss("Sunday", "mr") == "रविवार (Sunday)"
    assert gloss("Tuesday", "hi") == "मंगलवार (Tuesday)"
    assert gloss("Tuesday", "mr") == "मंगळवार (Tuesday)"
    assert gloss("Vyatipata", "hi") == "व्यतिपात (Vyatipata)"
    assert gloss("Shukla Trayodashi", "mr") == "शुक्ल त्रयोदशी (Shukla Trayodashi)"
    assert gloss("Ashwini", "hi") == "अश्विनी (Ashwini)"
    assert gloss("Pisces", "en") == "Pisces"
    assert gloss(2, "mr") == 2


def test_daily_insight_templates_translate_inserted_names() -> None:
    catalog = Catalog("i18n")
    marathi = catalog.format(
        "daily_insight.pro",
        "mr",
        transit_moon_sign="Aries",
        moon_house=2,
        natal_moon="Pisces",
        tithi="Shukla Trayodashi",
        yoga="Vyatipata",
    )
    assert "मीन (Pisces)" in marathi
    assert "मेष (Aries)" in marathi
    assert "व्यतिपात (Vyatipata)" in marathi
    hindi = catalog.format(
        "daily_insight.simple",
        "hi",
        natal_moon="Pisces",
    )
    assert "मीन (Pisces)" in hindi
    assert "रविवार" not in hindi
    english = catalog.format(
        "daily_insight.simple",
        "en",
        vara="Sunday",
        tithi="Shukla Trayodashi",
        panchang_nak="Ashwini",
        moon_house=2,
        natal_moon="Pisces",
    )
    assert "Pisces" in english
    assert "मीन" not in english
