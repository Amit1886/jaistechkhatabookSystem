import 'dart:math';

/// Generates stable offline IDs without needing internet/server.
/// Using string IDs avoids conflicts during sync.
class IdService {
  IdService._();

  static final _rand = Random.secure();

  static String newId() {
    final ts = DateTime.now().microsecondsSinceEpoch;
    final randomHex = List.generate(
      16,
      (_) => _rand.nextInt(16).toRadixString(16),
    ).join();
    return '$ts-$randomHex';
  }
}
