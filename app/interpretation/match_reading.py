"""Partnership reading from both charts, eight kootas, transits, and dashas."""

from __future__ import annotations

from datetime import date

from app.api.schemas import ChartResponse, LanguageCode
from app.core.transits import evaluate_current_transits
from app.interpretation.guardrails import verify_text
from app.interpretation.phala import (
    _g,
    _gochara,
    _lord,
    _matter,
    _observance,
    _planet,
    _say,
    _tone,
    _tpl,
    _where,
)


def _check(text: str, lang: str) -> str:
    verify_text(text, languages=(lang,))
    return text


def _m(key: str, lang: str, **kwargs: object) -> str:
    return _tpl("match", key, lang, **kwargs)


def _temper(sign: str, lang: str) -> str:
    return _tpl("temper", sign, lang)


def _behavior(planet: str, lang: str) -> str:
    return _tpl("behavior", planet, lang)


def _portrait(chart: ChartResponse, dasha: dict[str, object], lang: str) -> str:
    moon = _planet(chart, "Moon")
    sun = _planet(chart, "Sun")
    md = str(dasha["active_mahadasha"])
    ad = str(dasha["active_antardasha"])
    return " ".join(
        (
            _m(
                "portrait_lagna",
                lang,
                lagna=_g(chart.lagna_sign_name, lang),
                temper=_temper(chart.lagna_sign_name, lang),
            ),
            _m(
                "portrait_moon",
                lang,
                moon_sign=_g(moon.sign_name, lang),
                moon_nak=_g(moon.nakshatra_name, lang),
                moon_pada=moon.pada,
                temper=_temper(moon.sign_name, lang),
            ),
            _m("portrait_sun", lang),
            _where(chart, sun, lang),
            _m(
                "portrait_period",
                lang,
                md=_g(md, lang),
                ad=_g(ad, lang),
                ad_end=dasha["antardasha_end_date"],
            ),
            _where(chart, _planet(chart, md), lang),
        )
    )


def _seventh(chart: ChartResponse, lang: str) -> str:
    sign, lord = _lord(chart, 7)
    venus = _planet(chart, "Venus")
    parts = [
        _m("seventh_open", lang, sign=_g(sign, lang), lord=_g(lord.planet, lang)),
        _where(chart, lord, lang),
        _m("venus_note", lang),
    ]
    if venus.planet != lord.planet:
        parts.append(_where(chart, venus, lang))
    parts.append(_tone([lord.house, venus.house], lang))
    return " ".join(parts)


def _koota_meaning(name: str, scored: float, maximum: float, lang: str) -> str:
    full = scored + 0.01 >= maximum
    points = _m(
        "koota_points",
        lang,
        name=name,
        scored=f"{scored:g}",
        maximum=f"{maximum:g}",
    )
    key = {
        "Varna": "varna_ok" if full else "varna_mix",
        "Vashya": "vashya_ok" if full else "vashya_mix",
        "Tara": "tara_ok" if full else "tara_mix",
        "Yoni": "yoni_high" if scored >= 4 else ("yoni_mid" if scored >= 2.5 else "yoni_low"),
        "Graha Maitri": "maitri_ok" if full else "maitri_mix",
        "Gana": "gana_high" if scored >= 6 else ("gana_mid" if scored >= 5 else "gana_low"),
        "Bhakoot": "bhakoot_ok" if full else "bhakoot_low",
        "Nadi": "nadi_ok" if full else "nadi_low",
    }[name]
    return f"{points} {_m(key, lang)}"


def _care(
    kootas: list[dict[str, object]],
    mangal: dict[str, object],
    lang: str,
) -> str:
    weak = [
        str(row["koota"])
        for row in kootas
        if float(str(row["scored"])) + 0.01 < float(str(row["max_points"]))
        and str(row["koota"]) in {"Bhakoot", "Nadi", "Gana"}
        and float(str(row["scored"])) <= 1.0
    ]
    left = mangal["profile_a"]
    right = mangal["profile_b"]
    assert isinstance(left, dict) and isinstance(right, dict)
    a_on = bool(left["raw_mangal_indicator"]) and not bool(left["traditional_mitigation_present"])
    b_on = bool(right["raw_mangal_indicator"]) and not bool(right["traditional_mitigation_present"])
    if a_on and b_on:
        mars = _m("mars_both", lang)
    elif a_on or b_on:
        who = _say(
            lang,
            "first chart" if a_on else "partner chart",
            "पहली कुंडली" if a_on else "साथी की कुंडली",
            "पहिली कुंडली" if a_on else "जोडीदाराची कुंडली",
        )
        mars = _m("mars_one", lang, who=who)
    else:
        mars = _m("mars_none", lang)
    strains = _m("strains_some", lang, named=", ".join(weak)) if weak else _m("strains_none", lang)
    return _check(f"{strains} {mars}", lang)


