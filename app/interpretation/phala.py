"""Chart-specific readings from houses, dasha, and gochara.

Every sentence names a planet, sign, or house taken from the calculated chart.
Supportive and pressured houses change the advice. No result is promised.
"""

from __future__ import annotations

from app.api.schemas import ChartResponse, LanguageCode, PlanetPosition
from app.core.constants import RASHI_NAMES
from app.interpretation.guardrails import verify_text
from app.interpretation.terms import gloss

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

# deity, weekday, practice
_REMEDY = {
    "Sun": (
        "Surya",
        "Sunday",
        {
            "en": "offer water to the morning Sun and recite Aditya Hridayam once",
            "hi": "प्रातः सूर्य को जल दें और आदित्य हृदय एक बार पढ़ें",
            "mr": "सकाळी सूर्याला जल द्या आणि आदित्य हृदय एकदा म्हणा",
        },
    ),
    "Moon": (
        "Shiva",
        "Monday",
        {
            "en": "offer water on a Shiva linga and keep the evening quiet",
            "hi": "शिवलिंग पर जल दें और संध्या शांत रखें",
            "mr": "शिवलिंगावर जल द्या आणि संध्या शांत ठेवा",
        },
    ),
    "Mars": (
        "Hanuman",
        "Tuesday",
        {
            "en": "recite the Hanuman Chalisa before a Hanuman or Kartikeya image",
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
            "en": "offer a yellow flower or a banana and recite a Brihaspati name",
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
            "en": "light a sesame-oil lamp for Shani and finish one slow, honest task the same day",
            "hi": "शनि के लिए तिल के तेल का दीप जलाएँ और उसी दिन एक धीमा, ईमानदार काम पूरा करें",
            "mr": "शनीसाठी तीळतेलाचा दीप लावा आणि त्याच दिवशी एक सावकाश, प्रामाणिक काम पूर्ण करा",
        },
    ),
    "Rahu": (
        "Durga",
        "Saturday",
        {
            "en": "recite a Durga name and finish one disciplined task the same day",
            "hi": "दुर्गा का नाम जपें और उसी दिन एक अनुशासित काम पूरा करें",
            "mr": "दुर्गेचे नाम जपा आणि त्याच दिवशी एक शिस्तबद्ध काम पूर्ण करा",
        },
    ),
    "Ketu": (
        "Ganesha",
        "Tuesday",
        {
            "en": "recite a Ganesha name before the difficult task is begun",
            "hi": "कठिन काम शुरू करने से पहले गणेश का नाम जपें",
            "mr": "कठीण काम सुरू करण्यापूर्वी गणेशाचे नाम जपा",
        },
    ),
}


def _say(lang: str, en: str, hi: str, mr: str) -> str:
    return {"en": en, "hi": hi, "mr": mr}[lang]


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
    return _say(
        lang,
        {
            1: "the body, personal direction, and how people meet you",
            2: "savings, family resources, and speech",
            3: "effort, skill, siblings, and short journeys",
            4: "home, the mother, and emotional rest",
            5: "children, study, affection, and creative work",
            6: "service, competition, debts, and daily obstacles",
            7: "marriage, partnership, and one-to-one agreements",
            8: "shared resources and changes that arrive without much warning",
            9: "teachers, long journeys, and fortune",
            10: "career, public duty, and reputation",
            11: "income, gains, and the circle that supports you",
            12: "expenses, rest, and time away from home",
        }[house],
        {
            1: "शरीर, व्यक्तिगत दिशा और लोगों के सामने आपका ठहराव",
            2: "बचत, पारिवारिक साधन और वाणी",
            3: "परिश्रम, कौशल, सहोदर और छोटी यात्रा",
            4: "घर, माता और मानसिक विश्राम",
            5: "संतान, अध्ययन, स्नेह और रचनात्मक काम",
            6: "सेवा, प्रतिस्पर्धा, ऋण और रोज के व्यवधान",
            7: "विवाह, साझेदारी और आमने-सामने के समझौते",
            8: "साझे साधन और वे परिवर्तन जो कम चेतावनी के साथ आते हैं",
            9: "गुरु, लंबी यात्रा और भाग्य",
            10: "करियर, सार्वजनिक कर्तव्य और प्रतिष्ठा",
            11: "आय, लाभ और साथ देने वाला वृत्त",
            12: "खर्च, विश्राम और घर से दूर का समय",
        }[house],
        {
            1: "शरीर, वैयक्तिक दिशा आणि लोकांसमोर तुमचे ठराविक रूप",
            2: "बचत, कौटुंबिक साधने आणि वाणी",
            3: "परिश्रम, कौशल्य, भावंडे आणि छोट्या प्रवास",
            4: "घर, माता आणि मानसिक विश्रांती",
            5: "अपत्य, अभ्यास, स्नेह आणि निर्मितीचे काम",
            6: "सेवा, स्पर्धा, कर्ज आणि रोजचे अडथळे",
            7: "विवाह, भागीदारी आणि समोरासमोरचे करार",
            8: "सामायिक साधने आणि कमी सूचना देऊन येणारे बदल",
            9: "गुरु, लांब प्रवास आणि भाग्य",
            10: "करिअर, सार्वजनिक कर्तव्य आणि प्रतिष्ठा",
            11: "उत्पन्न, लाभ आणि साथ देणारे वर्तुळ",
            12: "खर्च, विश्रांती आणि घरापासून दूरचा काळ",
        }[house],
    )


