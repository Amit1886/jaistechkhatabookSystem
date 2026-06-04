from django.db import models
from django.conf import settings
from django.db.models import Q
import hashlib


class UISettings(models.Model):
    # 🎨 COLORS
    primary_color = models.CharField(max_length=20, default="#4f46e5")
    secondary_color = models.CharField(max_length=20, default="#0ea5e9")
    success_color = models.CharField(max_length=20, default="#16a34a")
    danger_color = models.CharField(max_length=20, default="#dc2626")

    # 🌙 THEME
    theme_mode = models.CharField(
        max_length=20,
        choices=[("light","Light"),("dark","Dark")],
        default="light"
    )

    # 📐 LAYOUT
    sidebar_position = models.CharField(
        max_length=20,
        choices=[("left","Left"),("right","Right")],
        default="left"
    )

    sidebar_collapsed = models.BooleanField(default=False)

    # 🧭 NAVIGATION
    show_dashboard = models.BooleanField(default=True)
    show_party = models.BooleanField(default=True)
    show_transaction = models.BooleanField(default=True)
    show_commerce = models.BooleanField(default=True)
    show_reports = models.BooleanField(default=True)
    show_settings = models.BooleanField(default=True)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return "UI / Theme Settings"


class SaaSSettings(models.Model):
    enable_multi_company = models.BooleanField(default=False)
    enable_multi_user = models.BooleanField(default=True)

    enable_subscription = models.BooleanField(default=True)
    enable_trial = models.BooleanField(default=True)
    trial_days = models.PositiveIntegerField(default=7)

    enable_audit_logs = models.BooleanField(default=True)
    enable_api_access = models.BooleanField(default=False)

    def __str__(self):
        return "SaaS Settings"


class CompanySettings(models.Model):
    company_name = models.CharField(max_length=200)
    logo = models.ImageField(upload_to="logos/", blank=True, null=True)
    mobile = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)

    class Meta:
        verbose_name = "Company Setting"
        verbose_name_plural = "Company Settings"

    def __str__(self):
        return self.company_name


class AppSettings(models.Model):
    # 🏢 Company
    company_name = models.CharField(max_length=200)
    currency_symbol = models.CharField(max_length=10, default="₹")
    financial_year_start = models.DateField()

    # 🔐 System
    maintenance_mode = models.BooleanField(default=False)
    enable_notifications = models.BooleanField(default=True)
    enable_chat = models.BooleanField(default=True)

    # 👤 Users
    allow_user_signup = models.BooleanField(default=True)
    allow_social_login = models.BooleanField(default=True)

    # 📊 Dashboard
    show_profit_loss = models.BooleanField(default=True)
    show_daily_summary = models.BooleanField(default=True)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return "Global App Settings"


class ModuleSettings(models.Model):
    MODULE_CHOICES = [
        ("party", "Party"),
        ("transaction", "Transaction"),
        ("commerce", "Commerce"),
        ("billing", "Billing"),
        ("stock", "Stock"),
        ("warehouse", "Warehouse"),
        ("payment", "Payment"),
        ("subscription", "Subscription"),
    ]

    module = models.CharField(max_length=50, choices=MODULE_CHOICES, unique=True)

    enabled = models.BooleanField(default=True)

    settings = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"{self.module.title()} Settings"


class FeatureSettings(models.Model):
    FEATURE_CHOICES = [
        ("otp", "OTP System"),
        ("emi", "EMI"),
        ("gst", "GST"),
        ("chat", "Chat"),
        ("payment_gateway", "Payment Gateway"),
        ("notification", "Notifications"),
        ("daily_summary", "Daily Summary"),
        ("voice_ai", "Voice AI Calling"),
        ("qr_system", "QR Onboarding"),
        ("whatsapp_mini", "WhatsApp Mini App"),
        ("shop_onboarding", "Shop Onboarding"),
    ]

    feature = models.CharField(max_length=50, choices=FEATURE_CHOICES, unique=True)

    enabled = models.BooleanField(default=True)
    config = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"{self.feature.title()} Feature"


