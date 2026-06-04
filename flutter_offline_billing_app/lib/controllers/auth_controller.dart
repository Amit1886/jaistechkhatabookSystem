import 'package:get/get.dart';

import '../models/user_model.dart';
import 'enterprise_app_controller.dart';
import '../services/auth_service.dart';
import '../services/sync_service.dart';

class AuthController extends GetxController {
  AuthController({
    required AuthService auth,
    required SyncService sync,
  })  : _auth = auth,
        _sync = sync;

  final AuthService _auth;
  final SyncService _sync;

  final Rxn<UserModel> currentUser = Rxn<UserModel>();
  final RxBool isBusy = false.obs;
  final RxString error = ''.obs;
  final RxString sessionMode = 'guest'.obs;

  @override
  void onInit() {
    super.onInit();
    bootstrap();
  }

  Future<void> bootstrap() async {
    isBusy.value = true;
    error.value = '';
    try {
      final user = await _auth.bootstrap();
      currentUser.value = user;
      sessionMode.value = user == null ? 'guest' : 'enterprise';
      isBusy.value = false;
      try {
        await _sync.bootstrap();
      } catch (e) {
        error.value = e.toString();
      }
      if (user != null && Get.isRegistered<EnterpriseAppController>()) {
        await Get.find<EnterpriseAppController>().refreshConfig();
      }
      _sync.start();
    } catch (e) {
      error.value = e.toString();
      currentUser.value = null;
      sessionMode.value = 'guest';
    } finally {
      isBusy.value = false;
    }
  }

  Future<void> login(
      {required String username, required String password}) async {
    isBusy.value = true;
    error.value = '';
    try {
      final user = await _auth.login(username: username, password: password);
      currentUser.value = user;
      sessionMode.value = 'enterprise';
      await _sync.syncOnce();
      if (Get.isRegistered<EnterpriseAppController>()) {
        await Get.find<EnterpriseAppController>().refreshConfig();
      }
    } catch (e) {
      error.value = e.toString();
      rethrow;
    } finally {
      isBusy.value = false;
    }
  }

  Future<void> loginOffline(
      {required String username, required String password}) async {
    isBusy.value = true;
    error.value = '';
    try {
      final user =
          await _auth.loginOffline(username: username, password: password);
      currentUser.value = user;
      sessionMode.value = 'offline';
      await _sync.syncOnce();
      if (Get.isRegistered<EnterpriseAppController>()) {
        await Get.find<EnterpriseAppController>().refreshConfig();
      }
    } catch (e) {
      error.value = e.toString();
      rethrow;
    } finally {
      isBusy.value = false;
    }
  }

  Future<void> signupOffline(
      {required String username,
      required String password,
      String? name}) async {
    isBusy.value = true;
    error.value = '';
    try {
      final user = await _auth.signupOffline(
          username: username, password: password, name: name);
      currentUser.value = user;
      sessionMode.value = 'offline';
      await _sync.syncOnce();
      if (Get.isRegistered<EnterpriseAppController>()) {
        await Get.find<EnterpriseAppController>().refreshConfig();
      }
    } catch (e) {
      error.value = e.toString();
      rethrow;
    } finally {
      isBusy.value = false;
    }
  }

  Future<void> signupOnline(
      {required String username,
      required String password,
      String? name}) async {
    isBusy.value = true;
    error.value = '';
    try {
      final user = await _auth.signupOnline(
        username: username,
        password: password,
        name: name,
      );
      currentUser.value = user;
      sessionMode.value = 'enterprise';
      await _sync.syncOnce();
      if (Get.isRegistered<EnterpriseAppController>()) {
        await Get.find<EnterpriseAppController>().refreshConfig();
      }
    } catch (e) {
      error.value = e.toString();
      rethrow;
    } finally {
      isBusy.value = false;
    }
  }

  Future<void> logout() async {
    await _auth.logout();
    currentUser.value = null;
    sessionMode.value = 'guest';
  }

  Future<void> loginDemo() async {
    isBusy.value = true;
    error.value = '';
    try {
      final now = DateTime.now();
      currentUser.value = UserModel(
        id: 'Demotest3',
        email: 'demotest3@enterprise.demo',
        name: 'Demotest3',
        createdAt: now,
        updatedAt: now,
        isSynced: true,
        isDeleted: false,
      );
      sessionMode.value = 'demo';
      if (Get.isRegistered<EnterpriseAppController>()) {
        await Get.find<EnterpriseAppController>().refreshConfig();
      }
    } finally {
      isBusy.value = false;
    }
  }
}
