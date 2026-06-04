from celery import shared_task
from django.utils import timezone

from .models import Branch, OfferCampaign
from .services.pricing import recalculate_branch_prices


@shared_task
def run_dynamic_pricing_cycle():
    updated = 0
    for branch in Branch.objects.filter(is_active=True):
        updated += len(recalculate_branch_prices(branch=branch))
    return {"updated_prices": updated}


@shared_task
def sync_offer_campaign_statuses():
    now = timezone.now()
    live = OfferCampaign.objects.filter(status=OfferCampaign.Status.SCHEDULED, starts_at__lte=now, ends_at__gte=now).update(
        status=OfferCampaign.Status.LIVE
    )
    ended = OfferCampaign.objects.filter(status__in=[OfferCampaign.Status.SCHEDULED, OfferCampaign.Status.LIVE], ends_at__lt=now).update(
        status=OfferCampaign.Status.ENDED
    )
    return {"live": live, "ended": ended}
