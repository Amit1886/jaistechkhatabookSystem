import '../database/local_db.dart';
import '../database/tables.dart';
import '../models/party_model.dart';
import 'api_service.dart';
import 'id_service.dart';

class PartyService {
  PartyService(this._db, {ApiService? api}) : _api = api;

  final LocalDb _db;
  final ApiService? _api;

  Future<List<PartyModel>> list({
    required String businessId,
    String? type, // customer | supplier | null (all)
    String? query,
  }) async {
    final api = _api;
    if (api != null) {
      try {
        final queryParams = <String, String>{};
        if (type != null && type.isNotEmpty) queryParams['type'] = type;
        if (query != null && query.trim().isNotEmpty) {
          queryParams['q'] = query.trim();
        }
        final res = await api.getJson(
          '/api/app/customers/',
          query: queryParams.isEmpty ? null : queryParams,
        );
        final rows = (res['results'] as List? ?? const [])
            .whereType<Map>()
            .map((row) => PartyModel.fromJson(
                  Map<String, dynamic>.from(row),
                  businessId: businessId,
                  type: (row['type'] ?? type ?? 'customer').toString(),
                ))
            .toList();
        for (final row in rows) {
          await _db.upsert(Tables.parties, row.toMap());
        }
        return rows;
      } catch (_) {
        // Local cache remains the offline fallback.
      }
    }

    final where = <String>['business_id = ?', 'is_deleted = 0'];
    final args = <Object?>[businessId];
    if (type != null && type.isNotEmpty) {
      where.add('type = ?');
      args.add(type);
    }
    if (query != null && query.trim().isNotEmpty) {
      where.add('name LIKE ?');
      args.add('%${query.trim()}%');
    }
    final rows = await _db.query(
      Tables.parties,
      where: where.join(' AND '),
      whereArgs: args,
      orderBy: 'updated_at DESC',
      limit: 500,
    );
    return rows.map(PartyModel.fromMap).toList();
  }

  Future<PartyModel> create({
    required String businessId,
    required String type,
    required String name,
    String? phone,
    String? address,
    String? gstin,
    double openingBalance = 0,
  }) async {
    final now = DateTime.now();
    final party = PartyModel(
      id: IdService.newId(),
      businessId: businessId,
      type: type,
      name: name.trim(),
      phone: phone?.trim().isEmpty ?? true ? null : phone?.trim(),
      address: address?.trim().isEmpty ?? true ? null : address?.trim(),
      gstin: gstin?.trim().isEmpty ?? true ? null : gstin?.trim(),
      openingBalance: openingBalance,
      createdAt: now,
      updatedAt: now,
      isSynced: false,
      isDeleted: false,
    );
    final api = _api;
    if (api != null) {
      try {
        final res = await api.postJson('/api/app/customers/', {
          'type': party.type,
          'name': party.name,
          'phone': party.phone,
          'address': party.address,
          'gstin': party.gstin,
          'opening_balance': party.openingBalance,
        });
        final saved = PartyModel.fromJson(
          res,
          businessId: businessId,
          type: (res['type'] ?? type).toString(),
        );
        await _db.upsert(Tables.parties, saved.toMap());
        return saved;
      } catch (_) {
        // Keep offline create when API is unavailable.
      }
    }

    await _db.upsert(Tables.parties, party.toMap());
    return party;
  }

  Future<void> update(PartyModel party) async {
    final updated = party.copyWith(updatedAt: DateTime.now(), isSynced: false);
    final api = _api;
    if (api != null) {
      try {
        final res = await api.patchJson('/api/app/customers/${party.id}/', {
          'type': updated.type,
          'name': updated.name,
          'phone': updated.phone,
          'address': updated.address,
          'gstin': updated.gstin,
          'opening_balance': updated.openingBalance,
        });
        final saved = PartyModel.fromJson(
          res,
          businessId: party.businessId,
          type: (res['type'] ?? updated.type).toString(),
        );
        await _db.upsert(Tables.parties, saved.toMap());
        return;
      } catch (_) {
        // Keep offline update when API is unavailable.
      }
    }
    await _db.upsert(Tables.parties, updated.toMap());
  }

  Future<void> delete({required String partyId}) async {
    final api = _api;
    if (api != null) {
      try {
        await api.deleteJson('/api/app/customers/$partyId/');
        await _db.softDeleteById(Tables.parties, partyId);
        return;
      } catch (_) {
        // Keep offline delete when API is unavailable.
      }
    }
    await _db.softDeleteById(Tables.parties, partyId);
  }
}
