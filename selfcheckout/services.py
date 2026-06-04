from __future__ import annotations

import random
import re
import secrets
from decimal import Decimal

from django.db import transaction
from django.db.models import Count, Q, Sum
from django.utils import timezone

from commerce.models import Invoice, Order, OrderItem, Payment, Product
from khataapp.models import Party

from .models import CheckoutCartItem, CheckoutSession, CustomerMembership, CustomerOTPChallenge, KioskDevice, KioskEvent, QueueTicket, SupportRequest

try:
    from khataapp.core_engine.models.loyalty import LoyaltyAccount, LoyaltyLedgerEntry
except Exception:
    LoyaltyAccount = None
    LoyaltyLedgerEntry = None


def money(value) -> Decimal:
    return Decimal(str(value or "0")).quantize(Decimal("0.01"))


def normalize_mobile(value: str) -> str:
    digits = re.sub(r"\D+", "", value or "")
    if len(digits) > 10:
        digits = digits[-10:]
    return digits


def mask_mobile(mobile: str) -> str:
    mobile = normalize_mobile(mobile)
    return f"******{mobile[-4:]}" if len(mobile) >= 4 else mobile


def ensure_membership(*, owner, party: Party, welcome: bool = False) -> CustomerMembership:
    code = f"SC{party.id:06d}"
    membership, _ = CustomerMembership.objects.get_or_create(
        party=party,
        defaults={
            "owner": owner,
            "member_code": code,
            "qr_token": secrets.token_urlsafe(24),
            "welcome_coupon": "WELCOME100" if welcome else "",
        },
    )
    updates = {}
    if membership.owner_id != getattr(owner, "id", None):
        updates["owner"] = owner
    if not membership.member_code:
        updates["member_code"] = code
    if not membership.qr_token:
        updates["qr_token"] = secrets.token_urlsafe(24)
    if welcome and not membership.welcome_coupon:
        updates["welcome_coupon"] = "WELCOME100"
    if updates:
        CustomerMembership.objects.filter(id=membership.id).update(**updates)
        for key, val in updates.items():
            setattr(membership, key, val)
    return membership


def ensure_loyalty(*, owner, party: Party, welcome: bool = False):
    if not LoyaltyAccount:
        return None
    account, _ = LoyaltyAccount.objects.get_or_create(owner=owner, party=party)
    membership = ensure_membership(owner=owner, party=party, welcome=welcome)
    if welcome and not membership.welcome_awarded:
        points = 100
        cashback = Decimal("25.00")
        account.points = int(account.points or 0) + points
        account.cashback_total = money(account.cashback_total + cashback)
        account.save(update_fields=["points", "cashback_total", "updated_at"])
        if LoyaltyLedgerEntry:
            LoyaltyLedgerEntry.objects.create(
                account=account,
                owner=owner,
                source=LoyaltyLedgerEntry.Source.MANUAL,
                points_delta=points,
                cashback_delta=cashback,
                meta={"source": "self_checkout_welcome", "coupon": membership.welcome_coupon or "WELCOME100"},
            )
        membership.welcome_awarded = True
        membership.last_seen_at = timezone.now()
        membership.save(update_fields=["welcome_awarded", "last_seen_at"])
    return account


def customer_orders(party: Party, limit: int = 4) -> list[dict]:
    orders = Order.objects.filter(party=party).prefetch_related("items__product").order_by("-created_at")[:limit]
    return [
        {
            "id": order.id,
            "date": order.created_at.strftime("%d %b"),
            "amount": str(money(order.total_amount())),
            "items": ", ".join([getattr(item.product, "name", item.raw_name or "Item") for item in order.items.all()[:3]]),
        }
        for order in orders
    ]


def favorite_products(*, owner, party: Party, limit: int = 4) -> list[dict]:
    product_ids = (
        OrderItem.objects.filter(order__party=party, product__isnull=False)
        .values("product_id")
        .annotate(total_qty=Sum("qty"), times=Count("id"))
        .order_by("-times", "-total_qty")
        .values_list("product_id", flat=True)[:limit]
    )
    products = Product.objects.filter(id__in=list(product_ids))
    payloads = [product_payload(product) for product in products]
    for payload in payloads:
        payload["reason"] = "Frequent purchase"
    if len(payloads) < limit:
        seen = [p["id"] for p in payloads]
        for product in Product.objects.filter(Q(owner=owner) | Q(owner__isnull=True)).exclude(id__in=seen).order_by("-stock", "name")[: limit - len(payloads)]:
            item = product_payload(product)
            item["reason"] = "Recommended for your profile"
            payloads.append(item)
    return payloads


