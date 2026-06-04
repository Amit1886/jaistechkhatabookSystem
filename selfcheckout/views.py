import json
import random
import secrets
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from commerce.models import Product

from .models import CheckoutSession, KioskInteractionEvent, MobileContinueSession, PromoMedia, RetailBroadcast, RetailSyncSnapshot, RewardCampaign, RewardDrop, SupportRequest
from .services import (
    add_scan,
    assign_queue_ticket,
    complete_checkout,
    continue_as_guest,
    create_support_request,
    health_ping,
    identify_by_membership,
    idle_recovery,
    active_theme_payload,
    kiosk_snapshot,
    parse_voice_command,
    recalculate_session,
    recover_customer_session,
    rfid_detect,
    remove_item,
    search_products,
    send_customer_otp,
    session_payload,
    update_item_quantity,
    verify_customer_otp,
)
from .realtime import publish_cart, publish_payment, publish_kiosk_event, publish_store_event


@login_required
def kiosk(request):
    kiosk_id = request.GET.get("kiosk") or "KIOSK-1"
    session = CheckoutSession.objects.filter(owner=request.user, kiosk_id=kiosk_id, status=CheckoutSession.Status.ACTIVE).order_by("-id").first()
    if not session:
        session = CheckoutSession.objects.create(owner=request.user, kiosk_id=kiosk_id)
    recalculate_session(session)
    health_ping(session=session, data={"source": "kiosk_load"})
    return render(request, "selfcheckout/kiosk.html", {"checkout_session": session, "cart_state": session_payload(session)})


@login_required
def cart(request, session_key):
    session = get_object_or_404(CheckoutSession.objects.select_related("invoice"), owner=request.user, session_key=session_key)
    recalculate_session(session)
    return JsonResponse({"ok": True, "cart": session_payload(session)})


@login_required
def product_search(request):
    return JsonResponse({"ok": True, "products": search_products(owner=request.user, query=request.GET.get("q") or "")})


@login_required
def intelligence(request, session_key):
    session = get_object_or_404(CheckoutSession, owner=request.user, session_key=session_key)
    recalculate_session(session)
    return JsonResponse({"ok": True, "cart": session_payload(session), "queue": kiosk_snapshot(owner=request.user)})


def retail_state_payload(owner) -> dict:
    products = []
    for p in Product.objects.filter(Q(owner=owner) | Q(owner__isnull=True)).order_by("name")[:120]:
        stock = int(getattr(p, "stock", 0) or 0)
        sold_events = KioskInteractionEvent.objects.filter(owner=owner, product=p, kind=KioskInteractionEvent.EventKind.ADD, created_at__gte=timezone.now() - timedelta(hours=6)).count()
        badges = []
        if stock <= 0:
            badges.append("Restocking Soon")
        elif stock <= 2:
            badges.append(f"Only {stock} Left")
        if sold_events >= 3:
            badges.append("Fast Moving")
        if sold_events >= 5:
            badges.append("High Demand")
        products.append({"id": str(p.id), "stock": stock, "price": str(p.price), "badges": badges, "updated_at": timezone.now().isoformat()})
    broadcasts = list(
        RetailBroadcast.objects
        .filter(owner=owner, is_active=True, starts_at__lte=timezone.now())
        .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now()))
        .values("id", "title", "message", "priority", "voice_enabled")
        .order_by("-created_at")[:5]
    )
    return {"products": products, "broadcasts": broadcasts, "server_time": timezone.now().isoformat()}


@login_required
def retail_state(request, session_key):
    get_object_or_404(CheckoutSession, owner=request.user, session_key=session_key)
    payload = retail_state_payload(request.user)
    snapshot, _ = RetailSyncSnapshot.objects.get_or_create(owner=request.user, key="retail_state", defaults={"payload": payload})
    snapshot.payload = payload
    snapshot.version += 1
    snapshot.updated_at = timezone.now()
    snapshot.save(update_fields=["payload", "version", "updated_at"])
    return JsonResponse({"ok": True, "state": payload, "version": snapshot.version})


def publish_inventory_sync(owner):
    publish_store_event(owner.id, "retail.inventory", retail_state_payload(owner))