def _where(chart: ChartResponse, planet: PlanetPosition, lang: str) -> str:
    base = _say(
        lang,
        f"{_g(planet.planet, lang)} is in {_g(planet.sign_name, lang)}, house {planet.house}, nakshatra {_g(planet.nakshatra_name, lang)}, pada {planet.pada}",
        f"{_g(planet.planet, lang)} {_g(planet.sign_name, lang)} में है, भाव {planet.house}, नक्षत्र {_g(planet.nakshatra_name, lang)}, चरण {planet.pada}",
        f"{_g(planet.planet, lang)} {_g(planet.sign_name, lang)} मध्ये आहे, भाव {planet.house}, नक्षत्र {_g(planet.nakshatra_name, lang)}, चरण {planet.pada}",
    )
    if not planet.is_retrograde:
        return base + _say(lang, ".", "।", ".")
    return base + _say(
        lang,
        ". It is retrograde, so the result tends to ripen after review.",
        "। यह वक्री है, इसलिए फल पुनरावलोकन के बाद पकता है।",
        ". तो वक्री आहे, म्हणून फळ पुनरावलोकनानंतर पक्व होते.",
    )


def _tone(houses: list[int], lang: str) -> str:
    if any(house in _PRESSURE for house in houses):
        return _say(
            lang,
            "Be cautious here. Take protective measures before a large step, and do not rush. This configuration is not favorable for haste.",
            "यहाँ सावधानी रखें। बड़े कदम से पहले रक्षात्मक उपाय करें और जल्दबाजी न करें। यह ग्रह स्थिति जल्दबाजी के लिए अनुकूल नहीं है।",
            "येथे सावध राहा. मोठ्या पावलापूर्वी संरक्षणात्मक उपाय करा आणि घाई करू नका. ही ग्रहस्थिती घाईसाठी अनुकूल नाही.",
        )
    return _say(
        lang,
        "This configuration is supportive. Use it for the matters named here, and still check the practical details before you commit.",
        "यह ग्रह स्थिति सहायक है। इसे यहाँ बताए विषयों के लिए उपयोग करें, और वचन से पहले व्यावहारिक विवरण जाँच लें।",
        "ही ग्रहस्थिती सहाय्यक आहे. येथे सांगितलेल्या विषयांसाठी तिचा वापर करा, आणि वचन देण्यापूर्वी व्यावहारिक तपशील तपासा.",
    )