def customer_profile_payload(*, owner, party: Party | None, session: CheckoutSession | None = None) -> dict:
    if not party:
        return {
            "identified": False,
            "mode": getattr(session, "customer_mode", "unidentified") if session else "unidentified",
            "title": "Identify customer",
            "message": "Choose existing, new, or guest checkout.",
        }
    membership = ensure_membership(owner=owner, party=party)
    loyalty = ensure_loyalty(owner=owner, party=party)
    tier = membership.tier
    points = int(getattr(loyalty, "points", 0) or 0)
    if points >= 3000:
        tier = "Platinum"
    elif points >= 1000:
        tier = "Gold"
    elif getattr(party, "is_premium", False):
        tier = "VIP"
    if tier != membership.tier:
        membership.tier = tier
        membership.save(update_fields=["tier"])
    mode = getattr(session, "customer_mode", "existing") if session else "existing"
    return {
        "identified": True,
        "id": party.id,
        "name": party.name,
        "mobile": party.mobile or "",
        "masked_mobile": mask_mobile(party.mobile),
        "email": party.email or "",
        "mode": mode,
        "is_guest": mode == "guest",
        "is_active": bool(getattr(party, "is_active", True)),
        "category": getattr(party, "customer_category", "") or "Retail",
        "tier": tier,
        "loyalty_points": points,
        "wallet_balance": str(money(membership.wallet_balance)),
        "cashback_total": str(money(getattr(loyalty, "cashback_total", 0) if loyalty else 0)),
        "member_code": membership.member_code,
        "qr_token": membership.qr_token,
        "nfc_uid": membership.nfc_uid or "",
        "welcome_coupon": membership.welcome_coupon,
        "previous_orders": customer_orders(party),
        "favorites": favorite_products(owner=owner, party=party),
        "offers": personalized_offers(owner=owner, party=party, membership=membership, loyalty=loyalty),
        "message": ("Welcome back " + party.name) if mode != "guest" else "Guest checkout ready.",
    }


def personalized_offers(*, owner, party: Party, membership: CustomerMembership, loyalty=None) -> list[dict]:
    points = int(getattr(loyalty, "points", 0) or 0)
    offers = []
    if membership.welcome_coupon:
        offers.append({"code": membership.welcome_coupon, "title": "Welcome coupon unlocked", "saving": "100.00"})
    if points >= 1000:
        offers.append({"code": "VIP-REWARD", "title": "VIP repeat customer reward", "saving": "150.00"})
    if getattr(party, "customer_category", ""):
        offers.append({"code": "SMART-COMBO", "title": f"{party.customer_category} combo suggestion", "saving": "75.00"})
    if not offers:
        offers.append({"code": "LOYALTY25", "title": "Loyalty starter cashback", "saving": "25.00"})
    return offers[:3]


def session_customer_payload(session: CheckoutSession) -> dict:
    return customer_profile_payload(owner=session.owner, party=session.customer, session=session)


def product_payload(product: Product) -> dict:
    image = ""
    try:
        image = product.image.url if getattr(product, "image", None) else ""
    except Exception:
        image = ""
    return {
        "id": product.id,
        "name": product.name,
        "sku": product.sku,
        "barcode": product.sku,
        "price": str(money(product.price)),
        "tax_percent": str(money(getattr(product, "gst_rate", 0))),
        "stock": int(getattr(product, "stock", 0) or 0),
        "image": image or "/static/img/billentra-logo.png",
        "unit": getattr(product, "unit", "") or "pcs",
        "nutrition": {
            "energy": f"{random.randint(80, 260)} kcal",
            "protein": f"{random.randint(1, 12)} g",
            "sugar": f"{random.randint(0, 24)} g",
        },
        "specs": [
            {"label": "Freshness", "value": random.choice(["A+", "Premium", "Verified"])},
            {"label": "Shelf", "value": random.choice(["Aisle 2", "Aisle 5", "Smart Rack"])},
            {"label": "RFID", "value": f"RF-{product.id:05d}"},
        ],
    }


def item_payload(item: CheckoutCartItem) -> dict:
    product = item.product
    base = product_payload(product)
    return {
        **base,
        "item_id": item.id,
        "quantity": str(money(item.quantity)),
        "unit_price": str(money(item.unit_price)),
        "discount": str(money(item.discount)),
        "line_total": str(money(item.line_total)),
        "tax": str(money((item.line_total * (item.tax_percent or Decimal("0.00"))) / Decimal("100"))),
    }


def session_payload(session: CheckoutSession) -> dict:
    items = [item_payload(item) for item in session.items.select_related("product").order_by("id")]
    recommendations = recommend_products(session)
    offers = coupon_suggestions(session)
    return {
        "session_key": str(session.session_key),
        "kiosk_id": session.kiosk_id,
        "status": session.status,
        "items": items,
        "item_count": len(items),
        "quantity_count": str(money(sum((money(item["quantity"]) for item in items), Decimal("0.00")))),
        "subtotal": str(money(session.subtotal)),
        "discount_total": str(money(session.discount_total)),
        "tax_total": str(money(session.tax_total)),
        "total": str(money(session.total)),
        "payment_method": session.payment_method,
        "payment_reference": session.payment_reference,
        "invoice_number": getattr(session.invoice, "number", "") if session.invoice_id else "",
        "applied_coupon": session.applied_coupon,
        "recommendations": recommendations,
        "offers": offers,
        "fraud_flags": session.fraud_flags,
        "assistant": assistant_message(session),
        "customer": session_customer_payload(session),
        "theme": active_theme_payload(session=session),
        "support": support_snapshot(session=session),
        "mobile_continue": mobile_continue_payload(session=session),
    }


