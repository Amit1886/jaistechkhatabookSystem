import 'dart:async';

import 'package:get/get.dart';

import '../services/sync_service.dart';

class SyncController extends GetxController {
  SyncController(this._sync);

  final SyncService _sync;

  final Rx<SyncStatus> status = SyncStatus.idle.obs;
  final RxString lastError = ''.obs;
  final Rxn<DateTime> lastSyncAt = Rxn<DateTime>();

  Timer? _poller;

  @override
  void onInit() {
    super.onInit();
    _poller = Timer.periodic(const Duration(seconds: 1), (_) {
      status.value = _sync.status;
      lastError.value = _sync.lastError ?? '';
      lastSyncAt.value = _sync.lastSyncAt;
    });
  }

  @override
  void onClose() {
    _poller?.cancel();
    _poller = null;
    super.onClose();
  }

  Future<void> syncNow() => _sync.syncOnce();
}