def _bond(
    name_a: str,
    chart_a: ChartResponse,
    name_b: str,
    chart_b: ChartResponse,
    lang: str,
) -> str:
    opening = _m(
        "bond_open",
        lang,
        name_a=name_a,
        temp_a=_temper(chart_a.lagna_sign_name, lang),
        name_b=name_b,
        temp_b=_temper(chart_b.lagna_sign_name, lang),
    )
    return " ".join(
        (
            opening,
            _say(lang, f"For {name_a}:", f"{name_a} के लिए:", f"{name_a} साठी:"),
            _seventh(chart_a, lang),
            _say(lang, f"For {name_b}:", f"{name_b} के लिए:", f"{name_b} साठी:"),
            _seventh(chart_b, lang),
        )
    )


def _household(name: str, chart: ChartResponse, dasha: dict[str, object], lang: str) -> str:
    fourth, fourth_lord = _lord(chart, 4)
    fifth, fifth_lord = _lord(chart, 5)
    second, second_lord = _lord(chart, 2)
    md = str(dasha["active_mahadasha"])
    ad = str(dasha["active_antardasha"])
    return _m(
        "household",
        lang,
        name=name,
        fourth=_g(fourth, lang),
        fourth_lord=_g(fourth_lord.planet, lang),
        fourth_where=_where(chart, fourth_lord, lang),
        fifth=_g(fifth, lang),
        fifth_where=_where(chart, fifth_lord, lang),
        second=_g(second, lang),
        second_where=_where(chart, second_lord, lang),
        tone=_tone([fourth_lord.house, fifth_lord.house, second_lord.house], lang),
        ad_end=dasha["antardasha_end_date"],
        md=_g(md, lang),
        ad=_g(ad, lang),
    )


def _motions(name: str, transits: dict[str, object], lang: str) -> str:
    jh = int(str(transits["jupiter_house_from_moon"]))
    sh = int(str(transits["saturn_house_from_moon"]))
    sade = transits["sade_sati"]
    assert isinstance(sade, dict)
    placed = _m(
        "motions_person",
        lang,
        name=name,
        date=transits["target_date"],
        jup_sign=_g(transits["jupiter_transit_sign"], lang),
        jh=jh,
        j_matter=_matter(jh, lang),
        sat_sign=_g(transits["saturn_transit_sign"], lang),
        sh=sh,
        s_matter=_matter(sh, lang),
    )
    pressure = _m("sade_on" if bool(sade["is_active"]) else "sade_off", lang)
    touch = _m("touch_7" if (jh == 7 or sh == 7) else "touch_other", lang)
    return " ".join((placed, _gochara(transits, lang), pressure, touch))


def _conduct(name: str, chart: ChartResponse, dasha: dict[str, object], lang: str) -> str:
    md = str(dasha["active_mahadasha"])
    ad = str(dasha["active_antardasha"])
    return " ".join(
        (
            _m(
                "conduct",
                lang,
                name=name,
                md=_g(md, lang),
                ad=_g(ad, lang),
                behavior=_behavior(md, lang),
            ),
            _where(chart, _planet(chart, ad), lang),
            _observance(chart, md, lang),
        )
    )


