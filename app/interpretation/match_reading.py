"""Partnership reading from both charts, the eight kootas, and both dashas.

The Ashtakoota total stays a Moon-sign score. These sentences name the Lagna,
the 7th house, Venus, Mangal, and the dasha each person is actually running.
"""

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
    _where,
)

_TEMPER = {
    "Aries": (
        "quick action, and impatience when a plan stalls",
        "शीघ्र कर्म, और अटकी योजना पर अधीरता",
        "त्वरित कृती, आणि अडकलेल्या योजनेवर अधीरता",
    ),
    "Taurus": (
        "a steady pace, with care for comfort and resources",
        "स्थिर गति, और सुख तथा साधनों की चिंता",
        "स्थिर गती, आणि सुख व साधनांची काळजी",
    ),
    "Gemini": (
        "learning through talk, and a change of approach when facts change",
        "बातचीत से सीखना, और नए तथ्य पर तरीका बदलना",
        "बोलून शिकणे, आणि नव्या तपशीलावर मार्ग बदलणे",
    ),
    "Cancer": (
        "protection of home and mood, and a long memory for small slights",
        "घर और मन की रक्षा, और छोटी ठेस की लंबी स्मृति",
        "घर आणि मनाचे रक्षण, आणि छोट्या ठेसेची दीर्घ स्मृती",
    ),
    "Leo": (
        "a visible role, and a need for respect inside the household",
        "दिखाई देने वाली भूमिका, और घर में सम्मान की आवश्यकता",
        "दिसणारी भूमिका, आणि घरात मानाची गरज",
    ),
    "Virgo": (
        "attention to detail, and a wish that practical work be done properly",
        "बारीकी पर ध्यान, और व्यावहारिक काम के ठीक होने की चाह",
        "बारकाव्याकडे लक्ष, आणि व्यावहारिक काम नीट व्हावे ही इच्छा",
    ),
    "Libra": (
        "a fair exchange, and discomfort with an unresolved argument",
        "न्यायपूर्ण आदान-प्रदान, और अधूरे विवाद से असहजता",
        "न्याय्य देवाणघेवाण, आणि अपूर्ण वादाबद्दल अस्वस्थता",
    ),
    "Scorpio": (
        "a private inner life, and a full commitment after trust",
        "निजी भीतरी जीवन, और विश्वास के बाद पूरा वचन",
        "खाजगी आतील जीवन, आणि विश्वासानंतर पूर्ण वचन",
    ),
    "Sagittarius": (
        "room for belief, study, and movement",
        "विश्वास, अध्ययन और गति के लिए जगह",
        "श्रद्धा, अभ्यास आणि हालचालीसाठी जागा",
    ),
    "Capricorn": (
        "trust measured by duty kept over time",
        "समय के साथ निभाए कर्तव्य से मापा गया विश्वास",
        "काळानुसार निभावलेल्या कर्तव्यावरून मोजलेला विश्वास",
    ),
    "Aquarius": (
        "loyalty to a principle, and a need for some independence",
        "एक सिद्धांत के प्रति निष्ठा, और कुछ स्वतंत्रता की आवश्यकता",
        "एका तत्त्वाशी निष्ठा, आणि थोड्या स्वतंत्रतेची गरज",
    ),
    "Pisces": (
        "absorption of the other mood, and a need for a quiet edge",
        "दूसरे के मन को ग्रहण करना, और एक शांत किनारे की आवश्यकता",
        "दुसऱ्याच्या मनःस्थितीचा स्वीकार, आणि एका शांत किनाऱ्याची गरज",
    ),
}

