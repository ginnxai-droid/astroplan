import json
import re
from datetime import date, time
from pathlib import Path

from app.api.schemas import BirthDetailsInput
from app.core.chart import calculate_chart
from app.core.dasha import calculate_vimshottari_dasha
from app.core.panchang import calculate_daily_panchang
from app.core.transits import evaluate_current_transits
from app.interpretation.question import answer_question
from app.interpretation.readings import generate_daily_area_readings
from app.interpretation.rules import load_rules
from app.interpretation.voice import sentence_count

_REJECTED = (
    "अहंकारापेक्षा छोटे",
    "आरोपेक्षा छोटे",
    "आशेपेक्षा छोटे",
    "गर्दी करू नका",
    "स्तुती मागू नका",
    "ताबा मिळवण्यासाठी",
    "भाषण नको",
    "मतभेद लपवू नका",
    "smaller than your pride",
    "smaller than the hope",
    "smaller than the accusation",
    "smaller than ego",
)


def test_marathi_life_cards_are_spoken_and_not_glosses() -> None:
    voice = json.loads(
        Path("app/interpretation/voice.json").read_text(encoding="utf-8")
    )
    for section in ("work", "money", "home", "talk", "step", "area_open", "care_line"):
        blob = json.dumps(voice[section], ensure_ascii=False)
        for phrase in _REJECTED:
            assert phrase not in blob
    inp = BirthDetailsInput(
        birth_date=date(1992, 5, 10),
        birth_time=time(14, 30),
        name="Test Person",
        place_name="Pune",
        country="India",
        latitude=18.5204,
        longitude=73.8567,
        language="mr",
    )
    chart = calculate_chart(inp, 18.5204, 73.8567, "Asia/Kolkata")
    moon = next(p for p in chart.planets if p.planet == "Moon")
    target = date(2026, 11, 25)
    dasha = calculate_vimshottari_dasha(inp.birth_date, moon.longitude, target)
    transits = evaluate_current_transits(chart, target)
    panchang = calculate_daily_panchang(target, 18.5204, 73.8567, "Asia/Kolkata")
    rules = load_rules("rules/mvp_rules.yaml", allow_draft=True)
    areas = generate_daily_area_readings(chart, dasha, transits, panchang, rules, "mr")
    for key in ("career", "finances", "home", "relationships"):
        text = areas[key][0].simple_text
        assert sentence_count(text) > 1
        for phrase in _REJECTED:
            assert phrase not in text


def test_house_and_job_answers_follow_the_question() -> None:
    inp = BirthDetailsInput(
        birth_date=date(1993, 11, 14),
        birth_time=time(10, 15),
        name="Aarav",
        place_name="Pune",
        country="India",
        latitude=18.5204,
        longitude=73.8567,
        language="en",
    )
    chart = calculate_chart(inp, 18.5204, 73.8567, "Asia/Kolkata")
    moon = next(p for p in chart.planets if p.planet == "Moon")
    target = date(2026, 11, 25)
    dasha = calculate_vimshottari_dasha(inp.birth_date, moon.longitude, target)
    transits = evaluate_current_transits(chart, target)
    house_q = "when I buy new house"
    job_q = "I'm desperate to change my job...when will I get it"
    for lang in ("en", "hi", "mr"):
        house, _facts = answer_question(
            question=house_q,
            lang=lang,
            area="home",
            chart=chart,
            dasha=dasha,
            transits=transits,
        )
        job, _facts = answer_question(
            question=job_q,
            lang=lang,
            area="career",
            chart=chart,
            dasha=dasha,
            transits=transits,
        )
        assert "Lagna is" not in house
        assert "नक्षत्र" not in house
        assert "Lagna is" not in job
        assert "नक्षत्र" not in job
        if lang == "en":
            assert re.search(r"home|house", house, re.IGNORECASE)
            assert re.search(r"wait|period|through", house, re.IGNORECASE)
            assert re.search(r"work|job", job, re.IGNORECASE)
            assert re.search(r"period|wait|suit|fit|through", job, re.IGNORECASE)
        elif lang == "mr":
            assert "घर" in house
            assert re.search(r"काळ|थांब", house)
            assert re.search(r"काम|नोकरी", job)
        else:
            assert "घर" in house
            assert re.search(r"समय|रुक", house)
            assert re.search(r"काम|नौकरी", job)
