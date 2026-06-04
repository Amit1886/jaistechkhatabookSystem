from decimal import Decimal
from datetime import timedelta

from django.db.models import Count, Sum
from django.utils import timezone

from orders.models import OrderItem
from products.models import Product

from ..models import BranchInventory, BranchPrice, DynamicPriceLog, OfferCampaign, PricingRule
from .realtime import publish_retail_event


def _now_in_rule_window(rule, now):
    if rule.starts_at and rule.starts_at > now:
        return False
    if rule.ends_at and rule.ends_at < now:
        return False
    if rule.time_window_start and rule.time_window_end:
        current_time = now.time()
        if rule.time_window_start <= rule.time_window_end:
            return rule.time_window_start <= current_time <= rule.time_window_end
        return current_time >= rule.time_window_start or current_time <= rule.time_window_end
    return True


def _rule_matches(rule, product, branch=None, quantity=1, customer_segment=""):
    if rule.product_id and rule.product_id != product.id:
        return False
    if rule.category_id and rule.category_id != product.category_id:
        return False
    if rule.branch_id and (not branch or rule.branch_id != branch.id):
        return False
    if quantity < rule.min_qty:
        return False
    if rule.customer_segment and rule.customer_segment != customer_segment:
        return False
    if rule.condition_type == PricingRule.ConditionType.STOCK_LOW and branch:
        stock = BranchInventory.objects.filter(branch=branch, product=product).first()
        if not stock or stock.sellable_qty > rule.stock_threshold:
            return False
    if rule.condition_type == PricingRule.ConditionType.EXPIRY_NEAR and branch:
        if not rule.expiry_days_threshold:
            return False
        max_date = timezone.localdate() + timedelta(days=rule.expiry_days_threshold)
        if not BranchInventory.objects.filter(branch=branch, product=product, expiry_date__lte=max_date).exists():
            return False
    return True


def _apply_adjustment(base_price, rule):
    base_price = Decimal(base_price or 0)
    value = Decimal(rule.adjustment_value or 0)
    if rule.adjustment_type == PricingRule.AdjustmentType.SET_PRICE:
        return max(value, Decimal("0.00"))
    if rule.adjustment_type == PricingRule.AdjustmentType.FIXED:
        return max(base_price + value, Decimal("0.00"))
    return max(base_price + (base_price * value / Decimal("100.00")), Decimal("0.00"))


def calculate_dynamic_price(product, branch=None, quantity=1, customer_segment="", channel="pos"):
    now = timezone.now()
    base_price = product.b2c_price if channel in {"b2c", "quick"} else product.b2b_price
    if channel == "pos":
        base_price = product.b2c_price

    branch_price = None
    if branch:
        branch_price = BranchPrice.objects.filter(branch=branch, product=product).first()
        if branch_price and (
            (not branch_price.starts_at or branch_price.starts_at <= now)
            and (not branch_price.ends_at or branch_price.ends_at >= now)
        ):
            base_price = branch_price.price

    applied_rule = None
    final_price = Decimal(base_price or 0)
    rules = PricingRule.objects.select_related("product", "category", "branch").filter(is_active=True).order_by("priority", "-updated_at")
    for rule in rules:
        if _now_in_rule_window(rule, now) and _rule_matches(rule, product, branch, quantity, customer_segment):
            final_price = _apply_adjustment(final_price, rule)
            applied_rule = rule
            break

    active_campaign = _active_campaign_for(product, branch, now)
    if active_campaign:
        if active_campaign.discount_percent:
            final_price = max(final_price - (final_price * active_campaign.discount_percent / Decimal("100.00")), Decimal("0.00"))
        if active_campaign.discount_amount:
            final_price = max(final_price - active_campaign.discount_amount, Decimal("0.00"))

    offer_tag = ""
    if applied_rule and applied_rule.offer_tag:
        offer_tag = applied_rule.offer_tag
    elif active_campaign and active_campaign.badge_text:
        offer_tag = active_campaign.badge_text
    elif branch_price and branch_price.offer_tag:
        offer_tag = branch_price.offer_tag

    return {
        "product_id": product.id,
        "branch_id": branch.id if branch else None,
        "base_price": str(Decimal(base_price or 0).quantize(Decimal("0.01"))),
        "final_price": str(final_price.quantize(Decimal("0.01"))),
        "compare_at_price": str(Decimal(base_price or 0).quantize(Decimal("0.01"))),
        "offer_tag": offer_tag,
        "rule_id": applied_rule.id if applied_rule else None,
        "campaign_id": active_campaign.id if active_campaign else None,
        "expires_at": active_campaign.ends_at.isoformat() if active_campaign and active_campaign.ends_at else None,
    }


def _active_campaign_for(product, branch, now):
    campaigns = OfferCampaign.objects.filter(
        status__in=[OfferCampaign.Status.SCHEDULED, OfferCampaign.Status.LIVE],
        starts_at__lte=now,
        ends_at__gte=now,
        auto_apply=True,
    ).prefetch_related("products", "categories", "branches")
    for campaign in campaigns:
        branch_match = not campaign.branches.exists() or (branch and campaign.branches.filter(id=branch.id).exists())
        product_match = campaign.products.filter(id=product.id).exists()
        category_match = product.category_id and campaign.categories.filter(id=product.category_id).exists()
        if branch_match and (product_match or category_match or (not campaign.products.exists() and not campaign.categories.exists())):
            return campaign
    return None


def recalculate_branch_prices(branch=None, product_ids=None, channel="pos", actor=None):
    products = Product.objects.filter(is_active=True)
    if product_ids:
        products = products.filter(id__in=product_ids)
    logs = []
    for product in products.select_related("category"):
        result = calculate_dynamic_price(product, branch=branch, channel=channel)
        old_price = Decimal(result["base_price"])
        new_price = Decimal(result["final_price"])
        if old_price != new_price:
            logs.append(
                DynamicPriceLog.objects.create(
                    rule_id=result["rule_id"],
                    campaign_id=result["campaign_id"],
                    branch=branch,
                    product=product,
                    old_price=old_price,
                    new_price=new_price,
                    reason=result["offer_tag"] or "dynamic_pricing",
                    created_by=actor,
                    event_payload=result,
                )
            )
            publish_retail_event("pricing", "price.updated", result)
    return logs


def pricing_analytics(days=30):
    since = timezone.now() - timezone.timedelta(days=days)
    return {
        "price_changes": DynamicPriceLog.objects.filter(created_at__gte=since).count(),
        "campaign_logs": list(
            DynamicPriceLog.objects.filter(created_at__gte=since, campaign__isnull=False)
            .values("campaign__name")
            .annotate(changes=Count("id"))
            .order_by("-changes")[:10]
        ),
        "margin_impact": list(
            DynamicPriceLog.objects.filter(created_at__gte=since)
            .values("branch__name")
            .annotate(total_delta=Sum("new_price") - Sum("old_price"))
            .order_by("-total_delta")[:10]
        ),
        "top_discounted_products": list(
            OrderItem.objects.filter(order__created_at__gte=since, line_discount__gt=0)
            .values("product__name")
            .annotate(discount=Sum("line_discount"), sold=Sum("qty"))
            .order_by("-discount")[:10]
        ),
        "failed_campaigns": OfferCampaign.objects.filter(status=OfferCampaign.Status.FAILED, updated_at__gte=since).count(),
    }
