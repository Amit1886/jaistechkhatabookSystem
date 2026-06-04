import '../local_db.dart';
import '../tables.dart';

class SyncStateDao {
  SyncStateDao(this._db);

  final LocalDb _db;

  Future<String?> getValue(String key) async {
    final rows = await _db.query(Tables.syncState, where: 'key = ?', whereArgs: [key], limit: 1);
    if (rows.isEmpty) return null;
    return rows.first['value']?.toString();
  }

  Future<void> setValue(String key, String value) async {
    await _db.upsert(Tables.syncState, {'key': key, 'value': value});
  }
}

