from django.db import models


class SalesAnalyticsSnapshot(models.Model):
    snapshot_date = models.DateField(db_index=True)
    total_sales = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_orders = models.PositiveIntegerField(default=0)
    pos_sales = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    online_sales = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    heatmap_payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class ProductVelocity(models.Model):
    product = models.ForeignKey("products.Product", on_delete=models.CASCADE, related_name="velocity_rows")
    period = models.CharField(max_length=20, default="7d")
    sold_qty = models.IntegerField(default=0)
    velocity_score = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_dead_stock = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("product", "period")


class SalesmanPerformance(models.Model):
    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="salesman_performance")
    period_start = models.DateField()
    period_end = models.DateField()
    orders_count = models.PositiveIntegerField(default=0)
    sales_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    margin_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    conversion_rate = models.DecimalField(max_digits=6, decimal_places=2, default=0)


class CreditRiskScore(models.Model):
    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="credit_scores")
    score = models.PositiveIntegerField(default=0)
    reason = models.CharField(max_length=255, blank=True)
    generated_at = models.DateTimeField(auto_now_add=True)


class EngagementMetric(models.Model):
    class Metric(models.TextChoices):
        VOICE_SUCCESS = "voice_success", "Voice call success %"
        QR_TO_SIGNUP = "qr_to_signup", "QR scan to signup ratio"
        WHATSAPP_CONVERSION = "wa_conversion", "WhatsApp conversion rate"
        AGENT_HEATMAP = "agent_heatmap", "Agent performance heatmap"

    metric = models.CharField(max_length=40, choices=Metric.choices, db_index=True)
    period_start = models.DateField(db_index=True)
    period_end = models.DateField(db_index=True)
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["metric", "period_start", "period_end"], name="eng_metric_idx")]