def _gochara(transits: dict[str, object], lang: str) -> str:
    jh = int(str(transits["jupiter_house_from_moon"]))
    sh = int(str(transits["saturn_house_from_moon"]))
    jup = _say(
        lang,
        "Jupiter's transit is in a classically supportive house from the birth Moon."
        if jh in _JUPITER_EASY
        else "Jupiter's transit is not in a classically supportive house from the birth Moon, so growth asks for patience.",
        "बृहस्पति का गोचर जन्म चंद्र से शास्त्रीय रूप से सहायक भाव में है।"
        if jh in _JUPITER_EASY
        else "बृहस्पति का गोचर जन्म चंद्र से शास्त्रीय रूप से सहायक भाव में नहीं है, इसलिए वृद्धि के लिए धैर्य चाहिए।",
        "गुरूचे गोचर जन्म चंद्रापासून शास्त्रीय सहाय्यक भावात आहे."
        if jh in _JUPITER_EASY
        else "गुरूचे गोचर जन्म चंद्रापासून शास्त्रीय सहाय्यक भावात नाही, म्हणून वाढीसाठी धीर हवा.",
    )
    sat = _say(
        lang,
        "Saturn's transit is in a house where steady labour is rewarded."
        if sh in _SATURN_EASY
        else "Saturn's transit asks for slower commitments and cleaner routines.",
        "शनि का गोचर उस भाव में है जहाँ स्थिर परिश्रम फल देता है।"
        if sh in _SATURN_EASY
        else "शनि का गोचर धीमे वचन और साफ दिनचर्या माँगता है।",
        "शनीचे गोचर त्या भावात आहे जिथे स्थिर परिश्रम फळ देते."
        if sh in _SATURN_EASY
        else "शनीचे गोचर सावकाश वचन आणि स्वच्छ दिनक्रम मागते.",
    )
    return f"{jup} {sat}"


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


def _deity(name: str, lang: str) -> str:
    en, hi, mr = _DEITY[name]
    return _say(lang, en, hi, mr)


def _observance(chart: ChartResponse, planet_name: str, lang: str) -> str:
    planet = _planet(chart, planet_name)
    deity, weekday, practice = _REMEDY[planet_name]
    shown = _deity(deity, lang)
    return _say(
        lang,
        f"For {_g(planet_name, lang)} in house {planet.house}, the fitting observance is {shown} on {_g(weekday, lang)}: {practice[lang]}. This is aimed at {_matter(planet.house, lang)}. The practice asks for no purchase, and it does not force a result.",
        f"भाव {planet.house} में {_g(planet_name, lang)} के लिए उपयुक्त उपासना {_g(weekday, lang)} को {shown} की है: {practice[lang]}। यह {_matter(planet.house, lang)} के लिए है। इस अभ्यास में कोई खरीद नहीं है, और यह फल को बाध्य नहीं करता।",
        f"भाव {planet.house} मधील {_g(planet_name, lang)} साठी योग्य उपासना {_g(weekday, lang)} रोजी {shown} ची आहे: {practice[lang]}. हे {_matter(planet.house, lang)} साठी आहे. या अभ्यासात खरेदी नाही, आणि तो फळाला बंधनकारक करत नाही.",
    )