@login_required
@require_POST
def admin_broadcast(request):
    title = (request.POST.get("title") or "Store announcement")[:140]
    message = (request.POST.get("message") or "")[:280]
    priority = request.POST.get("priority") or RetailBroadcast.Priority.NORMAL
    if priority not in dict(RetailBroadcast.Priority.choices):
        priority = RetailBroadcast.Priority.NORMAL
    broadcast = RetailBroadcast.objects.create(
        owner=request.user,
        title=title,
        message=message,
        priority=priority,
        voice_enabled=request.POST.get("voice_enabled", "1") != "0",
        expires_at=timezone.now() + timedelta(minutes=int(request.POST.get("minutes") or 20)),
    )
    payload = {"id": broadcast.id, "title": broadcast.title, "message": broadcast.message, "priority": broadcast.priority, "voice_enabled": broadcast.voice_enabled}
    publish_store_event(request.user.id, "retail.broadcast", payload)
    return JsonResponse({"ok": True, "broadcast": payload})


@login_required
def queue_status(request):
    return JsonResponse({"ok": True, "queue": kiosk_snapshot(owner=request.user)})


@login_required
@require_POST
def queue_assign(request):
    return JsonResponse({"ok": True, "assignment": assign_queue_ticket(owner=request.user), "queue": kiosk_snapshot(owner=request.user)})


@login_required
def theme(request, session_key):
    session = get_object_or_404(CheckoutSession, owner=request.user, session_key=session_key)
    payload = active_theme_payload(session=session, requested=request.GET.get("theme") or "")
    return JsonResponse({"ok": True, "theme": payload})


@login_required
@require_POST
def support_request(request, session_key):
    session = get_object_or_404(CheckoutSession, owner=request.user, session_key=session_key)
    try:
        result = create_support_request(
            session=session,
            issue_type=request.POST.get("issue_type") or "general_help",
            priority=request.POST.get("priority") or "normal",
            notes=request.POST.get("notes") or "",
        )
        publish_kiosk_event(session, "support.update", result)
        return JsonResponse({"ok": True, **result})
    except Exception as exc:
        return JsonResponse({"ok": False, "detail": str(exc)}, status=400)


@login_required
@require_POST
def interaction_events(request, session_key):
    session = get_object_or_404(CheckoutSession, owner=request.user, session_key=session_key)
    raw = request.POST.get("events") or request.body.decode("utf-8", errors="ignore") or "[]"
    try:
        incoming = json.loads(raw)
        if isinstance(incoming, dict):
            incoming = incoming.get("events", [])
    except Exception:
        incoming = []
    events = []
    for item in incoming[:80]:
        if not isinstance(item, dict):
            continue
        product_id = item.get("product_id") or None
        kind = item.get("kind") if item.get("kind") in dict(KioskInteractionEvent.EventKind.choices) else KioskInteractionEvent.EventKind.CLICK
        events.append(KioskInteractionEvent(
            session=session,
            owner=request.user,
            product_id=product_id if str(product_id or "").isdigit() else None,
            kiosk_id=session.kiosk_id,
            kind=kind,
            area=(item.get("area") or "kiosk")[:80],
            x=max(0, min(10000, int(float(item.get("x") or 0)))),
            y=max(0, min(10000, int(float(item.get("y") or 0)))),
            intensity=max(1, min(100, int(float(item.get("intensity") or 1)))),
            duration_ms=max(0, int(float(item.get("duration_ms") or 0))),
            payload=item.get("payload") if isinstance(item.get("payload"), dict) else {},
        ))
    if events:
        KioskInteractionEvent.objects.bulk_create(events)
        publish_kiosk_event(session, "analytics.heatmap", {"count": len(events), "kiosk_id": session.kiosk_id})
    return JsonResponse({"ok": True, "saved": len(events)})


