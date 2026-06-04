from __future__ import annotations

from django.conf import settings
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.text import slugify


class Vendor(models.Model):
    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="vendor",
        help_text="Primary account owning this vendor/store.",
    )
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=90, unique=True, blank=True)
    subdomain = models.SlugField(
        max_length=63,
        unique=True,
        help_text="Store subdomain like 'acme' for acme.yourdomain.com",
        db_index=True,
    )
    is_active = models.BooleanField(default=True, db_index=True)

    primary_warehouse = models.ForeignKey(
        "warehouse.Warehouse",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="primary_vendors",
    )
    warehouses = models.ManyToManyField(
        "warehouse.Warehouse",
        through="vendors.VendorWarehouse",
        related_name="vendors",
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["subdomain", "is_active"]),
        ]

    def clean(self):
        if self.subdomain:
            sub = slugify(self.subdomain).replace("-", "")
            if sub in {"www", "api", "admin"}:
                raise ValidationError({"subdomain": "This subdomain is reserved."})

    def save(self, *args, **kwargs):
        if self.subdomain:
            self.subdomain = slugify(self.subdomain).lower()
        if not self.slug:
            self.slug = slugify(self.name)[:90]
        super().save(*args, **kwargs)

        try:
            group, _ = Group.objects.get_or_create(name="Vendor")
            self.owner.groups.add(group)
        except Exception:
            pass

    def __str__(self):
        return f"{self.name} ({self.subdomain})"


class VendorStoreSettings(models.Model):
    vendor = models.OneToOneField(Vendor, on_delete=models.CASCADE, related_name="store_settings")

    support_email = models.EmailField(blank=True)
    support_phone = models.CharField(max_length=20, blank=True)

    address_line1 = models.CharField(max_length=255, blank=True)
    address_line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=80, blank=True)
    state = models.CharField(max_length=80, blank=True)
    pincode = models.CharField(max_length=12, blank=True)
    country = models.CharField(max_length=80, blank=True, default="India")

    timezone = models.CharField(max_length=64, blank=True, default="Asia/Kolkata")
    currency = models.CharField(max_length=8, blank=True, default="INR")

    # Extensible, Shopify-like store settings (future-proof).
    # Keep optional settings here to avoid frequent schema changes.
    settings_json = models.JSONField(default=dict, blank=True)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Settings({self.vendor_id})"


class VendorWarehouse(models.Model):
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name="vendor_warehouses")
    warehouse = models.ForeignKey("warehouse.Warehouse", on_delete=models.CASCADE, related_name="warehouse_vendors")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("vendor", "warehouse")
        indexes = [models.Index(fields=["vendor", "is_active"])]

    def __str__(self):
        return f"{self.vendor_id}:{self.warehouse_id}"


class VendorMembership(models.Model):
    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        STAFF = "staff", "Staff"

    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="vendor_memberships")
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.STAFF, db_index=True)
    department = models.CharField(max_length=80, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("vendor", "user")
        indexes = [models.Index(fields=["vendor", "role", "is_active"])]

    def __str__(self):
        return f"{self.vendor_id}:{self.user_id}:{self.role}"


class VendorPaymentGatewayConfig(models.Model):
    class Provider(models.TextChoices):
        RAZORPAY = "razorpay", "Razorpay"
        PAYTM = "paytm", "Paytm"
        STRIPE = "stripe", "Stripe"

    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name="payment_gateways")
    provider = models.CharField(max_length=30, choices=Provider.choices, db_index=True)
    is_active = models.BooleanField(default=False, db_index=True)
    config = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("vendor", "provider")
        indexes = [models.Index(fields=["vendor", "provider", "is_active"])]

    def __str__(self):
        return f"{self.vendor_id}:{self.provider}"


class VendorShippingProviderConfig(models.Model):
    class Provider(models.TextChoices):
        DELHIVERY = "delhivery", "Delhivery"
        SHIPROCKET = "shiprocket", "Shiprocket"
        BLUEDART = "bluedart", "BlueDart"

    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name="shipping_providers")
    provider = models.CharField(max_length=30, choices=Provider.choices, db_index=True)
    is_active = models.BooleanField(default=False, db_index=True)
    config = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("vendor", "provider")
        indexes = [models.Index(fields=["vendor", "provider", "is_active"])]

    def __str__(self):
        return f"{self.vendor_id}:{self.provider}"