_BEHAVIOR = {
    "Sun": (
        "carry a visible duty, and do not demand praise for it",
        "दिखने वाला कर्तव्य निभाएँ, और उसके लिए प्रशंसा की माँग न करें",
        "दिसणारे कर्तव्य निभावा, आणि त्याबद्दल स्तुतीची मागणी करू नका",
    ),
    "Moon": (
        "keep the household rhythm steady, and postpone a hard talk when upset",
        "घर की लय स्थिर रखें, और क्षुब्ध होने पर कठिन बात टालें",
        "घराची लय स्थिर ठेवा, आणि अस्वस्थ असताना कठीण चर्चा पुढे ढकला",
    ),
    "Mars": (
        "pause before answering in anger, and put the heat into a shared task",
        "क्रोध में उत्तर देने से पहले रुकें, और ताप को साझे काम में लगाएँ",
        "रागात उत्तर देण्यापूर्वी थांबा, आणि ताप सामायिक कामात लावा",
    ),
    "Mercury": (
        "say the practical point plainly, and do not win by cleverness",
        "व्यावहारिक बात साफ कहें, और चतुराई से जीतने की कोशिश न करें",
        "व्यावहारिक मुद्दा स्पष्ट सांगा, आणि हुशारीने जिंकण्याचा प्रयत्न करू नका",
    ),
    "Jupiter": (
        "guide without lecturing, and keep a money promise small enough to keep",
        "उपदेश के बिना मार्ग दिखाएँ, और धन का वचन इतना छोटा रखें कि निभ जाए",
        "उपदेशाशिवाय मार्ग दाखवा, आणि धनाचे वचन इतके छोटे ठेवा की ते निभावता येईल",
    ),
    "Venus": (
        "protect courtesy and comfort, and do not hide a conflict under sweetness",
        "शिष्टता और सुख की रक्षा करें, और मधुरता के नीचे संघर्ष न छिपाएँ",
        "सौजन्य आणि सुखाचे रक्षण करा, आणि गोडपणाखाली संघर्ष लपवू नका",
    ),
    "Saturn": (
        "accept a slower pace, and finish one real duty each week",
        "धीमी गति स्वीकारें, और हर सप्ताह एक वास्तविक कर्तव्य पूरा करें",
        "सावकाश गती स्वीकारा, आणि प्रत्येक आठवड्यात एक खरे कर्तव्य पूर्ण करा",
    ),
    "Rahu": (
        "tell the partner before chasing an unusual plan",
        "असामान्य योजना से पहले साथी को बताएँ",
        "असाधारण योजना आधी जोडीदाराला सांगा",
    ),
    "Ketu": (
        "stay present for ordinary household duties instead of withdrawing",
        "हटने के बजाय घर के साधारण कर्तव्य में उपस्थित रहें",
        "माघार घेण्याऐवजी घरातील साध्या कर्तव्यात उपस्थित राहा",
    ),
}


def _check(text: str, lang: str) -> str:
    verify_text(text, languages=(lang,))
    return text


def _temper(sign: str, lang: str) -> str:
    en, hi, mr = _TEMPER[sign]
    return _say(lang, en, hi, mr)


def _behavior(planet: str, lang: str) -> str:
    en, hi, mr = _BEHAVIOR[planet]
    return _say(lang, en, hi, mr)


def _portrait(chart: ChartResponse, dasha: dict[str, object], lang: str) -> str:
    moon = _planet(chart, "Moon")
    sun = _planet(chart, "Sun")
    md = str(dasha["active_mahadasha"])
    ad = str(dasha["active_antardasha"])
    return " ".join(
        (
            _say(
                lang,
                f"Lagna {_g(chart.lagna_sign_name, lang)} shows {_temper(chart.lagna_sign_name, lang)}.",
                f"लग्न {_g(chart.lagna_sign_name, lang)} यह स्वभाव दिखाता है: {_temper(chart.lagna_sign_name, lang)}।",
                f"लग्न {_g(chart.lagna_sign_name, lang)} हा स्वभाव दाखवते: {_temper(chart.lagna_sign_name, lang)}.",
            ),
            _say(
                lang,
                f"The Moon in {_g(moon.sign_name, lang)}, nakshatra {_g(moon.nakshatra_name, lang)}, pada {moon.pada}, sets the emotional habit: {_temper(moon.sign_name, lang)}.",
                f"चंद्र {_g(moon.sign_name, lang)} में, नक्षत्र {_g(moon.nakshatra_name, lang)}, चरण {moon.pada}, भावना की आदत तय करता है: {_temper(moon.sign_name, lang)}।",
                f"चंद्र {_g(moon.sign_name, lang)} मध्ये, नक्षत्र {_g(moon.nakshatra_name, lang)}, चरण {moon.pada}, भावनांची सवय ठरवतो: {_temper(moon.sign_name, lang)}.",
            ),
            _say(
                lang,
                "The Sun shows how this person wants dignity inside the marriage.",
                "सूर्य बताता है कि विवाह में यह व्यक्ति सम्मान कैसे चाहता है।",
                "सूर्य सांगतो की विवाहात ही व्यक्ती मान कसा राखू इच्छिते.",
            ),
            _where(chart, sun, lang),
            _say(
                lang,
                f"Current period: {_g(md, lang)} Mahadasha, {_g(ad, lang)} Antardasha, through {dasha['antardasha_end_date']}.",
                f"वर्तमान काल: {_g(md, lang)} महादशा, {_g(ad, lang)} अंतर्दशा, {dasha['antardasha_end_date']} तक।",
                f"सध्याचा काळ: {_g(md, lang)} महादशा, {_g(ad, lang)} अंतरदशा, {dasha['antardasha_end_date']} पर्यंत.",
            ),
            _where(chart, _planet(chart, md), lang),
        )
    )


