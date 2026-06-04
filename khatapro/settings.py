import os
import sys
import importlib.util
from datetime import timedelta
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

# =========================================================
# DESKTOP / RUNTIME
# =========================================================
IS_FROZEN = bool(getattr(sys, "frozen", False))

DESKTOP_MODE = IS_FROZEN or (
    os.getenv("DESKTOP_MODE", "False").strip().lower()
    in {"1", "true", "yes", "on"}
)

RUNNING_RUNSERVER = "runserver" in sys.argv
RUNNING_TESTS = "test" in sys.argv

_kp_app_data_dir = os.getenv("KP_APP_DATA_DIR")

if _kp_app_data_dir:
    APP_DATA_DIR = Path(_kp_app_data_dir)
else:
    APP_DATA_DIR = Path(
        os.getenv("LOCALAPPDATA")
        or os.getenv("APPDATA")
        or str(BASE_DIR)
    ) / "Billentra"

DESKTOP_DATA_DIR = APP_DATA_DIR if (IS_FROZEN or DESKTOP_MODE) else BASE_DIR

try:
    DESKTOP_DATA_DIR.mkdir(parents=True, exist_ok=True)
except Exception:
    DESKTOP_DATA_DIR = BASE_DIR

# =========================================================
# ENV LOAD
# =========================================================
_meipass = getattr(sys, "_MEIPASS", None)

if _meipass:
    load_dotenv(
        dotenv_path=str(Path(_meipass) / ".env"),
        override=False
    )

load_dotenv(dotenv_path=str(BASE_DIR / ".env"), override=False)
load_dotenv(dotenv_path=str(DESKTOP_DATA_DIR / ".env"), override=True)

# =========================================================
# SECURITY
# =========================================================
DEBUG = os.getenv(
    "DEBUG",
    "True"
).strip().lower() in {"1", "true", "yes", "on"}

SECRET_KEY = (
    os.getenv("DJANGO_SECRET_KEY")
    or "dev-secret-key-please-change"
).strip()

OTP_BYPASS = os.getenv("OTP_BYPASS", "True") == "True"

ALLOWED_HOSTS = [
    h.strip()
    for h in os.getenv("ALLOWED_HOSTS", "*").split(",")
    if h.strip()
]

if os.getenv("RENDER_EXTERNAL_HOSTNAME"):
    ALLOWED_HOSTS.append(os.getenv("RENDER_EXTERNAL_HOSTNAME"))

if DESKTOP_MODE and "*" not in ALLOWED_HOSTS:
    for _h in ("localhost", "127.0.0.1", "127.0.0.2"):
        if _h not in ALLOWED_HOSTS:
            ALLOWED_HOSTS.append(_h)

BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8000")

# =========================================================
# OPTIONAL FEATURES
# =========================================================
LIGHTWEIGHT_DEPLOYMENT = (
    os.getenv("LIGHTWEIGHT_DEPLOYMENT", "")
    .strip()
    .lower()
    in {"1", "true", "yes", "on"}
)

_disable_jazzmin_env = (
    os.getenv("DISABLE_JAZZMIN", "")
    .strip()
    .lower()
    in {"1", "true", "yes", "on"}
)

_has_jazzmin = importlib.util.find_spec("jazzmin") is not None
_enable_jazzmin = _has_jazzmin and not _disable_jazzmin_env

