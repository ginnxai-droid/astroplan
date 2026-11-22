"""Chart-specific readings from houses, D9 Navamsa, dasha, panchang, and gochara."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.api.schemas import ChartResponse, LanguageCode, PlanetPosition
from app.core.constants import RASHI_NAMES
from app.interpretation.guardrails import verify_text
from app.interpretation.terms import gloss

_DATA: dict[str, Any] = json.loads(
    Path(__file__).with_name("phala_text.json").read_text(encoding="utf-8")
)
_LANG_IDX = {"en": 0, "hi": 1, "mr": 2}

_LORDS = {
    "Aries": "Mars",
    "Taurus": "Venus",
    "Gemini": "Mercury",
    "Cancer": "Moon",
    "Leo": "Sun",
    "Virgo": "Mercury",
    "Libra": "Venus",
    "Scorpio": "Mars",
    "Sagittarius": "Jupiter",
    "Capricorn": "Saturn",
    "Aquarius": "Saturn",
    "Pisces": "Jupiter",
}
_VARA_LORDS = {
    "Sunday": "Sun",
    "Monday": "Moon",
    "Tuesday": "Mars",
    "Wednesday": "Mercury",
    "Thursday": "Jupiter",
    "Friday": "Venus",
    "Saturday": "Saturn",
}
_PRESSURE = {6, 8, 12}
_JUPITER_EASY = {2, 5, 7, 9, 11}
_SATURN_EASY = {3, 6, 11}

_MONTHS = {
    "January": ("January", "जनवरी", "जानेवारी"),
    "February": ("February", "फरवरी", "फेब्रुवारी"),
    "March": ("March", "मार्च", "मार्च"),
    "April": ("April", "अप्रैल", "एप्रिल"),
    "May": ("May", "मई", "मे"),
    "June": ("June", "जून", "जून"),
    "July": ("July", "जुलाई", "जुलै"),
    "August": ("August", "अगस्त", "ऑगस्ट"),
    "September": ("September", "सितंबर", "सप्टेंबर"),
    "October": ("October", "अक्टूबर", "ऑक्टोबर"),
    "November": ("November", "नवंबर", "नोव्हेंबर"),
    "December": ("December", "दिसंबर", "डिसेंबर"),
}

_REMEDY = {
    "Sun": (
        "Surya",
        "Sunday",
        {
            "en": "offer water to morning Surya and recite Aditya Hridayam once",
            "hi": "प्रातः सूर्य को जल दें और आदित्य हृदय एक बार पढ़ें",
            "mr": "सकाळी सूर्याला जल द्या आणि आदित्य हृदय एकदा म्हणा",
        },
    ),
    "Moon": (
        "Shiva",
        "Monday",
        {
            "en": "offer water on a Shiva linga and keep evening hours calm",
            "hi": "शिवलिंग पर जल दें और संध्या शांत रखें",
            "mr": "शिवलिंगावर जल द्या आणि संध्या शांत ठेवा",
        },
    ),
    "Mars": (
        "Hanuman",
        "Tuesday",
        {
            "en": "recite Hanuman Chalisa before a Hanuman or Kartikeya image",
            "hi": "हनुमान या कार्तिकेय की मूर्ति के आगे हनुमान चालीसा पढ़ें",
            "mr": "हनुमान किंवा कार्तिकेय मूर्तीसमोर हनुमान चालीसा म्हणा",
        },
    ),
    "Mercury": (
        "Vishnu",
        "Wednesday",
        {
            "en": "recite a short Vishnu name before study or accounts",
            "hi": "पढ़ाई या हिसाब से पहले विष्णु का संक्षिप्त नाम जपें",
            "mr": "अभ्यास किंवा हिशोबापूर्वी विष्णूचे छोटे नाम जपा",
        },
    ),
    "Jupiter": (
        "Brihaspati",
        "Thursday",
        {
            "en": "offer a yellow flower or banana and recite a Brihaspati name",
            "hi": "पीला फूल या केला अर्पित करें और बृहस्पति का नाम जपें",
            "mr": "पिवळे फूल किंवा केळी अर्पण करा आणि बृहस्पतीचे नाम जपा",
        },
    ),
    "Venus": (
        "Lakshmi",
        "Friday",
        {
            "en": "light a lamp for Lakshmi and recite a short Shukra name",
            "hi": "लक्ष्मी के लिए दीप जलाएँ और शुक्र का संक्षिप्त नाम जपें",
            "mr": "लक्ष्मीसाठी दीप लावा आणि शुक्राचे छोटे नाम जपा",
        },
    ),
    "Saturn": (
        "Shani",
        "Saturday",
        {
            "en": "light a sesame-oil lamp for Shani and complete one steady duty that day",
            "hi": "शनि के लिए तिल के तेल का दीप जलाएँ और उसी दिन एक धीमा, ईमानदार काम पूरा करें",
            "mr": "शनीसाठी तीळतेलाचा दीप लावा आणि त्याच दिवशी एक सावकाश, प्रामाणिक काम पूर्ण करा",
        },
    ),
    "Rahu": (
        "Durga",
        "Saturday",
        {
            "en": "recite a Durga name and finish one disciplined task that day",
            "hi": "दुर्गा का नाम जपें और उसी दिन एक अनुशासित काम पूरा करें",
            "mr": "दुर्गेचे नाम जपा आणि त्याच दिवशी एक शिस्तबद्ध काम पूर्ण करा",
        },
    ),
    "Ketu": (
        "Ganesha",
        "Tuesday",
        {
            "en": "recite a Ganesha name before starting a demanding task",
            "hi": "कठिन काम शुरू करने से पहले गणेश का नाम जपें",
            "mr": "कठीण काम सुरू करण्यापूर्वी गणेशाचे नाम जपा",
        },
    ),
}

_DEITY = {
    "Surya": ("Surya", "सूर्य", "सूर्य"),
    "Shiva": ("Shiva", "शिव", "शिव"),
    "Hanuman": ("Hanuman", "हनुमान", "हनुमान"),
    "Vishnu": ("Vishnu", "विष्णु", "विष्णू"),
    "Brihaspati": ("Brihaspati", "बृहस्पति", "बृहस्पती"),
    "Lakshmi": ("Lakshmi", "लक्ष्मी", "लक्ष्मी"),
    "Shani": ("Shani", "शनि", "शनी"),
    "Durga": ("Durga", "दुर्गा", "दुर्गा"),
    "Ganesha": ("Ganesha", "गणेश", "गणेश"),
}


def _say(lang: str, en: str, hi: str, mr: str) -> str:
    return {"en": en, "hi": hi, "mr": mr}[lang]


def _tpl(section: str, key: str, lang: str, **kwargs: object) -> str:
    raw = str(_DATA[section][key][_LANG_IDX[lang]])
    return raw.format(**kwargs) if kwargs else raw


def _line(key: str, lang: str, **kwargs: object) -> str:
    return _tpl("lines", key, lang, **kwargs)


def _g(value: object, lang: str) -> str:
    return str(gloss(value, lang))


def _planet(chart: ChartResponse, name: str) -> PlanetPosition:
    return next(p for p in chart.planets if p.planet == name)


def _house_sign(lagna_index: int, house: int) -> str:
    return RASHI_NAMES[(lagna_index - 1 + house - 1) % 12]


def _lord(chart: ChartResponse, house: int) -> tuple[str, PlanetPosition]:
    sign = _house_sign(chart.lagna_sign_index, house)
    name = _LORDS[sign]
    return sign, _planet(chart, name)


def _matter(house: int, lang: str) -> str:
    return _tpl("matter", str(house), lang)


def _where(chart: ChartResponse, planet: PlanetPosition, lang: str) -> str:
    del chart
    base = _line(
        "where",
        lang,
        planet=_g(planet.planet, lang),
        sign=_g(planet.sign_name, lang),
        house=planet.house,
        nak=_g(planet.nakshatra_name, lang),
        pada=planet.pada,
        d9=_g(planet.navamsa_sign_name, lang),
    )
    tail = _line("retro_yes" if planet.is_retrograde else "retro_no", lang)
    return base + tail


def _tone(houses: list[int], lang: str) -> str:
    key = "tone_pressure" if any(h in _PRESSURE for h in houses) else "tone_support"
    return _line(key, lang)


def _gochara(transits: dict[str, object], lang: str) -> str:
    jh = int(str(transits["jupiter_house_from_moon"]))
    sh = int(str(transits["saturn_house_from_moon"]))
    jup = _line("jup_easy" if jh in _JUPITER_EASY else "jup_hard", lang)
    sat = _line("sat_easy" if sh in _SATURN_EASY else "sat_hard", lang)
    return f"{jup} {sat}"


def _deity(name: str, lang: str) -> str:
    en, hi, mr = _DEITY[name]
    return _say(lang, en, hi, mr)


def _observance(chart: ChartResponse, planet_name: str, lang: str) -> str:
    planet = _planet(chart, planet_name)
    deity, weekday, practice = _REMEDY[planet_name]
    return _line(
        "observance",
        lang,
        planet=_g(planet_name, lang),
        house=planet.house,
        deity=_deity(deity, lang),
        weekday=_g(weekday, lang),
        practice=practice[lang],
        matter=_matter(planet.house, lang),
    )


def _anchor_and_period(chart: ChartResponse, dasha: dict[str, object], lang: str) -> str:
    moon = _planet(chart, "Moon")
    md = str(dasha["active_mahadasha"])
    ad = str(dasha["active_antardasha"])
    pd = str(dasha.get("active_pratyantardasha") or ad)
    return " ".join(
        (
            _line(
                "chart_anchor",
                lang,
                lagna=_g(chart.lagna_sign_name, lang),
                moon_sign=_g(moon.sign_name, lang),
                moon_nak=_g(moon.nakshatra_name, lang),
                moon_pada=moon.pada,
                moon_d9=_g(moon.navamsa_sign_name, lang),
            ),
            _line(
                "period_full",
                lang,
                md=_g(md, lang),
                ad=_g(ad, lang),
                pd=_g(pd, lang),
                ad_end=dasha["antardasha_end_date"],
            ),
        )
    )


def _outlook(
    chart: ChartResponse,
    dasha: dict[str, object],
    transits: dict[str, object],
    lang: str,
) -> str:
    md = str(dasha["active_mahadasha"])
    ad = str(dasha["active_antardasha"])
    parts = [
        _anchor_and_period(chart, dasha, lang),
        _where(chart, _planet(chart, md), lang),
    ]
    if ad != md:
        parts.append(_where(chart, _planet(chart, ad), lang))
    parts.append(
        _line(
            "jup_sat_transit",
            lang,
            jup_sign=_g(transits["jupiter_transit_sign"], lang),
            jup_h=transits["jupiter_house_from_moon"],
            sat_sign=_g(transits["saturn_transit_sign"], lang),
            sat_h=transits["saturn_house_from_moon"],
        )
    )
    parts.append(_gochara(transits, lang))
    return " ".join(parts)


def _career(chart: ChartResponse, lang: str) -> str:
    sign, lord = _lord(chart, 10)
    sun = _planet(chart, "Sun")
    parts = [
        _line("career_open", lang, sign=_g(sign, lang), lord=_g(lord.planet, lang)),
        _where(chart, lord, lang),
    ]
    if sun.planet != lord.planet:
        parts.append(_line("sun_role", lang))
        parts.append(_where(chart, sun, lang))
    parts.append(
        _line(
            "lord_matter",
            lang,
            lord=_g(lord.planet, lang),
            house=lord.house,
            matter=_matter(lord.house, lang),
        )
    )
    parts.append(_tone([lord.house, sun.house], lang))
    return " ".join(parts)


def _relationship(chart: ChartResponse, lang: str) -> str:
    seventh, lord = _lord(chart, 7)
    fifth, fifth_lord = _lord(chart, 5)
    venus = _planet(chart, "Venus")
    parts = [
        _line(
            "rel_open",
            lang,
            seventh=_g(seventh, lang),
            lord=_g(lord.planet, lang),
        ),
        _where(chart, lord, lang),
    ]
    if venus.planet == lord.planet:
        parts.append(_line("venus_same_lord", lang, d9=_g(venus.navamsa_sign_name, lang)))
    else:
        parts.append(_line("venus_role", lang))
        parts.append(_where(chart, venus, lang))
    parts.append(
        _line(
            "fifth_open",
            lang,
            fifth=_g(fifth, lang),
            fifth_lord=_g(fifth_lord.planet, lang),
        )
    )
    if fifth_lord.planet not in {lord.planet, venus.planet}:
        parts.append(_where(chart, fifth_lord, lang))
    parts.append(_tone([lord.house, venus.house, fifth_lord.house], lang))
    return " ".join(parts)


def _money(chart: ChartResponse, transits: dict[str, object], lang: str) -> str:
    second, second_lord = _lord(chart, 2)
    eleventh, eleventh_lord = _lord(chart, 11)
    jupiter = _planet(chart, "Jupiter")
    jh = int(str(transits["jupiter_house_from_moon"]))
    parts = [
        _line(
            "money_open",
            lang,
            second=_g(second, lang),
            second_lord=_g(second_lord.planet, lang),
            eleventh=_g(eleventh, lang),
            eleventh_lord=_g(eleventh_lord.planet, lang),
        ),
        _where(chart, second_lord, lang),
    ]
    if eleventh_lord.planet != second_lord.planet:
        parts.append(_where(chart, eleventh_lord, lang))
    if jupiter.planet not in {second_lord.planet, eleventh_lord.planet}:
        parts.append(_line("natal_jup", lang))
        parts.append(_where(chart, jupiter, lang))
    parts.append(
        _line(
            "transit_jup_money",
            lang,
            jup_sign=_g(transits["jupiter_transit_sign"], lang),
            jup_h=jh,
            matter=_matter(jh, lang),
        )
    )
    parts.append(_tone([second_lord.house, eleventh_lord.house, jupiter.house], lang))
    return " ".join(parts)


def _home(chart: ChartResponse, transits: dict[str, object], lang: str) -> str:
    sign, lord = _lord(chart, 4)
    moon = _planet(chart, "Moon")
    sh = int(str(transits["saturn_house_from_moon"]))
    parts = [
        _line("home_open", lang, sign=_g(sign, lang), lord=_g(lord.planet, lang)),
        _where(chart, lord, lang),
    ]
    if moon.planet == lord.planet:
        parts.append(
            _line(
                "moon_same_fourth",
                lang,
                matter=_matter(moon.house, lang),
                d9=_g(moon.navamsa_sign_name, lang),
            )
        )
    else:
        parts.append(_where(chart, moon, lang))
    parts.append(
        _line(
            "sat_home",
            lang,
            sat_sign=_g(transits["saturn_transit_sign"], lang),
            sat_h=sh,
            matter=_matter(sh, lang),
        )
    )
    parts.append(_tone([lord.house, moon.house], lang))
    return " ".join(parts)


def _months(
    months: tuple[str, str, str],
    dasha: dict[str, object],
    transits: dict[str, object],
    lang: str,
) -> str:
    md = _g(dasha["active_mahadasha"], lang)
    ad = _g(dasha["active_antardasha"], lang)
    jup = _g(transits["jupiter_transit_sign"], lang)
    sat = _g(transits["saturn_transit_sign"], lang)
    focuses = (
        _say(lang, "career and reputation", "करियर और प्रतिष्ठा", "करिअर आणि प्रतिष्ठा"),
        _say(lang, "money and partnership", "धन और साझेदारी", "धन आणि भागीदारी"),
        _say(
            lang,
            "home, children, and steady follow-through",
            "घर, संतान और स्थिर अनुसरण",
            "घर, अपत्य आणि सातत्यपूर्ण काम",
        ),
    )
    lines = []
    for name, focus in zip(months, focuses, strict=True):
        local = _MONTHS[name][_LANG_IDX[lang]]
        lines.append(
            _line(
                "month_line",
                lang,
                month=local,
                md=md,
                ad=ad,
                jup=jup,
                sat=sat,
                focus=focus,
            )
        )
    return " ".join(lines)


def _check(text: str, lang: str) -> str:
    verify_text(text, languages=(lang,))
    return text


def year_reading(
    chart: ChartResponse,
    dasha: dict[str, object],
    transits: dict[str, object],
    lang: LanguageCode,
) -> str:
    close = _line("year_close", lang)
    return _check(f"{_outlook(chart, dasha, transits, lang)} {close}", lang)


def quarter_reading(
    chart: ChartResponse,
    dasha: dict[str, object],
    transits: dict[str, object],
    lang: LanguageCode,
    months: tuple[str, str, str],
) -> str:
    md = str(dasha["active_mahadasha"])
    ad = str(dasha["active_antardasha"])
    parts = [
        _say(lang, "Outlook.", "समग्र दृष्टि।", "एकूण दृष्टी."),
        _outlook(chart, dasha, transits, lang),
        _career(chart, lang),
        _relationship(chart, lang),
        _money(chart, transits, lang),
        _home(chart, transits, lang),
        _months(months, dasha, transits, lang),
        _say(lang, "Observance.", "उपासना।", "उपासना."),
        _observance(chart, md, lang),
    ]
    if ad != md and _planet(chart, ad).house in _PRESSURE:
        parts.append(_observance(chart, ad, lang))
    return _check(" ".join(parts), lang)


def area_reading(
    chart: ChartResponse,
    dasha: dict[str, object],
    transits: dict[str, object],
    lang: LanguageCode,
    area: str,
) -> str:
    body = {
        "career": _career(chart, lang),
        "relationships": _relationship(chart, lang),
        "finances": _money(chart, transits, lang),
        "home": _home(chart, transits, lang),
    }[area]
    house_for_area = {"career": 10, "relationships": 7, "finances": 2, "home": 4}[area]
    _, area_lord = _lord(chart, house_for_area)
    md = str(dasha["active_mahadasha"])
    parts = [_anchor_and_period(chart, dasha, lang)]
    if md != area_lord.planet:
        parts.append(_where(chart, _planet(chart, md), lang))
    parts.append(body)
    parts.append(_observance(chart, area_lord.planet, lang))
    return _check(" ".join(parts), lang)


def area_pro_reading(
    chart: ChartResponse,
    dasha: dict[str, object],
    transits: dict[str, object],
    lang: LanguageCode,
    area: str,
) -> str:
    house_for_area = {"career": 10, "relationships": 7, "finances": 2, "home": 4}[area]
    karaka_name = {
        "career": "Sun",
        "relationships": "Venus",
        "finances": "Jupiter",
        "home": "Moon",
    }[area]
    label = {
        "career": _say(lang, "10th-house Career", "दशम भाव करियर", "दशम भाव करिअर"),
        "relationships": _say(lang, "7th-house Partnership", "सप्तम भाव संबंध", "सप्तम भाव नाते"),
        "finances": _say(lang, "2nd/11th-house Finance", "द्वितीय/एकादश धन", "द्वितीय/एकादश धन"),
        "home": _say(lang, "4th-house Domestic", "चतुर्थ भाव गृह", "चतुर्थ भाव गृह"),
    }[area]
    sign, lord = _lord(chart, house_for_area)
    karaka = _planet(chart, karaka_name)
    moon = _planet(chart, "Moon")
    md = str(dasha["active_mahadasha"])
    ad = str(dasha["active_antardasha"])
    pd = str(dasha.get("active_pratyantardasha") or ad)
    return _check(
        _line(
            "area_pro",
            lang,
            area_label=label,
            lagna=_g(chart.lagna_sign_name, lang),
            moon_sign=_g(moon.sign_name, lang),
            moon_nak=_g(moon.nakshatra_name, lang),
            moon_pada=moon.pada,
            sign=_g(sign, lang),
            lord=_g(lord.planet, lang),
            lord_h=lord.house,
            lord_sign=_g(lord.sign_name, lang),
            lord_nak=_g(lord.nakshatra_name, lang),
            lord_pada=lord.pada,
            lord_d9=_g(lord.navamsa_sign_name, lang),
            karaka=_g(karaka.planet, lang),
            karaka_h=karaka.house,
            karaka_sign=_g(karaka.sign_name, lang),
            karaka_d9=_g(karaka.navamsa_sign_name, lang),
            md=_g(md, lang),
            ad=_g(ad, lang),
            pd=_g(pd, lang),
            ad_end=dasha["antardasha_end_date"],
            jup_sign=_g(transits["jupiter_transit_sign"], lang),
            jup_h=transits["jupiter_house_from_moon"],
            sat_sign=_g(transits["saturn_transit_sign"], lang),
            sat_h=transits["saturn_house_from_moon"],
        ),
        lang,
    )


def _transit_moon_lagna_house(chart: ChartResponse, transits: dict[str, object]) -> int:
    t_sign = str(transits["moon_transit_sign"])
    t_idx = RASHI_NAMES.index(t_sign) + 1
    return ((t_idx - chart.lagna_sign_index) % 12) + 1


def daily_reading(
    chart: ChartResponse,
    panchang: dict[str, object],
    transits: dict[str, object],
    lang: LanguageCode,
    dasha: dict[str, object] | None = None,
) -> str:
    moon = _planet(chart, "Moon")
    m_house = int(str(transits["moon_house_from_natal_moon"]))
    l_house = _transit_moon_lagna_house(chart, transits)
    vara_raw = str(panchang["vara"])
    vara_lord_name = _VARA_LORDS.get(vara_raw, "Sun")
    vara_lord = _planet(chart, vara_lord_name)
    who = chart.input_summary.name
    parts = [
        _line(
            "daily_open",
            lang,
            who=who,
            lagna=_g(chart.lagna_sign_name, lang),
            moon_sign=_g(moon.sign_name, lang),
            moon_nak=_g(moon.nakshatra_name, lang),
            moon_pada=moon.pada,
            date=panchang["date"],
            vara=_g(vara_raw, lang),
            tithi=_g(panchang["tithi"], lang),
            yoga=_g(panchang["yoga"], lang),
        ),
        _line(
            "daily_moon",
            lang,
            t_sign=_g(transits["moon_transit_sign"], lang),
            t_nak=_g(transits["moon_transit_nakshatra"], lang),
            m_house=m_house,
            m_matter=_matter(m_house, lang),
            l_house=l_house,
            lagna=_g(chart.lagna_sign_name, lang),
            l_matter=_matter(l_house, lang),
        ),
        _line(
            "daily_vara",
            lang,
            vara_lord=_g(vara_lord.planet, lang),
            vara_where=_where(chart, vara_lord, lang),
            vara_h=vara_lord.house,
            vara_matter=_matter(vara_lord.house, lang),
        ),
    ]
    if dasha is not None:
        md = str(dasha["active_mahadasha"])
        ad = str(dasha["active_antardasha"])
        pd = str(dasha.get("active_pratyantardasha") or ad)
        parts.append(
            _line(
                "period_full",
                lang,
                md=_g(md, lang),
                ad=_g(ad, lang),
                pd=_g(pd, lang),
                ad_end=dasha["antardasha_end_date"],
            )
        )
    parts.append(_tone([m_house, l_house, vara_lord.house], lang))
    parts.append(_gochara(transits, lang))
    parts.append(_observance(chart, vara_lord_name, lang))
    return _check(" ".join(parts), lang)


def daily_pro_reading(
    chart: ChartResponse,
    panchang: dict[str, object],
    transits: dict[str, object],
    lang: LanguageCode,
    dasha: dict[str, object] | None = None,
) -> str:
    moon = _planet(chart, "Moon")
    m_house = int(str(transits["moon_house_from_natal_moon"]))
    l_house = _transit_moon_lagna_house(chart, transits)
    vara_raw = str(panchang["vara"])
    vara_lord = _planet(chart, _VARA_LORDS.get(vara_raw, "Sun"))
    if dasha is not None:
        md = _g(dasha["active_mahadasha"], lang)
        ad = _g(dasha["active_antardasha"], lang)
        pd = _g(dasha.get("active_pratyantardasha") or dasha["active_antardasha"], lang)
        dasha_tag = f"Vimshottari {md}-{ad}-{pd}"
    else:
        dasha_tag = _g(vara_raw, lang)
    return _check(
        _line(
            "daily_pro",
            lang,
            lagna=_g(chart.lagna_sign_name, lang),
            moon_sign=_g(moon.sign_name, lang),
            moon_nak=_g(moon.nakshatra_name, lang),
            moon_pada=moon.pada,
            t_sign=_g(transits["moon_transit_sign"], lang),
            t_nak=_g(transits["moon_transit_nakshatra"], lang),
            m_house=m_house,
            l_house=l_house,
            vara=_g(vara_raw, lang),
            vara_lord=_g(vara_lord.planet, lang),
            vara_h=vara_lord.house,
            vara_sign=_g(vara_lord.sign_name, lang),
            vara_d9=_g(vara_lord.navamsa_sign_name, lang),
            tithi=_g(panchang["tithi"], lang),
            yoga=_g(panchang["yoga"], lang),
            dasha_tag=dasha_tag,
            jup_sign=_g(transits["jupiter_transit_sign"], lang),
            jup_h=transits["jupiter_house_from_moon"],
            sat_sign=_g(transits["saturn_transit_sign"], lang),
            sat_h=transits["saturn_house_from_moon"],
        ),
        lang,
    )


def daily_area_reading(
    chart: ChartResponse,
    dasha: dict[str, object],
    transits: dict[str, object],
    panchang: dict[str, object],
    lang: LanguageCode,
    area: str,
) -> tuple[str, str]:
    moon = _planet(chart, "Moon")
    m_house = int(str(transits["moon_house_from_natal_moon"]))
    l_house = _transit_moon_lagna_house(chart, transits)
    md = _g(dasha["active_mahadasha"], lang)
    ad = _g(dasha["active_antardasha"], lang)
    pd = _g(dasha.get("active_pratyantardasha") or dasha["active_antardasha"], lang)
    vara_raw = str(panchang["vara"])
    vara_lord = _planet(chart, _VARA_LORDS.get(vara_raw, "Sun"))

    if area == "relationships":
        seventh, lord = _lord(chart, 7)
        venus = _planet(chart, "Venus")
        lead = _line(
            "daily_rel",
            lang,
            date=panchang["date"],
            t_sign=_g(transits["moon_transit_sign"], lang),
            t_nak=_g(transits["moon_transit_nakshatra"], lang),
            m_house=m_house,
            moon_sign=_g(moon.sign_name, lang),
            l_house=l_house,
            lagna=_g(chart.lagna_sign_name, lang),
            l_matter=_matter(l_house, lang),
            tithi=_g(panchang["tithi"], lang),
            seventh=_g(seventh, lang),
            lord=_g(lord.planet, lang),
            lord_h=lord.house,
            lord_d9=_g(lord.navamsa_sign_name, lang),
            venus_sign=_g(venus.sign_name, lang),
            venus_h=venus.house,
            venus_d9=_g(venus.navamsa_sign_name, lang),
            md=md,
            ad=ad,
            pd=pd,
        )
        simple = f"{lead} {_tone([m_house, lord.house, venus.house], lang)}"
    elif area == "career":
        tenth, lord = _lord(chart, 10)
        sun = _planet(chart, "Sun")
        lead = _line(
            "daily_work",
            lang,
            date=panchang["date"],
            vara=_g(vara_raw, lang),
            vara_lord=_g(vara_lord.planet, lang),
            vara_h=vara_lord.house,
            vara_sign=_g(vara_lord.sign_name, lang),
            vara_d9=_g(vara_lord.navamsa_sign_name, lang),
            vara_matter=_matter(vara_lord.house, lang),
            tenth=_g(tenth, lang),
            lord=_g(lord.planet, lang),
            lord_h=lord.house,
            lord_nak=_g(lord.nakshatra_name, lang),
            lord_d9=_g(lord.navamsa_sign_name, lang),
            sun_sign=_g(sun.sign_name, lang),
            sun_h=sun.house,
            l_house=l_house,
            md=md,
            ad=ad,
            pd=pd,
        )
        simple = f"{lead} {_tone([l_house, vara_lord.house, lord.house], lang)}"
    elif area == "finances":
        second, second_lord = _lord(chart, 2)
        eleventh, eleventh_lord = _lord(chart, 11)
        lead = _line(
            "daily_money",
            lang,
            date=panchang["date"],
            t_sign=_g(transits["moon_transit_sign"], lang),
            m_house=m_house,
            m_matter=_matter(m_house, lang),
            l_house=l_house,
            second=_g(second, lang),
            second_lord=_g(second_lord.planet, lang),
            second_h=second_lord.house,
            second_d9=_g(second_lord.navamsa_sign_name, lang),
            eleventh=_g(eleventh, lang),
            eleventh_lord=_g(eleventh_lord.planet, lang),
            eleventh_h=eleventh_lord.house,
            jup_sign=_g(transits["jupiter_transit_sign"], lang),
            jup_h=transits["jupiter_house_from_moon"],
        )
        simple = f"{lead} {_tone([m_house, second_lord.house, eleventh_lord.house], lang)}"
    else:
        fourth, lord = _lord(chart, 4)
        lead = _line(
            "daily_home",
            lang,
            date=panchang["date"],
            fourth=_g(fourth, lang),
            lord=_g(lord.planet, lang),
            lord_h=lord.house,
            lord_sign=_g(lord.sign_name, lang),
            lord_d9=_g(lord.navamsa_sign_name, lang),
            moon_sign=_g(moon.sign_name, lang),
            moon_h=moon.house,
            t_sign=_g(transits["moon_transit_sign"], lang),
            t_nak=_g(transits["moon_transit_nakshatra"], lang),
            sat_sign=_g(transits["saturn_transit_sign"], lang),
            sat_h=transits["saturn_house_from_moon"],
            abhijit=panchang["abhijit_muhurat"],
            rahu=panchang["rahu_kaal"],
        )
        simple = f"{lead} {_tone([m_house, lord.house, moon.house], lang)}"

    pro = area_pro_reading(chart, dasha, transits, lang, area)
    return _check(simple, lang), pro


def transit_note(transits: dict[str, object], lang: str) -> str:
    sade = transits["sade_sati"]
    note = _line(
        "transit_quarter",
        lang,
        jup_sign=_g(transits["jupiter_transit_sign"], lang),
        jup_h=transits["jupiter_house_from_moon"],
        sat_sign=_g(transits["saturn_transit_sign"], lang),
        sat_h=transits["saturn_house_from_moon"],
    )
    if isinstance(sade, dict) and sade.get("is_active"):
        note = f"{note} {_line('sade_sati_note', lang)}"
    return _check(note, lang)
