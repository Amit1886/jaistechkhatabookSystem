from __future__ import annotations

from celery import shared_task
from django.utils import timezone

from marketing.models import Campaign
from marketing.services import start_campaign
from marketing.models import CampaignMessage
from marketing.services import mark_message_failed, mark_message_sent


@shared_task
def process_scheduled_campaigns():
    now = timezone.now()
    qs = Campaign.objects.filter(status=Campaign.Status.SCHEDULED, scheduled_at__lte=now).order_by("scheduled_at")[:50]
    for campaign in qs:
        try:
            start_campaign(campaign=campaign, actor=campaign.created_by)
        except Exception as exc:
            campaign.mark_failed(str(exc))


@shared_task
def process_pending_campaign_messages(limit: int = 200):
    """
    Dispatch pending CampaignMessage rows using platform connectors:
    - WhatsApp: whatsapp.api_connector.send_whatsapp_message (global provider config)
    - SMS: sms_center.sms_service.send_sms
    - Email: Django send_mail

    Paid ads channels are stored but not executed in Phase A.
    """

    qs = CampaignMessage.objects.select_related("campaign").filter(status=CampaignMessage.Status.PENDING).order_by("created_at")[:limit]
    if not qs:
        return 0

    from django.core.mail import send_mail

    sent = 0
    def _vendor_id_from_campaign(campaign: Campaign):
        try:
            meta = campaign.metadata or {}
            if isinstance(meta, dict) and meta.get("vendor_id"):
                return int(meta.get("vendor_id"))
        except Exception:
            return None
        return None

    for msg in qs:
        camp = msg.campaign
        to = (msg.destination or "").strip()
        body = (msg.payload or {}).get("copy") or camp.ad_copy or ""
        try:
            if camp.channel == Campaign.Channel.WHATSAPP:
                from whatsapp.api_connector import send_whatsapp_message

                res = send_whatsapp_message(to=to, message=body)
                if res.ok:
                    mark_message_sent(msg, provider_ref=res.provider)
                    sent += 1
                else:
                    mark_message_failed(msg, error=res.response_text)
            elif camp.channel == Campaign.Channel.SMS:
                from sms_center.sms_service import send_sms, send_google_sms
                provider_override = None
                google_overrides = {}
                try:
                    from vendors.models import VendorMarketingProviderConfig

                    vid = _vendor_id_from_campaign(camp)
                    if vid:
                        cfg = VendorMarketingProviderConfig.objects.filter(vendor_id=vid, provider="sms").first()
                        if cfg and cfg.is_active:
                            blob = cfg.config or {}
                            provider_override = str(blob.get("provider") or "").strip().lower() or None
                            if provider_override == "google":
                                google_overrides = {
                                    "api_key": (blob.get("api_key") or "").strip() or None,
                                    "sender_id": (blob.get("sender_id") or "").strip() or None,
                                    "api_url": (blob.get("api_url") or "").strip() or None,
                                }
                except Exception:
                    provider_override = None
                    google_overrides = {}

                if provider_override == "google":
                    res = send_google_sms(to, body, **google_overrides)
                    ok = bool(res.get("ok"))
                else:
                    res = send_sms(to, body, purpose="marketing", provider_override=provider_override)
                    ok = bool(res.get("ok") or res.get("success"))

                if ok:
                    mark_message_sent(msg, provider_ref=str(res.get("provider") or "sms"))
                    sent += 1
                else:
                    mark_message_failed(msg, error=str(res))
            elif camp.channel == Campaign.Channel.EMAIL:
                if not to:
                    raise ValueError("Missing email destination")
                send_mail(
                    subject=camp.name,
                    message=body,
                    from_email=None,
                    recipient_list=[to],
                    fail_silently=False,
                )
                mark_message_sent(msg, provider_ref="email")
                sent += 1
            else:
                mark_message_failed(msg, error="Paid ads execution is not enabled in Phase A.")
        except Exception as exc:
            mark_message_failed(msg, error=f"{type(exc).__name__}: {exc}")
    return sent


@shared_task
def process_paid_ad_runs(limit: int = 30):
    """
    Phase A demo paid ads runner.

    For channels: facebook/instagram/google/ott
    - Creates simulated metrics and marks run as completed once spend reaches budget_total.
    """

    from decimal import Decimal
    from random import randint

    from marketing.models import PaidAdRun

    qs = PaidAdRun.objects.select_related("campaign").filter(status__in=[PaidAdRun.Status.QUEUED, PaidAdRun.Status.RUNNING]).order_by("queued_at")[:limit]
    if not qs:
        return 0

    progressed = 0
    for run in qs:
        try:
            if run.status == PaidAdRun.Status.QUEUED:
                run.mark_running()

            budget_total = Decimal(str(run.budget_total or 0))
            if budget_total <= 0:
                budget_total = Decimal("100.00")
                run.budget_total = budget_total

            spent = Decimal(str(run.budget_spent or 0))
            delta_spent = Decimal(str(randint(10, 30)))
            spent = min(budget_total, spent + delta_spent)
            run.budget_spent = spent

            run.impressions = int(run.impressions or 0) + randint(200, 600)
            run.clicks = int(run.clicks or 0) + randint(5, 25)
            run.conversions = int(run.conversions or 0) + randint(0, 3)
            run.save(update_fields=["budget_total", "budget_spent", "impressions", "clicks", "conversions", "updated_at"])

            # Reflect spent back into Campaign for centralized view.
            try:
                Campaign.objects.filter(id=run.campaign_id).update(budget_spent=run.budget_spent)
            except Exception:
                pass

            if spent >= budget_total:
                run.mark_completed()
                try:
                    run.campaign.mark_completed()
                except Exception:
                    pass
            progressed += 1
        except Exception as exc:
            run.mark_failed(f"{type(exc).__name__}: {exc}")
            try:
                run.campaign.mark_failed(str(exc))
            except Exception:
                pass
    return progressed