# =========================================================
# INSTALLED APPS
# =========================================================
INSTALLED_APPS = [

    *([] if not _enable_jazzmin else ["jazzmin"]),

    *([] if (DESKTOP_MODE or LIGHTWEIGHT_DEPLOYMENT) else ["daphne"]),

    # Django
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",

    # Core Packages
    "rest_framework",
    "rest_framework_simplejwt",
    "corsheaders",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    *([] if (DESKTOP_MODE or LIGHTWEIGHT_DEPLOYMENT)
      else ["allauth.socialaccount.providers.google"]),

    "drf_spectacular",
    "django_filters",
    "widget_tweaks",
    "solo",
    "mathfilters",

    *([] if (DESKTOP_MODE or LIGHTWEIGHT_DEPLOYMENT) else ["channels"]),

    # Main Apps
    "accounts.apps.AccountsConfig",
    "khataapp.apps.KhataappConfig",
    "mobileapi",
    "superapp",
    "commerce.apps.CommerceConfig",
    "ledger.apps.LedgerConfig",
    "billing.apps.BillingConfig",
    "core.apps.CoreConfig",
    "core_settings",
    "products",
    "orders",
    "pos",
    "users",
    "vendors.apps.VendorsConfig",
    "storefront.apps.StorefrontConfig",
    "saas.apps.SaaSConfig",
    "enterprise_control.apps.EnterpriseControlConfig",
    "warehouse",
    "payments",
    "reports",
    "system_mode",
    "ai_engine",
    "realtime",
    "location.apps.LocationConfig",
    "crm.apps.CrmConfig",
    "event_bus.apps.EventBusConfig",
    "whatsapp.apps.WhatsAppConfig",
    "smart_bi.apps.SmartBIConfig",
    "voice.apps.VoiceConfig",
    "chatbot.apps.ChatbotConfig",
    "distribution.apps.DistributionConfig",
    "notifications.apps.NotificationsConfig",
    "delivery.apps.DeliveryConfig",
    "bank_import.apps.BankImportConfig",
    "leads.apps.LeadsConfig",
    "marketing.apps.MarketingConfig",
    "procurement.apps.ProcurementConfig",
    "analytics.apps.AnalyticsConfig",
    "commission.apps.CommissionConfig",
    "auto_discount.apps.AutoDiscountConfig",
    "ai_ocr.apps.AIOCRConfig",
    "ai_insights.apps.AIInsightsConfig",
    "wallet.apps.WalletConfig",
    "subscription.apps.SubscriptionConfig",
    "hierarchy.apps.HierarchyConfig",
    "validation.apps.ValidationConfig",
    "retail_os.apps.RetailOSConfig",
    "smart_khata.apps.SmartKhataConfig",
    "portal.apps.PortalConfig",
    "printer_config.apps.PrinterConfigConfig",
    "scanner_config.apps.ScannerConfigConfig",
    "sms_center.apps.SMSCenterConfig",
    "fraud_detection.apps.FraudDetectionConfig",
    "api_integrations.apps.APIIntegrationsConfig",
    "performance.apps.PerformanceConfig",
    "selfcheckout.apps.SelfCheckoutConfig",
    "jaistech_erp.apps.JaisTechERPConfig",

    # Platform
    "apps.platform.identity.apps.PlatformIdentityConfig",
    "apps.platform.workforce.apps.PlatformWorkforceConfig",
    "apps.platform.core.apps.PlatformCoreConfig",
    "apps.platform.saas_ecosystem.apps.PlatformSaaSEcosystemConfig",
    "apps.platform.tax_compliance.apps.PlatformTaxComplianceConfig",
    "apps.platform.reporting.apps.PlatformReportingConfig",
]

# =========================================================
# AUTH
# =========================================================
AUTH_USER_MODEL = "accounts.User"

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

SITE_ID = 1

# =========================================================
# MIDDLEWARE
# =========================================================
MIDDLEWARE = [

    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",

    *([] if (DESKTOP_MODE or RUNNING_RUNSERVER or LIGHTWEIGHT_DEPLOYMENT)
      else ["whitenoise.middleware.WhiteNoiseMiddleware"]),

    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",

    "jaistech_erp.middleware.AdminErrorNotificationMiddleware",

    "vendors.middleware.VendorSubdomainMiddleware",
    "saas.middleware.TenantBootstrapMiddleware",

    *(["khatapro.desktop_cache.NoCacheStaticMiddleware"]
      if DESKTOP_MODE else []),

    "core_settings.rate_limit.RateLimitMiddleware",

    *(["accounts.desktop_csrf.DesktopCsrfBypassMiddleware"]
      if DESKTOP_MODE else []),

    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",

    "allauth.account.middleware.AccountMiddleware",

    "core_settings.jwt_middleware.JWTAuthenticationMiddleware",

    "system_mode.middleware.SystemModeMiddleware",

    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",

    "core_settings.security_headers.SecurityHeadersMiddleware",

    "khataapp.middleware.RestrictAdminMiddleware",
    "core_settings.middleware.FeatureGateMiddleware",
]

# =========================================================
# URLS
# =========================================================
ROOT_URLCONF = "khatapro.urls"

WSGI_APPLICATION = "khatapro.wsgi.application"
ASGI_APPLICATION = "khatapro.asgi.application"