def active_theme_payload(*, session: CheckoutSession, requested: str = "") -> dict:
    now = timezone.localtime()
    month_day = now.strftime("%m-%d")
    if requested:
        key = requested
    elif month_day in {"10-20", "10-21", "10-22", "10-23", "10-24", "10-25"}:
        key = "diwali"
    elif month_day in {"03-13", "03-14", "03-15"}:
        key = "holi"
    elif month_day in {"12-24", "12-25"}:
        key = "christmas"
    elif month_day in {"12-31", "01-01"}:
        key = "newyear"
    elif now.hour >= 19 or now.hour < 6:
        key = "dark_neon"
    else:
        key = "light_premium"
    themes = {
        "light_premium": {"label": "Light Premium", "accent": "#14b8a6", "message": "Premium day mode active"},
        "dark_neon": {"label": "Dark Neon", "accent": "#42f8ff", "message": "Night retail mode active"},
        "cyberpunk": {"label": "Cyberpunk", "accent": "#ff4fd8", "message": "Cyberpunk campaign active"},
        "luxury": {"label": "Premium Luxury", "accent": "#ffd166", "message": "Luxury retail mode active"},
        "diwali": {"label": "Diwali", "accent": "#ffd166", "message": "Diwali smart offers unlocked"},
        "holi": {"label": "Holi", "accent": "#ff4fd8", "message": "Holi festive offers unlocked"},
        "christmas": {"label": "Christmas", "accent": "#5dffb1", "message": "Christmas retail mode active"},
        "newyear": {"label": "New Year", "accent": "#42f8ff", "message": "New Year rewards active"},
    }
    return {"key": key, **themes.get(key, themes["dark_neon"])}


def mobile_continue_payload(*, session: CheckoutSession) -> dict:
    return {
        "session_key": str(session.session_key),
        "url": f"/pos/self-checkout/?kiosk={session.kiosk_id}&continue={session.session_key}",
        "label": "Scan to continue on mobile",
    }


def support_snapshot(*, session: CheckoutSession) -> dict:
    req = session.support_requests.filter(status__in=[SupportRequest.Status.OPEN, SupportRequest.Status.ASSIGNED]).order_by("-opened_at").first()
    if not req:
        return {"active": False, "status": "", "request_id": "", "waiting_seconds": 0}
    return {
        "active": True,
        "status": req.status,
        "request_id": req.id,
        "issue_type": req.issue_type,
        "priority": req.priority,
        "waiting_seconds": int((timezone.now() - req.opened_at).total_seconds()),
    }


@transaction.atomic
def create_support_request(*, session: CheckoutSession, issue_type: str = "general_help", priority: str = "normal", notes: str = "") -> dict:
    kiosk, _ = KioskDevice.objects.get_or_create(kiosk_id=session.kiosk_id, defaults={"name": session.kiosk_id})
    existing = session.support_requests.select_for_update().filter(status__in=[SupportRequest.Status.OPEN, SupportRequest.Status.ASSIGNED]).order_by("-opened_at").first()
    if existing:
        req = existing
    else:
        req = SupportRequest.objects.create(
            session=session,
            kiosk=kiosk,
            owner=session.owner,
            issue_type=(issue_type or "general_help")[:60],
            priority=priority if priority in dict(SupportRequest.Priority.choices) else SupportRequest.Priority.NORMAL,
            customer_name=getattr(session.customer, "name", "") if session.customer_id else "",
            notes=notes or "",
        )
    KioskEvent.objects.create(session=session, kiosk=kiosk, event_type=KioskEvent.EventType.SUPPORT, message="Support requested", payload={"request_id": req.id, "issue_type": req.issue_type, "priority": req.priority}, severity=req.priority)
    return {"message": "Staff has been notified.", "support": support_snapshot(session=session)}


@transaction.atomic
def idle_recovery(*, session: CheckoutSession, stage: str = "warning") -> dict:
    stage = (stage or "warning")[:30]
    if stage == "timeout":
        session.ai_context = {**(session.ai_context or {}), "idle_timeout_at": timezone.now().isoformat(), "saved_cart_total": str(session.total)}
        session.status = CheckoutSession.Status.ABANDONED
        session.save(update_fields=["ai_context", "status", "last_activity_at"])
        KioskDevice.objects.filter(kiosk_id=session.kiosk_id).update(current_session=None, status=KioskDevice.Status.ONLINE, last_seen_at=timezone.now())
        KioskEvent.objects.create(session=session, event_type=KioskEvent.EventType.IDLE, message="Idle timeout reset", payload={"stage": stage})
        new_session = CheckoutSession.objects.create(owner=session.owner, kiosk_id=session.kiosk_id)
        return {"message": "Kiosk reset after idle timeout.", "session_key": str(new_session.session_key), "cart": session_payload(new_session)}
    KioskEvent.objects.create(session=session, event_type=KioskEvent.EventType.IDLE, message="Idle warning", payload={"stage": stage})
    return {"message": "Idle warning recorded.", "cart": session_payload(session)}


def assistant_message(session: CheckoutSession) -> str:
    if session.status == CheckoutSession.Status.PAID:
        return "Payment successful. Your receipt and exit QR are ready."
    if not session.customer_verified and session.customer_mode == "unidentified":
        return "Welcome. Identify yourself for rewards, or continue as guest."
    if session.customer_verified and session.customer_id:
        return f"Welcome back {session.customer.name}. Personalized offers are ready."
    count = session.items.count()
    if count == 0:
        return "Welcome to Smart Checkout. Scan an item or say Add Pepsi."
    if session.total > Decimal("0.00"):
        return "Cart updated in real time. I found the best savings for you."
    return "Please scan your next item."