@login_required
def interaction_dashboard(request):
    since = timezone.now() - timedelta(hours=24)
    qs = KioskInteractionEvent.objects.filter(owner=request.user, created_at__gte=since)
    hot_zones = list(qs.values("area").annotate(touches=Count("id"), intensity=Sum("intensity")).order_by("-intensity")[:10])
    products = list(qs.exclude(product_id__isnull=True).values("product__name").annotate(events=Count("id"), hover_ms=Sum("duration_ms")).order_by("-events")[:10])
    dead_zones = [area for area in ["scan-panel", "cart-panel", "payment-panel", "digital-shelf", "mobile-handoff"] if not qs.filter(area=area).exists()]
    html = f"""
    <html><head><title>Self Checkout Interaction Dashboard</title>
    <style>body{{font-family:Inter,system-ui;background:#07080d;color:#f8fbff;padding:24px}}.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}}.card{{border:1px solid rgba(255,255,255,.18);border-radius:18px;padding:16px;background:rgba(255,255,255,.08)}}li{{margin:8px 0}}</style></head>
    <body><h1>Live Heatmap Analytics</h1><p>Last 24 hours interaction intelligence.</p>
    <div class="grid"><div class="card"><h2>Hot Zones</h2><ol>{''.join(f'<li>{z["area"]}: {z["intensity"] or 0}</li>' for z in hot_zones) or '<li>No data yet</li>'}</ol></div>
    <div class="card"><h2>Dead Zones</h2><ol>{''.join(f'<li>{z}</li>' for z in dead_zones) or '<li>No dead zones</li>'}</ol></div>
    <div class="card"><h2>Product Engagement</h2><ol>{''.join(f'<li>{p["product__name"]}: {p["events"]} events, {p["hover_ms"] or 0}ms hover</li>' for p in products) or '<li>No product events</li>'}</ol></div></div>
    </body></html>
    """
    return HttpResponse(html)


@login_required
def staff_dashboard(request):
    alerts = SupportRequest.objects.filter(owner=request.user, status__in=[SupportRequest.Status.OPEN, SupportRequest.Status.ASSIGNED]).order_by("-opened_at")[:20]
    html = "<html><head><title>Self Checkout Staff Alerts</title><style>body{font-family:Inter,system-ui;background:#07080d;color:white;padding:24px}.alert{border:1px solid #ff5a76;border-radius:16px;padding:14px;margin:10px 0;background:rgba(255,90,118,.12)}</style></head><body><h1>Emergency Staff Assist</h1>"
    html += "".join(f"<div class='alert'><b>Kiosk {a.kiosk}</b> | {a.priority} | {a.issue_type}<br>Waiting: {int((timezone.now()-a.opened_at).total_seconds())}s</div>" for a in alerts) or "<p>No active alerts.</p>"
    html += "</body></html>"
    return HttpResponse(html)


@login_required
def digital_twin_dashboard(request):
    since = timezone.now() - timedelta(hours=2)
    sessions = CheckoutSession.objects.filter(owner=request.user, started_at__gte=since).order_by("-last_activity_at")[:20]
    interactions = KioskInteractionEvent.objects.filter(owner=request.user, created_at__gte=since)
    product_stats = interactions.exclude(product_id__isnull=True).values("product__name").annotate(events=Count("id"), intensity=Sum("intensity")).order_by("-intensity")[:12]
    kiosk_stats = interactions.values("kiosk_id", "area").annotate(events=Count("id")).order_by("-events")[:18]
    html = "<html><head><title>Digital Twin Store View</title><style>body{font-family:Inter,system-ui;background:#07080d;color:#f8fbff;padding:24px}.grid{display:grid;grid-template-columns:1.2fr 1fr;gap:16px}.card{border:1px solid rgba(66,248,255,.25);border-radius:18px;padding:16px;background:rgba(255,255,255,.08)}.kiosk{display:grid;grid-template-columns:1fr auto;gap:8px;padding:10px;border-bottom:1px solid rgba(255,255,255,.1)}.dot{width:10px;height:10px;border-radius:50%;background:#5dffb1;display:inline-block}</style></head><body><h1>Digital Twin Store View</h1><p>Realtime kiosk usage, cart activity, queues, and interaction intelligence.</p><div class='grid'>"
    html += "<section class='card'><h2>Live Kiosks</h2>" + "".join(f"<div class='kiosk'><span><span class='dot'></span> {s.kiosk_id} | {s.status} | Rs {s.total}</span><b>{s.last_activity_at:%H:%M:%S}</b></div>" for s in sessions) + "</section>"
    html += "<section class='card'><h2>Product Engagement</h2><ol>" + ("".join(f"<li>{p['product__name']}: {p['events']} events, intensity {p['intensity'] or 0}</li>" for p in product_stats) or "<li>No product events yet</li>") + "</ol></section>"
    html += "<section class='card'><h2>Store Activity Map</h2><ol>" + ("".join(f"<li>{k['kiosk_id']} / {k['area']}: {k['events']}</li>" for k in kiosk_stats) or "<li>No activity yet</li>") + "</ol></section>"
    html += "<section class='card'><h2>Broadcast Console</h2><p>Use POST /pos/self-checkout/admin-broadcast/ from admin tools to send instant store-wide alerts.</p><p>Fields: title, message, priority, minutes, voice_enabled.</p></section>"
    html += "</div></body></html>"
    return HttpResponse(html)