class VendorMarketingProviderConfig(models.Model):
    """
    Stores per-vendor marketing + social channel credentials/settings.

    NOTE: Actual paid ads execution depends on provider APIs (Phase B).
    In Phase A we store credentials + enable/disable and use them for UI gating.
    """

    class Provider(models.TextChoices):
        WHATSAPP = "whatsapp", "WhatsApp"
        SMS = "sms", "SMS"
        EMAIL = "email", "Email"
        FACEBOOK = "facebook", "Facebook"
        INSTAGRAM = "instagram", "Instagram"
        GOOGLE = "google", "Google"
        OTT = "ott", "OTT Ads"
        INFLUENCER = "influencer", "Influencer"

    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name="marketing_providers")
    provider = models.CharField(max_length=30, choices=Provider.choices, db_index=True)
    is_active = models.BooleanField(default=False, db_index=True)
    config = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("vendor", "provider")
        indexes = [models.Index(fields=["vendor", "provider", "is_active"])]

    def __str__(self):
        return f"{self.vendor_id}:{self.provider}"


class VendorCatalog(models.Model):
    """
    Shopify-like catalogs for a vendor:
    - choose which products are included/excluded
    - optional price adjustment (% increase/decrease)
    - optional market tags (Phase A: stored only)
    """

    class PriceDirection(models.TextChoices):
        INCREASE = "increase", "Increase"
        DECREASE = "decrease", "Decrease"

    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name="catalogs")
    title = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True, db_index=True)

    # Phase A: store market codes/labels (e.g. "India", "UAE") without geo enforcement.
    markets_json = models.JSONField(default=list, blank=True)

    currency = models.CharField(max_length=8, blank=True, default="INR")
    price_adjustment_percent = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    price_adjustment_direction = models.CharField(
        max_length=16, choices=PriceDirection.choices, default=PriceDirection.DECREASE
    )
    include_compare_at_price = models.BooleanField(default=False)

    auto_include_new_products = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=["vendor", "is_active", "updated_at"]),
        ]
        ordering = ["-updated_at", "-id"]

    def __str__(self) -> str:
        return f"{self.vendor_id}:{self.title}"


