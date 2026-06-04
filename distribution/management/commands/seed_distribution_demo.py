from django.core.management.base import BaseCommand

from distribution.models import (
    AppPlatform,
    AppVersion,
    FeatureRegistry,
    Industry,
    IndustryModuleMap,
    ModuleRegistry,
    RemoteConfig,
    SoftwareBuild,
)


class Command(BaseCommand):
    help = "Seed demo industries, platforms, modules, and download-center software."

    def handle(self, *args, **options):
        industries = [
            ("apparel-clothing", "Apparel & Clothing", "shirt", 10),
            ("boutiques", "Boutiques", "hanger", 20),
            ("footwear", "Footwear", "shoe", 30),
            ("grocery", "Supermarket & Groceries", "basket", 40),
            ("restaurant", "Restaurant", "utensils", 50),
            ("pharmacy", "Pharma & Healthcare", "medical", 60),
            ("electronics", "Electrical, Electronics & Computers", "cpu", 70),
            ("wholesale", "Hypermarket & Departmental Stores", "warehouse", 80),
            ("bakery", "Bakery", "cake", 90),
            ("salon", "Salon", "scissors", 100),
            ("hardware", "Hardware", "tool", 110),
            ("textile", "Textile", "layers", 120),
        ]
        industry_objs = {}
        for slug, name, icon, order in industries:
            obj, _ = Industry.objects.update_or_create(slug=slug, defaults={"name": name, "icon": icon, "sort_order": order, "is_active": True})
            industry_objs[slug] = obj

        platforms = [
            ("web", "Web App", AppPlatform.PlatformType.WEB, "globe", 10),
            ("android-apk", "Android APK", AppPlatform.PlatformType.ANDROID_APK, "android", 20),
            ("desktop-exe", "Desktop EXE", AppPlatform.PlatformType.DESKTOP_EXE, "monitor", 30),
            ("embedded-pos", "Embedded POS", AppPlatform.PlatformType.EMBEDDED_POS, "terminal", 40),
            ("self-checkout", "Self Checkout Kiosk", AppPlatform.PlatformType.SELF_CHECKOUT, "scan", 50),
            ("pwa", "PWA", AppPlatform.PlatformType.PWA, "cloud", 60),
            ("tablet-pos", "Tablet POS", AppPlatform.PlatformType.TABLET_POS, "tablet", 70),
            ("mobile-pos", "Mobile POS", AppPlatform.PlatformType.MOBILE_POS, "phone", 80),
        ]
        platform_objs = {}
        for code, name, ptype, icon, order in platforms:
            obj, _ = AppPlatform.objects.update_or_create(code=code, defaults={"name": name, "platform_type": ptype, "icon": icon, "sort_order": order, "is_active": True})
            platform_objs[code] = obj
            AppVersion.objects.update_or_create(platform=obj, version="1.0.0", defaults={"is_current": True, "release_notes": "Live-sync enabled baseline."})

        features = [
            ("barcode-pos", "Barcode POS", ["grocery", "apparel-clothing", "footwear", "electronics", "wholesale"], ["web", "desktop-exe", "tablet-pos"]),
            ("self-checkout", "Self Checkout", ["grocery", "wholesale"], ["self-checkout", "web"]),
            ("kitchen-display", "Kitchen Display", ["restaurant", "bakery"], ["web", "tablet-pos"]),
            ("qr-menu", "QR Menu Ordering", ["restaurant", "bakery"], ["web", "pwa", "android-apk"]),
            ("batch-expiry", "Batch & Expiry Tracking", ["pharmacy"], ["web", "desktop-exe"]),
            ("inventory-control", "Complete Inventory Control", ["grocery", "apparel-clothing", "electronics", "wholesale", "textile"], ["web", "desktop-exe"]),
            ("delivery-management", "Delivery Management App", ["grocery", "restaurant", "pharmacy"], ["android-apk", "web"]),
        ]
        for slug, name, ind_slugs, platform_codes in features:
            feature, _ = FeatureRegistry.objects.update_or_create(slug=slug, defaults={"name": name, "version": "1.0.0", "is_enabled": True, "rollout_status": FeatureRegistry.RolloutStatus.STABLE})
            feature.industries.set([industry_objs[s] for s in ind_slugs if s in industry_objs])
            feature.supported_platforms.set([platform_objs[p] for p in platform_codes if p in platform_objs])

        modules = [
            ("pos-terminal", "POS Terminal", ModuleRegistry.ModuleType.POS_MODULE, "/pos/ui/", "barcode-pos", ["grocery", "apparel-clothing", "footwear", "electronics", "wholesale"]),
            ("self-checkout-kiosk", "Express Checkout POS", ModuleRegistry.ModuleType.KIOSK_MODULE, "/pos/self-checkout/", "self-checkout", ["grocery", "wholesale"]),
            ("kitchen-display", "Kitchen Display System", ModuleRegistry.ModuleType.PAGE, "/api/v1/super-app/kitchen-queue/", "kitchen-display", ["restaurant", "bakery"]),
            ("qr-table-ordering", "QR Table Ordering", ModuleRegistry.ModuleType.PAGE, "/api/v1/super-app/table-orders/", "qr-menu", ["restaurant", "bakery"]),
            ("pharmacy-expiry-alerts", "Expiry Alerts", ModuleRegistry.ModuleType.DASHBOARD_CARD, "/reports/", "batch-expiry", ["pharmacy"]),
            ("inventory-control", "Complete Inventory Control", ModuleRegistry.ModuleType.PAGE, "/api/v1/products/", "inventory-control", ["grocery", "apparel-clothing", "electronics", "wholesale", "textile"]),
        ]
        for idx, (slug, name, mtype, route, feature_slug, ind_slugs) in enumerate(modules, start=1):
            module, _ = ModuleRegistry.objects.update_or_create(
                slug=slug,
                defaults={"name": name, "module_type": mtype, "route_path": route, "component_key": slug, "version": "1.0.0", "is_enabled": True, "sort_order": idx * 10},
            )
            module.industries.set([industry_objs[s] for s in ind_slugs if s in industry_objs])
            feature = FeatureRegistry.objects.filter(slug=feature_slug).first()
            if feature:
                module.features.set([feature])
            for s in ind_slugs:
                if s in industry_objs:
                    IndustryModuleMap.objects.update_or_create(industry=industry_objs[s], module=module, defaults={"is_required": True, "default_enabled": True})

        build_specs = [
            ("apparel-pos", "APPAREL & CLOTHING", "web", "apparel-clothing", "/accounts/signup/"),
            ("boutiques-pos", "BOUTIQUES", "web", "boutiques", "/accounts/signup/"),
            ("footwear-pos", "FOOTWEAR", "web", "footwear", "/accounts/signup/"),
            ("shoes-pos", "SHOES", "web", "footwear", "/accounts/signup/"),
            ("textile-pos", "TEXTILE", "web", "textile", "/accounts/signup/"),
            ("inventory-control", "COMPLETE INVENTORY CONTROL", "web", "grocery", "/api/v1/products/"),
            ("delivery-app", "DELIVERY MANAGEMENT APP", "android-apk", "restaurant", ""),
            ("online-ordering", "ONLINE ORDERING APP", "pwa", "restaurant", "/store/"),
            ("express-checkout-pos", "EXPRESS CHECKOUT POS", "self-checkout", "grocery", "/pos/self-checkout/"),
            ("price-checking-app", "PRICE CHECKING APP", "android-apk", "grocery", ""),
            ("business-assistant", "BUSINESS ASSISTANT", "pwa", "wholesale", "/app/"),
            ("pos-reporting-app", "24*7 POS REPORTING APP", "android-apk", "electronics", "/smart-bi/"),
            ("pharmacy-pos", "PHARMACY POS", "web", "pharmacy", "/accounts/signup/"),
            ("restaurant-pos", "RESTAURANT POS", "web", "restaurant", "/accounts/signup/"),
        ]
        for idx, (slug, title, platform_code, industry_slug, launch) in enumerate(build_specs, start=1):
            platform = platform_objs.get(platform_code)
            build, _ = SoftwareBuild.objects.update_or_create(
                slug=slug,
                defaults={
                    "title": title,
                    "build_type": platform.platform_type if platform else SoftwareBuild.BuildType.WEB,
                    "platform": platform,
                    "version": "1.0.0",
                    "web_launch_url": launch,
                    "pwa_url": launch if platform_code == "pwa" else "",
                    "play_store_url": "https://play.google.com/store" if platform_code in {"android-apk", "self-checkout"} else "",
                    "app_store_url": "https://www.apple.com/app-store/" if platform_code in {"android-apk", "self-checkout"} and idx % 2 == 0 else "",
                    "external_url": launch,
                    "release_notes": "Demo live-sync software entry.",
                    "is_published": True,
                    "allow_public_download": True,
                    "sort_order": idx * 10,
                },
            )
            if industry_slug in industry_objs:
                build.industries.set([industry_objs[industry_slug]])

        RemoteConfig.objects.update_or_create(
            key="global-live-sync",
            scope=RemoteConfig.Scope.GLOBAL,
            defaults={
                "payload": {
                    "dynamic_menus": True,
                    "auto_refresh_seconds": 30,
                    "offline_cache": True,
                    "pwa_enabled": True,
                    "no_rebuild_feature_delivery": True,
                },
                "version": 1,
                "is_active": True,
            },
        )
        self.stdout.write(self.style.SUCCESS("Distribution demo data seeded. Open /downloads/"))

