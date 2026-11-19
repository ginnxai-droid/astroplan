# G2 Advisor Review Packet

**Status: everything below is still `draft`. Nothing in this packet is approved.**

This packet contains every artifact that release gate **G2** requires a named human
Jyotish advisor to review. Reviewing it replaces the four `draft` blocks listed below.

## Who signs and what the signature means

- The signer is recorded as `reviewer` (and `reviewed_at`) in four files. The name
  becomes part of the public repository and its git history permanently.
- Signing certifies: classical citations are right for the stated tradition, evidence
  templates describe the placement correctly, strength grades are fair, outcome
  criteria are observable, festival dates and tithi rules are correct for 2026, the
  Ashtakoota tables are orthodox, and the Hindi/Marathi wording faithfully carries the
  meaning of the English text.
- The gate is enforced by `tests/test_g2_signoff.py`; production refuses to start
  with any draft entry (`allow_draft_rules=false`).

## How to respond

Reply with either **"approve all"** or a per-item list of corrections, plus the
reviewer name to record and the review date. Example:

```
Approve all, except:
- RULE_PARASHARI_YOGA_HAMSA: change strength_grade to 'supported'
- Holi: date should be 2026-03-04
Reviewer: <name>
Date: 2026-11-19
```

---

## 1. Rules — `rules/mvp_rules.yaml` (8 items)

Each rule shows its classical citation, placement evidence template, strength grade,
observable outcome criterion, and the user-visible wording in all three languages.

### RULE_PARASHARI_CAREER_10H

- **Category:** career  ·  **Tradition:** Parashari
- **Classical source:** Brihat Parashara Hora Shastra (BPHS), Ch. 21 (Karma Bhava)
- **Evidence template:** `Sun in {sun_sign} (House {sun_house}, D9 {sun_navamsa}); Dasha: {md}-{ad}`
- **Strength grade:** `supported`
- **Observable outcome criterion:** Job role, title, or workplace changed by the stated window end.

Wording key `career_10h_discipline`:

| Language | `.simple` | `.pro` |
| --- | --- | --- |
| en | Steady professional progress is supported through structured planning and consistent effort. | 10th-house karmic indicators and Saturn/Jupiter transit alignment support methodical career consolidation. |
| hi | व्यवस्थित योजना और निरंतर प्रयास से कार्यक्षेत्र में स्थिर प्रगति के संकेत हैं। | दशम भाव के संकेतक और शनि/बृहस्पति का गोचर करियर में अनुशासित प्रगति का समर्थन करते हैं। |
| mr | नियोजनबद्ध कार्य आणि सातत्यपूर्ण प्रयत्नांमुळे करिअरमध्ये स्थिर प्रगती दिसून येते. | दशम भावातील ग्रहस्थिती आणि शनी/गुरूचे गोचर व्यावसायिक स्थैर्याला पूरक आहेत. |

Verdict: [ ] approve  [ ] approve with edits  [ ] reject — notes:

### RULE_PARASHARI_REL_7H

- **Category:** relationships  ·  **Tradition:** Parashari
- **Classical source:** Brihat Parashara Hora Shastra (BPHS), Ch. 18 (Yuvati Bhava)
- **Evidence template:** `Venus in {venus_sign} (House {venus_house}, D9 {venus_navamsa})`
- **Strength grade:** `likely`
- **Observable outcome criterion:** Partnership status or a joint commitment changed by the stated window end.

Wording key `relationships_7h_harmony`:

| Language | `.simple` | `.pro` |
| --- | --- | --- |
| en | Clear communication and mutual patience strengthen partnerships during this period. | 7th-house and Navamsa (D9) relational factors favor constructive dialogue over impulsive decisions. |
| hi | स्पष्ट संवाद और आपसी धैर्य से इस अवधि में संबंधों में मधुरता बढ़ेगी। | सप्तम भाव और नवांश (D9) की स्थिति संबंधों में संतुलित संवाद का समर्थन करती है। |
| mr | स्पष्ट संवाद आणि संयमामुळे या काळात नातेसंबंध अधिक दृढ होतील. | सप्तम भाव आणि नवांश (D9) मधील स्थिती नातेसंबंधात सामंजस्याला प्रोत्साहन देते. |

Verdict: [ ] approve  [ ] approve with edits  [ ] reject — notes:

### RULE_PARASHARI_FIN_2H_11H

- **Category:** finances  ·  **Tradition:** Parashari
- **Classical source:** Brihat Parashara Hora Shastra (BPHS), Ch. 13 & 22 (Dhana & Labha Bhava)
- **Evidence template:** `Jupiter in {jup_sign} (House {jup_house}); Transit Jupiter House {jup_transit} from Moon`
- **Strength grade:** `supported`
- **Observable outcome criterion:** Household savings or monthly income moved by the stated window end.

Wording key `finances_2h_11h_prudence`:

