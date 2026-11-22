/// Same area words as rules/ask_lexicon.yaml. The question is never sent to a model.
const lifeAreaOrder = ['career', 'relationships', 'finances', 'home'];

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
    'नौकरी',
    'करियर',
    'नोकरी',
    'करिअर',
  ],
  'relationships': [
    'marriage',
    'marry',
    'married',
    'partner',
    'spouse',
    'relationship',
    'commit',
    'विवाह',
    'शादी',
    'रिश्ते',
    'नाते',
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
    'पैसा',
    'कर्ज',
    'पैसे',
  ],
  'home': [
    'home',
    'house',
    'property',
    'rent',
    'move',
    'renovate',
    'family',
    'घर',
    'मकान',
    'जमीन',
    'घरबदल',
  ],
};

bool _matches(String lowered, String term) {
  final ascii = term.runes.every((unit) => unit < 128);
  if (ascii) {
    return RegExp('(?<![a-z])${RegExp.escape(term.toLowerCase())}')
        .hasMatch(lowered);
  }
  return lowered.contains(term);
}

/// One life area when a single area has the most matching words, otherwise none.
String? classifyLifeArea(String question) {
  final lowered = question.toLowerCase();
  final scores = <String, int>{};
  for (final area in lifeAreaOrder) {
    final hits =
        lifeAreaTerms[area]!.where((term) => _matches(lowered, term)).length;
    if (hits > 0) scores[area] = hits;
  }
  if (scores.isEmpty) return null;
  final best = scores.values.reduce((left, right) => left > right ? left : right);
  final winners = [
    for (final entry in scores.entries)
      if (entry.value == best) entry.key
  ];
  if (winners.length != 1) return null;
  return winners.single;
}
