class PosRuntimeProfile {
  const PosRuntimeProfile({
    required this.touchOptimized,
    required this.barcodeEnabled,
    required this.thermalPrinterEnabled,
    required this.offlineBillingEnabled,
    required this.kitchenModeEnabled,
    required this.customerDisplayEnabled,
  });

  final bool touchOptimized;
  final bool barcodeEnabled;
  final bool thermalPrinterEnabled;
  final bool offlineBillingEnabled;
  final bool kitchenModeEnabled;
  final bool customerDisplayEnabled;

  factory PosRuntimeProfile.fromFeatures(Map<String, bool> features) {
    return PosRuntimeProfile(
      touchOptimized: features['touch'] ?? true,
      barcodeEnabled: features['barcode_scanner'] ?? false,
      thermalPrinterEnabled: features['thermal_printer'] ?? false,
      offlineBillingEnabled: features['offline_mode'] ?? true,
      kitchenModeEnabled: features['kitchen_mode'] ?? true,
      customerDisplayEnabled: features['customer_display'] ?? true,
    );
  }
}