| Language | `.simple` | `.pro` |
| --- | --- | --- |
| en | Income flow is supported when paired with mindful budgeting and long-term savings. | Dhana (2nd) and Labha (11th) house placements indicate supported cash-flow stability with disciplined allocation. |
| hi | संतुलित बजट और दीर्घकालिक बचत के साथ आर्थिक स्थिति स्थिर रहने के संकेत हैं। | धन (द्वितीय) और लाभ (एकादश) भाव की स्थिति अनुशासित वित्तीय प्रबंधन का समर्थन करती है। |
| mr | योग्य आर्थिक नियोजन आणि दीर्घकालीन बचतीमुळे आर्थिक स्थिती स्थिर राहील. | द्वितीय (धन) आणि एकादश (लाभ) भावातील स्थिती आर्थिक शिस्तीला पूरक आहे. |

Verdict: [ ] approve  [ ] approve with edits  [ ] reject — notes:

### RULE_PARASHARI_HOME_4H

- **Category:** home  ·  **Tradition:** Parashari
- **Classical source:** Brihat Parashara Hora Shastra (BPHS), Ch. 15 (Sukha Bhava)
- **Evidence template:** `Moon in {moon_sign} ({moon_nak} Pada {moon_pada}, House {moon_house})`
- **Strength grade:** `supported`
- **Observable outcome criterion:** Residence or living arrangement changed by the stated window end.

Wording key `home_4h_stability`:

| Language | `.simple` | `.pro` |
| --- | --- | --- |
| en | Domestic peace and home organization benefit from calm routines and family cooperation. | Sukha (4th) house placement and Moon alignment support domestic grounding and property upkeep. |
| hi | शांत दिनचर्या और पारिवारिक सहयोग से घर-परिवार में सुख-शांति बनी रहेगी। | चतुर्थ (सुख) भाव और चंद्रमा की स्थिति पारिवारिक संतुलन और गृह-प्रबंधन के लिए अनुकूल है। |
| mr | शांत दिनचर्या आणि कौटुंबिक सहकार्यामुळे घरात सुख-शांती टिकून राहील. | चतुर्थ (सुख) भाव आणि चंद्राची स्थिती कौटुंबिक स्थैर्यासाठी अनुकूल आहे. |

Verdict: [ ] approve  [ ] approve with edits  [ ] reject — notes:

### RULE_PARASHARI_YOGA_GAJAKESARI

- **Category:** yoga  ·  **Tradition:** Parashari
- **Classical source:** Brihat Parashara Hora Shastra (BPHS), Ch. 36
- **Evidence template:** `Jupiter in {jup_sign} ({jup_from_moon}th from Moon in {moon_sign})`
- **Strength grade:** `supported`
- **Observable outcome criterion:** DRAFTED — Social or professional influence measurably increased (a new role, audience, or public recognition) by the stated window end.

Wording key `yoga.gajakesari`:

| Language | `.simple` | `.pro` |
| --- | --- | --- |
| en | Gajakesari Yoga supports long-term wisdom, ethical reputation, and steady resilience. | Jupiter in a Kendra (1st, 4th, 7th, or 10th) from Moon forms Gajakesari Yoga (BPHS Ch. 36). |
| hi | गजकेसरी योग दीर्घकालिक विवेक, सम्मान और भावनात्मक स्थिरता को बल देता है। | चंद्रमा से केंद्र (1, 4, 7, 10) में बृहस्पति की स्थिति गजकेसरी योग बनाती है (बृहत् पाराशर होरा शास्त्र अ. 36)। |
| mr | गजकेसरी योग दीर्घकालीन प्रगल्भता, सन्मान आणि मानसिक स्थैर्याला बळ देतो. | चंद्रापासून केंद्रात (1, 4, 7, 10) गुरू असल्यास गजकेसरी योग होतो (बृहत् पाराशर होरा शास्त्र अ. 36). |

Verdict: [ ] approve  [ ] approve with edits  [ ] reject — notes:

### RULE_PARASHARI_YOGA_BUDHADITYA

- **Category:** yoga  ·  **Tradition:** Parashari
- **Classical source:** Phaladeepika, Ch. 6
- **Evidence template:** `Sun and Mercury conjoined in {sun_sign} (House {sun_house})`
- **Strength grade:** `supported`
- **Observable outcome criterion:** DRAFTED — Learning, writing, or analytical output produced a concrete result (a qualification, publication, or analytical role) by the stated window end.

Wording key `yoga.budhaditya`:

| Language | `.simple` | `.pro` |
| --- | --- | --- |
| en | Budhaditya Yoga supports analytical clarity, learning, and articulate communication. | Sun and Mercury conjoined in the same Rashi form Budhaditya Yoga (Phaladeepika Ch. 6). |
| hi | बुधादित्य योग बौद्धिक स्पष्टता, अध्ययन और प्रभावी संवाद में सहायक है। | एक ही राशि में सूर्य और बुध की युति से बुधादित्य योग बनता है (फलदीपिका अ. 6)। |
| mr | बुधादित्य योग वैचारिक स्पष्टता, अभ्यास आणि प्रभावी संवादास पूरक ठरतो. | एकाच राशीत रवी आणि बुध यांच्या युतीने बुधादित्य योग तयार होतो (फलदीपिका अ. 6). |

Verdict: [ ] approve  [ ] approve with edits  [ ] reject — notes:

