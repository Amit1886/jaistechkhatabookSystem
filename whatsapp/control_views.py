from __future__ import annotations

import json
import uuid
from decimal import Decimal
from datetime import timedelta, datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import redirect, render, get_object_or_404
from django.urls import reverse
from django.utils import timezone

from khatapro import DISABLE_CELERY
from whatsapp.models import Bot, BotFlow, BotMessage, BotTemplate, BroadcastCampaign, Customer, WhatsAppAccount, WhatsAppMessage, WhatsAppSession
from whatsapp.services.friendly_errors import friendly_error
from whatsapp.tasks import run_broadcast_campaign
from whatsapp.services.supplier_reminders import send_supplier_payment_reminders


def _bot_for_account(account: WhatsAppAccount) -> Bot | None:
    try:
        bot = account.bot  # type: ignore[attr-defined]
    except Exception:
        bot = None
    return bot if isinstance(bot, Bot) else None


def _template_payload_for_bot(bot: Bot) -> dict:
    bot_messages = list(BotMessage.objects.filter(bot=bot).order_by("key")[:500])
    bot_flows = list(BotFlow.objects.filter(bot=bot).order_by("priority", "name")[:500])
    return {
        "messages": [
            {
                "key": m.key,
                "message_type": m.message_type,
                "text": m.text,
                "media_url": m.media_url,
                "filename": m.filename,
            }
            for m in bot_messages
        ],
        "flows": [
            {
                "name": f.name,
                "description": f.description,
                "trigger_type": f.trigger_type,
                "trigger_value": f.trigger_value,
                "trigger_payload": f.trigger_payload or {},
                "actions": f.actions or [],
                "priority": f.priority,
                "is_active": bool(f.is_active),
            }
            for f in bot_flows
        ],
    }