# -----------------------------
# Unified Settings Center Models
# -----------------------------

class SettingCategory(models.Model):
    slug = models.SlugField(max_length=80, unique=True)
    label = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, blank=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "label"]

    def __str__(self):
        return self.label


class SettingDefinition(models.Model):
    DATA_TYPES = [
        ("string", "String"),
        ("text", "Text"),
        ("number", "Number"),
        ("boolean", "Boolean"),
        ("select", "Select"),
        ("json", "JSON"),
        ("date", "Date"),
    ]

    SCOPE_CHOICES = [
        ("global", "Global"),
        ("user", "User"),
    ]

    category = models.ForeignKey(SettingCategory, on_delete=models.CASCADE, related_name="definitions")
    key = models.SlugField(max_length=120, unique=True)
    label = models.CharField(max_length=160)
    help_text = models.CharField(max_length=255, blank=True)
    data_type = models.CharField(max_length=20, choices=DATA_TYPES, default="string")
    default_value = models.JSONField(default=dict, blank=True)
    options = models.JSONField(default=list, blank=True)
    scope = models.CharField(max_length=20, choices=SCOPE_CHOICES, default="global")
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "label"]

    def __str__(self):
        return self.label


class SettingValue(models.Model):
    definition = models.ForeignKey(SettingDefinition, on_delete=models.CASCADE, related_name="values")
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="settings_values",
    )
    value = models.JSONField(default=dict, blank=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="settings_updates",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["definition", "owner"],
                condition=Q(owner__isnull=False),
                name="unique_setting_value_owner",
            ),
            models.UniqueConstraint(
                fields=["definition"],
                condition=Q(owner__isnull=True),
                name="unique_setting_value_global",
            ),
        ]


class DesktopRelease(models.Model):
    """
    Cloud-managed Windows desktop release.

    Admin uploads the EXE and sets `version`. Desktop clients can download the
    latest published build when online.

    Note: This project also runs locally (desktop mode). On desktop machines,
    this model can exist but is typically unused unless you also host releases locally.
    """

    version = models.CharField(max_length=50, default="0.0.0", db_index=True)
    windows_exe = models.FileField(upload_to="desktop_releases/", blank=True, null=True)
    sha256 = models.CharField(max_length=64, blank=True, default="")
    android_apk = models.FileField(upload_to="android_releases/", blank=True, null=True)
    android_sha256 = models.CharField(max_length=64, blank=True, default="")
    notes = models.TextField(blank=True, default="")
    is_published = models.BooleanField(default=False, db_index=True)
    published_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Desktop Release"
        verbose_name_plural = "Desktop Releases"

    def save(self, *args, **kwargs):
        # Hard singleton.
        self.pk = 1

        # IMPORTANT: do not open/close uploaded temporary files before Django saves them,
        # otherwise Windows temp uploads can disappear and cause FileNotFoundError during save.
        super().save(*args, **kwargs)