@login_required
@require_POST
def mobile_handoff(request, session_key):
    session = get_object_or_404(CheckoutSession, owner=request.user, session_key=session_key)
    MobileContinueSession.objects.filter(session=session, is_active=True, expires_at__lt=timezone.now()).update(is_active=False)
    handoff = MobileContinueSession.objects.create(
        session=session,
        owner=request.user,
        token=secrets.token_urlsafe(32),
        device_label=(request.POST.get("device_label") or "Customer mobile")[:120],
        expires_at=timezone.now() + timedelta(minutes=20),
    )
    url = request.build_absolute_uri(f"/pos/self-checkout/mobile/{handoff.token}/")
    payload = {"token": handoff.token, "url": url, "expires_at": handoff.expires_at.isoformat()}
    publish_kiosk_event(session, "mobile.handoff", payload)
    return JsonResponse({"ok": True, **payload})


def mobile_continue(request, token):
    handoff = get_object_or_404(MobileContinueSession.objects.select_related("session", "owner"), token=token, is_active=True, expires_at__gt=timezone.now())
    handoff.last_seen_at = timezone.now()
    handoff.save(update_fields=["last_seen_at"])
    session = handoff.session
    recalculate_session(session)
    return render(request, "selfcheckout/mobile_continue.html", {"handoff": handoff, "cart_state": session_payload(session)})


@login_required
@require_POST
def reward_drop(request, session_key):
    session = get_object_or_404(CheckoutSession, owner=request.user, session_key=session_key)
    campaign = RewardCampaign.objects.filter(owner=request.user, is_active=True).order_by("-id").first()
    if not campaign:
        campaign = RewardCampaign.objects.create(owner=request.user, name="Smart Checkout Lucky Drop")
    won = random.randint(1, 100) <= campaign.probability
    title = "Surprise unlocked" if won else "Thanks for shopping"
    drop = RewardDrop.objects.create(
        session=session,
        campaign=campaign,
        reward_type="cashback" if won else "none",
        title=title,
        coupon_code=campaign.coupon_code if won else "",
        cashback_amount=campaign.cashback_amount if won else Decimal("0.00"),
        payload={"won": won, "probability": campaign.probability},
    )
    payload = {"won": won, "title": drop.title, "coupon": drop.coupon_code, "cashback": str(drop.cashback_amount)}
    publish_kiosk_event(session, "reward.drop", payload)
    return JsonResponse({"ok": True, "reward": payload})


@login_required
@require_POST
def idle(request, session_key):
    session = get_object_or_404(CheckoutSession, owner=request.user, session_key=session_key)
    try:
        result = idle_recovery(session=session, stage=request.POST.get("stage") or "warning")
        publish_kiosk_event(session, "idle.update", result)
        return JsonResponse({"ok": True, **result})
    except Exception as exc:
        return JsonResponse({"ok": False, "detail": str(exc)}, status=400)


@login_required
def recover_session(request):
    return JsonResponse({"ok": True, **recover_customer_session(owner=request.user, mobile=request.GET.get("mobile") or "")})


@login_required
@require_POST
def customer_send_otp(request, session_key):
    session = get_object_or_404(CheckoutSession, owner=request.user, session_key=session_key)
    try:
        return JsonResponse({"ok": True, **send_customer_otp(session=session, mobile=request.POST.get("mobile", ""), purpose=request.POST.get("purpose") or "existing")})
    except Exception as exc:
        return JsonResponse({"ok": False, "detail": str(exc)}, status=400)


@login_required
@require_POST
def customer_verify_otp(request, session_key):
    session = get_object_or_404(CheckoutSession, owner=request.user, session_key=session_key)
    try:
        result = verify_customer_otp(
            session=session,
            mobile=request.POST.get("mobile", ""),
            otp=request.POST.get("otp", ""),
            name=request.POST.get("name", ""),
            email=request.POST.get("email", ""),
            mode=request.POST.get("mode") or "existing",
        )
        publish_cart(session, result["cart"])
        return JsonResponse({"ok": True, **result})
    except Exception as exc:
        return JsonResponse({"ok": False, "detail": str(exc)}, status=400)


@login_required
@require_POST
def customer_membership(request, session_key):
    session = get_object_or_404(CheckoutSession, owner=request.user, session_key=session_key)
    try:
        result = identify_by_membership(
            session=session,
            token=request.POST.get("token", ""),
            nfc_uid=request.POST.get("nfc_uid", ""),
            face_hash=request.POST.get("face_hash", ""),
        )
        publish_cart(session, result["cart"])
        return JsonResponse({"ok": True, **result})
    except Exception as exc:
        return JsonResponse({"ok": False, "detail": str(exc)}, status=400)