def _outlook(chart: ChartResponse, dasha: dict[str, object], transits: dict[str, object], lang: str) -> str:
    md = str(dasha["active_mahadasha"])
    ad = str(dasha["active_antardasha"])
    pd = str(dasha["active_pratyantardasha"])
    moon = _planet(chart, "Moon")
    return " ".join(
        (
            _say(
                lang,
                f"Lagna is {_g(chart.lagna_sign_name, lang)}. Birth Moon is {_g(moon.sign_name, lang)}, nakshatra {_g(moon.nakshatra_name, lang)}, pada {moon.pada}.",
                f"लग्न {_g(chart.lagna_sign_name, lang)} है। जन्म चंद्र {_g(moon.sign_name, lang)} है, नक्षत्र {_g(moon.nakshatra_name, lang)}, चरण {moon.pada}।",
                f"लग्न {_g(chart.lagna_sign_name, lang)} आहे. जन्म चंद्र {_g(moon.sign_name, lang)} आहे, नक्षत्र {_g(moon.nakshatra_name, lang)}, चरण {moon.pada}.",
            ),
            _say(
                lang,
                f"The period is {_g(md, lang)} Mahadasha, {_g(ad, lang)} Antardasha, {_g(pd, lang)} Pratyantar, through {dasha['antardasha_end_date']}.",
                f"काल {_g(md, lang)} महादशा, {_g(ad, lang)} अंतर्दशा, {_g(pd, lang)} प्रत्यंतर है, {dasha['antardasha_end_date']} तक।",
                f"काळ {_g(md, lang)} महादशा, {_g(ad, lang)} अंतरदशा, {_g(pd, lang)} प्रत्यंतर आहे, {dasha['antardasha_end_date']} पर्यंत.",
            ),
            _where(chart, _planet(chart, md), lang),
            _where(chart, _planet(chart, ad), lang),
            _say(
                lang,
                f"Jupiter transits {_g(transits['jupiter_transit_sign'], lang)}, house {transits['jupiter_house_from_moon']} from the birth Moon. Saturn transits {_g(transits['saturn_transit_sign'], lang)}, house {transits['saturn_house_from_moon']} from that Moon.",
                f"बृहस्पति {_g(transits['jupiter_transit_sign'], lang)} से गोचर कर रहा है, जन्म चंद्र से भाव {transits['jupiter_house_from_moon']}। शनि {_g(transits['saturn_transit_sign'], lang)} में है, उसी चंद्र से भाव {transits['saturn_house_from_moon']}।",
                f"गुरू {_g(transits['jupiter_transit_sign'], lang)} मधून गोचर करतो, जन्म चंद्रापासून भाव {transits['jupiter_house_from_moon']}. शनी {_g(transits['saturn_transit_sign'], lang)} मध्ये आहे, त्याच चंद्रापासून भाव {transits['saturn_house_from_moon']}.",
            ),
            _gochara(transits, lang),
        )
    )


def _career(chart: ChartResponse, lang: str) -> str:
    sign, lord = _lord(chart, 10)
    sun = _planet(chart, "Sun")
    return " ".join(
        (
            _say(
                lang,
                f"Career. The 10th house falls in {_g(sign, lang)} and its lord is {_g(lord.planet, lang)}.",
                f"करियर। दशम भाव {_g(sign, lang)} में पड़ता है और उसका स्वामी {_g(lord.planet, lang)} है।",
                f"करिअर. दशम भाव {_g(sign, lang)} मध्ये येतो आणि त्याचा स्वामी {_g(lord.planet, lang)} आहे.",
            ),
            _where(chart, lord, lang),
            _say(
                lang,
                "The Sun carries authority and public role.",
                "सूर्य अधिकार और सार्वजनिक भूमिका का कारक है।",
                "सूर्य अधिकार आणि सार्वजनिक भूमिकेचा कारक आहे.",
            ),
            _where(chart, sun, lang),
            _say(
                lang,
                f"The lord's house describes {_matter(lord.house, lang)}.",
                f"स्वामी का भाव {_matter(lord.house, lang)} बताता है।",
                f"स्वामीचा भाव {_matter(lord.house, lang)} सांगतो.",
            ),
            _tone([lord.house, sun.house], lang),
        )
    )


def _relationship(chart: ChartResponse, lang: str) -> str:
    seventh, lord = _lord(chart, 7)
    fifth, fifth_lord = _lord(chart, 5)
    venus = _planet(chart, "Venus")
    return " ".join(
        (
            _say(
                lang,
                f"Relationships, marriage, and children. The 7th house falls in {_g(seventh, lang)} and its lord is {_g(lord.planet, lang)}.",
                f"संबंध, विवाह और संतान। सप्तम भाव {_g(seventh, lang)} में पड़ता है और उसका स्वामी {_g(lord.planet, lang)} है।",
                f"नाते, विवाह आणि अपत्य. सप्तम भाव {_g(seventh, lang)} मध्ये येतो आणि त्याचा स्वामी {_g(lord.planet, lang)} आहे.",
            ),
            _where(chart, lord, lang),
            _say(
                lang,
                "Venus carries marriage, comfort, and agreement.",
                "शुक्र विवाह, सुख और समझौते का कारक है।",
                "शुक्र विवाह, सुख आणि कराराचा कारक आहे.",
            ),
            _where(chart, venus, lang),
            _say(
                lang,
                f"The 5th house, for children and affection, falls in {_g(fifth, lang)}.",
                f"संतान और स्नेह का पंचम भाव {_g(fifth, lang)} में पड़ता है।",
                f"अपत्य आणि स्नेहाचा पंचम भाव {_g(fifth, lang)} मध्ये येतो.",
            ),
            _where(chart, fifth_lord, lang),
            _tone([lord.house, venus.house, fifth_lord.house], lang),
        )
    )