def coupon_suggestions(session: CheckoutSession) -> list[dict]:
    qty = sum((item.quantity for item in session.items.all()), Decimal("0.00"))
    subtotal = sum((item.quantity * item.unit_price for item in session.items.all()), Decimal("0.00"))
    offers = []
    if qty >= 2:
        offers.append({"code": "SMART-B2G1", "title": "Buy 2 smart saver", "saving": str(money(min(subtotal * Decimal("0.05"), Decimal("80")))), "auto": True})
    if subtotal >= Decimal("999"):
        offers.append({"code": "FESTIVAL100", "title": "Festival instant saving", "saving": "100.00", "auto": True})
    if not offers:
        offers.append({"code": "WELCOME25", "title": "Welcome reward", "saving": "25.00", "auto": False})
    return offers


def apply_best_coupon(session: CheckoutSession) -> CheckoutSession:
    items = list(session.items.select_related("product"))
    if not items:
        if session.applied_coupon:
            session.applied_coupon = ""
            session.save(update_fields=["applied_coupon", "last_activity_at"])
        recalculate_session(session)
        return session
    subtotal = sum((item.quantity * item.unit_price for item in items), Decimal("0.00"))
    qty = sum((item.quantity for item in items), Decimal("0.00"))
    best_code = ""
    best_saving = Decimal("0.00")
    if qty >= 2:
        best_code = "SMART-B2G1"
        best_saving = min(subtotal * Decimal("0.05"), Decimal("80.00"))
    if subtotal >= Decimal("999.00") and Decimal("100.00") > best_saving:
        best_code = "FESTIVAL100"
        best_saving = Decimal("100.00")
    if not best_code and subtotal > 0:
        best_code = "WELCOME25"
        best_saving = min(Decimal("25.00"), subtotal)
    if best_code:
        per_item = money(best_saving / Decimal(len(items)))
        remaining = money(best_saving)
        for index, item in enumerate(items):
            discount = remaining if index == len(items) - 1 else min(per_item, remaining)
            item.discount = money(discount)
            item.save(update_fields=["discount"])
            remaining = money(remaining - discount)
        session.applied_coupon = best_code
        session.save(update_fields=["applied_coupon", "last_activity_at"])
        KioskEvent.objects.create(session=session, event_type=KioskEvent.EventType.COUPON, message=f"Auto coupon {best_code} applied", payload={"saving": str(best_saving)})
    recalculate_session(session)
    return session


def recommend_products(session: CheckoutSession, limit: int = 4) -> list[dict]:
    if session.customer_id:
        return favorite_products(owner=session.owner, party=session.customer, limit=limit)
    in_cart = list(session.items.values_list("product_id", flat=True))
    qs = Product.objects.filter(Q(owner=session.owner) | Q(owner__isnull=True)).exclude(id__in=in_cart).order_by("-stock", "name")
    results = []
    for product in qs[:limit]:
        payload = product_payload(product)
        payload["reason"] = random.choice(["Pairs with your cart", "Trending now", "Low wait aisle", "Smart combo"])
        results.append(payload)
    return results


def recalculate_session(session: CheckoutSession) -> CheckoutSession:
    subtotal = Decimal("0.00")
    tax_total = Decimal("0.00")
    discount_total = Decimal("0.00")
    for item in session.items.select_related("product"):
        line_base = item.quantity * item.unit_price
        discount_total += item.discount
        taxable = max(line_base - item.discount, Decimal("0.00"))
        subtotal += taxable
        tax_total += (taxable * (item.tax_percent or Decimal("0.00"))) / Decimal("100")
    session.subtotal = money(subtotal)
    session.discount_total = money(discount_total)
    session.tax_total = money(tax_total)
    session.total = money(session.subtotal + session.tax_total)
    session.save(update_fields=["subtotal", "discount_total", "tax_total", "total", "last_activity_at"])
    return session


def detect_fraud(session: CheckoutSession) -> list[dict]:
    flags = []
    total_qty = sum((item.quantity for item in session.items.all()), Decimal("0.00"))
    if total_qty >= 15 and session.total < Decimal("500.00"):
        flags.append({"code": "LOW_VALUE_HIGH_QTY", "label": "High quantity with unusually low value"})
    recent_scans = KioskEvent.objects.filter(session=session, event_type__in=[KioskEvent.EventType.SCAN, KioskEvent.EventType.RFID], created_at__gte=timezone.now() - timezone.timedelta(seconds=8)).count()
    if recent_scans > 8:
        flags.append({"code": "RAPID_SCAN", "label": "Rapid repeated scans detected"})
    session.fraud_flags = flags
    session.save(update_fields=["fraud_flags", "last_activity_at"])
    return flags