def _seventh(chart: ChartResponse, lang: str) -> str:
    sign, lord = _lord(chart, 7)
    venus = _planet(chart, "Venus")
    return " ".join(
        (
            _say(
                lang,
                f"The 7th house falls in {_g(sign, lang)}. Its lord is {_g(lord.planet, lang)}.",
                f"सप्तम भाव {_g(sign, lang)} में है। उसका स्वामी {_g(lord.planet, lang)} है।",
                f"सप्तम भाव {_g(sign, lang)} मध्ये आहे. त्याचा स्वामी {_g(lord.planet, lang)} आहे.",
            ),
            _where(chart, lord, lang),
            _say(
                lang,
                "Venus carries marriage, courtesy, and comfort.",
                "शुक्र विवाह, शिष्टता और सुख का कारक है।",
                "शुक्र विवाह, सौजन्य आणि सुखाचा कारक आहे.",
            ),
            _where(chart, venus, lang),
            _tone([lord.house, venus.house], lang),
        )
    )


def _koota_meaning(name: str, scored: float, maximum: float, lang: str) -> str:
    full = scored + 0.01 >= maximum
    points = _say(
        lang,
        f"{name} scores {scored:g} of {maximum:g}.",
        f"{name} में {scored:g} में से {maximum:g} अंक हैं।",
        f"{name} मध्ये {maximum:g} पैकी {scored:g} गुण आहेत.",
    )
    detail = {
        "Varna": _say(
            lang,
            "The two Moon signs share a work rhythm."
            if full
            else "One Moon sign sets the work pace more often. Name that pace instead of treating it as a flaw.",
            "दोनों चंद्र राशियों की कार्य-लय मिलती है।"
            if full
            else "एक चंद्र राशि काम की गति अधिक तय करती है। उसे दोष मानने के बजाय नाम देकर रखें।",
            "दोन्ही चंद्र राशींची कामाची लय जुळते."
            if full
            else "एक चंद्र राशी कामाची गती अधिक ठरवते. तिला दोष न मानता नाव देऊन ठेवा.",
        ),
        "Vashya": _say(
            lang,
            "Mutual support between the Moon signs comes readily."
            if full
            else "Support between the Moon signs needs a repeated, deliberate habit.",
            "चंद्र राशियों का परस्पर सहारा सहज बनता है।"
            if full
            else "चंद्र राशियों का सहारा बार-बार के सचेत अभ्यास से बनता है।",
            "चंद्र राशींचा परस्पर आधार सहज तयार होतो."
            if full
            else "चंद्र राशींचा आधार वारंवारच्या जाणीवपूर्वक सरावातून तयार होतो.",
        ),
        "Tara": _say(
            lang,
            "The nakshatra count is a supportive Tara."
            if full
            else "Tara is mixed. Speak health and travel plans aloud. Do not assume them.",
            "नक्षत्र गणना सहायक तारा है।"
            if full
            else "तारा मिश्र है। स्वास्थ्य और यात्रा की योजना बोलकर रखें। अनुमान न करें।",
            "नक्षत्र मोजणी सहाय्यक तारा आहे."
            if full
            else "तारा मिश्र आहे. आरोग्य आणि प्रवासाच्या योजना बोलून ठेवा. गृहित धरू नका.",
        ),
        "Yoni": _say(
            lang,
            "Instinctive timing matches."
            if scored >= 4
            else "Instinctive timing is workable."
            if scored >= 2.5
            else "Instinctive timing differs. A slow reply is not a refusal.",
            "सहज समय मिलता है।"
            if scored >= 4
            else "सहज समय काम चलाऊ है।"
            if scored >= 2.5
            else "सहज समय अलग है। धीमा उत्तर अस्वीकार नहीं है।",
            "सहज वेळ जुळतो."
            if scored >= 4
            else "सहज वेळ चालण्यासारखा आहे."
            if scored >= 2.5
            else "सहज वेळ वेगळा आहे. मंद उत्तर नकार नाही.",
        ),
        "Graha Maitri": _say(
            lang,
            "The Moon-sign lords are the same, so mental friendship is direct."
            if full
            else "Mental friendship is partial. Explain the reason, not only the feeling.",
            "चंद्र राशि के स्वामी एक हैं, इसलिए मानसिक मित्रता सीधी है।"
            if full
            else "मानसिक मित्रता आंशिक है। केवल भाव नहीं, कारण भी कहें।",
            "चंद्र राशीचे स्वामी एकच आहेत, म्हणून मानसिक मैत्री सरळ आहे."
            if full
            else "मानसिक मैत्री अंशतः आहे. केवळ भावना नव्हे, कारणही सांगा.",
        ),
        "Gana": _say(
            lang,
            "Daily style matches."
            if scored >= 6
            else "Daily style can meet in the middle."
            if scored >= 5
            else "Daily style clashes. Agree the quiet hours and the social hours of the house.",
            "दैनिक शैली मिलती है।"
            if scored >= 6
            else "दैनिक शैली बीच का रास्ता निकाल सकती है।"
            if scored >= 5
            else "दैनिक शैली टकराती है। घर के शांत घंटे और मिलने के घंटे तय करें।",
            "दैनंदिन शैली जुळते."
            if scored >= 6
            else "दैनंदिन शैली मधला मार्ग काढू शकते."
            if scored >= 5
            else "दैनंदिन शैली आदळते. घराचे शांत तास आणि भेटीचे तास ठरवा.",
        ),
        "Bhakoot": _say(
            lang,
            "The Moon signs avoid the classical 2/12, 5/9, and 6/8 strain."
            if full
            else "Bhakoot is strained. Be cautious with family plans and shared money. Take protective measures before a large household decision. This sign pair is not favorable for haste.",
            "चंद्र राशियाँ शास्त्रीय 2/12, 5/9 और 6/8 तनाव से बची हैं।"
            if full
            else "भकूट तनाव में है। पारिवारिक योजना और साझे धन में सावधानी रखें। बड़े घरेलू निर्णय से पहले रक्षात्मक उपाय करें। यह राशि युग्म जल्दबाजी के लिए अनुकूल नहीं है।",
            "चंद्र राशी शास्त्रीय 2/12, 5/9 आणि 6/8 ताणापासून दूर आहेत."
            if full
            else "भकूट ताणात आहे. कौटुंबिक योजना आणि सामायिक धनात सावध राहा. मोठ्या घरगुती निर्णयापूर्वी संरक्षणात्मक उपाय करा. ही राशी जोडी घाईसाठी अनुकूल नाही.",
        ),
        "Nadi": _say(
            lang,
            "The nadis differ, so the classical vitality balance is present."
            if full
            else "Nadi is the same. Be cautious about children and shared vitality. This is not a final prohibition. Take protective measures and give the question time.",
            "नाड़ी भिन्न है, इसलिए शास्त्रीय जीवन-संतुलन मौजूद है।"
            if full
            else "नाड़ी एक है। संतान और साझी जीवन-शक्ति के विषय में सावधानी रखें। यह अंतिम निषेध नहीं है। रक्षात्मक उपाय करें और प्रश्न को समय दें।",
            "नाडी वेगळ्या आहेत, म्हणून शास्त्रीय जीवन-संतुलन आहे."
            if full
            else "नाडी एकच आहे. अपत्य आणि सामायिक जीवनशक्तीबाबत सावध राहा. हा अंतिम निषेध नाही. संरक्षणात्मक उपाय करा आणि प्रश्नाला वेळ द्या.",
        ),
    }[name]
    return f"{points} {detail}"


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
        mars = _say(
            lang,
            "Both charts carry unmitigated Mangal. Traditional reading treats the heat as mutual. Still pause before an argument becomes a contest.",
            "दोनों कुंडली में बिना शमन का मंगल है। शास्त्र इस ताप को परस्पर मानता है। फिर भी विवाद को प्रतियोगिता बनने से पहले रुकें।",
            "दोन्ही कुंडल्यांत शमनाशिवाय मंगळ आहे. शास्त्र हा ताप परस्पर मानते. तरी वाद स्पर्धा होण्यापूर्वी थांबा.",
        )
    elif a_on or b_on:
        who = _say(lang, "the first chart" if a_on else "the partner chart", "पहली कुंडली" if a_on else "साथी की कुंडली", "पहिली कुंडली" if a_on else "जोडीदाराची कुंडली")
        mars = _say(
            lang,
            f"Mangal is active in {who} and not in the other. Mars energy is uneven. Keep sharp speech off the marriage, and let the chart with Mangal use Tuesday for a Hanuman observance.",
            f"मंगल {who} में सक्रिय है, दूसरी में नहीं। मंगल की ऊर्जा असमान है। तीखी वाणी विवाह से बाहर रखें, और मंगल वाली कुंडली मंगलवार को हनुमान की उपासना करे।",
            f"मंगळ {who} मध्ये सक्रिय आहे, दुसऱ्यामध्ये नाही. मंगळाची ऊर्जा असमान आहे. तीव्र वाणी विवाहाबाहेर ठेवा, आणि मंगळ असलेली कुंडली मंगळवारी हनुमान उपासना करो.",
        )
    else:
        mars = _say(
            lang,
            "Mangal is absent or traditionally mitigated in both charts. Mars is not the strain to manage.",
            "मंगल दोनों कुंडली में नहीं है, या शास्त्रीय शमन के साथ है। मंगल वह तनाव नहीं है जिसे सँभालना है।",
            "मंगळ दोन्ही कुंडल्यांत नाही, किंवा शास्त्रीय शमनासह आहे. मंगळ हा ताण सांभाळायचा नाही.",
        )
    if not weak:
        strains = _say(
            lang,
            "Bhakoot, Nadi, and Gana are not in the strained band. The remaining work is ordinary care in speech and money.",
            "भकूट, नाड़ी और गण तनाव वाले स्तर पर नहीं हैं। शेष काम वाणी और धन की साधारण सावधानी है।",
            "भकूट, नाडी आणि गण ताणाच्या पातळीवर नाहीत. उरलेले काम वाणी आणि धनाची साधी सावधगिरी आहे.",
        )
    else:
        named = ", ".join(weak)
        strains = _say(
            lang,
            f"Strained parameters: {named}. Be cautious there. Take protective measures before a family, money, or children decision. The configuration is not favorable for haste, and it is not a final prohibition.",
            f"तनाव वाले कारक: {named}। वहाँ सावधानी रखें। परिवार, धन या संतान के निर्णय से पहले रक्षात्मक उपाय करें। यह स्थिति जल्दबाजी के लिए अनुकूल नहीं है, और यह अंतिम निषेध नहीं है।",
            f"ताणाचे घटक: {named}. तेथे सावध राहा. कुटुंब, धन किंवा अपत्याच्या निर्णयापूर्वी संरक्षणात्मक उपाय करा. ही स्थिती घाईसाठी अनुकूल नाही, आणि हा अंतिम निषेध नाही.",
        )
    return _check(f"{strains} {mars}", lang)