def _money(chart: ChartResponse, transits: dict[str, object], lang: str) -> str:
    second, second_lord = _lord(chart, 2)
    eleventh, eleventh_lord = _lord(chart, 11)
    jupiter = _planet(chart, "Jupiter")
    return " ".join(
        (
            _say(
                lang,
                f"Money. The 2nd house falls in {_g(second, lang)} and its lord is {_g(second_lord.planet, lang)}.",
                f"धन। द्वितीय भाव {_g(second, lang)} में पड़ता है और उसका स्वामी {_g(second_lord.planet, lang)} है।",
                f"धन. द्वितीय भाव {_g(second, lang)} मध्ये येतो आणि त्याचा स्वामी {_g(second_lord.planet, lang)} आहे.",
            ),
            _where(chart, second_lord, lang),
            _say(
                lang,
                f"The 11th house falls in {_g(eleventh, lang)} and its lord is {_g(eleventh_lord.planet, lang)}.",
                f"एकादश भाव {_g(eleventh, lang)} में पड़ता है और उसका स्वामी {_g(eleventh_lord.planet, lang)} है।",
                f"एकादश भाव {_g(eleventh, lang)} मध्ये येतो आणि त्याचा स्वामी {_g(eleventh_lord.planet, lang)} आहे.",
            ),
            _where(chart, eleventh_lord, lang),
            _say(
                lang,
                "Natal Jupiter carries increase.",
                "जन्म का बृहस्पति वृद्धि का कारक है।",
                "जन्म कुंडलीतील गुरू वाढीचा कारक आहे.",
            ),
            _where(chart, jupiter, lang),
            _say(
                lang,
                f"By transit, Jupiter is in {_g(transits['jupiter_transit_sign'], lang)}, house {transits['jupiter_house_from_moon']} from the birth Moon.",
                f"गोचर में बृहस्पति {_g(transits['jupiter_transit_sign'], lang)} में है, जन्म चंद्र से भाव {transits['jupiter_house_from_moon']}।",
                f"गोचरात गुरू {_g(transits['jupiter_transit_sign'], lang)} मध्ये आहे, जन्म चंद्रापासून भाव {transits['jupiter_house_from_moon']}.",
            ),
            _tone([second_lord.house, eleventh_lord.house, jupiter.house], lang),
        )
    )


def _home(chart: ChartResponse, transits: dict[str, object], lang: str) -> str:
    sign, lord = _lord(chart, 4)
    moon = _planet(chart, "Moon")
    return " ".join(
        (
            _say(
                lang,
                f"Home and family. The 4th house falls in {_g(sign, lang)} and its lord is {_g(lord.planet, lang)}.",
                f"घर और परिवार। चतुर्थ भाव {_g(sign, lang)} में पड़ता है और उसका स्वामी {_g(lord.planet, lang)} है।",
                f"घर आणि कुटुंब. चतुर्थ भाव {_g(sign, lang)} मध्ये येतो आणि त्याचा स्वामी {_g(lord.planet, lang)} आहे.",
            ),
            _where(chart, lord, lang),
            _where(chart, moon, lang),
            _say(
                lang,
                f"Saturn by transit is in house {transits['saturn_house_from_moon']} from the birth Moon, so domestic plans follow that pace.",
                f"शनि का गोचर जन्म चंद्र से भाव {transits['saturn_house_from_moon']} में है, इसलिए घरेलू योजना उसी गति से चलती है।",
                f"शनीचे गोचर जन्म चंद्रापासून भाव {transits['saturn_house_from_moon']} मध्ये आहे, म्हणून घरातील योजना त्या गतीने चालतात.",
            ),
            _tone([lord.house, moon.house], lang),
        )
    )


