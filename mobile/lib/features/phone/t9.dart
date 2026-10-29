/// Keypad search ("smart dial"): digits typed on the keypad match a contact's number, or the letters of a name through
/// the phone-keypad mapping (2 = abc … 9 = wxyz), at the start of any word. Pure Dart, unit-tested.
const _letters = {
  'a': '2', 'b': '2', 'c': '2', 'd': '3', 'e': '3', 'f': '3', 'g': '4', 'h': '4', 'i': '4', 'j': '5', 'k': '5', 'l': '5', 'm': '6', 'n': '6', 'o': '6',
  'p': '7', 'q': '7', 'r': '7', 's': '7', 't': '8', 'u': '8', 'v': '8', 'w': '9', 'x': '9', 'y': '9', 'z': '9',
};

const keypadLetters = {'2': 'ABC', '3': 'DEF', '4': 'GHI', '5': 'JKL', '6': 'MNO', '7': 'PQRS', '8': 'TUV', '9': 'WXYZ', '0': '+'};

String t9Digits(String text) => text.toLowerCase().split('').map((c) => _letters[c] ?? (RegExp(r'\d').hasMatch(c) ? c : ' ')).join();

String digitsOnly(String text) => text.replaceAll(RegExp(r'[^\d]'), '');

class T9Match<T> {
  const T9Match(this.item, this.score);
  final T item;
  /// Lower is better: name-word start 0, number prefix 1, number contains 2.
  final int score;
}

/// Matches for [query] (keypad digits, at least one). [name] and [number] read an item.
List<T> t9Search<T>(List<T> items, String query, {required String Function(T) name, required String Function(T) number, int limit = 6}) {
  final q = digitsOnly(query);
  if (q.isEmpty) return const [];
  final matches = <T9Match<T>>[];
  for (final item in items) {
    final words = t9Digits(name(item)).split(' ').where((w) => w.isNotEmpty);
    final digits = digitsOnly(number(item));
    // Local numbers are typed with 0 (0754…); stored ones may be +255754…
    final local = digits.startsWith('255') && digits.length > 9 ? '0${digits.substring(3)}' : digits;
    if (words.any((w) => w.startsWith(q))) {
      matches.add(T9Match(item, 0));
    } else if (digits.startsWith(q) || local.startsWith(q)) {
      matches.add(T9Match(item, 1));
    } else if (q.length >= 3 && (digits.contains(q) || local.contains(q))) {
      matches.add(T9Match(item, 2));
    }
  }
  matches.sort((a, b) => a.score.compareTo(b.score));
  return matches.take(limit).map((m) => m.item).toList();
}