### RULE_PARASHARI_YOGA_HAMSA

- **Category:** yoga  ·  **Tradition:** Parashari
- **Classical source:** Brihat Parashara Hora Shastra (BPHS), Ch. 75 (Pancha Mahapurusha)
- **Evidence template:** `Jupiter in {jup_sign} (House {jup_house} Kendra in own/exalted sign)`
- **Strength grade:** `likely`
- **Observable outcome criterion:** DRAFTED — A values- or aesthetics-driven undertaking was completed or publicly recognised by the stated window end.

Wording key `yoga.hamsa`:

| Language | `.simple` | `.pro` |
| --- | --- | --- |
| en | Hamsa Mahapurusha Yoga supports ethical leadership, deep learning, and balanced judgment. | Jupiter in own or exalted Rashi (Cancer, Sagittarius, or Pisces) in a Kendra (1, 4, 7, 10) from Lagna forms Hamsa Yoga (BPHS Ch. 75). |
| hi | हंस महापुरुष योग नैतिक नेतृत्व, गहन अध्ययन और संतुलित निर्णय क्षमता को बल देता है। | लग्न से केंद्र (1, 4, 7, 10) में स्वग्रही या उच्च (कर्क, धनु, मीन) का बृहस्पति हंस योग बनाता है (बृहत् पाराशर होरा शास्त्र अ. 75)। |
| mr | हंस महापुरुष योग नैतिक नेतृत्व, सखोल अभ्यास आणि संतुलित निर्णयक्षमतेला बळ देतो. | लग्नापासून केंद्रात (1, 4, 7, 10) स्वगृही किंवा उच्च राशीत (कर्क, धनु, मीन) गुरू असल्यास हंस योग होतो (बृहत् पाराशर होरा शास्त्र अ. 75). |

Verdict: [ ] approve  [ ] approve with edits  [ ] reject — notes:

### RULE_PARASHARI_MANGAL_CONTEXT

- **Category:** dosha_context  ·  **Tradition:** Parashari
- **Classical source:** Brihat Parashara Hora Shastra (BPHS), Ch. 80
- **Evidence template:** `Mars in {mars_sign} (House {mars_house} from Lagna, House {mars_moon_house} from Moon)`
- **Strength grade:** `contested`
- **Observable outcome criterion:** DRAFTED — A partnership conflict or negotiation episode concluded without separation by the stated window end.

Wording key `dosha.mangal_context`:

| Language | `.simple` | `.pro` |
| --- | --- | --- |
| en | High partnership drive is indicated; traditional mitigations and open communication keep relationships balanced. | Mars in house {mars_house} from Lagna ({mars_moon_house} from Moon); classical texts note cancellations and chart balance. |
| hi | संबंधों में उच्च ऊर्जा के संकेत हैं; पारंपरिक परिहार और संवाद से संतुलन बना रहता है। | लग्न से {mars_house} भाव (चंद्र से {mars_moon_house} भाव) में मंगल; शास्त्रीय ग्रंथों में इसके कई परिहार बताए गए हैं। |
| mr | भागीदारीत उच्च ऊर्जा दिसून येते; पारंपारिक परिहार आणि संवादातून समतोल राखता येतो. | लग्नापासून {mars_house} भावात (चंद्रापासून {mars_moon_house} भावात) मंगळ; शास्त्रीय ग्रंथांत याचे अनेक परिहार दिले आहेत. |

Verdict: [ ] approve  [ ] approve with edits  [ ] reject — notes:

---

## 2. Festivals — `data/festivals.yaml` (4 items, year 2026)

| Festival | Date | Tradition | Tithi rule | Verdict |
| --- | --- | --- | --- | --- |
| Makar Sankranti | 2026-01-14 | smarta_maharashtra_north | Sun ingress into Makara (Capricorn) | [ ] approve — notes: |
| Holi (Phalguna Purnima) | 2026-03-03 | smarta_maharashtra_north | Phalguna Shukla Purnima | [ ] approve — notes: |
| Ganesh Chaturthi | 2026-09-14 | smarta_maharashtra_north | Bhadrapada Shukla Chaturthi | [ ] approve — notes: |
| Diwali Lakshmi Puja (Kartika Amavasya) | 2026-11-08 | smarta_maharashtra_north | Ashvina/Kartika Amavasya Pradosh | [ ] approve — notes: |

---

## 3. Ashtakoota tables — `rules/ashtakoota_tables.yaml`

These tables drive the 36-point match. Sign lords:

| Sign | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Lord | Mars | Venus | Mercury | Moon | Sun | Mercury | Venus | Mars | Jupiter | Saturn | Saturn | Jupiter |

Varna by sign (code values: 4 Brahmin · 3 Kshatriya · 2 Vaishya · 1 Shudra):

| Sign | Aries | Taurus | Gemini | Cancer | Leo | Virgo | Libra | Scorpio | Sagittarius | Capricorn | Aquarius | Pisces |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Varna | Kshatriya | Vaishya | Shudra | Brahmin | Kshatriya | Vaishya | Shudra | Brahmin | Kshatriya | Vaishya | Shudra | Brahmin |