@transaction.atomic
def add_scan(*, session: CheckoutSession, barcode: str = "", product_id=None, quantity=1) -> CheckoutCartItem:
    if session.status not in {CheckoutSession.Status.ACTIVE, CheckoutSession.Status.PAYMENT_PENDING}:
        raise ValueError("Checkout session is not editable.")
    product_qs = Product.objects.select_for_update().filter(Q(owner=session.owner) | Q(owner__isnull=True))
    product = product_qs.filter(id=product_id).first() if product_id else None
    if not product and barcode:
        code = barcode.strip()
        product = product_qs.filter(Q(sku__iexact=code) | Q(name__iexact=code)).first()
    if not product:
        raise ValueError("Product not found.")
    qty = money(quantity)
    if qty <= 0:
        raise ValueError("Quantity must be greater than zero.")
    existing_qty = CheckoutCartItem.objects.filter(session=session, product=product).values_list("quantity", flat=True).first() or Decimal("0.00")
    available = Decimal(str(getattr(product, "stock", 0) or 0))
    if available >= 0 and existing_qty + qty > available:
        raise ValueError(f"Only {available} units available in stock.")
    item, created = CheckoutCartItem.objects.select_for_update().get_or_create(
        session=session,
        product=product,
        defaults={
            "barcode": barcode or product.sku,
            "quantity": qty,
            "unit_price": product.price,
            "tax_percent": getattr(product, "gst_rate", Decimal("0.00")) or Decimal("0.00"),
        },
    )
    if not created:
        item.quantity = money(item.quantity + qty)
        item.save(update_fields=["quantity"])
    recalculate_session(session)
    apply_best_coupon(session)
    KioskEvent.objects.create(session=session, event_type=KioskEvent.EventType.SCAN, message=f"Product scanned: {product.name}", payload={"product_id": product.id, "quantity": str(qty)})
    detect_fraud(session)
    return item


@transaction.atomic
def update_item_quantity(*, session: CheckoutSession, item_id: int, quantity) -> CheckoutCartItem:
    if session.status != CheckoutSession.Status.ACTIVE:
        raise ValueError("Checkout session is not editable.")
    item = CheckoutCartItem.objects.select_for_update().select_related("product").get(session=session, id=item_id)
    qty = money(quantity)
    if qty <= 0:
        item.delete()
        recalculate_session(session)
        apply_best_coupon(session)
        return item
    available = Decimal(str(getattr(item.product, "stock", 0) or 0))
    if available >= 0 and qty > available:
        raise ValueError(f"Only {available} units available in stock.")
    item.quantity = qty
    item.save(update_fields=["quantity"])
    recalculate_session(session)
    apply_best_coupon(session)
    return item


@transaction.atomic
def remove_item(*, session: CheckoutSession, item_id: int) -> None:
    if session.status != CheckoutSession.Status.ACTIVE:
        raise ValueError("Checkout session is not editable.")
    CheckoutCartItem.objects.filter(session=session, id=item_id).delete()
    recalculate_session(session)
    apply_best_coupon(session)


def search_products(*, owner, query: str, limit: int = 12) -> list[dict]:
    query = (query or "").strip()
    qs = Product.objects.filter(Q(owner=owner) | Q(owner__isnull=True)).order_by("name")
    if query:
        qs = qs.filter(Q(name__icontains=query) | Q(sku__icontains=query) | Q(description__icontains=query))
    return [product_payload(product) for product in qs[:limit]]


@transaction.atomic
def send_customer_otp(*, session: CheckoutSession, mobile: str, purpose: str = "existing") -> dict:
    mobile = normalize_mobile(mobile)
    if len(mobile) != 10:
        raise ValueError("Enter a valid 10 digit mobile number.")
    existing = Party.objects.filter(owner=session.owner, party_type="customer", mobile=mobile).order_by("-is_active", "-id").first()
    if existing and not getattr(existing, "is_active", True):
        raise ValueError("This customer profile is inactive. Please contact staff.")
    if purpose == "existing" and not existing:
        purpose = CustomerOTPChallenge.Purpose.ONBOARD
    code = f"{random.randint(100000, 999999)}"
    CustomerOTPChallenge.objects.filter(session=session, mobile=mobile, is_verified=False).update(expires_at=timezone.now())
    challenge = CustomerOTPChallenge.objects.create(
        session=session,
        owner=session.owner,
        mobile=mobile,
        purpose=purpose,
        code=code,
        expires_at=timezone.now() + timezone.timedelta(minutes=5),
    )
    session.ai_context = {**(session.ai_context or {}), "pending_mobile": mobile, "customer_detected": bool(existing)}
    session.save(update_fields=["ai_context", "last_activity_at"])
    KioskEvent.objects.create(session=session, event_type=KioskEvent.EventType.CUSTOMER, message="OTP sent", payload={"mobile": mask_mobile(mobile), "purpose": purpose, "existing": bool(existing)})
    return {
        "challenge_id": challenge.id,
        "mobile": mobile,
        "masked_mobile": mask_mobile(mobile),
        "existing": bool(existing),
        "new_customer_detected": not bool(existing),
        "expires_in": 300,
        "dev_otp": code,
        "message": "OTP sent successfully." if existing else "New customer detected. OTP sent for quick onboarding.",
    }