TEST_RUNNER = "khatapro.test_runner.AppOnlyDiscoverRunner"

# =========================================================
# TEMPLATES
# =========================================================
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",

                "accounts.context_processors.erp_role_context",
                "core_settings.context_processors.global_settings",
                "system_mode.context_processors.system_mode_context",
                "smart_bi.context_processors.festival_context",
                "storefront.context_processors.storefront_nav",
                "storefront.context_processors.user_vendor_switch",
                "storefront.context_processors.storefront_apps",
                "saas.context_processors.tenant_info",
                "saas.context_processors.user_permissions",
                "saas.context_processors.subscription_info",
                "saas.context_processors.feature_flags",
            ],
        },
    },
]

# =========================================================
# DATABASE
# =========================================================
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

if DATABASE_URL:

    DATABASES = {
        "default": dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=600,
            ssl_require=False,
        )
    }

else:

    SQLITE_PATH = (
        os.getenv("SQLITE_PATH")
        or str((DESKTOP_DATA_DIR / "db.sqlite3").resolve())
    )

    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": SQLITE_PATH,
            "OPTIONS": {
                "timeout": 60
            },
            "CONN_MAX_AGE": 3600 if (
                DESKTOP_MODE or RUNNING_RUNSERVER
            ) else 0,
        }
    }

# =========================================================
# PASSWORD VALIDATION
# =========================================================
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME":
        "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {
        "NAME":
        "django.contrib.auth.password_validation.MinimumLengthValidator"
    },
    {
        "NAME":
        "django.contrib.auth.password_validation.CommonPasswordValidator"
    },
    {
        "NAME":
        "django.contrib.auth.password_validation.NumericPasswordValidator"
    },
]

# =========================================================
# LANGUAGE
# =========================================================
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

# =========================================================
# STATIC / MEDIA
# =========================================================
STATIC_URL = "/static/"
MEDIA_URL = "/media/"

STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_ROOT = DESKTOP_DATA_DIR / "media"

SERVE_STATICFILES = (
    os.getenv("SERVE_STATICFILES", "").strip().lower()
    in {"1", "true", "yes", "on"}
) or DESKTOP_MODE or IS_FROZEN

try:
    MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
except Exception:
    pass

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage"
    },
    "staticfiles": {
        "BACKEND":
        "django.contrib.staticfiles.storage.StaticFilesStorage"
    },
}

STATICFILES_STORAGE = STORAGES["staticfiles"]["BACKEND"]

# =========================================================
# REST FRAMEWORK
# =========================================================
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "fastapi_app.auth.drf_auth.FastAPIAccessTokenAuthentication",
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ),

    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.AllowAny",
    ),

    "DEFAULT_SCHEMA_CLASS":
        "drf_spectacular.openapi.AutoSchema",

    "DEFAULT_PAGINATION_CLASS":
        "rest_framework.pagination.PageNumberPagination",

    "PAGE_SIZE": 20,

    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
}

# =========================================================
# JWT
# =========================================================
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(days=1),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "AUTH_HEADER_TYPES": ("Bearer",),
}

# =========================================================
# SPECTACULAR
# =========================================================
SPECTACULAR_SETTINGS = {
    "TITLE": "Billentra API",
    "DESCRIPTION": "Universal ERP + POS + Billing API",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

# =========================================================
# CORS
# =========================================================
CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = True

# =========================================================
# LOGIN
# =========================================================
LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"

ACCOUNT_EMAIL_VERIFICATION = "none"
ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = False

# =========================================================
# GOOGLE LOGIN
# =========================================================
SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "APP": {
            "client_id": os.getenv("GOOGLE_CLIENT_ID", ""),
            "secret": os.getenv("GOOGLE_SECRET", ""),
            "key": "",
        },
        "SCOPE": ["email", "profile", "openid"],
        "AUTH_PARAMS": {
            "access_type": "online"
        },
    }
}

# =========================================================
# CHANNELS
# =========================================================
REDIS_URL = os.getenv("REDIS_URL", "").strip()

if REDIS_URL:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND":
            "channels_redis.core.RedisChannelLayer",
            "CONFIG": {
                "hosts": [REDIS_URL]
            },
        }
    }
else:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND":
            "channels.layers.InMemoryChannelLayer",
        }
    }