Gana and Nadi by nakshatra (`app/core/matching.py` maps 0/1/2 as shown):

| # | Nakshatra | Gana | Nadi |
| --- | --- | --- | --- |
| 1 | Ashwini | Deva | Adi |
| 2 | Bharani | Manushya | Madhya |
| 3 | Krittika | Rakshasa | Antya |
| 4 | Rohini | Manushya | Antya |
| 5 | Mrigashira | Deva | Madhya |
| 6 | Ardra | Manushya | Adi |
| 7 | Punarvasu | Deva | Adi |
| 8 | Pushya | Deva | Madhya |
| 9 | Ashlesha | Rakshasa | Antya |
| 10 | Magha | Rakshasa | Adi |
| 11 | Purva Phalguni | Manushya | Madhya |
| 12 | Uttara Phalguni | Manushya | Antya |
| 13 | Hasta | Deva | Adi |
| 14 | Chitra | Rakshasa | Madhya |
| 15 | Swati | Deva | Antya |
| 16 | Vishakha | Rakshasa | Antya |
| 17 | Anuradha | Deva | Madhya |
| 18 | Jyeshtha | Rakshasa | Adi |
| 19 | Mula | Rakshasa | Adi |
| 20 | Purva Ashadha | Manushya | Madhya |
| 21 | Uttara Ashadha | Manushya | Antya |
| 22 | Shravana | Deva | Antya |
| 23 | Dhanishta | Rakshasa | Madhya |
| 24 | Shatabhisha | Rakshasa | Adi |
| 25 | Purva Bhadrapada | Manushya | Adi |
| 26 | Uttara Bhadrapada | Manushya | Madhya |
| 27 | Revati | Deva | Antya |

Bhakoot dosha distances (moon-sign offset counts treated as adverse): 2, 6, 8, 12.

Scoring formulas (Varna, Vashya, Tara, Yoni, Graha Maitri, Gana, Bhakoot, Nadi)
live in `app/core/matching.py:44-58` and are visible there in full; G2 certifies
the table data above, while the arithmetic itself is unit-tested.

Verdict: [ ] approve  [ ] approve with edits  [ ] reject — notes:

---

## 4. Trilingual catalogs — `i18n/en.json`, `hi.json`, `mr.json` (55 keys each)