def _months(months: tuple[str, str, str], dasha: dict[str, object], transits: dict[str, object], lang: str) -> str:
    md = _g(dasha["active_mahadasha"], lang)
    ad = _g(dasha["active_antardasha"], lang)
    jup = _g(transits["jupiter_transit_sign"], lang)
    sat = _g(transits["saturn_transit_sign"], lang)
    focuses = (
        _say(lang, "career and reputation", "करियर और प्रतिष्ठा", "करिअर आणि प्रतिष्ठा"),
        _say(lang, "money and partnership", "धन और साझेदारी", "धन आणि भागीदारी"),
        _say(lang, "home, children, and the care points already named", "घर, संतान और ऊपर बताए सावध बिंदु", "घर, अपत्य आणि वर सांगितलेले सावध मुद्दे"),
    )
    lines = []
    for name, focus in zip(months, focuses, strict=True):
        local = _MONTHS[name][{"en": 0, "hi": 1, "mr": 2}[lang]]
        lines.append(
            _say(
                lang,
                f"{local}. The same {md}-{ad} period applies, with Jupiter in {jup} and Saturn in {sat}. Give this month's working weight to {focus}.",
                f"{local}। वही {md}-{ad} काल लागू है, बृहस्पति {jup} में और शनि {sat} में। इस माह का कार्यभार {focus} पर रखें।",
                f"{local}. तोच {md}-{ad} काळ लागू आहे, गुरू {jup} मध्ये आणि शनी {sat} मध्ये. या महिन्याचा कार्यभार {focus} वर ठेवा.",
            )
        )
    return " ".join(lines)


def _check(text: str, lang: str) -> str:
    verify_text(text, languages=(lang,))
    return text


def year_reading(chart: ChartResponse, dasha: dict[str, object], transits: dict[str, object], lang: LanguageCode) -> str:
    close = _say(
        lang,
        "The quarters below follow this same birth chart. Each one uses the dasha and the Jupiter and Saturn positions of that quarter for career, partnership, children, money, and home.",
        "नीचे की तिमाहियाँ इसी जन्म कुंडली से बनती हैं। हर तिमाही उस काल की दशा और बृहस्पति-शनि की स्थिति से करियर, साझेदारी, संतान, धन और घर बताती है।",
        "खालील तिमाही याच जन्म कुंडलीतून येतात. प्रत्येक तिमाही त्या काळातील दशा आणि गुरू-शनीच्या स्थितीतून करिअर, भागीदारी, अपत्य, धन आणि घर सांगते.",
    )
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


def _header(chart: ChartResponse, dasha: dict[str, object], lang: str) -> str:
    moon = _planet(chart, "Moon")
    md = str(dasha["active_mahadasha"])
    ad = str(dasha["active_antardasha"])
    return " ".join(
        (
            _say(
                lang,
                f"Lagna is {_g(chart.lagna_sign_name, lang)}. Birth Moon is {_g(moon.sign_name, lang)}, nakshatra {_g(moon.nakshatra_name, lang)}, pada {moon.pada}.",
                f"लग्न {_g(chart.lagna_sign_name, lang)} है। जन्म चंद्र {_g(moon.sign_name, lang)} है, नक्षत्र {_g(moon.nakshatra_name, lang)}, चरण {moon.pada}।",
                f"लग्न {_g(chart.lagna_sign_name, lang)} आहे. जन्म चंद्र {_g(moon.sign_name, lang)} आहे, नक्षत्र {_g(moon.nakshatra_name, lang)}, चरण {moon.pada}.",
            ),
            _say(
                lang,
                f"The period is {_g(md, lang)} Mahadasha and {_g(ad, lang)} Antardasha.",
                f"काल {_g(md, lang)} महादशा और {_g(ad, lang)} अंतर्दशा है।",
                f"काळ {_g(md, lang)} महादशा आणि {_g(ad, lang)} अंतरदशा आहे.",
            ),
            _where(chart, _planet(chart, md), lang),
        )
    )


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
    md = str(dasha["active_mahadasha"])
    return _check(" ".join((_header(chart, dasha, lang), body, _observance(chart, md, lang))), lang)