@login_required
@require_POST
def guest_checkout(request, session_key):
    session = get_object_or_404(CheckoutSession, owner=request.user, session_key=session_key)
    try:
        result = continue_as_guest(session=session)
        publish_cart(session, result["cart"])
        return JsonResponse({"ok": True, **result})
    except Exception as exc:
        return JsonResponse({"ok": False, "detail": str(exc)}, status=400)


@login_required
@require_POST
def scan(request, session_key):
    session = get_object_or_404(CheckoutSession, owner=request.user, session_key=session_key)
    try:
        add_scan(session=session, barcode=request.POST.get("barcode", ""), product_id=request.POST.get("product_id") or None, quantity=request.POST.get("quantity") or 1)
        session.refresh_from_db()
        cart_data = session_payload(session)
        publish_cart(session, cart_data)
        publish_inventory_sync(request.user)
        return JsonResponse({"ok": True, "cart": cart_data})
    except Exception as exc:
        return JsonResponse({"ok": False, "detail": str(exc)}, status=400)


@login_required
@require_POST
def voice_command(request, session_key):
    session = get_object_or_404(CheckoutSession, owner=request.user, session_key=session_key)
    try:
        result = parse_voice_command(session=session, command=request.POST.get("command", ""))
        return JsonResponse({"ok": True, **result})
    except Exception as exc:
        return JsonResponse({"ok": False, "detail": str(exc)}, status=400)


@login_required
@require_POST
def rfid(request, session_key):
    session = get_object_or_404(CheckoutSession, owner=request.user, session_key=session_key)
    try:
        result = rfid_detect(session=session, tag=request.POST.get("tag", ""))
        publish_cart(session, result["cart"])
        publish_inventory_sync(request.user)
        return JsonResponse({"ok": True, **result})
    except Exception as exc:
        return JsonResponse({"ok": False, "detail": str(exc)}, status=400)


@login_required
@require_POST
def nfc_tap(request, session_key):
    session = get_object_or_404(CheckoutSession, owner=request.user, session_key=session_key)
    try:
        invoice = complete_checkout(
            session=session,
            payment_method=request.POST.get("method") or "nfc_tap",
            payment_reference=request.POST.get("reference") or f"NFC-{session.session_key.hex[:10].upper()}",
        )
        session.refresh_from_db()
        payload = {
            "ok": True,
            "invoice_id": invoice.id,
            "invoice_number": invoice.number,
            "amount": str(invoice.amount),
            "verification_token": f"VERIFY-{invoice.id}-{session.session_key.hex[:8].upper()}",
            "cart": session_payload(session),
        }
        publish_payment(session, payload)
        publish_inventory_sync(request.user)
        return JsonResponse(payload)
    except Exception as exc:
        return JsonResponse({"ok": False, "detail": str(exc)}, status=400)


@login_required
@require_POST
def health(request, session_key):
    session = get_object_or_404(CheckoutSession, owner=request.user, session_key=session_key)
    payload = {key: request.POST.get(key) for key in request.POST.keys()}
    return JsonResponse({"ok": True, "queue": health_ping(session=session, data=payload)})


@login_required
@require_POST
def update_item(request, session_key, item_id):
    session = get_object_or_404(CheckoutSession, owner=request.user, session_key=session_key)
    try:
        update_item_quantity(session=session, item_id=item_id, quantity=request.POST.get("quantity") or 0)
        session.refresh_from_db()
        cart_data = session_payload(session)
        publish_cart(session, cart_data)
        publish_inventory_sync(request.user)
        return JsonResponse({"ok": True, "cart": cart_data})
    except Exception as exc:
        return JsonResponse({"ok": False, "detail": str(exc)}, status=400)


@login_required
@require_POST
def remove_cart_item(request, session_key, item_id):
    session = get_object_or_404(CheckoutSession, owner=request.user, session_key=session_key)
    try:
        remove_item(session=session, item_id=item_id)
        session.refresh_from_db()
        cart_data = session_payload(session)
        publish_cart(session, cart_data)
        publish_inventory_sync(request.user)
        return JsonResponse({"ok": True, "cart": cart_data})
    except Exception as exc:
        return JsonResponse({"ok": False, "detail": str(exc)}, status=400)