@login_required
def whatsapp_control_center(request):
    accounts = list(
        WhatsAppAccount.objects.filter(owner=request.user)
        .order_by("-updated_at", "-created_at")
    )

    selected_id = (request.GET.get("account") or "").strip()
    selected = None
    if selected_id:
        selected = next((a for a in accounts if str(a.id) == selected_id), None)
    if not selected and accounts:
        selected = accounts[0]

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()

        if action == "create_account":
            provider = (request.POST.get("provider") or WhatsAppAccount.Provider.META_CLOUD_API).strip()
            label = (request.POST.get("label") or "").strip()
            phone_number = (request.POST.get("phone_number") or "").strip()

            meta_phone_number_id = (request.POST.get("meta_phone_number_id") or "").strip()
            meta_waba_id = (request.POST.get("meta_waba_id") or "").strip()
            meta_graph_version = (request.POST.get("meta_graph_version") or "v20.0").strip() or "v20.0"
            meta_access_token = (request.POST.get("meta_access_token") or "").strip()
            meta_app_secret = (request.POST.get("meta_app_secret") or "").strip()

            gateway_base_url = (request.POST.get("gateway_base_url") or "").strip()
            gateway_session_id = (request.POST.get("gateway_session_id") or "").strip()
            gateway_api_key = (request.POST.get("gateway_api_key") or "").strip()

            try:
                acc = WhatsAppAccount.objects.create(
                    owner=request.user,
                    label=label,
                    phone_number=phone_number,
                    provider=provider,
                    meta_phone_number_id=meta_phone_number_id,
                    meta_waba_id=meta_waba_id,
                    meta_graph_version=meta_graph_version,
                    gateway_base_url=gateway_base_url,
                    gateway_session_id=gateway_session_id,
                    status=WhatsAppAccount.Status.DISCONNECTED,
                )
                if meta_access_token:
                    acc.meta_access_token = meta_access_token
                if meta_app_secret:
                    acc.meta_app_secret = meta_app_secret
                if gateway_api_key:
                    acc.gateway_api_key = gateway_api_key
                acc.save()
                messages.success(request, "WhatsApp account added.")
                return redirect(reverse("whatsapp:control_center") + f"?account={acc.id}")
            except Exception:
                messages.error(request, "Failed to add WhatsApp account. Check details / duplicates.")
                return redirect(request.path)

        if action == "toggle_bot" and selected:
            bot = _bot_for_account(selected)
            if bot:
                bot.is_enabled = not bool(bot.is_enabled)
                bot.save(update_fields=["is_enabled", "updated_at"])
                messages.success(request, f"Bot {'enabled' if bot.is_enabled else 'disabled'}.")
            return redirect(reverse("whatsapp:control_center") + f"?account={selected.id}")

        if action == "toggle_auto_reply" and selected:
            bot = _bot_for_account(selected)
            if bot:
                bot.auto_reply_enabled = not bool(bot.auto_reply_enabled)
                bot.save(update_fields=["auto_reply_enabled", "updated_at"])
                messages.success(request, f"Auto-reply {'enabled' if bot.auto_reply_enabled else 'disabled'}.")
            return redirect(reverse("whatsapp:control_center") + f"?account={selected.id}")

        if action == "update_quick" and selected:
            try:
                from khataapp.models import FieldAgent

                selected.quick_commerce_enabled = bool(request.POST.get("quick_commerce_enabled"))
                selected.quick_delivery_radius_km = Decimal(str(request.POST.get("quick_delivery_radius_km") or "0") or "0")
                selected.store_latitude = Decimal(str(request.POST.get("store_latitude") or "0")) if (request.POST.get("store_latitude") or "").strip() else None
                selected.store_longitude = Decimal(str(request.POST.get("store_longitude") or "0")) if (request.POST.get("store_longitude") or "").strip() else None
                agent_id = (request.POST.get("quick_assign_agent_id") or "").strip()
                if agent_id:
                    selected.quick_assign_agent = FieldAgent.objects.filter(owner=request.user, id=agent_id).first()
                else:
                    selected.quick_assign_agent = None
                selected.save(
                    update_fields=[
                        "quick_commerce_enabled",
                        "quick_delivery_radius_km",
                        "store_latitude",
                        "store_longitude",
                        "quick_assign_agent",
                        "updated_at",
                    ]
                )
                messages.success(request, "Quick commerce settings updated.")
            except Exception:
                messages.error(request, "Failed to update quick commerce settings.")
            return redirect(reverse("whatsapp:control_center") + f"?account={selected.id}")

        if action == "create_message" and selected:
            bot = _bot_for_account(selected)
            if not bot:
                messages.error(request, "Bot not found for this account.")
                return redirect(reverse("whatsapp:control_center") + f"?account={selected.id}")
            key = (request.POST.get("message_key") or "").strip()
            text = (request.POST.get("message_text") or "").strip()
            message_type = (request.POST.get("message_type") or "text").strip().lower()
            media_url = (request.POST.get("media_url") or "").strip()
            filename = (request.POST.get("filename") or "").strip()
            if not key:
                messages.error(request, "Message key is required.")
                return redirect(reverse("whatsapp:control_center") + f"?account={selected.id}")
            try:
                BotMessage.objects.update_or_create(
                    bot=bot,
                    key=key,
                    defaults={
                        "message_type": message_type,
                        "text": text,
                        "media_url": media_url,
                        "filename": filename,
                    },
                )
                messages.success(request, "Bot message saved.")
            except Exception:
                messages.error(request, "Failed to save bot message (duplicate key?).")
            return redirect(reverse("whatsapp:control_center") + f"?account={selected.id}#bot")

        if action == "delete_message" and selected:
            bot = _bot_for_account(selected)
            msg_id = (request.POST.get("message_id") or "").strip()
            if bot and msg_id:
                try:
                    BotMessage.objects.filter(id=msg_id, bot=bot).delete()
                    messages.success(request, "Bot message deleted.")
                except Exception:
                    messages.error(request, "Failed to delete bot message.")
            return redirect(reverse("whatsapp:control_center") + f"?account={selected.id}#bot")

        if action == "create_flow" and selected:
            bot = _bot_for_account(selected)
            if not bot:
                messages.error(request, "Bot not found for this account.")
                return redirect(reverse("whatsapp:control_center") + f"?account={selected.id}")

            flow_id = (request.POST.get("flow_id") or "").strip()
            name = (request.POST.get("flow_name") or "").strip() or "Flow"
            trigger_type = (request.POST.get("trigger_type") or BotFlow.TriggerType.KEYWORD).strip()
            trigger_value = (request.POST.get("trigger_value") or "").strip()
            try:
                priority = int(request.POST.get("priority") or 100)
            except Exception:
                priority = 100
            is_active = bool(request.POST.get("is_active"))

            actions = []
            actions_json = (request.POST.get("actions_json") or "").strip()
            if actions_json:
                try:
                    parsed = json.loads(actions_json)
                    if isinstance(parsed, list):
                        actions = parsed
                except Exception:
                    actions = []

            if not actions:
                action_type = (request.POST.get("action_type") or "send_text").strip().lower()
                if action_type == "send_text":
                    actions = [{"type": "send_text", "text": (request.POST.get("action_text") or "").strip()}]
                elif action_type == "send_message_key":
                    actions = [{"type": "send_message_key", "key": (request.POST.get("action_key") or "").strip()}]
                elif action_type == "run_order_bot":
                    actions = [{"type": "run_order_bot"}]
                elif action_type == "connect_human":
                    actions = [{"type": "connect_human"}]
                elif action_type == "ai_reply":
                    actions = [{"type": "ai_reply"}]

            if not trigger_value:
                messages.error(request, "Trigger value is required (example: hi, 1, support).")
                return redirect(reverse("whatsapp:control_center") + f"?account={selected.id}#bot")

            try:
                flow = BotFlow.objects.filter(id=flow_id, bot=bot).first() if flow_id else None
                if not flow:
                    flow = BotFlow.objects.filter(bot=bot, name=name).first()
                if flow:
                    flow.name = name
                    flow.trigger_type = trigger_type
                    flow.trigger_value = trigger_value
                    flow.actions = actions
                    flow.priority = priority
                    flow.is_active = is_active
                    flow.save(update_fields=["name", "trigger_type", "trigger_value", "actions", "priority", "is_active", "updated_at"])
                else:
                    BotFlow.objects.create(
                        bot=bot,
                        name=name,
                        trigger_type=trigger_type,
                        trigger_value=trigger_value,
                        actions=actions,
                        priority=priority,
                        is_active=is_active,
                    )
                messages.success(request, "Bot flow saved.")
            except Exception:
                messages.error(request, "Failed to save bot flow.")
            return redirect(reverse("whatsapp:control_center") + f"?account={selected.id}#bot")

        if action == "toggle_flow" and selected:
            bot = _bot_for_account(selected)
            flow_id = (request.POST.get("flow_id") or "").strip()
            if bot and flow_id:
                flow = BotFlow.objects.filter(id=flow_id, bot=bot).first()
                if flow:
                    flow.is_active = not bool(flow.is_active)
                    flow.save(update_fields=["is_active", "updated_at"])
                    messages.success(request, f"Flow {'enabled' if flow.is_active else 'disabled'}.")
            return redirect(reverse("whatsapp:control_center") + f"?account={selected.id}#bot")

        if action == "delete_flow" and selected:
            bot = _bot_for_account(selected)
            flow_id = (request.POST.get("flow_id") or "").strip()
            if bot and flow_id:
                try:
                    BotFlow.objects.filter(id=flow_id, bot=bot).delete()
                    messages.success(request, "Bot flow deleted.")
                except Exception:
                    messages.error(request, "Failed to delete bot flow.")
            return redirect(reverse("whatsapp:control_center") + f"?account={selected.id}#bot")

        if action == "apply_template" and selected:
            bot = _bot_for_account(selected)
            tpl_id = (request.POST.get("template_id") or "").strip()
            if not bot:
                messages.error(request, "Bot not found for this account.")
                return redirect(reverse("whatsapp:control_center") + f"?account={selected.id}")
            tpl_qs = BotTemplate.objects.filter(id=tpl_id, is_active=True) if tpl_id else BotTemplate.objects.none()
            if tpl_id and not (request.user.is_staff or request.user.is_superuser):
                tpl_qs = tpl_qs.filter(Q(owner__isnull=True) | Q(owner=request.user))
            tpl = tpl_qs.first() if tpl_id else None
            if not tpl:
                messages.error(request, "Template not found.")
                return redirect(reverse("whatsapp:control_center") + f"?account={selected.id}#bot")
            try:
                payload = tpl.payload or {}
                msgs = payload.get("messages") if isinstance(payload, dict) else None
                flows = payload.get("flows") if isinstance(payload, dict) else None

                if isinstance(msgs, list):
                    for m in msgs:
                        if not isinstance(m, dict):
                            continue
                        key = str(m.get("key") or "").strip()
                        if not key:
                            continue
                        BotMessage.objects.update_or_create(
                            bot=bot,
                            key=key,
                            defaults={
                                "message_type": str(m.get("message_type") or "text").strip().lower(),
                                "text": str(m.get("text") or "").strip(),
                                "media_url": str(m.get("media_url") or "").strip(),
                                "filename": str(m.get("filename") or "").strip(),
                            },
                        )

                if isinstance(flows, list):
                    for f in flows:
                        if not isinstance(f, dict):
                            continue
                        name = str(f.get("name") or "").strip()
                        if not name:
                            continue
                        existing = BotFlow.objects.filter(bot=bot, name=name).first()
                        defaults = {
                            "description": str(f.get("description") or "").strip(),
                            "trigger_type": str(f.get("trigger_type") or BotFlow.TriggerType.KEYWORD).strip(),
                            "trigger_value": str(f.get("trigger_value") or "").strip(),
                            "trigger_payload": f.get("trigger_payload") if isinstance(f.get("trigger_payload"), dict) else {},
                            "actions": f.get("actions") if isinstance(f.get("actions"), list) else [],
                            "priority": int(f.get("priority") or 100),
                            "is_active": bool(f.get("is_active", True)),
                        }
                        if existing:
                            for k, v in defaults.items():
                                setattr(existing, k, v)
                            existing.save(update_fields=list(defaults.keys()) + ["updated_at"])
                        else:
                            BotFlow.objects.create(bot=bot, name=name, **defaults)

                if bot.kind != tpl.kind:
                    bot.kind = tpl.kind
                    bot.save(update_fields=["kind", "updated_at"])

                messages.success(request, f"Template '{tpl.name}' applied.")
            except Exception:
                messages.error(request, "Failed to apply template.")
            return redirect(reverse("whatsapp:control_center") + f"?account={selected.id}#bot")

        if action == "save_template" and selected:
            bot = _bot_for_account(selected)
            if not bot:
                messages.error(request, "Bot not found for this account.")
                return redirect(reverse("whatsapp:control_center") + f"?account={selected.id}#bot")

            name = (request.POST.get("template_name") or "").strip()[:140]
            description = (request.POST.get("template_description") or "").strip()[:2000]
            kind = (request.POST.get("template_kind") or bot.kind or Bot.Kind.ORDER).strip()
            if not name:
                messages.error(request, "Template name is required.")
                return redirect(reverse("whatsapp:control_center") + f"?account={selected.id}#bot")
            try:
                BotTemplate.objects.create(
                    owner=request.user,
                    name=name,
                    kind=kind,
                    description=description,
                    payload=_template_payload_for_bot(bot),
                    is_active=True,
                )
                messages.success(request, "Template saved to your library.")
            except Exception:
                messages.error(request, "Failed to save template (duplicate name?).")
            return redirect(reverse("whatsapp:control_center") + f"?account={selected.id}#bot")

        if action == "update_template" and selected:
            bot = _bot_for_account(selected)
            tpl_id = (request.POST.get("template_id") or "").strip()
            if not (bot and tpl_id):
                messages.error(request, "Bot/template not found.")
                return redirect(reverse("whatsapp:control_center") + f"?account={selected.id}#bot")
            tpl = BotTemplate.objects.filter(id=tpl_id, owner=request.user).first()
            if not tpl:
                messages.error(request, "You can only update your own templates.")
                return redirect(reverse("whatsapp:control_center") + f"?account={selected.id}#bot")
            try:
                tpl.name = (request.POST.get("template_name") or tpl.name).strip()[:140] or tpl.name
                tpl.description = (request.POST.get("template_description") or tpl.description).strip()[:2000]
                tpl.kind = (request.POST.get("template_kind") or tpl.kind).strip() or tpl.kind
                tpl.payload = _template_payload_for_bot(bot)
                tpl.is_active = True
                tpl.save(update_fields=["name", "description", "kind", "payload", "is_active", "updated_at"])
                messages.success(request, "Template updated.")
            except Exception:
                messages.error(request, "Failed to update template.")
            return redirect(reverse("whatsapp:control_center") + f"?account={selected.id}#bot")

        if action == "delete_template" and selected:
            tpl_id = (request.POST.get("template_id") or "").strip()
            if not tpl_id:
                return redirect(reverse("whatsapp:control_center") + f"?account={selected.id}#bot")
            try:
                BotTemplate.objects.filter(id=tpl_id, owner=request.user).delete()
                messages.success(request, "Template deleted.")
            except Exception:
                messages.error(request, "Failed to delete template.")
            return redirect(reverse("whatsapp:control_center") + f"?account={selected.id}#bot")

        if action == "add_customer_tag" and selected:
            cust_id = (request.POST.get("customer_id") or "").strip()
            tag = (request.POST.get("tag") or "").strip().lower()[:60]
            if cust_id and tag:
                cust = Customer.objects.filter(id=cust_id, owner=request.user, whatsapp_account=selected).first()
                if cust:
                    tags = list(cust.tags or [])
                    if tag not in tags:
                        tags.append(tag)
                        cust.tags = tags
                        cust.save(update_fields=["tags", "updated_at"])
                        messages.success(request, f"Tag '{tag}' added.")
            return redirect(reverse("whatsapp:control_center") + f"?account={selected.id}&customer={cust_id}")

        if action == "remove_customer_tag" and selected:
            cust_id = (request.POST.get("customer_id") or "").strip()
            tag = (request.POST.get("tag") or "").strip().lower()[:60]
            if cust_id and tag:
                cust = Customer.objects.filter(id=cust_id, owner=request.user, whatsapp_account=selected).first()
                if cust:
                    tags = [t for t in (cust.tags or []) if str(t).lower() != tag]
                    cust.tags = tags
                    cust.save(update_fields=["tags", "updated_at"])
                    messages.success(request, f"Tag '{tag}' removed.")
            return redirect(reverse("whatsapp:control_center") + f"?account={selected.id}&customer={cust_id}")

        if action == "request_qr" and selected:
            if selected.provider != WhatsAppAccount.Provider.WEB_GATEWAY:
                messages.error(request, "QR is supported only for Web Gateway accounts.")
                return redirect(reverse("whatsapp:control_center") + f"?account={selected.id}")
            try:
                from whatsapp.services.provider_clients import get_outbound_client

                if not (selected.gateway_session_id or "").strip():
                    selected.gateway_session_id = uuid.uuid4().hex
                    selected.save(update_fields=["gateway_session_id", "updated_at"])

                client = get_outbound_client(selected)
                res = client.request_qr()  # type: ignore[attr-defined]
                sess = WhatsAppSession.objects.filter(account=selected).order_by("-updated_at").first()
                if not sess:
                    sess = WhatsAppSession.objects.create(account=selected)
                payload = (res.response_text or "").strip()
                is_connected = bool(res.ok) and payload.lower() == "connected"
                sess.status = WhatsAppSession.Status.CONNECTED if is_connected else (WhatsAppSession.Status.QR_REQUIRED if res.ok else WhatsAppSession.Status.ERROR)
                sess.qr_payload = "" if is_connected else payload
                sess.last_qr_at = timezone.now()
                sess.last_connected_at = timezone.now() if is_connected else sess.last_connected_at
                sess.last_error = "" if res.ok else payload[:2000]
                sess.save(update_fields=["status", "qr_payload", "last_qr_at", "last_connected_at", "last_error", "updated_at"])
                selected.status = WhatsAppAccount.Status.CONNECTED if is_connected else (WhatsAppAccount.Status.CONNECTING if res.ok else WhatsAppAccount.Status.ERROR)
                selected.save(update_fields=["status", "updated_at"])
                if res.ok:
                    messages.success(request, "Already connected." if is_connected else "QR requested from gateway.")
                else:
                    err = friendly_error(payload or "qr_request_failed")
                    messages.error(request, f"QR request failed: {err[:220]}")
            except Exception:
                messages.error(request, "Failed to request QR. Check gateway settings.")
            return redirect(reverse("whatsapp:control_center") + f"?account={selected.id}")

        if action == "create_broadcast" and selected:
            name = (request.POST.get("broadcast_name") or "Broadcast Campaign").strip()[:140]
            text = (request.POST.get("broadcast_text") or "").strip()
            target_type = (request.POST.get("target_type") or BroadcastCampaign.TargetType.ALL_CUSTOMERS).strip()
            tag = (request.POST.get("target_tag") or "").strip().lower()
            scheduled_raw = (request.POST.get("scheduled_at") or "").strip()
            if not text:
                messages.error(request, "Broadcast message text is required.")
                return redirect(reverse("whatsapp:control_center") + f"?account={selected.id}")
            payload = {}
            if target_type == BroadcastCampaign.TargetType.CUSTOMER_TAG and tag:
                payload = {"tag": tag}

            scheduled_at = None
            if scheduled_raw:
                # datetime-local -> naive localtime; store as aware
                try:
                    dt = datetime.fromisoformat(scheduled_raw)
                    if timezone.is_naive(dt):
                        dt = timezone.make_aware(dt, timezone.get_current_timezone())
                    scheduled_at = dt
                except Exception:
                    scheduled_at = None

            camp = BroadcastCampaign.objects.create(
                owner=request.user,
                whatsapp_account=selected,
                name=name,
                status=BroadcastCampaign.Status.SCHEDULED if scheduled_at else BroadcastCampaign.Status.DRAFT,
                target_type=target_type,
                target_payload=payload,
                message_type=BroadcastCampaign.MessageType.TEXT,
                text=text,
                scheduled_at=scheduled_at,
            )
            messages.success(request, "Broadcast campaign created.")
            return redirect(reverse("whatsapp:control_center") + f"?account={selected.id}#broadcasts")

        if action == "start_broadcast" and selected:
            camp_id = (request.POST.get("campaign_id") or "").strip()
            camp = BroadcastCampaign.objects.filter(id=camp_id, owner=request.user, whatsapp_account=selected).first()
            if not camp:
                messages.error(request, "Campaign not found.")
                return redirect(reverse("whatsapp:control_center") + f"?account={selected.id}")
            try:
                if DISABLE_CELERY:
                    run_broadcast_campaign.run(str(camp.id))  # type: ignore[attr-defined]
                else:
                    run_broadcast_campaign.apply_async(args=(str(camp.id),), retry=False, ignore_result=True)
            except Exception:
                run_broadcast_campaign.run(str(camp.id))  # type: ignore[attr-defined]
            messages.success(request, "Broadcast started.")
            return redirect(reverse("whatsapp:control_center") + f"?account={selected.id}#broadcasts")

        if action == "send_supplier_reminders" and selected:
            try:
                out = send_supplier_payment_reminders(owner=request.user, account=selected, dry_run=False)
                if out.get("sent"):
                    messages.success(request, f"Supplier reminders sent: {out.get('sent')} (failed {out.get('failed')}, skipped {out.get('skipped')}).")
                else:
                    messages.info(request, "No supplier reminders sent (no dues or suppliers missing WhatsApp numbers).")
            except Exception:
                messages.error(request, "Failed to send supplier reminders.")
            return redirect(reverse("whatsapp:control_center") + f"?account={selected.id}#advisor")

        if action == "send_manual" and selected:
            to_raw = (request.POST.get("to_number") or "").strip()
            text = (request.POST.get("message_text") or "").strip()
            if not to_raw or not text:
                messages.error(request, "To number and message are required.")
                return redirect(reverse("whatsapp:control_center") + f"?account={selected.id}")
            try:
                from whatsapp.services.provider_clients import send_text as send_text_out
                from whatsapp.services.phone import normalize_wa_phone
                from django.conf import settings

                to = normalize_wa_phone(to_raw, default_country_code=str(getattr(settings, "WA_DEFAULT_COUNTRY_CODE", "") or ""))
                res = send_text_out(account=selected, to=to, text=text)
                WhatsAppMessage.objects.create(
                    owner=request.user,
                    whatsapp_account=selected,
                    direction=WhatsAppMessage.Direction.OUTBOUND,
                    from_number=(selected.phone_number or "").strip(),
                    to_number=to or to_raw,
                    body=text,
                    message_type="text",
                    provider_message_id=res.provider_message_id,
                    raw_payload={"provider": res.provider, "status_code": res.status_code, "response": res.response_text[:5000]},
                    status=WhatsAppMessage.Status.PROCESSED if res.ok else WhatsAppMessage.Status.FAILED,
                    error="" if res.ok else (res.response_text or "")[:2000],
                    parsed_intent="manual_send",
                )
                if res.ok:
                    messages.success(request, f"Message sent to {to or to_raw}.")
                else:
                    err = friendly_error(res.response_text or "send_failed")
                    if len(err) > 220:
                        err = err[:220] + "..."
                    messages.error(request, f"Send failed: {err}")
            except Exception:
                messages.error(request, "Failed to send message.")
            return redirect(reverse("whatsapp:control_center") + f"?account={selected.id}")

        messages.error(request, "Invalid action.")
        return redirect(request.path)

    logs = []
    broadcasts = []
    analytics = {}
    latest_session = None
    global_templates = []
    my_templates = []
    bot_messages = []
    bot_flows = []
    edit_flow = None
    field_agents = []
    customers = []
    selected_customer = None
    if selected:
        customer_id = (request.GET.get("customer") or "").strip()
        log_qs = WhatsAppMessage.objects.filter(owner=request.user, whatsapp_account=selected)
        if customer_id:
            selected_customer = Customer.objects.filter(owner=request.user, whatsapp_account=selected, id=customer_id).first()
            if selected_customer:
                log_qs = log_qs.filter(customer=selected_customer)
        logs = list(log_qs.order_by("-created_at", "-id")[:200])
        customers = list(
            Customer.objects.filter(owner=request.user, whatsapp_account=selected)
            .order_by("-last_seen_at", "-updated_at", "-created_at")[:80]
        )
        broadcasts = list(
            BroadcastCampaign.objects.filter(owner=request.user, whatsapp_account=selected)
            .order_by("-updated_at", "-created_at")[:20]
        )
        latest_session = WhatsAppSession.objects.filter(account=selected).order_by("-updated_at").first()
        try:
            global_templates = list(BotTemplate.objects.filter(is_active=True, owner__isnull=True).order_by("name")[:200])
            my_templates = list(BotTemplate.objects.filter(owner=request.user).order_by("name")[:200])
        except Exception:
            global_templates = []
            my_templates = []
        bot = _bot_for_account(selected)
        if bot:
            bot_messages = list(BotMessage.objects.filter(bot=bot).order_by("key")[:200])
            bot_flows = list(BotFlow.objects.filter(bot=bot).order_by("priority", "name")[:200])
            flow_id = (request.GET.get("flow") or "").strip()
            if flow_id:
                edit_flow = BotFlow.objects.filter(bot=bot, id=flow_id).first()
        try:
            from khataapp.models import FieldAgent

            field_agents = list(FieldAgent.objects.filter(owner=request.user, is_active=True).select_related("user").order_by("user__username")[:200])
        except Exception:
            field_agents = []

        # Basic analytics (7 days)
        since = timezone.now() - timedelta(days=7)
        qs = WhatsAppMessage.objects.filter(owner=request.user, whatsapp_account=selected, created_at__gte=since)
        received = qs.filter(direction=WhatsAppMessage.Direction.INBOUND).count()
        sent = qs.filter(direction=WhatsAppMessage.Direction.OUTBOUND).count()
        unique_customers = qs.values("customer_id").exclude(customer_id__isnull=True).distinct().count()
        orders_count = 0
        try:
            from commerce.models import WhatsAppOrderInbox

            orders_count = (
                WhatsAppOrderInbox.objects.filter(owner=request.user, whatsapp_account=selected, created_at__gte=since)
                .exclude(order__isnull=True)
                .count()
            )
        except Exception:
            orders_count = 0
        analytics = {
            "since": since,
            "received": received,
            "sent": sent,
            "unique_customers": unique_customers,
            "orders": orders_count,
        }

    # Auto-generated webhook URLs
    meta_webhook_url = ""
    gateway_webhook_url = ""
    if selected:
        meta_webhook_url = request.build_absolute_uri(reverse("whatsapp_meta_webhook", kwargs={"account_id": str(selected.id)}))
        gateway_webhook_url = request.build_absolute_uri(
            reverse("whatsapp_gateway_inbound_webhook", kwargs={"account_id": str(selected.id)})
        )

    return render(
        request,
        "whatsapp/control_center.html",
        {
            "accounts": accounts,
            "selected": selected,
            "logs": logs,
            "meta_webhook_url": meta_webhook_url,
            "gateway_webhook_url": gateway_webhook_url,
            "latest_session": latest_session,
            "broadcasts": broadcasts,
            "analytics": analytics,
            "global_templates": global_templates,
            "my_templates": my_templates,
            "bot_messages": bot_messages,
            "bot_flows": bot_flows,
            "edit_flow": edit_flow,
            "field_agents": field_agents,
            "customers": customers,
            "selected_customer": selected_customer,
        },
    )


def whatsapp_mini_site(request, account_id: str):
    """
    Lightweight public mini-site surfaced inside WhatsApp (PWA-friendly).
    Shows a simple menu + product highlights; no login required.
    """
    account = get_object_or_404(WhatsAppAccount, id=account_id)
    products = []
    try:
        from commerce.models import Product  # type: ignore

        products = list(
            Product.objects.filter(owner=account.owner).order_by("-updated_at")[:12].values("name", "price", "sku")
        )
    except Exception:
        products = []

    actions = [
        {"label": "View Products", "slug": "products"},
        {"label": "Generate Bill", "slug": "bill"},
        {"label": "Check Reports", "slug": "reports"},
        {"label": "Upgrade Plan", "slug": "upgrade"},
    ]
    return render(
        request,
        "whatsapp/mini_site.html",
        {"account": account, "products": products, "actions": actions},
    )
