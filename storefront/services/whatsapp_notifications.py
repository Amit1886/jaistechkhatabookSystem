from __future__ import annotations

from django.conf import settings

def notify_order_placed(*, order):
    """
    Notify customer about a placed order.

    Respects vendor notification toggles (Settings > Notifications).
    """
    customer_mobile = getattr(order.customer, "mobile", "") or ""
    customer_email = getattr(order.customer, "email", "") or ""
    vendor_name = getattr(order.vendor, "name", "Store")
    text = f"New order {order.order_number} placed on {vendor_name}. Total: ₹{order.total_amount}"

    from .vendor_messaging import (
        send_vendor_email,
        send_vendor_sms,
        send_vendor_whatsapp,
        vendor_channel_enabled,
    )

    results = {"whatsapp": None, "sms": None, "email": None}
    ok_any = False

    if vendor_channel_enabled(order.vendor, "whatsapp") and customer_mobile:
        wa = send_vendor_whatsapp(vendor=order.vendor, to=customer_mobile, message=text)
        results["whatsapp"] = {"ok": wa.ok, "provider": wa.provider, "error": wa.error}
        ok_any = ok_any or bool(wa.ok)

    if vendor_channel_enabled(order.vendor, "sms") and customer_mobile:
        sm = send_vendor_sms(vendor=order.vendor, to=customer_mobile, message=text)
        results["sms"] = {"ok": sm.ok, "provider": sm.provider, "error": sm.error}
        ok_any = ok_any or bool(sm.ok)

    if vendor_channel_enabled(order.vendor, "email") and customer_email:
        em = send_vendor_email(vendor=order.vendor, to=customer_email, subject=f"Order placed: {order.order_number}", message=text)
        results["email"] = {"ok": em.ok, "provider": em.provider, "error": em.error}
        ok_any = ok_any or bool(em.ok)

    return {"ok": ok_any, "status": "sent" if ok_any else "skipped", "results": results}


def notify_order_status(*, order, status_label: str):
    """
    Notify customer about an order status update.

    Respects vendor notification toggles (Settings > Notifications).
    """
    customer_mobile = getattr(order.customer, "mobile", "") or ""
    customer_email = getattr(order.customer, "email", "") or ""
    text = f"Order {order.order_number} update: {status_label}"

    from .vendor_messaging import (
        send_vendor_email,
        send_vendor_sms,
        send_vendor_whatsapp,
        vendor_channel_enabled,
    )

    results = {"whatsapp": None, "sms": None, "email": None}
    ok_any = False

    if vendor_channel_enabled(order.vendor, "whatsapp") and customer_mobile:
        wa = send_vendor_whatsapp(vendor=order.vendor, to=customer_mobile, message=text)
        results["whatsapp"] = {"ok": wa.ok, "provider": wa.provider, "error": wa.error}
        ok_any = ok_any or bool(wa.ok)

    if vendor_channel_enabled(order.vendor, "sms") and customer_mobile:
        sm = send_vendor_sms(vendor=order.vendor, to=customer_mobile, message=text)
        results["sms"] = {"ok": sm.ok, "provider": sm.provider, "error": sm.error}
        ok_any = ok_any or bool(sm.ok)

    if vendor_channel_enabled(order.vendor, "email") and customer_email:
        em = send_vendor_email(vendor=order.vendor, to=customer_email, subject=f"Order update: {order.order_number}", message=text)
        results["email"] = {"ok": em.ok, "provider": em.provider, "error": em.error}
        ok_any = ok_any or bool(em.ok)

    return {"ok": ok_any, "status": "sent" if ok_any else "skipped", "results": results}