@login_required
@require_POST
def pay(request, session_key):
    session = get_object_or_404(CheckoutSession, owner=request.user, session_key=session_key)
    try:
        invoice = complete_checkout(session=session, payment_method=request.POST.get("method") or "upi", payment_reference=request.POST.get("reference") or "")
        session.refresh_from_db()
        payload = {
            "ok": True,
            "invoice_id": invoice.id,
            "invoice_number": invoice.number,
            "amount": str(invoice.amount),
            "verification_token": f"VERIFY-{invoice.id}-{session.session_key.hex[:8].upper()}",
            "cart": session_payload(session),
        }
        publish_payment(session, payload)
        publish_inventory_sync(request.user)
        return JsonResponse(payload)
    except Exception as exc:
        return JsonResponse({"ok": False, "detail": str(exc)}, status=400)


@login_required
@require_POST
def reset(request):
    kiosk_id = request.POST.get("kiosk_id") or "KIOSK-1"
    CheckoutSession.objects.filter(owner=request.user, kiosk_id=kiosk_id, status=CheckoutSession.Status.ACTIVE).update(status=CheckoutSession.Status.ABANDONED)
    session = CheckoutSession.objects.create(owner=request.user, kiosk_id=kiosk_id)
    return JsonResponse({"ok": True, "session_key": str(session.session_key), "cart": session_payload(session)})


@login_required
def live_products(request):
    """
    Live feed for kiosk product ticker.
    Returns compact JSON with product data optimized for scrolling display.
    """
    def to_abs(url: str) -> str:
        """Convert relative URL to absolute."""
        if not url:
            return ""
        if url.startswith("http://") or url.startswith("https://"):
            return url
        scheme = "https" if request.is_secure() else "http"
        return f"{scheme}://{request.get_host()}{url}"
    
    qs = (
        Product.objects
        .filter(Q(owner=request.user) | Q(owner__isnull=True), stock__gt=0)
        .order_by("name")[:80]
    )

    if not qs.exists():
        demo_products = [
            (f"SELFCO-{request.user.id}-COOKIE", "Chocolate Cookies", "99.00", 50),
            (f"SELFCO-{request.user.id}-JUICE", "Orange Juice", "70.00", 50),
            (f"SELFCO-{request.user.id}-COLA", "Coca Cola", "40.00", 50),
            (f"SELFCO-{request.user.id}-CHIPS", "Potato Chips", "20.00", 50),
        ]
        for sku, name, price, stock in demo_products:
            Product.objects.get_or_create(
                sku=sku,
                defaults={
                    "owner": request.user,
                    "name": name,
                    "price": price,
                    "stock": stock,
                    "unit": "pcs",
                },
            )
        qs = (
            Product.objects
            .filter(Q(owner=request.user) | Q(owner__isnull=True), stock__gt=0)
            .order_by("name")[:80]
        )
    
    products = []
    active_media = {
        item.product_id: item
        for item in PromoMedia.objects.filter(owner=request.user, is_active=True).filter(Q(starts_at__isnull=True) | Q(starts_at__lte=timezone.now())).filter(Q(ends_at__isnull=True) | Q(ends_at__gte=timezone.now())).select_related("product")[:50]
    }
    for p in qs:
        image_url = ""
        if p.image:
            try:
                image_url = to_abs(p.image.url)
            except Exception:
                pass
        
        stock = int(getattr(p, "stock", 0) or 0)
        media = active_media.get(p.id)
        badges = []
        if stock <= 2:
            badges.append("Only 2 Left" if stock else "Restocking Soon")
        if p.id in active_media:
            badges.append(media.badge or "Flash Sale")
        if random.randint(1, 100) > 76:
            badges.append("Trending Now")
        product_data = {
            "id": str(p.id),
            "sku": p.sku or "",
            "name": (p.name or "")[:60],
            "category": str(p.category) if p.category else "General",
            "price": str(p.price or "0"),
            "stock": stock,
            "badges": badges[:3],
            "promo_video": media.media_url if media else "",
            "expiry_warning": "Check freshness before billing" if random.randint(1, 100) > 92 else "",
            "image": image_url or "/static/img/billentra-logo.png",
            "is_featured": bool(stock > 0),
        }
        products.append(product_data)
        
        if len(products) >= 60:
            break
    
    return JsonResponse(
        {"ok": True, "products": products, "count": len(products)},
        json_dumps_params={"separators": (",", ":")}
    )