@transaction.atomic
def verify_customer_otp(*, session: CheckoutSession, mobile: str, otp: str, name: str = "", email: str = "", mode: str = "existing") -> dict:
    mobile = normalize_mobile(mobile)
    otp = (otp or "").strip()
    challenge = (
        CustomerOTPChallenge.objects.select_for_update()
        .filter(session=session, owner=session.owner, mobile=mobile, is_verified=False, expires_at__gte=timezone.now())
        .order_by("-id")
        .first()
    )
    if not challenge:
        raise ValueError("OTP expired. Please request a new OTP.")
    if challenge.attempts >= 5:
        raise ValueError("Too many OTP attempts. Please restart verification.")
    if challenge.code != otp:
        challenge.attempts += 1
        challenge.save(update_fields=["attempts"])
        raise ValueError("Invalid OTP.")
    party = Party.objects.filter(owner=session.owner, party_type="customer", mobile=mobile).order_by("-is_active", "-id").first()
    created = False
    if party and not getattr(party, "is_active", True):
        raise ValueError("This customer profile is inactive. Please contact staff.")
    if not party:
        party = Party.objects.create(
            owner=session.owner,
            party_type="customer",
            mobile=mobile,
            whatsapp_number=mobile,
            sms_number=mobile,
            name=(name or f"Customer {mobile[-4:]}")[:100],
            email=email or "",
            customer_category="Self Checkout",
        )
        created = True
    elif name and (party.name or "").startswith("Customer "):
        party.name = name[:100]
        if email:
            party.email = email
        party.save(update_fields=["name", "email"])
    challenge.is_verified = True
    challenge.verified_at = timezone.now()
    challenge.save(update_fields=["is_verified", "verified_at"])
    session.customer = party
    session.customer_mode = "new" if created or mode == "new" else "existing"
    session.customer_verified = True
    session.customer_verified_at = timezone.now()
    session.save(update_fields=["customer", "customer_mode", "customer_verified", "customer_verified_at", "last_activity_at"])
    membership = ensure_membership(owner=session.owner, party=party, welcome=created)
    membership.last_seen_at = timezone.now()
    membership.save(update_fields=["last_seen_at"])
    ensure_loyalty(owner=session.owner, party=party, welcome=created)
    KioskEvent.objects.create(session=session, event_type=KioskEvent.EventType.CUSTOMER, message="Customer verified", payload={"party_id": party.id, "mode": session.customer_mode, "created": created})
    return {"created": created, "message": "Account created successfully." if created else f"Welcome back {party.name}.", "customer": session_customer_payload(session), "cart": session_payload(session)}


@transaction.atomic
def identify_by_membership(*, session: CheckoutSession, token: str = "", nfc_uid: str = "", face_hash: str = "") -> dict:
    query = Q()
    method = ""
    if face_hash:
        query |= Q(face_hash=face_hash, consent_face=True)
        method = "face"
    if nfc_uid:
        query |= Q(nfc_uid=nfc_uid)
        method = method or "nfc"
    if token:
        query |= Q(qr_token=token) | Q(member_code=token)
        method = method or "qr"
    if not query:
        raise ValueError("Membership credential is required.")
    membership = CustomerMembership.objects.select_related("party").filter(query, owner=session.owner).first()
    if not membership:
        raise ValueError("Membership not found.")
    if membership.is_blocked:
        raise ValueError("Membership is blocked. Please contact staff.")
    party = membership.party
    if not getattr(party, "is_active", True):
        raise ValueError("Customer profile is inactive.")
    session.customer = party
    session.customer_mode = "existing"
    session.customer_verified = True
    session.customer_verified_at = timezone.now()
    session.save(update_fields=["customer", "customer_mode", "customer_verified", "customer_verified_at", "last_activity_at"])
    membership.last_seen_at = timezone.now()
    membership.save(update_fields=["last_seen_at"])
    ensure_loyalty(owner=session.owner, party=party)
    KioskEvent.objects.create(session=session, event_type=KioskEvent.EventType.CUSTOMER, message=f"Customer identified by {method}", payload={"party_id": party.id, "method": method})
    return {"message": f"Welcome back {party.name}.", "method": method, "customer": session_customer_payload(session), "cart": session_payload(session)}


@transaction.atomic
def continue_as_guest(*, session: CheckoutSession) -> dict:
    if session.customer_id and session.customer_mode == "guest":
        return {"message": "Guest checkout ready.", "customer": session_customer_payload(session), "cart": session_payload(session)}
    guest_reference = f"GUEST-{session.session_key.hex[:10].upper()}"
    party = Party.objects.create(
        owner=session.owner,
        party_type="customer",
        name=f"Guest {session.session_key.hex[:6].upper()}",
        mobile="",
        customer_category="Guest Checkout",
    )
    session.customer = party
    session.customer_mode = "guest"
    session.customer_verified = False
    session.guest_reference = guest_reference
    session.save(update_fields=["customer", "customer_mode", "customer_verified", "guest_reference", "last_activity_at"])
    ensure_membership(owner=session.owner, party=party)
    KioskEvent.objects.create(session=session, event_type=KioskEvent.EventType.CUSTOMER, message="Guest checkout started", payload={"guest_reference": guest_reference})
    return {"message": "Guest checkout ready. You can start shopping instantly.", "customer": session_customer_payload(session), "cart": session_payload(session)}


def recover_customer_session(*, owner, mobile: str) -> dict:
    mobile = normalize_mobile(mobile)
    if len(mobile) != 10:
        return {"found": False, "sessions": []}
    party = Party.objects.filter(owner=owner, party_type="customer", mobile=mobile).first()
    if not party:
        return {"found": False, "sessions": []}
    sessions = CheckoutSession.objects.filter(owner=owner, customer=party, status=CheckoutSession.Status.ACTIVE).order_by("-last_activity_at")[:3]
    return {
        "found": True,
        "customer": customer_profile_payload(owner=owner, party=party),
        "sessions": [{"session_key": str(item.session_key), "kiosk_id": item.kiosk_id, "updated": item.last_activity_at.isoformat(), "total": str(item.total)} for item in sessions],
    }


