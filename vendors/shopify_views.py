from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.urls import reverse

from vendors.models import Vendor, VendorShopifyConnection


@login_required
def shopify_oauth_callback(request: HttpRequest) -> HttpResponse:
    """
    OAuth callback endpoint registered in Shopify Dev Dashboard.
    """
    from vendors.services.shopify_oauth import (
        exchange_code_for_access_token,
        get_shopify_client_id,
        is_valid_shop_domain,
        normalize_shop_domain,
        unsign_oauth_state,
        verify_shopify_hmac,
    )

    if not get_shopify_client_id():
        messages.error(request, "Shopify is not configured by admin yet.")
        return redirect("/")

    qp = {k: (request.GET.get(k) or "") for k in request.GET.keys()}
    shop = normalize_shop_domain(qp.get("shop") or "")
    code = (qp.get("code") or "").strip()
    state = (qp.get("state") or "").strip()

    if not shop or not code or not state:
        messages.error(request, "Missing Shopify OAuth parameters.")
        return redirect("/")

    if not is_valid_shop_domain(shop):
        messages.error(request, "Invalid shop domain.")
        return redirect("/")

    if not verify_shopify_hmac(qp):
        messages.error(request, "Invalid Shopify HMAC signature.")
        return redirect("/")

    state_obj = unsign_oauth_state(state)
    if not state_obj:
        messages.error(request, "OAuth state expired or invalid. Please try again.")
        return redirect("/")

    vendor_id = state_obj.get("vendor_id")
    subdomain = state_obj.get("subdomain")
    user_id = state_obj.get("user_id")
    if user_id and int(user_id) != int(request.user.id):
        messages.error(request, "OAuth user mismatch. Please retry from the vendor dashboard.")
        return redirect("/")

    vendor = Vendor.objects.filter(id=vendor_id, subdomain=subdomain, is_active=True).first()
    if not vendor:
        messages.error(request, "Vendor not found.")
        return redirect("/")

    try:
        token_data = exchange_code_for_access_token(shop_domain=shop, code=code)
        access_token = (token_data.get("access_token") or "").strip()
        scope = (token_data.get("scope") or "").strip()
        if not access_token:
            messages.error(request, "Failed to obtain Shopify access token.")
            return redirect(reverse("vendor-settings-apps", kwargs={"subdomain": vendor.subdomain}))

        VendorShopifyConnection.objects.update_or_create(
            vendor=vendor,
            defaults={
                "shop_domain": shop,
                "access_token": access_token,
                "scope": scope,
                "is_active": True,
                "last_error": "",
            },
        )
        messages.success(request, f"Shopify connected: {shop}")
    except Exception as exc:
        VendorShopifyConnection.objects.update_or_create(
            vendor=vendor,
            defaults={"shop_domain": shop, "is_active": False, "last_error": str(exc)[:255]},
        )
        messages.error(request, f"Shopify connect failed: {exc}")

    return redirect(reverse("vendor-settings-apps", kwargs={"subdomain": vendor.subdomain}))