# =========================================================
# SECURITY SETTINGS
# =========================================================
SECURE_PROXY_SSL_HEADER = (
    "HTTP_X_FORWARDED_PROTO",
    "https"
)

SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True

SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

SECURE_SSL_REDIRECT = False

SECURE_CONTENT_TYPE_NOSNIFF = True

X_FRAME_OPTIONS = "SAMEORIGIN"

CSRF_TRUSTED_ORIGINS = [
    x.strip()
    for x in os.getenv(
        "CSRF_TRUSTED_ORIGINS",
        ""
    ).split(",")
    if x.strip()
]

# =========================================================
# SESSION ENGINE
# =========================================================
if DESKTOP_MODE:
    SESSION_ENGINE = (
        "django.contrib.sessions.backends.signed_cookies"
    )

# =========================================================
# EMAIL
# =========================================================
EMAIL_BACKEND = (
    "django.core.mail.backends.console.EmailBackend"
    if DEBUG else
    "django.core.mail.backends.smtp.EmailBackend"
)

EMAIL_HOST = os.getenv("EMAIL_HOST", "")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))

EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")

EMAIL_USE_TLS = True
EMAIL_USE_SSL = False

DEFAULT_FROM_EMAIL = os.getenv(
    "DEFAULT_FROM_EMAIL",
    "no-reply@example.com"
)

# =========================================================
# OPENAI
# =========================================================
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# =========================================================
# DEFAULT FIELD
# =========================================================
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# =========================================================
# JAZZMIN
# =========================================================
JAZZMIN_SETTINGS = {
    "site_title": "Billentra Admin",
    "site_header": "Billentra",
    "site_brand": "Billentra",
    "welcome_sign": "Smart Billing Easy Business",
    "show_sidebar": True,
    "navigation_expanded": True,
    "search_model": [
        "accounts.User",
        "products.Product",
        "billing.BillingInvoice",
        "enterprise_control.DynamicModule",
        "core.EnterpriseSetting",
    ],
    "order_with_respect_to": [
        "accounts",
        "auth",
        "saas",
        "enterprise_control",
        "core",
        "core_settings",
        "superapp",
        "pos",
        "selfcheckout",
        "reports",
        "analytics",
        "api_integrations",
        "billing",
        "products",
        "orders",
        "commerce",
        "vendors",
        "crm",
        "ledger",
        "warehouse",
        "payments",
        "whatsapp",
        "sms_center",
        "notifications",
        "printer_config",
        "scanner_config",
    ],
    "icons": {
        "accounts": "fas fa-users-cog",
        "auth": "fas fa-shield-alt",
        "saas": "fas fa-layer-group",
        "enterprise_control": "fas fa-sliders-h",
        "core": "fas fa-cogs",
        "core_settings": "fas fa-tools",
        "products": "fas fa-boxes",
        "orders": "fas fa-shopping-cart",
        "billing": "fas fa-file-invoice-dollar",
        "pos": "fas fa-cash-register",
        "selfcheckout": "fas fa-qrcode",
        "reports": "fas fa-chart-bar",
        "analytics": "fas fa-chart-line",
        "api_integrations": "fas fa-plug",
        "vendors": "fas fa-store",
        "crm": "fas fa-address-book",
        "warehouse": "fas fa-warehouse",
        "payments": "fas fa-credit-card",
        "whatsapp": "fab fa-whatsapp",
        "sms_center": "fas fa-sms",
        "notifications": "fas fa-bell",
        "printer_config": "fas fa-print",
        "scanner_config": "fas fa-barcode",
        "enterprise_control.DynamicModule": "fas fa-th-large",
        "enterprise_control.Workspace": "fas fa-desktop",
        "enterprise_control.DashboardWidget": "fas fa-chart-pie",
        "enterprise_control.PermissionTemplate": "fas fa-user-lock",
        "enterprise_control.ThemeConfig": "fas fa-palette",
        "core.EnterpriseSetting": "fas fa-toggle-on",
        "core.OfflineSyncBatch": "fas fa-sync",
    },
}

JAZZMIN_UI_TWEAKS = {
    "theme": "default",
    "navbar": "navbar-dark",
    "sidebar": "sidebar-dark-primary",
}

# =========================================================
# LOGGING
# =========================================================
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,

    "formatters": {
        "standard": {
            "format":
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        },
    },

    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
        },
    },

    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
}