def parse_voice_command(*, session: CheckoutSession, command: str) -> dict:
    raw = (command or "").strip()
    text = raw.lower()
    if not text:
        return {"action": "noop", "message": "Please say a command."}

    KioskEvent.objects.create(session=session, event_type=KioskEvent.EventType.VOICE, message=raw)
    checkout_terms = ["checkout", "pay", "payment", "bill", "bhugtan", "chalo checkout"]
    coupon_terms = ["coupon", "offer", "discount", "kupon"]
    remove_terms = ["remove", "delete", "hatao", "nikalo"]
    repeat_terms = ["repeat last", "repeat item", "last item", "dobara", "phir se"]
    search_terms = ["search", "find", "khojo", "dhundo"]
    if any(term in text for term in checkout_terms):
        return {"action": "checkout", "message": "Opening secure tap and QR checkout."}
    if any(term in text for term in coupon_terms):
        apply_best_coupon(session)
        return {"action": "coupon", "message": "Best coupon applied.", "cart": session_payload(session)}
    if any(term in text for term in repeat_terms):
        last = session.items.order_by("-id").first()
        if last:
            add_scan(session=session, product_id=last.product_id, quantity=1)
            return {"action": "repeat", "message": "Last item repeated.", "cart": session_payload(session)}
        return {"action": "noop", "message": "No last item found."}

    qty_match = re.search(r"(\d+)", text)
    qty = int(qty_match.group(1)) if qty_match else 1
    cleaned = re.sub(r"\b(add|scan|search|find|remove|delete|item|items|please|mujhe|do|two|ek|one)\b", " ", text)
    cleaned = re.sub(r"\d+", " ", cleaned).strip()
    product = None
    if cleaned:
        product = Product.objects.filter(Q(owner=session.owner) | Q(owner__isnull=True)).filter(Q(name__icontains=cleaned) | Q(sku__icontains=cleaned)).first()
    if any(term in text for term in search_terms):
        return {"action": "search", "message": f"Showing results for {cleaned or raw}.", "products": search_products(owner=session.owner, query=cleaned or raw)}
    if any(term in text for term in remove_terms):
        if product:
            item = session.items.filter(product=product).first()
            if item:
                remove_item(session=session, item_id=item.id)
                return {"action": "remove", "message": f"{product.name} removed.", "cart": session_payload(session)}
        return {"action": "noop", "message": "I could not find that item in cart."}
    if product:
        add_scan(session=session, product_id=product.id, quantity=qty)
        return {"action": "add", "message": f"{product.name} added successfully.", "cart": session_payload(session), "product": product_payload(product)}
    return {"action": "noop", "message": "I could not understand the product. Please scan or search it."}


def rfid_detect(*, session: CheckoutSession, tag: str) -> dict:
    code = (tag or "").strip().replace("RF-", "")
    product_id = int(code) if code.isdigit() else None
    item = add_scan(session=session, product_id=product_id, barcode=tag, quantity=1)
    KioskEvent.objects.create(session=session, event_type=KioskEvent.EventType.RFID, message=f"RFID detected: {item.product.name}", payload={"tag": tag})
    return {"message": "RFID item auto detected.", "product": product_payload(item.product), "cart": session_payload(session)}