def _bond(
    name_a: str,
    chart_a: ChartResponse,
    name_b: str,
    chart_b: ChartResponse,
    lang: str,
) -> str:
    opening = _say(
        lang,
        (
            f"{name_a} meets a partner through this temperament: {_temper(chart_a.lagna_sign_name, lang)}. "
            f"{name_b} meets a partner through this temperament: {_temper(chart_b.lagna_sign_name, lang)}. "
            "The relationship is read from both 7th houses and from Venus. The Moon score does not replace that reading."
        ),
        (
            f"{name_a} साथी से इस स्वभाव से मिलता है: {_temper(chart_a.lagna_sign_name, lang)}। "
            f"{name_b} साथी से इस स्वभाव से मिलता है: {_temper(chart_b.lagna_sign_name, lang)}। "
            "संबंध दोनों सप्तम भाव और शुक्र से पढ़ा जाता है। चंद्र का अंक उस पठन की जगह नहीं लेता।"
        ),
        (
            f"{name_a} जोडीदाराला या स्वभावाने भेटते: {_temper(chart_a.lagna_sign_name, lang)}. "
            f"{name_b} जोडीदाराला या स्वभावाने भेटते: {_temper(chart_b.lagna_sign_name, lang)}. "
            "नाते दोन्ही सप्तम भाव आणि शुक्र यांच्यावरून वाचले जाते. चंद्राचा गुण त्या वाचनाची जागा घेत नाही."
        ),
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
    return " ".join(
        (
            _say(
                lang,
                f"For {name}, the marriage is lived through home, children, and family resources.",
                f"{name} के लिए विवाह घर, संतान और पारिवारिक साधनों से जिया जाता है।",
                f"{name} साठी विवाह घर, अपत्य आणि कौटुंबिक साधनांतून जगला जातो.",
            ),
            _say(
                lang,
                f"The 4th house falls in {_g(fourth, lang)}. Its lord is {_g(fourth_lord.planet, lang)}.",
                f"चतुर्थ भाव {_g(fourth, lang)} में है। उसका स्वामी {_g(fourth_lord.planet, lang)} है।",
                f"चतुर्थ भाव {_g(fourth, lang)} मध्ये आहे. त्याचा स्वामी {_g(fourth_lord.planet, lang)} आहे.",
            ),
            _where(chart, fourth_lord, lang),
            _say(
                lang,
                f"The 5th house, for children and affection, falls in {_g(fifth, lang)}.",
                f"संतान और स्नेह का पंचम भाव {_g(fifth, lang)} में है।",
                f"अपत्य आणि स्नेहाचा पंचम भाव {_g(fifth, lang)} मध्ये आहे.",
            ),
            _where(chart, fifth_lord, lang),
            _say(
                lang,
                f"The 2nd house, for family resources and speech, falls in {_g(second, lang)}.",
                f"पारिवारिक साधन और वाणी का द्वितीय भाव {_g(second, lang)} में है।",
                f"कौटुंबिक साधने आणि वाणीचा द्वितीय भाव {_g(second, lang)} मध्ये आहे.",
            ),
            _where(chart, second_lord, lang),
            _tone([fourth_lord.house, fifth_lord.house, second_lord.house], lang),
            _say(
                lang,
                (
                    f"Through {dasha['antardasha_end_date']}, {_g(md, lang)} Mahadasha and "
                    f"{_g(ad, lang)} Antardasha are the period in which these houses are active for the marriage."
                ),
                (
                    f"{dasha['antardasha_end_date']} तक {_g(md, lang)} महादशा और "
                    f"{_g(ad, lang)} अंतर्दशा वह काल है जिसमें ये भाव विवाह के लिए सक्रिय हैं।"
                ),
                (
                    f"{dasha['antardasha_end_date']} पर्यंत {_g(md, lang)} महादशा आणि "
                    f"{_g(ad, lang)} अंतरदशा हा काळ आहे ज्यात हे भाव विवाहासाठी सक्रिय आहेत."
                ),
            ),
        )
    )


def _motions(name: str, transits: dict[str, object], lang: str) -> str:
    jh = int(str(transits["jupiter_house_from_moon"]))
    sh = int(str(transits["saturn_house_from_moon"]))
    sade = transits["sade_sati"]
    assert isinstance(sade, dict)
    placed = _say(
        lang,
        (
            f"For {name}, on {transits['target_date']}, Jupiter transits {_g(transits['jupiter_transit_sign'], lang)}, "
            f"house {jh} from the birth Moon. That motion touches {_matter(jh, lang)}. "
            f"Saturn transits {_g(transits['saturn_transit_sign'], lang)}, house {sh} from the birth Moon. "
            f"That motion touches {_matter(sh, lang)}."
        ),
        (
            f"{name} के लिए, {transits['target_date']} को, बृहस्पति {_g(transits['jupiter_transit_sign'], lang)} से गोचर कर रहा है, "
            f"जन्म चंद्र से भाव {jh}। यह गति {_matter(jh, lang)} को छूती है। "
            f"शनि {_g(transits['saturn_transit_sign'], lang)} में है, जन्म चंद्र से भाव {sh}। "
            f"यह गति {_matter(sh, lang)} को छूती है।"
        ),
        (
            f"{name} साठी, {transits['target_date']} रोजी, गुरू {_g(transits['jupiter_transit_sign'], lang)} मधून गोचर करतो, "
            f"जन्म चंद्रापासून भाव {jh}. ही गती {_matter(jh, lang)} ला स्पर्श करते. "
            f"शनी {_g(transits['saturn_transit_sign'], lang)} मध्ये आहे, जन्म चंद्रापासून भाव {sh}. "
            f"ही गती {_matter(sh, lang)} ला स्पर्श करते."
        ),
    )
    if bool(sade["is_active"]):
        pressure = _say(
            lang,
            "Saturn stands beside this birth Moon. Be cautious with pace, duty, and household decisions. Take protective measures. This period is not favorable for haste.",
            "शनि इस जन्म चंद्र के पास है। गति, कर्तव्य और घरेलू निर्णयों में सावधानी रखें। रक्षात्मक उपाय करें। यह काल जल्दबाजी के लिए अनुकूल नहीं है।",
            "शनी या जन्म चंद्राजवळ आहे. गती, कर्तव्य आणि घरगुती निर्णयांत सावध राहा. संरक्षणात्मक उपाय करा. हा काळ घाईसाठी अनुकूल नाही.",
        )
    else:
        pressure = _say(
            lang,
            "Saturn is not in the 12th, 1st, or 2nd from this birth Moon.",
            "शनि इस जन्म चंद्र से बारहवें, पहले या दूसरे भाव में नहीं है।",
            "शनी या जन्म चंद्रापासून बाराव्या, पहिल्या किंवा दुसऱ्या भावात नाही.",
        )
    if jh == 7 or sh == 7:
        touch = _say(
            lang,
            "One of these transits occupies the 7th from the birth Moon, so the partnership itself is the topic of the current motion.",
            "इन गोचरों में से एक जन्म चंद्र से सप्तम भाव में है, इसलिए साझेदारी ही वर्तमान गति का विषय है।",
            "या गोचरांपैकी एक जन्म चंद्रापासून सप्तम भावात आहे, म्हणून भागीदारी ही सध्याच्या गतीचा विषय आहे.",
        )
    else:
        touch = _say(
            lang,
            "Neither Jupiter nor Saturn occupies the 7th from this birth Moon. The marriage is touched through the houses named above, not by a direct transit on the partnership house.",
            "बृहस्पति और शनि में से कोई भी इस जन्म चंद्र से सप्तम भाव में नहीं है। विवाह ऊपर बताए भावों से छूता है, साझेदारी भाव पर सीधे गोचर से नहीं।",
            "गुरू आणि शनी यांपैकी एकही या जन्म चंद्रापासून सप्तम भावात नाही. विवाह वर सांगितलेल्या भावांतून स्पर्श होतो, भागीदारी भावावरील थेट गोचराने नाही.",
        )
    return " ".join((placed, _gochara(transits, lang), pressure, touch))


def _conduct(name: str, chart: ChartResponse, dasha: dict[str, object], lang: str) -> str:
    md = str(dasha["active_mahadasha"])
    ad = str(dasha["active_antardasha"])
    return " ".join(
        (
            _say(
                lang,
                f"{name} is running {_g(md, lang)} Mahadasha and {_g(ad, lang)} Antardasha. In this marriage, {name} should {_behavior(md, lang)}.",
                f"{name} की {_g(md, lang)} महादशा और {_g(ad, lang)} अंतर्दशा चल रही है। इस विवाह में {name} को {_behavior(md, lang)}।",
                f"{name} ची {_g(md, lang)} महादशा आणि {_g(ad, lang)} अंतरदशा चालू आहे. या विवाहात {name} ने {_behavior(md, lang)}.",
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
            _koota_meaning(str(row["koota"]), float(str(row["scored"])), float(str(row["max_points"])), lang),
            lang,
        )
    mangal = match["mangal_dosha_check"]
    assert isinstance(mangal, dict)
    frame = _say(
        lang,
        f"The form says {name_a} and {name_b} are already married. This outlook is for that marriage."
        if already_married
        else f"The form does not record a marriage already underway. This outlook is how a marriage between {name_a} and {name_b} tends to move. It does not say that a wedding must happen.",
        f"प्रपत्र कहता है कि {name_a} और {name_b} पहले से विवाहित हैं। यह दृष्टिकोण उसी विवाह के लिए है।"
        if already_married
        else f"प्रपत्र में चल रहा विवाह दर्ज नहीं है। यह दृष्टिकोण बताता है कि {name_a} और {name_b} का विवाह कैसे चलता है। यह नहीं कहता कि विवाह होना ही चाहिए।",
        f"प्रपत्र सांगते की {name_a} आणि {name_b} आधीच विवाहित आहेत. ही दृष्टी त्या विवाहासाठी आहे."
        if already_married
        else f"प्रपत्रात सुरू असलेला विवाह नोंदलेला नाही. ही दृष्टी सांगते की {name_a} आणि {name_b} यांचा विवाह कसा चालतो. विवाह झालाच पाहिजे, असे ती म्हणत नाही.",
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
            _say(
                lang,
                "These are the current motions of Jupiter and Saturn measured from each birth Moon. They describe the season the marriage is in. They do not name an exact event date.",
                "ये बृहस्पति और शनि की वर्तमान गति हैं, प्रत्येक जन्म चंद्र से मापी हुई। ये बताती हैं कि विवाह किस ऋतु में है। ये किसी घटना की ठीक तारीख नहीं बतातीं।",
                "या बृहस्पति आणि शनीच्या सध्याच्या गती आहेत, प्रत्येक जन्म चंद्रापासून मोजलेल्या. त्या सांगतात की विवाह कोणत्या ऋतूत आहे. त्या एखाद्या घटनेची नेमकी तारीख सांगत नाहीत.",
            ),
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
                        f"{place}. {when}. Lagna {_g(chart.lagna_sign_name, lang)}. Moon {_g(moon.sign_name, lang)}, nakshatra {_g(moon.nakshatra_name, lang)}, pada {moon.pada}.",
                        f"{place}। {when}। लग्न {_g(chart.lagna_sign_name, lang)}। चंद्र {_g(moon.sign_name, lang)}, नक्षत्र {_g(moon.nakshatra_name, lang)}, चरण {moon.pada}।",
                        f"{place}. {when}. लग्न {_g(chart.lagna_sign_name, lang)}. चंद्र {_g(moon.sign_name, lang)}, नक्षत्र {_g(moon.nakshatra_name, lang)}, चरण {moon.pada}.",
                    ),
                    lang,
                ),
                "character": _check(_portrait(chart, dasha, lang), lang),
            }
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
            "title": _say(
                lang,
                "Married life now" if already_married else "How married life tends to move",
                "विवाह की वर्तमान दशा" if already_married else "विवाहित जीवन की संभावित गति",
                "विवाहाची सध्याची स्थिती" if already_married else "विवाहित जीवनाची संभाव्य गती",
            ),
            "text": _check(life, lang),
        },
        {
            "title": _say(lang, "Strains and what to do", "तनाव और क्या करें", "ताण आणि काय करावे"),
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
    match["method_limitations_note"] = _check(
        _say(
            lang,
            "The 36-point score uses only the two Moon signs and nakshatras. The reading beside it uses both Lagnas, both 7th houses, Venus, Mangal, and the dasha each person is running.",
            "36 अंक केवल दोनों चंद्र राशियों और नक्षत्रों से हैं। उसके साथ का पठन दोनों लग्न, दोनों सप्तम भाव, शुक्र, मंगल और प्रत्येक की चल रही दशा से है।",
            "36 गुण केवळ दोन्ही चंद्र राशी आणि नक्षत्रांवरून आहेत. सोबतचे वाचन दोन्ही लग्न, दोन्ही सप्तम भाव, शुक्र, मंगळ आणि प्रत्येकाची चालू दशा यांच्यावरून आहे.",
        ),
        lang,
    )
    return match