def daily_reading(
    chart: ChartResponse,
    panchang: dict[str, object],
    transits: dict[str, object],
    lang: LanguageCode,
) -> str:
    moon = _planet(chart, "Moon")
    house = int(str(transits["moon_house_from_natal_moon"]))
    text = " ".join(
        (
            _say(
                lang,
                f"Today is read from the birth Moon in {_g(moon.sign_name, lang)}, nakshatra {_g(moon.nakshatra_name, lang)}, pada {moon.pada}.",
                f"आज का पठन जन्म चंद्र {_g(moon.sign_name, lang)}, नक्षत्र {_g(moon.nakshatra_name, lang)}, चरण {moon.pada} से है।",
                f"आजचे वाचन जन्म चंद्र {_g(moon.sign_name, lang)}, नक्षत्र {_g(moon.nakshatra_name, lang)}, चरण {moon.pada} पासून आहे.",
            ),
            _say(
                lang,
                f"The Moon now travels through {_g(transits['moon_transit_sign'], lang)}, nakshatra {_g(transits['moon_transit_nakshatra'], lang)}, house {house} from that birth Moon.",
                f"चंद्र इस समय {_g(transits['moon_transit_sign'], lang)} में है, नक्षत्र {_g(transits['moon_transit_nakshatra'], lang)}, उस जन्म चंद्र से भाव {house}।",
                f"चंद्र सध्या {_g(transits['moon_transit_sign'], lang)} मध्ये आहे, नक्षत्र {_g(transits['moon_transit_nakshatra'], lang)}, त्या जन्म चंद्रापासून भाव {house}.",
            ),
            _say(
                lang,
                f"House {house} from the birth Moon describes {_matter(house, lang)}.",
                f"जन्म चंद्र से भाव {house} {_matter(house, lang)} बताता है।",
                f"जन्म चंद्रापासून भाव {house} {_matter(house, lang)} सांगतो.",
            ),
            _tone([house], lang),
            _say(
                lang,
                f"Tithi is {_g(panchang['tithi'], lang)}. Yoga is {_g(panchang['yoga'], lang)}. Vara is {_g(panchang['vara'], lang)}.",
                f"तिथि {_g(panchang['tithi'], lang)} है। योग {_g(panchang['yoga'], lang)} है। वार {_g(panchang['vara'], lang)} है।",
                f"तिथी {_g(panchang['tithi'], lang)} आहे. योग {_g(panchang['yoga'], lang)} आहे. वार {_g(panchang['vara'], lang)} आहे.",
            ),
            _gochara(transits, lang),
        )
    )
    return _check(text, lang)


def transit_note(transits: dict[str, object], lang: str) -> str:
    sade = transits["sade_sati"]
    note = _say(
        lang,
        f"Jupiter in {_g(transits['jupiter_transit_sign'], lang)}, house {transits['jupiter_house_from_moon']} from the birth Moon, and Saturn in {_g(transits['saturn_transit_sign'], lang)}, house {transits['saturn_house_from_moon']} from the birth Moon, colour this quarter.",
        f"बृहस्पति {_g(transits['jupiter_transit_sign'], lang)} में, जन्म चंद्र से भाव {transits['jupiter_house_from_moon']}, और शनि {_g(transits['saturn_transit_sign'], lang)} में, जन्म चंद्र से भाव {transits['saturn_house_from_moon']}, इस तिमाही को रंग देते हैं।",
        f"गुरू {_g(transits['jupiter_transit_sign'], lang)} मध्ये, जन्म चंद्रापासून भाव {transits['jupiter_house_from_moon']}, आणि शनी {_g(transits['saturn_transit_sign'], lang)} मध्ये, जन्म चंद्रापासून भाव {transits['saturn_house_from_moon']}, या तिमाहीला रंग देतात.",
    )
    if isinstance(sade, dict) and sade.get("is_active"):
        note = f"{note} {_say(lang, 'Sade Sati is active from the birth Moon: keep routines steady and do not treat a delay as a final outcome.', 'जन्म चंद्र से साढ़ेसाती सक्रिय है: दिनचर्या स्थिर रखें और देरी को अंतिम फल न मानें।', 'जन्म चंद्रापासून साडेसाती सक्रिय आहे: दिनक्रम स्थिर ठेवा आणि विलंबाला अंतिम फळ मानू नका.')}"
    return _check(note, lang)
