/// Same area words as rules/ask_lexicon.yaml. The question is never sent to a model.
const lifeAreaOrder = ['career', 'relationships', 'finances', 'home', 'others'];

const lifeAreaTerms = <String, List<String>>{
  'career': [
    'job',
    'career',
    'promotion',
    'appraisal',
    'work',
    'role',
    'interview',
    'business',
    'startup',
    'office',
    'transfer',
    'boss',
    'employer',
    'profession',
    'employment',
    'नौकरी',
    'करियर',
    'प्रोमोशन',
    'ऑफिस',
    'व्यवसाय',
    'नोकरी',
    'करिअर',
    'कामा',
    'नोकरीचा',
  ],
  'relationships': [
    'marriage',
    'marry',
    'married',
    'partner',
    'spouse',
    'relationship',
    'commit',
    'love',
    'boyfriend',
    'girlfriend',
    'husband',
    'wife',
    'divorce',
    'wedding',
    'engagement',
    'विवाह',
    'शादी',
    'रिश्ते',
    'पति',
    'पत्नी',
    'प्रेम',
    'नाते',
    'लग्न',
    'जोडीदार',
  ],
  'finances': [
    'money',
    'finance',
    'loan',
    'debt',
    'saving',
    'invest',
    'salary',
    'income',
    'wealth',
    'expense',
    'spending',
    'profit',
    'loss',
    'पैसा',
    'कर्ज',
    'पैसे',
    'आय',
    'बचत',
    'धन',
    'उत्पन्न',
    'खर्च',
  ],
  'home': [
    'home',
    'house',
    'property',
    'rent',
    'move',
    'renovate',
    'family',
    'mother',
    'father',
    'parents',
    'domestic',
    'flat',
    'घर',
    'मकान',
    'जमीन',
    'परिवार',
    'माता',
    'पिता',
    'घरबदल',
    'कुटुंब',
    'आई',
    'वडील',
  ],
  'others': [
    'car',
    'vehicle',
    'bike',
    'scooter',
    'automobile',
    'गाड़ी',
    'गाडी',
    'कार',
    'वाहन',
  ],
};

const presentTimeCues = [
  'today',
  'now',
  'this week',
  'currently',
  'tonight',
  'this month',
  'आज',
  'अभी',
  'इस हफ्ते',
  'इस महीने',
  'आता',
  'या आठवड्यात',
  'सध्या',
  'या महिन्यात',
];

bool _matches(String lowered, String term) {
  final ascii = term.runes.every((unit) => unit < 128);
  if (ascii) {
    return RegExp('(?<![a-z])${RegExp.escape(term.toLowerCase())}')
        .hasMatch(lowered);
  }
  return lowered.contains(term);
}

/// One life area when a single area has the most matching words, otherwise none.
/// Others is only used when none of the four life areas match, so "car" does not tie with "career".
String? classifyLifeArea(String question) {
  final lowered = question.toLowerCase();
  final scores = <String, int>{};
  for (final area in lifeAreaOrder) {
    if (area == 'others') continue;
    final hits =
        lifeAreaTerms[area]!.where((term) => _matches(lowered, term)).length;
    if (hits > 0) scores[area] = hits;
  }
  if (scores.isEmpty) {
    final otherHits = lifeAreaTerms['others']!
        .where((term) => _matches(lowered, term))
        .length;
    return otherHits > 0 ? 'others' : null;
  }
  final best = scores.values.reduce((left, right) => left > right ? left : right);
  final winners = [
    for (final entry in scores.entries)
      if (entry.value == best) entry.key
  ];
  if (winners.length != 1) return null;
  return winners.single;
}

bool isPresentTimeQuestion(String question) {
  final lowered = question.toLowerCase();
  return presentTimeCues.any((cue) => _matches(lowered, cue));
}
