from decimal import Decimal

from django.db import models
from django.utils.text import slugify

from warehouse.models import Warehouse


class Category(models.Model):
    name = models.CharField(max_length=120)
    slug = models.SlugField(unique=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Product(models.Model):
    name = models.CharField(max_length=200)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name="products")
    slug = models.SlugField(max_length=255, unique=True, null=True, blank=True, db_index=True)
    sku = models.CharField(max_length=64, unique=True)
    barcode = models.CharField(max_length=128, unique=True, db_index=True)
    gst_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))
    mrp = models.DecimalField(max_digits=12, decimal_places=2)
    b2b_price = models.DecimalField(max_digits=12, decimal_places=2)
    b2c_price = models.DecimalField(max_digits=12, decimal_places=2)
    wholesale_price = models.DecimalField(max_digits=12, decimal_places=2)
    description = models.TextField(blank=True)

    # Shopify-like organization/meta (backend-driven; safe defaults).
    product_type = models.CharField(max_length=120, blank=True, default="")
    vendor_name = models.CharField(max_length=120, blank=True, default="")
    tags_json = models.JSONField(default=list, blank=True)
    collections_json = models.JSONField(default=list, blank=True)

    # Inventory/checkout flags
    track_inventory = models.BooleanField(default=True, db_index=True)
    allow_oos = models.BooleanField(default=False, db_index=True, help_text="Sell when out of stock")

    # Shipping basics (Phase A)
    is_physical = models.BooleanField(default=True, db_index=True)
    weight_kg = models.DecimalField(max_digits=10, decimal_places=3, default=Decimal("0.000"))
    country_of_origin = models.CharField(max_length=80, blank=True, default="")
    hs_code = models.CharField(max_length=32, blank=True, default="")

    # SEO (Phase A)
    seo_title = models.CharField(max_length=255, blank=True, default="")
    seo_description = models.TextField(blank=True, default="")

    # ---------------- B2B/B2C rules (Phase A) ----------------
    moq = models.PositiveIntegerField(default=1, help_text="Minimum order quantity for B2B.")
    bulk_qty = models.PositiveIntegerField(default=0, help_text="Bulk tier activates at this quantity (0 disables).")
    bulk_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, help_text="Bulk unit price for B2B.")
    is_b2b_only = models.BooleanField(default=False, db_index=True, help_text="Hide product for B2C users/guests.")
    is_online = models.BooleanField(default=False, db_index=True)
    fast_moving = models.BooleanField(default=False)
    low_stock_threshold = models.PositiveIntegerField(default=5)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["sku", "barcode"]),
            models.Index(fields=["fast_moving"]),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug and self.sku:
            self.slug = slugify(f"{self.name}-{self.sku}")[:255]
        super().save(*args, **kwargs)

    @property
    def primary_image_url(self) -> str:
        try:
            m = self.media.filter(media_type="image").order_by("sort_order", "id").first()
            if m:
                return m.media_url
        except Exception:
            pass
        return "/static/images/placeholder.png"


class ProductMedia(models.Model):
    class MediaType(models.TextChoices):
        IMAGE = "image", "Image"
        VIDEO = "video", "Video"

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="media")
    media_type = models.CharField(max_length=10, choices=MediaType.choices, default=MediaType.IMAGE, db_index=True)
    media = models.FileField(upload_to="product_media/")
    alt_text = models.CharField(max_length=200, blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["product", "media_type", "sort_order"])]
        ordering = ["sort_order", "id"]

    @property
    def media_url(self) -> str:
        """
        Backend-safe URL with fallback (for APIs/admin usage).
        Frontend templates may still use `media.url` directly.
        """
        try:
            if self.media and hasattr(self.media, "url"):
                return str(self.media.url)
        except Exception:
            pass
        return "/static/images/placeholder.png"


class ProductPriceRule(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="dynamic_price_rules")
    channel = models.CharField(max_length=20, choices=(("b2b", "B2B"), ("b2c", "B2C"), ("pos", "POS"), ("quick", "Quick")))
    min_qty = models.PositiveIntegerField(default=1)
    max_qty = models.PositiveIntegerField(null=True, blank=True)
    override_price = models.DecimalField(max_digits=12, decimal_places=2)
    is_active = models.BooleanField(default=True)

    class Meta:
        indexes = [models.Index(fields=["product", "channel", "is_active"])]


class WarehouseInventory(models.Model):
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name="inventories")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="warehouse_inventories")
    available_qty = models.IntegerField(default=0)
    reserved_qty = models.IntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("warehouse", "product")
        indexes = [models.Index(fields=["warehouse", "available_qty"])]

    @property
    def sellable_qty(self):
        return self.available_qty - self.reserved_qty
