import 'package:astroplan/ask_area.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('career words, including startup, route to career', () {
    const question =
        'it looks I stuck in my career...what should be my future...shall I get an new job or shall I Startup new business';
    expect(classifyLifeArea(question), 'career');
    expect(classifyLifeArea('Shall I startup?'), 'career');
  });

  test('a question outside the four areas stays closed', () {
    expect(classifyLifeArea('How is my health?'), isNull);
  });

  test('a tie between two areas does not pick one', () {
    expect(classifyLifeArea('Should I move for a new job?'), isNull);
  });
}