def describe_partnership(
    chart_a: ChartResponse,
    chart_b: ChartResponse,
    dasha_a: dict[str, object],
    dasha_b: dict[str, object],
    match: dict[str, object],
    *,
    name_a: str,
    name_b: str,
    place_a: str,
    place_b: str,
    when_a: str,
    when_b: str,
    lang: LanguageCode,
    already_married: bool,
    on_date: date,
) -> dict[str, object]:
    kootas = match["koota_breakdown"]
    assert isinstance(kootas, list)
    for row in kootas:
        assert isinstance(row, dict)
        row["meaning"] = _check(
            _koota_meaning(
                str(row["koota"]),
                float(str(row["scored"])),
                float(str(row["max_points"])),
                lang,
            ),
            lang,
        )
    mangal = match["mangal_dosha_check"]
    assert isinstance(mangal, dict)
    frame = _m(
        "frame_married" if already_married else "frame_unmarried",
        lang,
        name_a=name_a,
        name_b=name_b,
    )
    sky_a = evaluate_current_transits(chart_a, on_date)
    sky_b = evaluate_current_transits(chart_b, on_date)
    life = " ".join(
        (
            frame,
            _household(name_a, chart_a, dasha_a, lang),
            _household(name_b, chart_b, dasha_b, lang),
        )
    )
    motions = " ".join(
        (
            _m("motions_intro", lang),
            _motions(name_a, sky_a, lang),
            _motions(name_b, sky_b, lang),
        )
    )
    conduct = " ".join(
        (
            _conduct(name_a, chart_a, dasha_a, lang),
            _conduct(name_b, chart_b, dasha_b, lang),
        )
    )
    people = []
    for name, place, when, chart, dasha, role_en, role_hi, role_mr in (
        (name_a, place_a, when_a, chart_a, dasha_a, "You", "आप", "तुम्ही"),
        (name_b, place_b, when_b, chart_b, dasha_b, "Partner", "साथी", "जोडीदार"),
    ):
        moon = _planet(chart, "Moon")
        people.append(
            {
                "role": _say(lang, role_en, role_hi, role_mr),
                "name": name,
                "birth": _check(
                    _say(
                        lang,
                        (
                            f"{place}. {when}. Lagna {_g(chart.lagna_sign_name, lang)}. "
                            f"Moon {_g(moon.sign_name, lang)}, "
                            f"nakshatra {_g(moon.nakshatra_name, lang)}, pada {moon.pada}."
                        ),
                        (
                            f"{place}। {when}। लग्न {_g(chart.lagna_sign_name, lang)}। "
                            f"चंद्र {_g(moon.sign_name, lang)}, "
                            f"नक्षत्र {_g(moon.nakshatra_name, lang)}, चरण {moon.pada}।"
                        ),
                        (
                            f"{place}. {when}. लग्न {_g(chart.lagna_sign_name, lang)}. "
                            f"चंद्र {_g(moon.sign_name, lang)}, "
                            f"नक्षत्र {_g(moon.nakshatra_name, lang)}, चरण {moon.pada}."
                        ),
                    ),
                    lang,
                ),
                "character": _check(_portrait(chart, dasha, lang), lang),
            }
        )
    married_title = (
        ("Married life now", "विवाह की वर्तमान दशा", "विवाहाची सध्याची स्थिती")
        if already_married
        else (
            "How married life tends to move",
            "विवाहित जीवन की संभावित गति",
            "विवाहित जीवनाची संभाव्य गती",
        )
    )
    sections = [
        {
            "title": _say(lang, "Character", "स्वभाव", "स्वभाव"),
            "text": _check(
                f"{name_a}. {people[0]['character']} {name_b}. {people[1]['character']}",
                lang,
            ),
        },
        {
            "title": _say(lang, "The relationship", "संबंध", "नाते"),
            "text": _check(_bond(name_a, chart_a, name_b, chart_b, lang), lang),
        },
        {
            "title": _say(lang, *married_title),
            "text": _check(life, lang),
        },
        {
            "title": _say(
                lang,
                "Strains and what to do",
                "तनाव और क्या करें",
                "ताण आणि काय करावे",
            ),
            "text": _care(kootas, mangal, lang),
        },
        {
            "title": _say(
                lang,
                "Current planetary motions",
                "वर्तमान ग्रह गति",
                "सध्याची ग्रहगती",
            ),
            "text": _check(motions, lang),
        },
        {
            "title": _say(lang, "Dasha and conduct", "दशा और आचरण", "दशा आणि आचरण"),
            "text": _check(conduct, lang),
        },
    ]
    match["people"] = people
    match["sections"] = sections
    match["already_married"] = already_married
    match["method_limitations_note"] = _check(_m("limitations", lang), lang)
    return match
