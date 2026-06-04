import 'package:flutter/widgets.dart';

enum EnterpriseDeviceClass { mobile, tablet, desktop, ultrawide, pos, kiosk }

class EnterpriseBreakpoints {
  const EnterpriseBreakpoints._();

  static EnterpriseDeviceClass classify(BuildContext context) {
    final size = MediaQuery.sizeOf(context);
    final shortest = size.shortestSide;
    if (size.width >= 1600) return EnterpriseDeviceClass.ultrawide;
    if (size.width >= 1024) return EnterpriseDeviceClass.desktop;
    if (size.width >= 700) return EnterpriseDeviceClass.tablet;
    if (shortest >= 560 && size.width > size.height) {
      return EnterpriseDeviceClass.pos;
    }
    return EnterpriseDeviceClass.mobile;
  }

  static int gridColumns(BuildContext context) {
    return switch (classify(context)) {
      EnterpriseDeviceClass.ultrawide => 5,
      EnterpriseDeviceClass.desktop => 4,
      EnterpriseDeviceClass.tablet => 3,
      EnterpriseDeviceClass.pos => 3,
      EnterpriseDeviceClass.kiosk => 2,
      EnterpriseDeviceClass.mobile => 1,
    };
  }

  static EdgeInsets pagePadding(BuildContext context) {
    return switch (classify(context)) {
      EnterpriseDeviceClass.ultrawide => const EdgeInsets.all(28),
      EnterpriseDeviceClass.desktop => const EdgeInsets.all(22),
      EnterpriseDeviceClass.tablet => const EdgeInsets.all(18),
      _ => const EdgeInsets.all(14),
    };
  }

  static bool get isTouchOptimized =>
      WidgetsBinding.instance.platformDispatcher.views.first.physicalSize.width <
      1200;
}