class VendorCatalogProduct(models.Model):
    class Mode(models.TextChoices):
        INCLUDE = "include", "Included"
        EXCLUDE = "exclude", "Excluded"

    catalog = models.ForeignKey(VendorCatalog, on_delete=models.CASCADE, related_name="items")
    listing = models.ForeignKey("storefront.VendorProductListing", on_delete=models.CASCADE, related_name="catalog_items")
    mode = models.CharField(max_length=10, choices=Mode.choices, default=Mode.INCLUDE, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        unique_together = ("catalog", "listing")
        indexes = [
            models.Index(fields=["catalog", "mode", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.catalog_id}:{self.listing_id}:{self.mode}"


class VendorCatalogRollout(models.Model):
    """
    Shopify-like "Rollouts" for catalogs:
    Schedule which catalog becomes default for the store (optionally per markets).

    Phase A:
    - Markets are stored as labels only.
    - Rollout changes vendor's `default_catalog_id` (stored in VendorStoreSettings.settings_json).
    """

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SCHEDULED = "scheduled", "Scheduled"
        ACTIVE = "active", "Active"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"

    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name="catalog_rollouts")
    catalog = models.ForeignKey(VendorCatalog, on_delete=models.CASCADE, related_name="rollouts")
    title = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT, db_index=True)

    markets_json = models.JSONField(default=list, blank=True)
    starts_at = models.DateTimeField(null=True, blank=True, db_index=True)
    ends_at = models.DateTimeField(null=True, blank=True, db_index=True)
    revert_on_end = models.BooleanField(default=True)

    applied_at = models.DateTimeField(null=True, blank=True)
    reverted_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["vendor", "status", "starts_at"]),
            models.Index(fields=["vendor", "status", "ends_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.vendor_id}:{self.catalog_id}:{self.title}"


class VendorCustomerCompany(models.Model):
    """
    B2B customer companies for a vendor.

    Phase A: used for segmentation and vendor-side CRM basics.
    """

    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name="customer_companies")
    name = models.CharField(max_length=200)
    gstin = models.CharField(max_length=32, blank=True, default="", db_index=True)
    phone = models.CharField(max_length=20, blank=True, default="", db_index=True)
    email = models.EmailField(blank=True, default="")
    address = models.TextField(blank=True, default="")
    tags_json = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        ordering = ["-updated_at", "-id"]
        indexes = [
            models.Index(fields=["vendor", "is_active", "updated_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.vendor_id}:{self.name}"


class VendorCustomerCompanyMember(models.Model):
    company = models.ForeignKey(VendorCustomerCompany, on_delete=models.CASCADE, related_name="members")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="vendor_company_memberships")
    role = models.CharField(max_length=60, blank=True, default="")
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        unique_together = ("company", "user")
        indexes = [models.Index(fields=["company", "is_active", "created_at"])]

    def __str__(self) -> str:
        return f"{self.company_id}:{self.user_id}"


class VendorCustomerSegment(models.Model):
    """
    Shopify-like customer segments (rules-based).
    Rules are stored as JSON and evaluated server-side.

    Supported Phase A rules (optional):
    - pincode
    - min_orders
    - min_spent
    - has_company (true/false)
    """

    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name="customer_segments")
    title = models.CharField(max_length=200)
    is_active = models.BooleanField(default=True, db_index=True)
    rules_json = models.JSONField(default=dict, blank=True)
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        ordering = ["-updated_at", "-id"]
        indexes = [models.Index(fields=["vendor", "is_active", "updated_at"])]

    def __str__(self) -> str:
        return f"{self.vendor_id}:{self.title}"


class MarketplaceApp(models.Model):
    """
    Shopify-like app marketplace registry.

    Apps can be built-in (internal) or external (Phase B).
    """

    class Category(models.TextChoices):
        MARKETING = "marketing", "Marketing"
        SALES = "sales", "Sales"
        SUPPORT = "support", "Support"
        ANALYTICS = "analytics", "Analytics"
        SHIPPING = "shipping", "Shipping"
        PAYMENTS = "payments", "Payments"
        OTHER = "other", "Other"

    code = models.SlugField(max_length=80, unique=True)
    name = models.CharField(max_length=140)
    category = models.CharField(max_length=30, choices=Category.choices, default=Category.OTHER, db_index=True)
    short_description = models.CharField(max_length=220, blank=True, default="")
    description = models.TextField(blank=True, default="")
    icon = models.CharField(max_length=200, blank=True, default="", help_text="Static icon path or URL")
    rating = models.DecimalField(max_digits=3, decimal_places=1, default=0)
    is_active = models.BooleanField(default=True, db_index=True)
    is_builtin = models.BooleanField(default=True, db_index=True)

    default_config = models.JSONField(default=dict, blank=True)
    config_schema = models.JSONField(default=dict, blank=True, help_text="Optional schema for future UI generation.")

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        ordering = ["category", "name"]
        indexes = [models.Index(fields=["is_active", "category", "name"])]

    def __str__(self) -> str:
        return f"{self.code}"


class VendorAppInstall(models.Model):
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name="app_installs")
    app = models.ForeignKey(MarketplaceApp, on_delete=models.CASCADE, related_name="installs")
    is_installed = models.BooleanField(default=True, db_index=True)
    is_enabled = models.BooleanField(default=True, db_index=True)
    config = models.JSONField(default=dict, blank=True)
    installed_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        unique_together = ("vendor", "app")
        indexes = [models.Index(fields=["vendor", "is_enabled", "updated_at"])]

    def __str__(self) -> str:
        return f"{self.vendor_id}:{self.app_id}:{'on' if self.is_enabled else 'off'}"


class VendorShopifyConnection(models.Model):
    """
    Per-vendor Shopify connection.

    Stores the OAuth offline access token used for background sync.
    """

    vendor = models.OneToOneField(Vendor, on_delete=models.CASCADE, related_name="shopify_connection")
    shop_domain = models.CharField(max_length=120, blank=True, default="", db_index=True)
    access_token = models.TextField(blank=True, default="")
    scope = models.CharField(max_length=600, blank=True, default="")
    is_active = models.BooleanField(default=True, db_index=True)

    installed_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)
    last_sync_at = models.DateTimeField(null=True, blank=True, db_index=True)
    last_error = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        indexes = [models.Index(fields=["shop_domain", "is_active", "updated_at"])]

    def __str__(self) -> str:
        return f"{self.vendor_id}:{self.shop_domain or 'shopify'}"