def kiosk_snapshot(*, owner) -> dict:
    now = timezone.now()
    active_sessions = CheckoutSession.objects.filter(owner=owner, status__in=[CheckoutSession.Status.ACTIVE, CheckoutSession.Status.PAYMENT_PENDING]).count()
    kiosks = list(KioskDevice.objects.all())
    if not kiosks:
        for idx in range(1, 5):
            kiosks.append(KioskDevice.objects.create(kiosk_id=f"KIOSK-{idx}", name=f"Smart Kiosk {idx}"))
    waiting = QueueTicket.objects.filter(owner=owner, status=QueueTicket.Status.WAITING).count()
    available = [k for k in kiosks if k.status == KioskDevice.Status.ONLINE and not k.current_session_id]
    return {
        "active_kiosks": sum(1 for k in kiosks if k.status in {KioskDevice.Status.ONLINE, KioskDevice.Status.BUSY}),
        "waiting_users": waiting,
        "avg_checkout_time": int(sum(k.avg_checkout_seconds for k in kiosks) / max(len(kiosks), 1)),
        "active_sessions": active_sessions,
        "estimated_wait": max(30, waiting * 55 // max(len(available), 1)),
        "kiosks": [
            {
                "kiosk_id": k.kiosk_id,
                "name": k.name or k.kiosk_id,
                "zone": k.zone,
                "status": k.status,
                "scanner": k.scanner_status,
                "printer": k.printer_status,
                "payment": k.payment_status,
                "internet": k.internet_status,
                "camera": k.camera_status,
                "cpu": k.cpu_usage,
                "memory": k.memory_usage,
                "session": str(k.current_session.session_key) if k.current_session_id else "",
                "last_seen": k.last_seen_at.isoformat(),
                "stale": k.last_seen_at < now - timezone.timedelta(minutes=3),
            }
            for k in kiosks
        ],
    }


def assign_queue_ticket(*, owner) -> dict:
    snapshot = kiosk_snapshot(owner=owner)
    kiosk = KioskDevice.objects.filter(status=KioskDevice.Status.ONLINE, current_session__isnull=True).order_by("avg_checkout_seconds", "kiosk_id").first()
    code = f"Q{timezone.now().strftime('%H%M%S')}{random.randint(10, 99)}"
    ticket = QueueTicket.objects.create(
        owner=owner,
        ticket_code=code,
        status=QueueTicket.Status.ASSIGNED if kiosk else QueueTicket.Status.WAITING,
        assigned_kiosk=kiosk,
        assigned_at=timezone.now() if kiosk else None,
        estimated_wait_seconds=snapshot["estimated_wait"],
    )
    return {"ticket": ticket.ticket_code, "status": ticket.status, "assigned_kiosk": getattr(kiosk, "kiosk_id", ""), "estimated_wait": ticket.estimated_wait_seconds}


def health_ping(*, session: CheckoutSession, data: dict) -> dict:
    kiosk, _ = KioskDevice.objects.get_or_create(kiosk_id=session.kiosk_id, defaults={"name": session.kiosk_id})
    kiosk.status = KioskDevice.Status.BUSY if session.status == CheckoutSession.Status.ACTIVE else KioskDevice.Status.ONLINE
    kiosk.current_session = session if session.status == CheckoutSession.Status.ACTIVE else None
    for field in ["scanner_status", "printer_status", "payment_status", "internet_status", "camera_status"]:
        if data.get(field):
            setattr(kiosk, field, str(data[field])[:20])
    kiosk.cpu_usage = int(data.get("cpu_usage") or random.randint(12, 42))
    kiosk.memory_usage = int(data.get("memory_usage") or random.randint(28, 64))
    kiosk.last_seen_at = timezone.now()
    kiosk.diagnostics = data or {}
    kiosk.save()
    KioskEvent.objects.create(session=session, kiosk=kiosk, event_type=KioskEvent.EventType.HEALTH, message="Kiosk health ping", payload=data)
    return kiosk_snapshot(owner=session.owner)


@transaction.atomic
def complete_checkout(*, session: CheckoutSession, payment_method: str, payment_reference: str = "") -> Invoice:
    session = CheckoutSession.objects.select_for_update().select_related("customer").get(id=session.id)
    if session.invoice_id:
        return session.invoice
    if session.total <= 0 or not session.items.exists():
        raise ValueError("Cart is empty.")

    customer = session.customer or Party.objects.filter(owner=session.owner, party_type="customer", name="Self Checkout Customer").first()
    if not customer:
        customer = Party.objects.create(owner=session.owner, party_type="customer", name="Self Checkout Customer")
    items = list(session.items.select_for_update().select_related("product"))
    for item in items:
        product = Product.objects.select_for_update().get(id=item.product_id)
        available = Decimal(str(getattr(product, "stock", 0) or 0))
        if available >= 0 and item.quantity > available:
            raise ValueError(f"Stock changed for {product.name}. Available: {available}.")

    order = Order.objects.create(
        owner=session.owner,
        party=customer,
        placed_by="party",
        status="completed",
        order_type="SALE",
        order_source=f"SelfCheckout:{session.kiosk_id}",
        notes=f"Self checkout session {session.session_key}",
    )
    for item in items:
        OrderItem.objects.create(order=order, product=item.product, qty=int(item.quantity), price=item.unit_price, tax_percent=item.tax_percent)
        if getattr(item.product, "stock", None) is not None:
            new_stock = max(int(item.product.stock or 0) - int(item.quantity), 0)
            Product.objects.filter(id=item.product_id).update(stock=new_stock)
    order.tax_percent = max([item.tax_percent for item in items] or [Decimal("0.00")])
    order.save()
    order.discount_type = "flat" if session.discount_total else "none"
    order.discount_value = session.discount_total
    order.discount_amount = session.discount_total
    order.tax_amount = session.tax_total
    order.save()
    invoice = Invoice.objects.create(order=order, gst_type="GST" if order.tax_percent > 0 else "NON_GST", amount=session.total, status="paid")
    reference = payment_reference or f"SELF-{session.session_key}"
    Payment.objects.get_or_create(
        invoice=invoice,
        amount=invoice.amount,
        reference=reference,
        defaults={"method": payment_method, "note": "Self checkout kiosk payment"},
    )
    session.invoice = invoice
    session.status = CheckoutSession.Status.PAID
    session.payment_method = payment_method
    session.payment_reference = payment_reference or ""
    session.completed_at = timezone.now()
    session.save(update_fields=["invoice", "status", "payment_method", "payment_reference", "completed_at", "last_activity_at"])
    KioskDevice.objects.filter(kiosk_id=session.kiosk_id).update(status=KioskDevice.Status.ONLINE, current_session=None, last_seen_at=timezone.now())
    KioskEvent.objects.create(session=session, event_type=KioskEvent.EventType.PAYMENT, message="Payment received", payload={"method": payment_method, "invoice": invoice.number})
    if session.customer_id and session.customer_mode != "guest":
        loyalty = ensure_loyalty(owner=session.owner, party=session.customer)
        if loyalty:
            points = max(int(session.total // Decimal("50.00")), 1)
            loyalty.points = int(loyalty.points or 0) + points
            loyalty.save(update_fields=["points", "updated_at"])
            if LoyaltyLedgerEntry:
                LoyaltyLedgerEntry.objects.create(account=loyalty, owner=session.owner, source=LoyaltyLedgerEntry.Source.INVOICE, points_delta=points, meta={"invoice": invoice.number, "session": str(session.session_key)})
    return invoice