| Key | English | Hindi | Marathi |
| --- | --- | --- | --- |
| `chart.disclaimer` | Calculations are astronomically verifiable for stated settings. Interpretations follow traditional Parashari Jyotish rules and are not scientifically validated. | दी गई सेटिंग्स के लिए गणनाएं खगोलीय रूप से सत्यापन योग्य हैं। व्याख्याएं पारंपरिक पाराशरी ज्योतिष नियमों पर आधारित हैं। | दिलेल्या सेटिंग्ससाठी गणना खगोलशास्त्रीयदृष्ट्या पडताळण्यायोग्य आहेत. स्पष्टीकरणे पारंपारिक पाराशरी ज्योतिष नियमांवर आधारित आहेत. |
| `area.career` | Career | करियर | करिअर |
| `area.relationships` | Relationships | रिश्ते | नाती |
| `area.finances` | Finances | धन | पैसा |
| `area.home` | Home | घर | घर |
| `career_10h_discipline.simple` | Steady professional progress is supported through structured planning and consistent effort. | व्यवस्थित योजना और निरंतर प्रयास से कार्यक्षेत्र में स्थिर प्रगति के संकेत हैं। | नियोजनबद्ध कार्य आणि सातत्यपूर्ण प्रयत्नांमुळे करिअरमध्ये स्थिर प्रगती दिसून येते. |
| `career_10h_discipline.pro` | 10th-house karmic indicators and Saturn/Jupiter transit alignment support methodical career consolidation. | दशम भाव के संकेतक और शनि/बृहस्पति का गोचर करियर में अनुशासित प्रगति का समर्थन करते हैं। | दशम भावातील ग्रहस्थिती आणि शनी/गुरूचे गोचर व्यावसायिक स्थैर्याला पूरक आहेत. |
| `relationships_7h_harmony.simple` | Clear communication and mutual patience strengthen partnerships during this period. | स्पष्ट संवाद और आपसी धैर्य से इस अवधि में संबंधों में मधुरता बढ़ेगी। | स्पष्ट संवाद आणि संयमामुळे या काळात नातेसंबंध अधिक दृढ होतील. |
| `relationships_7h_harmony.pro` | 7th-house and Navamsa (D9) relational factors favor constructive dialogue over impulsive decisions. | सप्तम भाव और नवांश (D9) की स्थिति संबंधों में संतुलित संवाद का समर्थन करती है। | सप्तम भाव आणि नवांश (D9) मधील स्थिती नातेसंबंधात सामंजस्याला प्रोत्साहन देते. |
| `finances_2h_11h_prudence.simple` | Income flow is supported when paired with mindful budgeting and long-term savings. | संतुलित बजट और दीर्घकालिक बचत के साथ आर्थिक स्थिति स्थिर रहने के संकेत हैं। | योग्य आर्थिक नियोजन आणि दीर्घकालीन बचतीमुळे आर्थिक स्थिती स्थिर राहील. |
| `finances_2h_11h_prudence.pro` | Dhana (2nd) and Labha (11th) house placements indicate supported cash-flow stability with disciplined allocation. | धन (द्वितीय) और लाभ (एकादश) भाव की स्थिति अनुशासित वित्तीय प्रबंधन का समर्थन करती है। | द्वितीय (धन) आणि एकादश (लाभ) भावातील स्थिती आर्थिक शिस्तीला पूरक आहे. |
| `home_4h_stability.simple` | Domestic peace and home organization benefit from calm routines and family cooperation. | शांत दिनचर्या और पारिवारिक सहयोग से घर-परिवार में सुख-शांति बनी रहेगी। | शांत दिनचर्या आणि कौटुंबिक सहकार्यामुळे घरात सुख-शांती टिकून राहील. |
| `home_4h_stability.pro` | Sukha (4th) house placement and Moon alignment support domestic grounding and property upkeep. | चतुर्थ (सुख) भाव और चंद्रमा की स्थिति पारिवारिक संतुलन और गृह-प्रबंधन के लिए अनुकूल है। | चतुर्थ (सुख) भाव आणि चंद्राची स्थिती कौटुंबिक स्थैर्यासाठी अनुकूल आहे. |
| `daily_insight.simple` | Today's {vara} Panchang ({tithi}, {panchang_nak}) with transit Moon in House {moon_house} from natal {natal_moon} favors steady, mindful pacing. | आज का {vara} पंचांग ({tithi}, {panchang_nak}) और जन्म राशि {natal_moon} से {moon_house} भाव में चंद्र गोचर संतुलित दिनचर्या का समर्थन करता है। | आजचे {vara} पंचांग ({tithi}, {panchang_nak}) आणि जन्म राशी {natal_moon} पासून {moon_house} भावातील चंद्र गोचर शांत व नियोजनबद्ध दिवसास पूरक आहे. |
| `daily_insight.pro` | Gochara Moon in {transit_moon_sign} (House {moon_house} from Janma Rashi {natal_moon}) during {tithi} and {yoga} Yoga supports balanced daily execution. | जन्म राशि {natal_moon} से {moon_house} भाव ({transit_moon_sign}) में चंद्र गोचर, {tithi} और {yoga} योग व्यवस्थित कार्यों के लिए अनुकूल हैं। | जन्म राशी {natal_moon} पासून {moon_house} भावात ({transit_moon_sign}) चंद्र गोचर, {tithi} आणि {yoga} योग दैनंदिन संतुलनास अनुकूल आहेत. |
| `yoga.gajakesari.simple` | Gajakesari Yoga supports long-term wisdom, ethical reputation, and steady resilience. | गजकेसरी योग दीर्घकालिक विवेक, सम्मान और भावनात्मक स्थिरता को बल देता है। | गजकेसरी योग दीर्घकालीन प्रगल्भता, सन्मान आणि मानसिक स्थैर्याला बळ देतो. |
| `yoga.gajakesari.pro` | Jupiter in a Kendra (1st, 4th, 7th, or 10th) from Moon forms Gajakesari Yoga (BPHS Ch. 36). | चंद्रमा से केंद्र (1, 4, 7, 10) में बृहस्पति की स्थिति गजकेसरी योग बनाती है (बृहत् पाराशर होरा शास्त्र अ. 36)। | चंद्रापासून केंद्रात (1, 4, 7, 10) गुरू असल्यास गजकेसरी योग होतो (बृहत् पाराशर होरा शास्त्र अ. 36). |
| `yoga.budhaditya.simple` | Budhaditya Yoga supports analytical clarity, learning, and articulate communication. | बुधादित्य योग बौद्धिक स्पष्टता, अध्ययन और प्रभावी संवाद में सहायक है। | बुधादित्य योग वैचारिक स्पष्टता, अभ्यास आणि प्रभावी संवादास पूरक ठरतो. |
| `yoga.budhaditya.pro` | Sun and Mercury conjoined in the same Rashi form Budhaditya Yoga (Phaladeepika Ch. 6). | एक ही राशि में सूर्य और बुध की युति से बुधादित्य योग बनता है (फलदीपिका अ. 6)। | एकाच राशीत रवी आणि बुध यांच्या युतीने बुधादित्य योग तयार होतो (फलदीपिका अ. 6). |
| `yoga.hamsa.simple` | Hamsa Mahapurusha Yoga supports ethical leadership, deep learning, and balanced judgment. | हंस महापुरुष योग नैतिक नेतृत्व, गहन अध्ययन और संतुलित निर्णय क्षमता को बल देता है। | हंस महापुरुष योग नैतिक नेतृत्व, सखोल अभ्यास आणि संतुलित निर्णयक्षमतेला बळ देतो. |
| `yoga.hamsa.pro` | Jupiter in own or exalted Rashi (Cancer, Sagittarius, or Pisces) in a Kendra (1, 4, 7, 10) from Lagna forms Hamsa Yoga (BPHS Ch. 75). | लग्न से केंद्र (1, 4, 7, 10) में स्वग्रही या उच्च (कर्क, धनु, मीन) का बृहस्पति हंस योग बनाता है (बृहत् पाराशर होरा शास्त्र अ. 75)। | लग्नापासून केंद्रात (1, 4, 7, 10) स्वगृही किंवा उच्च राशीत (कर्क, धनु, मीन) गुरू असल्यास हंस योग होतो (बृहत् पाराशर होरा शास्त्र अ. 75). |
| `dosha.mangal_context.simple` | High partnership drive is indicated; traditional mitigations and open communication keep relationships balanced. | संबंधों में उच्च ऊर्जा के संकेत हैं; पारंपरिक परिहार और संवाद से संतुलन बना रहता है। | भागीदारीत उच्च ऊर्जा दिसून येते; पारंपारिक परिहार आणि संवादातून समतोल राखता येतो. |
| `dosha.mangal_context.pro` | Mars in house {mars_house} from Lagna ({mars_moon_house} from Moon); classical texts note cancellations and chart balance. | लग्न से {mars_house} भाव (चंद्र से {mars_moon_house} भाव) में मंगल; शास्त्रीय ग्रंथों में इसके कई परिहार बताए गए हैं। | लग्नापासून {mars_house} भावात (चंद्रापासून {mars_moon_house} भावात) मंगळ; शास्त्रीय ग्रंथांत याचे अनेक परिहार दिले आहेत. |
| `annual_overview.simple` | Your {year} annual forecast balances {md} Mahadasha themes with Jupiter transiting {jup_sign} and Saturn in {sat_sign}. | आपका {year} वार्षिक पूर्वानुमान {md} महादशा के विषयों को बृहस्पति के {jup_sign} गोचर और शनि के {sat_sign} में होने के साथ संतुलित करता है। | तुमचा {year} वार्षिक अंदाज {md} महादशेच्या विषयांना गुरूच्या {jup_sign} गोचर आणि शनीच्या {sat_sign} स्थितीसह संतुलित करतो. |
| `annual_overview.pro` | Annual synthesis for {lagna} Lagna / {moon} Rashi: {md}-{ad} Dasha with Saturn in House {sat_house} from Natal Moon. | {lagna} लग्न / {moon} राशि के लिए वार्षिक संश्लेषण: {md}-{ad} दशा, शनि नतल चंद्रमा से {sat_house} भाव में। | {lagna} लग्न / {moon} राशीसाठी वार्षिक संश्लेषण: {md}-{ad} दशा, शनी नातल चंद्रापासून {sat_house} भावात. |
| `why_this.label` | Why this? | यह क्यों? | हे का? |
| `tooltip.lagna` | Ascendant sign rising on the eastern horizon at birth; defines House 1. | जन्म के समय पूर्वी क्षितिज पर उदित होने वाली राशि; यह प्रथम भाव निर्धारित करती है। | जन्माच्या वेळी पूर्व क्षितिजावर उगवणारी रास; ही पहिले घर ठरवते. |
| `tooltip.rashi` | Sidereal zodiac sign occupied by the Moon or a planet (30 degrees each). | चंद्रमा या किसी ग्रह द्वारा अधिकृत निरयण राशि (प्रत्येक 30 अंश)। | चंद्र किंवा ग्रहाने व्यापलेली निरयण रास (प्रत्येकी 30 अंश). |
| `tooltip.nakshatra` | One of 27 lunar mansions (13 degrees 20 minutes each) along the ecliptic. | क्रांतिवृत्त के 27 चंद्र नक्षत्रों में से एक (प्रत्येक 13 अंश 20 कला)। | क्रांतिवृत्तावरील 27 चंद्र नक्षत्रांपैकी एक (प्रत्येकी 13 अंश 20 कला). |
| `tooltip.pada` | One of four quarters (3 degrees 20 minutes each) within a Nakshatra, corresponding to Navamsa (D9). | नक्षत्र के चार चरणों में से एक (प्रत्येक 3 अंश 20 कला), जो नवांश (D9) से संबंधित है। | नक्षत्राच्या चार चरणांपैकी एक (प्रत्येकी 3 अंश 20 कला), जे नवांशाशी (D9) जोडलेले आहे. |
| `tooltip.navamsa` | 9th divisional chart (D9) used in Parashari Jyotish to examine planetary strength and partnerships. | ग्रहों के बल और साझेदारी के विश्लेषण हेतु प्रयुक्त नवम वर्ग कुंडली (D9)। | ग्रहांचे बळ आणि जोडीदाराचे विश्लेषण करण्यासाठी वापरली जाणारी नवमांश कुंडली (D9). |
| `tooltip.ayanamsa` | Angular precession difference between tropical and sidereal zodiacs (Lahiri default). | सायण और निरयण राशि चक्र के बीच अयन चलन का अंतर (लहिरी डिफ़ॉल्ट)। | सायण आणि निरयण राशीचक्रातील संपातचलनाचे अंतर (लहिरी डिफॉल्ट). |
| `tooltip.dasha` | Vimshottari 120-year planetary period system anchored to Moon's birth Nakshatra. | जन्म के चंद्र नक्षत्र पर आधारित 120 वर्षीय विंशोत्तरी दशा प्रणाली। | जन्माच्या चंद्र नक्षत्रावर आधारित 120 वर्षांची विंशोत्तरी दशा पद्धती. |
| `tooltip.antardasha` | Sub-period within a major planetary period (Mahadasha). | महादशा के भीतर चलने वाली उप-अवधि। | महादशेतील उप-कालावधी. |
| `tooltip.pratyantardasha` | Third-level period within an Antardasha. | अंतर्दशा के भीतर चलने वाली तृतीय-स्तरीय अवधि। | अंतर्दशेतील तिसऱ्या स्तरावरील कालावधी. |
| `tooltip.tithi` | Lunar day defined by each 12-degree elongation between Moon and Sun at sunrise. | सूर्योदय के समय चंद्रमा और सूर्य के प्रत्येक 12 अंश के अंतर से बनने वाली चंद्र तिथि। | सूर्योदयाच्या वेळी चंद्र आणि सूर्यामधील प्रत्येक 12 अंशांच्या अंतराने बनणारी तिथी. |
| `tooltip.yoga` | Luni-solar angular sum divided into 27 segments, or a specific planetary combination in a chart. | सूर्य और चंद्रमा के भोगांशों का योग (27 पंचांग योग) अथवा कुंडली का विशेष ग्रह संयोग। | सूर्य आणि चंद्राच्या रेखांशांची बेरीज (27 पंचांग योग) किंवा कुंडलीतील विशिष्ट ग्रहयोग. |
| `tooltip.karana` | Half of a Tithi (6-degree Moon-Sun elongation). | तिथि का आधा भाग (सूर्य-चंद्र का 6 अंश का अंतर)। | तिथीचा अर्धा भाग (सूर्य-चंद्राचे 6 अंशांचे अंतर). |
| `tooltip.rahu_kaal` | One of eight daily daytime segments traditionally avoided for initiating new ventures. | सूर्योदय से सूर्यास्त के बीच के आठ भागों में से एक, जिसमें नए कार्य प्रारंभ करने से बचा जाता है। | सूर्योदयापासून सूर्यास्तापर्यंतच्या आठ भागांपैकी एक, ज्यात नवीन कामे सुरू करणे टाळले जाते. |
| `tooltip.abhijit` | Midday Muhurat around local solar noon traditionally considered supportive for constructive action. | स्थानीय मध्याह्न के आसपास का मुहूर्त जो रचनात्मक कार्यों के लिए अनुकूल माना जाता है। | स्थानिक मध्यान्हाच्या सुमारास असणारा मुहूर्त जो विधायक कामांसाठी अनुकूल मानला जातो. |
| `tooltip.sade_sati` | 7.5-year transit of Saturn through the 12th, 1st, and 2nd houses from natal Moon. | जन्म चंद्र राशि से 12वें, 1ले और 2रे भाव में शनि का साढ़े सात वर्षीय गोचर। | जन्म चंद्र राशीपासून 12व्या, 1ल्या आणि 2ऱ्या भावातून शनीचे साडेसात वर्षांचे भ्रमण. |
| `tooltip.ashtakoota` | Traditional 36-point Moon-based compatibility framework across 8 Koota categories. | आठ कूटों के आधार पर 36 गुणों की पारंपरिक कुंडली मिलान पद्धति। | आठ कूटांच्या आधारे 36 गुणांची पारंपारिक कुंडली गुणमिलन पद्धती. |
| `trust.about_calculations` | Steps 1 to 6 (geocoding, historical timezones, Swiss Ephemeris positions, Lahiri Ayanamsa, Whole-Sign houses, D9 Navamsa, Panchang, and Vimshottari Dasha) are deterministic mathematical calculations. | चरण 1 से 6 (स्थान, ऐतिहासिक समय क्षेत्र, स्विस एफेमेरिस ग्रह स्थिति, लहिरी अयनांश, भाव, नवांश, पंचांग और विंशोत्तरी दशा) पूर्णतः गणितीय गणनाएं हैं। | टप्पे 1 ते 6 (स्थान, ऐतिहासिक प्रमाणवेळ, स्विस एफेमेरिस ग्रहस्थिती, लहिरी अयनांश, भाव, नवांश, पंचांग आणि विंशोत्तरी दशा) या पूर्णपणे गणितीय गणना आहेत. |
| `trust.about_interpretations` | Steps 7 to 9 match chart placements against advisor-reviewed classical Parashari rules. Interpretations are traditional perspectives, never guaranteed or scientifically validated. | चरण 7 से 9 ज्योतिष सलाहकारों द्वारा समीक्षित पाराशरी नियमों पर आधारित हैं। ये पारंपरिक व्याख्याएं हैं, वैज्ञानिक रूप से प्रमाणित नहीं। | टप्पे 7 ते 9 हे तज्ज्ञ ज्योतिष सल्लागारांनी तपासलेल्या पाराशरी नियमांवर आधारित आहेत. ही पारंपारिक मते आहेत, वैज्ञानिकदृष्ट्या सिद्ध दावे नाहीत. |
| `trust.about_ledger` | Our Prediction Ledger is a pre-registered calibration log tracking how often users report stated outcomes over time. | हमारा प्रेडिक्शन लेजर एक पूर्व-पंजीकृत कैलिब्रेशन लॉग है जो दर्ज परिणामों का पारदर्शी सारांश दिखाता है। | आमचे प्रेडिक्शन लेजर हे पूर्व-नोंदणीकृत विधानांवर वापरकर्त्यांनी नोंदवलेल्या परिणामांचा पारदर्शक लॉग आहे. |
| `trust.professional_advice_disclaimer` | Astroplan readings are for cultural and reflective guidance only. Always consult qualified medical, financial, legal, or mental-health professionals for important life decisions. | एस्ट्रोप्लान के विवरण केवल सांस्कृतिक और आत्म-चिंतन मार्गदर्शन के लिए हैं। महत्वपूर्ण निर्णयों के लिए सदैव योग्य चिकित्सा, वित्तीय या कानूनी विशेषज्ञों से परामर्श लें। | एस्ट्रोप्लानमधील माहिती केवळ सांस्कृतिक व वैचारिक मार्गदर्शनासाठी आहे. महत्त्वाच्या निर्णयांसाठी नेहमी पात्र वैद्यकीय, आर्थिक किंवा कायदेशीर तज्ज्ञांचा सल्ला घ्यावा. |
| `error.unknown_timezone` | Unrecognized timezone identifier. | अमान्य समय-क्षेत्र (टाइमज़ोन) पहचानकर्ता। | अपरिचित टाइमझोन आयडेंटिफायर. |
| `error.ambiguous_location` | Location could not be uniquely resolved; please select a city candidate or enter manual coordinates. | स्थान स्पष्ट नहीं हो सका; कृपया सूची से शहर चुनें या अक्षांश/देशांतर दर्ज करें। | स्थान निश्चित करता आले नाही; कृपया यादीतून शहर निवडा किंवा अक्षांश/रेखांश प्रविष्ट करा. |
| `error.geocoder_unavailable` | Place lookup service is temporarily unreachable; please provide manual latitude and longitude. | स्थान खोज सेवा अस्थायी रूप से अनुपलब्ध है; कृपया अक्षांश और देशांतर दर्ज करें। | स्थान शोध सेवा तात्पुरती अनुपलब्ध आहे; कृपया अक्षांश आणि रेखांश प्रविष्ट करा. |
| `ask.coverage.uncovered_title` | No reviewed answer for this area yet. | इस विषय के लिए अभी समीक्षित उत्तर नहीं है। | या विषयासाठी सध्या तपासलेले उत्तर नाही. |
| `ask.coverage.uncovered_body` | Astroplan currently interprets four life areas from advisor-reviewed rules: {areas}. This question falls outside them, so we will not improvise an answer. | एस्ट्रोप्लान फिलहाल सलाहकार-समीक्षित नियमों से चार जीवन-क्षेत्रों की व्याख्या करता है: {areas}. यह प्रश्न इनसे बाहर है, इसलिए हम अपनी ओर से उत्तर नहीं गढ़ेंगे। | अ‍ॅस्ट्रोप्लॅन सध्या सल्लागार-तपासलेल्या नियमांवरून चार जीवनक्षेत्रांचा अर्थ लावते: {areas}. हा प्रश्न त्याबाहेर आहे, म्हणून आम्ही स्वतःहून उत्तर तयार करणार नाही. |
| `ask.coverage.suggestion` | Try asking about career, money, home, or relationships. | करियर, धन, घर या रिश्तों के बारे में पूछकर देखें। | करिअर, पैसा, घर किंवा नात्यांबद्दल विचारून पाहा. |
| `error.ask_question_invalid` | Please enter a question between 3 and 280 characters. | कृपया 3 से 280 अक्षरों के बीच प्रश्न लिखें। | कृपया 3 ते 280 अक्षरांमधील प्रश्न लिहा. |
| `error.ask_quota_exhausted` | Your three free questions for this week are used. They reset on Monday. | इस सप्ताह के तीन नि:शुल्क प्रश्न पूरे हो गए हैं। सोमवार को रीसेट होंगे। | या आठवड्याचे तीन मोफत प्रश्न संपले आहेत. सोमवारी पुन्हा सुरू होतील. |
| `error.ask_disabled` | Ask is not available right now. | अभी पूछें सुविधा उपलब्ध नहीं है। | सध्या विचारा सुविधा उपलब्ध नाही. |

Verdict: [ ] approve  [ ] approve with edits  [ ] reject — notes:

---

## 5. What G2 does not cover

- Chart mathematics and ephemeris output — covered by gate G1 and its frozen
  swetest reference set.
- Deterministic placement logic in Python (`app/core/yogas.py`,
  `app/interpretation/readings.py`) — unit-tested separately.

## 6. After approval

1. Applies `status: approved`, `reviewer`, `reviewed_at` to every item above.
2. Runs `pytest --gates -m release_gate_g2` and the full suite.
3. Commits the sign-off; the owner decides when to push.