class LandingVideo(models.Model):
    """
    Public website videos shown on the homepage.

    Admin can either upload a video file or provide a direct video URL.
    """

    title = models.CharField(max_length=140, blank=True, default="")
    video_file = models.FileField(upload_to="landing/videos/", blank=True, null=True)
    video_url = models.URLField(blank=True, default="", help_text="Direct MP4/WebM URL (optional).")
    thumbnail = models.ImageField(upload_to="landing/video_thumbs/", blank=True, null=True)
    is_active = models.BooleanField(default=True, db_index=True)
    sort_order = models.PositiveIntegerField(default=0, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        verbose_name = "Landing Video"
        verbose_name_plural = "Landing Videos"
        ordering = ["sort_order", "-created_at"]

    def __str__(self):
        return self.title or (self.video_url or (self.video_file.name if self.video_file else "Landing Video"))


class LandingPageSettings(models.Model):
    """
    Singleton settings for the public homepage (landing page).
    """

    brand_name = models.CharField(max_length=120, default="Billentra")
    hero_kicker = models.CharField(max_length=140, blank=True, default="Smart Billing • Easy Business")
    hero_title = models.CharField(max_length=220, default="Billing & Khata software built for Indian small businesses")
    hero_subtitle = models.TextField(
        blank=True,
        default="Create GST invoices, manage inventory, track ledger/khata, and get reports in one clean, fast system.",
    )

    stat_businesses = models.PositiveIntegerField(default=45000)
    stat_invoices = models.PositiveIntegerField(default=1250000)
    stat_reports = models.PositiveIntegerField(default=98000)

    clients_title = models.CharField(max_length=220, blank=True, default="They “Work With Us” — As Clients and Collaborators")

    usecases_kicker = models.CharField(max_length=200, blank=True, default="Designed for Every Business, Big or Small")
    usecases_title = models.CharField(max_length=200, blank=True, default="Who can use Billentra?")
    usecases_subtitle = models.TextField(
        blank=True,
        default="Whether you run a retail store, wholesale business, or service-based company — Billentra helps you manage billing, inventory, khata and reports with a clean workflow.",
    )

    videos_kicker = models.CharField(max_length=140, blank=True, default="A Peek Into Billentra")
    videos_title = models.CharField(max_length=140, blank=True, default="Swipe · Watch · Grow")
    videos_subtitle = models.CharField(
        max_length=240,
        blank=True,
        default="Add short demo videos from Admin and they will show here automatically.",
    )

    reviews_title = models.CharField(max_length=140, blank=True, default="Google Play Reviews")
    reviews_subtitle = models.CharField(max_length=240, blank=True, default="What customers say about Billentra")

    cta_title = models.CharField(max_length=200, blank=True, default="Get started with Billentra")
    cta_subtitle = models.TextField(
        blank=True,
        default="Join thousands of businesses using Billentra for faster invoicing, easier ledger tracking, and better financial management.",
    )

    support_title = models.CharField(max_length=160, blank=True, default="Contact Billentra")
    support_subtitle = models.CharField(
        max_length=240,
        blank=True,
        default="Call, email, or send a message — we usually respond within 24 hours.",
    )
    support_phone = models.CharField(max_length=40, blank=True, default="+91 95557 33478")
    support_email = models.EmailField(blank=True, default="support@billentra.com")
    support_address = models.CharField(max_length=240, blank=True, default="Station Road, Basti, Uttar Pradesh 272002")
    map_embed_url = models.URLField(
        blank=True,
        default="https://www.google.com/maps?q=Station%20Road%20Basti%20Uttar%20Pradesh%20272002&output=embed",
    )

    whatsapp_number = models.CharField(max_length=30, blank=True, default="919555733478")
    whatsapp_default_message = models.CharField(max_length=240, blank=True, default="Hi, I need help with Billentra")

    facebook_url = models.URLField(blank=True, default="")
    instagram_url = models.URLField(blank=True, default="")
    youtube_url = models.URLField(blank=True, default="")
    twitter_url = models.URLField(blank=True, default="")
    linkedin_url = models.URLField(blank=True, default="")

    show_clients = models.BooleanField(default=True)
    show_usecases = models.BooleanField(default=True)
    show_videos = models.BooleanField(default=True)
    show_reviews = models.BooleanField(default=True)
    show_download_popup = models.BooleanField(default=True)
    show_social_bar = models.BooleanField(default=True)
    show_whatsapp_widget = models.BooleanField(default=True)
    show_chatbot_widget = models.BooleanField(default=False)
    enable_websocket_chat = models.BooleanField(default=False)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Landing Page Settings"
        verbose_name_plural = "Landing Page Settings"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get_solo(cls):
        obj = cls.objects.filter(pk=1).first()
        return obj or cls.objects.create(pk=1)

    def __str__(self):
        return "Landing Page Settings"


class LandingClient(models.Model):
    name = models.CharField(max_length=120)
    logo = models.ImageField(upload_to="landing/clients/", blank=True, null=True)
    website_url = models.URLField(blank=True, default="")
    is_active = models.BooleanField(default=True, db_index=True)
    sort_order = models.PositiveIntegerField(default=0, db_index=True)

    class Meta:
        verbose_name = "Landing Client"
        verbose_name_plural = "Landing Clients"
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name


class LandingUseCase(models.Model):
    title = models.CharField(max_length=140)
    description = models.TextField(blank=True, default="")
    image = models.ImageField(upload_to="landing/usecases/", blank=True, null=True)
    is_active = models.BooleanField(default=True, db_index=True)
    sort_order = models.PositiveIntegerField(default=0, db_index=True)

    class Meta:
        verbose_name = "Landing Use Case"
        verbose_name_plural = "Landing Use Cases"
        ordering = ["sort_order", "title"]

    def __str__(self):
        return self.title


class LandingReview(models.Model):
    name = models.CharField(max_length=120)
    rating = models.PositiveSmallIntegerField(default=5)
    review = models.TextField(blank=True, default="")
    avatar = models.ImageField(upload_to="landing/reviews/", blank=True, null=True)
    source = models.CharField(max_length=80, blank=True, default="Google Play")
    is_active = models.BooleanField(default=True, db_index=True)
    sort_order = models.PositiveIntegerField(default=0, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Landing Review"
        verbose_name_plural = "Landing Reviews"
        ordering = ["sort_order", "-created_at"]

    def __str__(self):
        return f"{self.name} ({self.rating}/5)"


class LandingMarketingFeature(models.Model):
    title = models.CharField(max_length=140)
    description = models.CharField(max_length=240, blank=True, default="")
    icon = models.CharField(max_length=40, blank=True, default="", help_text="Optional icon name (Bootstrap/FontAwesome).")
    is_active = models.BooleanField(default=True, db_index=True)
    sort_order = models.PositiveIntegerField(default=0, db_index=True)

    class Meta:
        verbose_name = "Landing Feature"
        verbose_name_plural = "Landing Features"
        ordering = ["sort_order", "title"]

    def __str__(self):
        return self.title


class LandingPricingRow(models.Model):
    STATE_CHOICES = [
        ("text", "Text"),
        ("ok", "✔"),
        ("no", "✖"),
        ("trial", "⚠ Trial Only"),
    ]

    label = models.CharField(max_length=160)

    free_state = models.CharField(max_length=10, choices=STATE_CHOICES, default="text")
    free_text = models.CharField(max_length=200, blank=True, default="")

    pro_state = models.CharField(max_length=10, choices=STATE_CHOICES, default="text")
    pro_text = models.CharField(max_length=200, blank=True, default="")

    pro_max_state = models.CharField(max_length=10, choices=STATE_CHOICES, default="text")
    pro_max_text = models.CharField(max_length=200, blank=True, default="")

    is_active = models.BooleanField(default=True, db_index=True)
    sort_order = models.PositiveIntegerField(default=0, db_index=True)

    class Meta:
        verbose_name = "Landing Pricing Row"
        verbose_name_plural = "Landing Pricing Rows"
        ordering = ["sort_order", "label"]

    def __str__(self):
        return self.label


class SettingHistory(models.Model):
    definition = models.ForeignKey(SettingDefinition, on_delete=models.CASCADE, related_name="history")
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="settings_history",
    )
    previous_value = models.JSONField(default=dict, blank=True)
    new_value = models.JSONField(default=dict, blank=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="settings_history_updates",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        owner = self.owner.username if self.owner else "global"
        return f"{self.definition.key} change ({owner})"


class SettingPermission(models.Model):
    ROLE_CHOICES = [
        ("super_admin", "Super Admin"),
        ("admin", "Admin"),
        ("manager", "Manager"),
        ("user", "User"),
    ]

    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    category = models.ForeignKey(SettingCategory, on_delete=models.CASCADE, related_name="permissions")
    can_view = models.BooleanField(default=True)
    can_edit = models.BooleanField(default=True)
    hidden = models.BooleanField(default=False)

    class Meta:
        unique_together = ("role", "category")

    def __str__(self):
        return f"{self.role} -> {self.category.slug}"
