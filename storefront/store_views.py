from __future__ import annotations

import csv
from datetime import timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db import transaction
from django.db.models import Count, F, IntegerField, Max, Q, Sum
from django.db.models.expressions import ExpressionWrapper
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.http import require_GET, require_POST
from django.core.paginator import Paginator
from django.db.models.functions import Coalesce, TruncDate

from products.models import Category, Product, ProductMedia, WarehouseInventory
from vendors.models import (
    Vendor,
    VendorMembership,
    VendorMarketingProviderConfig,
    VendorPaymentGatewayConfig,
    VendorShippingProviderConfig,
    VendorStoreSettings,
    VendorShopifyConnection,
)

from .forms import CheckoutForm, VendorProductListingForm
from .models import (
    CustomerAddress,
    CustomerProfile,
    StoreOrder,
    StoreOrderItem,
    StoreOrderStatusEvent,
    StorePaymentAttempt,
    StoreShipment,
    VendorProductListing,
    VendorCoupon,
)
from .services.access import can_manage_vendor, ensure_vendor_access
from .services.commerce_sync import ensure_commerce_order_for_store_order
from .services.promotions import available_coupons_for_vendor, quote_coupon
from .services.session_cart import (
    add_item,
    build_cart_view,
    clear_vendor_cart,
    clear_vendor_coupon,
    set_qty,
    set_vendor_coupon_code,
)
from .services.session_wishlist import build_wishlist_view, get_vendor_wishlist_ids, toggle as toggle_wishlist


User = get_user_model()


def _can_access_billing_dashboard(user) -> bool:
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False) or getattr(user, "is_staff", False):
        return True
    try:
        return user.groups.filter(name__in=["Super Admin", "Admin", "Agent", "User"]).exists()
    except Exception:
        return False


def _resolve_vendor_from_path(subdomain: str) -> Vendor:
    v = Vendor.objects.filter(subdomain=(subdomain or "").strip().lower(), is_active=True).first()
    if not v:
        raise Http404("Vendor not found")
    return v


def _vendor_admin_context(*, request, vendor: Vendor, page: str, breadcrumb: str):
    return {
        "vendor": vendor,
        "vendor_admin_mode": True,
        "vendor_admin_page": page,
        "vendor_admin_breadcrumb": breadcrumb,
        "can_access_billing": _can_access_billing_dashboard(request.user),
    }


@require_GET
def store_index(request):
    """
    Public entry for non-subdomain browsing:
    - Shows vendors list.
    """
    vendors = Vendor.objects.filter(is_active=True).order_by("name")[:50]
    return render(
        request,
        "storefront/store_index.html",
        {"vendors": vendors, "can_access_billing": _can_access_billing_dashboard(request.user), "hide_sidebar": True},
    )


@require_GET
def store_home(request, subdomain: str):
    vendor = _resolve_vendor_from_path(subdomain)
    qs = VendorProductListing.objects.select_related("product", "product__category").filter(vendor=vendor, is_online=True)

    # B2B-only visibility: hide for guests and B2C users.
    store_type = (getattr(request.user, "store_type", "") or "").strip().lower() if getattr(request, "user", None) else ""
    is_b2b_user = store_type in {"b2b", "hybrid"} and store_type != "b2c"
    if not (getattr(request.user, "is_authenticated", False) and is_b2b_user):
        qs = qs.filter(Q(product__is_b2b_only=False) | Q(product__is_b2b_only__isnull=True))

    # Catalog (Shopify-like) filtering + pricing adjustment.
    active_catalog = None
    try:
        from vendors.services.catalogs import apply_catalog_filter, resolve_active_catalog

        active_catalog = resolve_active_catalog(vendor=vendor, catalog_id=request.GET.get("catalog"))
        qs = apply_catalog_filter(qs, catalog=active_catalog)
    except Exception:
        active_catalog = None

    price_expr = Coalesce("price_override", "product__b2c_price")
    qs = qs.annotate(effective_price_db=price_expr)
    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(
            Q(product__name__icontains=q)
            | Q(title__icontains=q)
            | Q(product__description__icontains=q)
            | Q(description__icontains=q)
        )

    cat_list = request.GET.getlist("category")
    if not cat_list:
        raw_cat = (request.GET.get("category") or "").strip()
        if raw_cat:
            cat_list = [c.strip() for c in raw_cat.split(",") if c.strip()]
    cat_list = [c.strip().lower() for c in cat_list if (c or "").strip()]
    if cat_list:
        qs = qs.filter(product__category__slug__in=cat_list)
    min_price = (request.GET.get("min_price") or "").strip()
    max_price = (request.GET.get("max_price") or "").strip()
    if min_price:
        try:
            qs = qs.filter(effective_price_db__gte=Decimal(min_price))
        except Exception:
            qs = qs.filter(effective_price_db__gte=min_price)
    if max_price:
        try:
            qs = qs.filter(effective_price_db__lte=Decimal(max_price))
        except Exception:
            qs = qs.filter(effective_price_db__lte=max_price)

    tag = (request.GET.get("tag") or "").strip().lower()
    if tag == "discount":
        qs = qs.filter(product__mrp__gt=F("effective_price_db"))
    elif tag == "trending":
        qs = qs.filter(Q(is_featured=True) | Q(product__fast_moving=True))
    elif tag == "top_rated":
        qs = qs.filter(rating_avg__gt=0)

    sort = (request.GET.get("sort") or "").strip().lower()
    if sort == "price_asc":
        qs = qs.order_by(F("effective_price_db").asc(nulls_last=True), "-updated_at")
    elif sort == "price_desc":
        qs = qs.order_by(F("effective_price_db").desc(nulls_last=True), "-updated_at")
    elif sort == "rating":
        qs = qs.order_by(Coalesce("rating_avg", 0).desc(), "-rating_count", "-updated_at")
    elif sort == "newest":
        qs = qs.order_by("-updated_at", "-id")
    else:
        qs = qs.order_by("-is_featured", "-updated_at")

    total_filtered = qs.count()
    paginator = Paginator(qs, 24)
    page_obj = paginator.get_page(request.GET.get("page") or 1)
    listings = list(page_obj.object_list)

    # Categories (with counts from online listings)
    categories = (
        Category.objects.filter(products__vendor_listings__vendor=vendor, products__vendor_listings__is_online=True)
        .annotate(
            product_count=Count(
                "products__vendor_listings",
                filter=Q(products__vendor_listings__vendor=vendor, products__vendor_listings__is_online=True),
                distinct=True,
            )
        )
        .distinct()
        .order_by("name")
    )
    cart_view = build_cart_view(vendor=vendor, session=request.session, user=(request.user if request.user.is_authenticated else None))
    wishlist_ids = get_vendor_wishlist_ids(request.session, vendor.id)
    wishlist_view = build_wishlist_view(vendor=vendor, session=request.session)

    # Build querystring for pagination links (exclude page).
    _qp = request.GET.copy()
    _qp.pop("page", None)
    base_qs = _qp.urlencode()

    # Attach computed UI helpers (no DB write).
    for l in listings:
        try:
            if is_b2b_user:
                from saas.utils.pricing import quote_price

                p = l.product
                moq = int(getattr(p, "moq", 1) or 1)
                qv = quote_price(
                    base_b2c_price=Decimal(str(getattr(p, "b2c_price", "0") or "0")),
                    base_b2b_price=Decimal(str(getattr(p, "b2b_price", "0") or "0")),
                    qty=max(1, moq),
                    moq=moq,
                    is_b2b_only=bool(getattr(p, "is_b2b_only", False)),
                    user_store_type=store_type,
                    bulk_price=Decimal(str(getattr(p, "bulk_price", "0") or "0")) if getattr(p, "bulk_price", None) is not None else None,
                    bulk_qty=int(getattr(p, "bulk_qty", 0) or 0),
                    mrp=Decimal(str(getattr(p, "mrp", "0") or "0")),
                )
                l.display_price = Decimal(str(l.price_override or qv.unit_price or "0"))
            else:
                l.display_price = Decimal(str(l.effective_price or "0"))
        except Exception:
            l.display_price = Decimal("0.00")
        try:
            from vendors.services.catalogs import apply_price_adjustment

            l.display_price = apply_price_adjustment(price=Decimal(str(l.display_price or "0")), catalog=active_catalog)
        except Exception:
            pass
        try:
            mrp = Decimal(str(getattr(l.product, "mrp", "0") or "0"))
            if mrp > 0 and mrp > l.display_price:
                l.discount_percent = int(
                    (((mrp - l.display_price) / mrp) * Decimal("100")).quantize(Decimal("1"))
                )
            else:
                l.discount_percent = 0
        except Exception:
            l.discount_percent = 0
    return render(
        request,
        "storefront/store_home.html",
        {
            "vendor": vendor,
            "active_catalog": active_catalog,
            "listings": listings,
            "cart": cart_view,
            "wishlist": wishlist_view,
            "wishlist_ids": wishlist_ids,
            "can_manage_vendor": can_manage_vendor(user=request.user, vendor=vendor),
            "can_access_billing": _can_access_billing_dashboard(request.user),
            "categories": categories,
            "active_categories": cat_list,
            "active_tag": tag,
            "active_sort": sort,
            "page_obj": page_obj,
            "base_qs": base_qs,
            "total_filtered": total_filtered,
            "hide_sidebar": True,
        },
    )


@require_GET
def store_product_detail(request, subdomain: str, slug: str):
    vendor = _resolve_vendor_from_path(subdomain)
    raw = (slug or "").strip()

    qs = Product.objects.select_related("category").prefetch_related("media")
    product = qs.filter(slug__iexact=raw).first()
    if not product:
        product = qs.filter(sku__iexact=raw).first()
    if not product and raw.isdigit():
        product = qs.filter(id=int(raw)).first()
    if not product:
        guessed = slugify(raw)
        if guessed and guessed != raw:
            product = qs.filter(slug__iexact=guessed).first()
    if not product:
        raise Http404("Product not found")

    store_type = (getattr(request.user, "store_type", "") or "").strip().lower() if getattr(request, "user", None) else ""
    is_b2b_user = store_type in {"b2b", "hybrid"} and store_type != "b2c"
    if getattr(product, "is_b2b_only", False) and not (getattr(request.user, "is_authenticated", False) and is_b2b_user):
        raise Http404("Product not available in this store")

    # Listing controls public visibility per vendor store.
    listing = VendorProductListing.objects.filter(vendor=vendor, product=product, is_online=True).first()
    if not listing and not getattr(product, "is_online", False):
        raise Http404("Product not available in this store")

    # Enforce active catalog restrictions if configured.
    active_catalog = None
    try:
        from vendors.services.catalogs import apply_catalog_filter, resolve_active_catalog

        active_catalog = resolve_active_catalog(vendor=vendor, catalog_id=request.GET.get("catalog"))
        if listing and active_catalog:
            check_qs = apply_catalog_filter(VendorProductListing.objects.filter(id=listing.id), catalog=active_catalog)
            if not check_qs.exists():
                raise Http404("Product not available in this catalog")
    except Http404:
        raise
    except Exception:
        active_catalog = None

    # If user hit via SKU/id or a non-canonical slug, redirect to canonical slug URL.
    if product.slug and raw.lower() != str(product.slug).lower():
        return redirect(reverse("store-product-detail", kwargs={"subdomain": vendor.subdomain, "slug": product.slug}))
    if listing:
        try:
            if is_b2b_user:
                from saas.utils.pricing import quote_price

                moq = int(getattr(product, "moq", 1) or 1)
                qv = quote_price(
                    base_b2c_price=Decimal(str(getattr(product, "b2c_price", "0") or "0")),
                    base_b2b_price=Decimal(str(getattr(product, "b2b_price", "0") or "0")),
                    qty=max(1, moq),
                    moq=moq,
                    is_b2b_only=bool(getattr(product, "is_b2b_only", False)),
                    user_store_type=store_type,
                    bulk_price=Decimal(str(getattr(product, "bulk_price", "0") or "0")) if getattr(product, "bulk_price", None) is not None else None,
                    bulk_qty=int(getattr(product, "bulk_qty", 0) or 0),
                    mrp=Decimal(str(getattr(product, "mrp", "0") or "0")),
                )
                listing.display_price = Decimal(str(listing.price_override or qv.unit_price or "0"))
            else:
                listing.display_price = Decimal(str(listing.effective_price or "0"))
        except Exception:
            listing.display_price = Decimal("0.00")
        try:
            from vendors.services.catalogs import apply_price_adjustment

            listing.display_price = apply_price_adjustment(price=Decimal(str(listing.display_price or "0")), catalog=active_catalog)
        except Exception:
            pass
        try:
            mrp = Decimal(str(getattr(listing.product, "mrp", "0") or "0"))
            if mrp > 0 and mrp > listing.display_price:
                listing.discount_percent = int(
                    (((mrp - listing.display_price) / mrp) * Decimal("100")).quantize(Decimal("1"))
                )
            else:
                listing.discount_percent = 0
        except Exception:
            listing.discount_percent = 0

    similar = []
    if getattr(product, "category_id", None):
        sim_qs = (
            VendorProductListing.objects.select_related("product", "product__category")
            .prefetch_related("product__media")
            .filter(vendor=vendor, is_online=True, product__category_id=product.category_id)
            .exclude(product_id=product.id)
        )
        try:
            from vendors.services.catalogs import apply_catalog_filter

            sim_qs = apply_catalog_filter(sim_qs, catalog=active_catalog)
        except Exception:
            pass
        similar = list(sim_qs.order_by("-is_featured", "-updated_at")[:8])
        for s in similar:
            try:
                s.display_price = Decimal(str(s.effective_price or "0"))
            except Exception:
                s.display_price = Decimal("0.00")
            try:
                from vendors.services.catalogs import apply_price_adjustment

                s.display_price = apply_price_adjustment(price=Decimal(str(s.display_price or "0")), catalog=active_catalog)
            except Exception:
                pass

    sold_by = {
        "name": vendor.name,
        "products_online": VendorProductListing.objects.filter(vendor=vendor, is_online=True).count(),
        "orders_total": StoreOrder.objects.filter(vendor=vendor).count(),
        "rating": float(listing.rating_avg) if (listing and listing.rating_avg) else 4.4,
        "ratings_count": int(listing.rating_count) if (listing and listing.rating_count) else 0,
    }
    media_list = list(product.media.all())
    hero_media = next((m for m in media_list if m.media_type == "image"), None) or (media_list[0] if media_list else None)
    cart_view = build_cart_view(vendor=vendor, session=request.session, user=(request.user if request.user.is_authenticated else None))
    wishlist_ids = get_vendor_wishlist_ids(request.session, vendor.id)
    wishlist_view = build_wishlist_view(vendor=vendor, session=request.session)
    return render(
        request,
        "storefront/store_product_detail.html",
        {
            "vendor": vendor,
            "active_catalog": active_catalog,
            "product": product,
            "listing": listing,
            "similar_listings": similar,
            "sold_by": sold_by,
            "media_list": media_list,
            "hero_media": hero_media,
            "cart": cart_view,
            "wishlist": wishlist_view,
            "wishlist_ids": wishlist_ids,
            "can_manage_vendor": can_manage_vendor(user=request.user, vendor=vendor),
            "can_access_billing": _can_access_billing_dashboard(request.user),
            "hide_sidebar": True,
        },
    )


@require_POST
def store_cart_add(request, subdomain: str):
    vendor = _resolve_vendor_from_path(subdomain)
    listing_id = int(request.POST.get("listing_id") or 0)
    qty = int(request.POST.get("qty") or 1)
    listing = get_object_or_404(VendorProductListing, vendor=vendor, id=listing_id, is_online=True)

    # B2B/B2C guardrails (backend-only)
    store_type = (getattr(request.user, "store_type", "") or "").strip().lower() if getattr(request, "user", None) else ""
    is_b2b_user = getattr(request.user, "is_authenticated", False) and store_type in {"b2b", "hybrid"} and store_type != "b2c"
    if getattr(listing.product, "is_b2b_only", False) and not is_b2b_user:
        raise Http404("Product not available")
    if is_b2b_user:
        moq = int(getattr(listing.product, "moq", 1) or 1)
        qty = max(qty, moq)

    add_item(request.session, vendor_id=vendor.id, listing_id=listing.id, qty=qty)
    messages.success(request, "Added to cart.")
    return redirect(request.META.get("HTTP_REFERER") or reverse("store-home", kwargs={"subdomain": vendor.subdomain}))


@require_POST
def store_buy_now(request, subdomain: str):
    """
    "Buy now" creates a single-item cart for the vendor and sends user to checkout.
    This avoids the empty-cart redirect on `/checkout/`.
    """
    vendor = _resolve_vendor_from_path(subdomain)
    listing_id = int(request.POST.get("listing_id") or 0)
    qty = int(request.POST.get("qty") or 1)
    listing = get_object_or_404(VendorProductListing, vendor=vendor, id=listing_id, is_online=True)

    store_type = (getattr(request.user, "store_type", "") or "").strip().lower() if getattr(request, "user", None) else ""
    is_b2b_user = getattr(request.user, "is_authenticated", False) and store_type in {"b2b", "hybrid"} and store_type != "b2c"
    if getattr(listing.product, "is_b2b_only", False) and not is_b2b_user:
        raise Http404("Product not available")
    if is_b2b_user:
        moq = int(getattr(listing.product, "moq", 1) or 1)
        qty = max(qty, moq)

    # Replace vendor cart with this one item (expected Buy Now behavior).
    clear_vendor_cart(request.session, vendor_id=vendor.id)
    add_item(request.session, vendor_id=vendor.id, listing_id=listing.id, qty=max(1, qty))
    messages.success(request, "Ready to checkout.")
    return redirect(reverse("store-checkout", kwargs={"subdomain": vendor.subdomain}))


@require_POST
def store_cart_update(request, subdomain: str):
    vendor = _resolve_vendor_from_path(subdomain)
    listing_id = int(request.POST.get("listing_id") or 0)
    qty = int(request.POST.get("qty") or 0)

    listing = VendorProductListing.objects.select_related("product").filter(vendor=vendor, id=listing_id).first()
    if listing:
        store_type = (getattr(request.user, "store_type", "") or "").strip().lower() if getattr(request, "user", None) else ""
        is_b2b_user = getattr(request.user, "is_authenticated", False) and store_type in {"b2b", "hybrid"} and store_type != "b2c"
        if getattr(listing.product, "is_b2b_only", False) and not is_b2b_user:
            qty = 0
        if is_b2b_user and qty > 0:
            moq = int(getattr(listing.product, "moq", 1) or 1)
            qty = max(qty, moq)

    set_qty(request.session, vendor_id=vendor.id, listing_id=listing_id, qty=qty)
    return redirect(reverse("store-cart", kwargs={"subdomain": vendor.subdomain}))


@require_GET
def store_cart_view(request, subdomain: str):
    vendor = _resolve_vendor_from_path(subdomain)
    cart_view = build_cart_view(vendor=vendor, session=request.session, user=(request.user if request.user.is_authenticated else None))
    coupon_quote_obj = None
    if cart_view.get("coupon_code"):
        coupon_quote_obj, _ = quote_coupon(
            vendor=vendor,
            code=cart_view["coupon_code"],
            user=request.user if getattr(request, "user", None) and request.user.is_authenticated else None,
            subtotal=cart_view["subtotal"],
        )
        if not coupon_quote_obj:
            clear_vendor_coupon(request.session, vendor_id=vendor.id)
            cart_view["coupon_code"] = ""
    discount = coupon_quote_obj.discount_amount if coupon_quote_obj else Decimal("0.00")
    cart_view["discount"] = discount
    cart_view["total"] = (Decimal(str(cart_view["subtotal"])) - discount).quantize(Decimal("0.01"))
    cart_view["coupon"] = coupon_quote_obj.coupon if coupon_quote_obj else None
    cart_view["available_coupons"] = available_coupons_for_vendor(vendor=vendor)
    wishlist_view = build_wishlist_view(vendor=vendor, session=request.session)
    return render(
        request,
        "storefront/store_cart.html",
        {
            "vendor": vendor,
            "cart": cart_view,
            "wishlist": wishlist_view,
            "can_manage_vendor": can_manage_vendor(user=request.user, vendor=vendor),
            "can_access_billing": _can_access_billing_dashboard(request.user),
            "hide_sidebar": True,
        },
    )


@require_POST
def store_coupon_apply(request, subdomain: str):
    vendor = _resolve_vendor_from_path(subdomain)
    cart_view = build_cart_view(vendor=vendor, session=request.session, user=(request.user if request.user.is_authenticated else None))
    code = (request.POST.get("code") or request.POST.get("coupon_code") or "").strip().upper()
    quote, err = quote_coupon(
        vendor=vendor,
        code=code,
        user=request.user if getattr(request, "user", None) and request.user.is_authenticated else None,
        subtotal=cart_view["subtotal"],
    )
    if quote:
        set_vendor_coupon_code(request.session, vendor_id=vendor.id, code=quote.coupon.code)
        messages.success(request, f"Coupon applied: {quote.coupon.code} (₹{quote.discount_amount} OFF)")
    else:
        clear_vendor_coupon(request.session, vendor_id=vendor.id)
        if err == "min_order_not_met":
            messages.error(request, "Coupon requires a higher cart total.")
        else:
            messages.error(request, "Invalid coupon code.")
    return redirect(reverse("store-cart", kwargs={"subdomain": vendor.subdomain}))


@require_POST
def store_coupon_clear(request, subdomain: str):
    vendor = _resolve_vendor_from_path(subdomain)
    clear_vendor_coupon(request.session, vendor_id=vendor.id)
    messages.info(request, "Coupon removed.")
    return redirect(reverse("store-cart", kwargs={"subdomain": vendor.subdomain}))


def _get_or_create_customer(*, email: str, mobile: str, full_name: str):
    email = (email or "").strip().lower()
    mobile = "".join([c for c in (mobile or "") if c.isdigit()]).strip()
    full_name = (full_name or "").strip()
    user = User.objects.filter(email__iexact=email).first()
    if not user:
        username = slugify(email.split("@")[0])[:30] or "customer"
        user = User.objects.create(
            email=email,
            username=username,
            mobile=mobile or None,
            is_active=True,
            store_type="b2c",
            primary_role="customer",
        )
        user.set_unusable_password()
        user.save(update_fields=["password"])
    profile, _ = CustomerProfile.objects.get_or_create(user=user, defaults={"full_name": full_name})
    if full_name and not profile.full_name:
        profile.full_name = full_name
        profile.save(update_fields=["full_name"])
    return user, profile


@transaction.atomic
def _create_order_from_cart(
    *,
    vendor: Vendor,
    customer_user,
    address_obj: CustomerAddress,
    cart_view: dict,
    coupon_quote=None,
    referrer_code: str = "",
) -> StoreOrder:
    order = StoreOrder.objects.create(vendor=vendor, customer=customer_user, address=address_obj)
    for row in cart_view["rows"]:
        listing = row["listing"]
        StoreOrderItem.objects.create(
            order=order,
            listing=listing,
            product=listing.product,
            qty=int(row["qty"]),
            unit_price=Decimal(str(row["unit_price"])),
        )
    if coupon_quote:
        order.applied_coupon = coupon_quote.coupon
        order.discount_amount = Decimal(str(coupon_quote.discount_amount or "0")).quantize(Decimal("0.01"))
    if referrer_code:
        order.referrer_code = (referrer_code or "").strip().upper()[:24]
    order.recalc_totals(save=True)
    StoreOrderStatusEvent.objects.create(order=order, status=order.status, note="Order placed (storefront)")
    # Centralize in billing (commerce) so all orders show up under `/commerce/orders/sales/`.
    try:
        co = ensure_commerce_order_for_store_order(store_order=order)
        if coupon_quote:
            from commerce.models import CouponUsage

            CouponUsage.objects.get_or_create(
                coupon=coupon_quote.coupon,
                user=customer_user,
                order=co,
                defaults={"discount_amount": order.discount_amount},
            )
    except Exception:
        # Never block checkout on billing sync issues.
        pass

    # Referral rewards (demo): credit both once per order.
    try:
        if order.referrer_code and not order.referral_reward_processed:
            ref_user = User.objects.filter(referral_code__iexact=order.referrer_code).first()
            if ref_user and ref_user.id != customer_user.id:
                from wallet.services import credit

                bonus = Decimal("25.00")
                credit(customer_user, bonus, source="referral_bonus", reference=order.order_number)
                credit(ref_user, bonus, source="referral_bonus", reference=order.order_number)
                order.referral_reward_processed = True
                order.save(update_fields=["referral_reward_processed", "updated_at"])
    except Exception:
        pass
    return order


def store_checkout(request, subdomain: str):
    vendor = _resolve_vendor_from_path(subdomain)
    cart_view = build_cart_view(vendor=vendor, session=request.session, user=(request.user if request.user.is_authenticated else None))
    if not cart_view["rows"]:
        messages.error(request, "Your cart is empty.")
        return redirect(reverse("store-home", kwargs={"subdomain": vendor.subdomain}))

    # Best-effort totals for summary (guest quote).
    active_coupon_quote = None
    if cart_view.get("coupon_code"):
        active_coupon_quote, _ = quote_coupon(
            vendor=vendor,
            code=cart_view["coupon_code"],
            user=request.user if getattr(request, "user", None) and request.user.is_authenticated else None,
            subtotal=cart_view["subtotal"],
        )
        if not active_coupon_quote:
            clear_vendor_coupon(request.session, vendor_id=vendor.id)
            cart_view["coupon_code"] = ""
    active_discount = active_coupon_quote.discount_amount if active_coupon_quote else Decimal("0.00")
    cart_view["discount"] = active_discount
    cart_view["total"] = (Decimal(str(cart_view["subtotal"])) - active_discount).quantize(Decimal("0.01"))

    if request.method == "POST":
        form = CheckoutForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            customer_user, profile = _get_or_create_customer(
                email=data["email"], mobile=data.get("mobile") or "", full_name=data["full_name"]
            )
            ref_code = (data.get("referrer_code") or "").strip().upper()
            if ref_code and not getattr(customer_user, "referred_by_id", None):
                referrer = User.objects.filter(referral_code__iexact=ref_code).first()
                if referrer and referrer.id != customer_user.id:
                    customer_user.referred_by = referrer
                    customer_user.save(update_fields=["referred_by"])

            # Re-quote coupon with user (per-user limits) and allow entering code at checkout.
            code = (data.get("coupon_code") or cart_view.get("coupon_code") or "").strip().upper()
            if code:
                set_vendor_coupon_code(request.session, vendor_id=vendor.id, code=code)
            local_quote = None
            if code:
                local_quote, _ = quote_coupon(vendor=vendor, code=code, user=customer_user, subtotal=cart_view["subtotal"])
            addr = CustomerAddress.objects.create(
                profile=profile,
                label="Home",
                line1=data["line1"],
                line2=data.get("line2") or "",
                landmark=data.get("landmark") or "",
                pincode=data["pincode"],
                district=data.get("district") or "",
                state=data.get("state") or "",
                latitude=data.get("latitude") or None,
                longitude=data.get("longitude") or None,
                alternate_mobile=data.get("alternate_mobile") or "",
                is_default=True,
            )
            order = _create_order_from_cart(
                vendor=vendor,
                customer_user=customer_user,
                address_obj=addr,
                cart_view=cart_view,
                coupon_quote=local_quote,
                referrer_code=ref_code,
            )
            clear_vendor_cart(request.session, vendor.id)
            clear_vendor_coupon(request.session, vendor_id=vendor.id)
            messages.success(request, f"Order placed: {order.order_number}")
            return redirect(reverse("store-payment-start", kwargs={"subdomain": vendor.subdomain, "token": str(order.public_token)}))
    else:
        # Prefill from session delivery location if available.
        initial = {}
        try:
            d = (request.session.get("store_delivery") or {}).get(str(vendor.id)) or {}
        except Exception:
            d = {}
        if isinstance(d, dict):
            if d.get("label"):
                initial["line1"] = d.get("label")
            if d.get("pincode"):
                initial["pincode"] = d.get("pincode")
            if d.get("latitude") is not None:
                initial["latitude"] = d.get("latitude")
            if d.get("longitude") is not None:
                initial["longitude"] = d.get("longitude")
        if cart_view.get("coupon_code"):
            initial["coupon_code"] = cart_view["coupon_code"]
        form = CheckoutForm(initial=initial)

    wishlist_view = build_wishlist_view(vendor=vendor, session=request.session)
    return render(
        request,
        "storefront/store_checkout.html",
        {
            "vendor": vendor,
            "cart": cart_view,
            "wishlist": wishlist_view,
            "form": form,
            "can_manage_vendor": can_manage_vendor(user=request.user, vendor=vendor),
            "can_access_billing": _can_access_billing_dashboard(request.user),
            "hide_sidebar": True,
        },
    )


@require_POST
def store_update_location(request, subdomain: str):
    """
    Stores delivery location hint in session for storefront browsing and checkout prefill.
    """
    vendor = _resolve_vendor_from_path(subdomain)
    label = (request.POST.get("label") or "").strip()
    pincode = (request.POST.get("pincode") or "").strip()
    lat = (request.POST.get("latitude") or "").strip()
    lng = (request.POST.get("longitude") or "").strip()
    try:
        lat_v = float(lat) if lat else None
    except Exception:
        lat_v = None
    try:
        lng_v = float(lng) if lng else None
    except Exception:
        lng_v = None

    blob = {"label": label, "pincode": pincode, "latitude": lat_v, "longitude": lng_v}
    data = request.session.get("store_delivery") or {}
    data[str(vendor.id)] = blob
    request.session["store_delivery"] = data
    request.session.modified = True
    messages.success(request, "Delivery location updated.")
    return redirect(request.META.get("HTTP_REFERER") or reverse("store-home", kwargs={"subdomain": vendor.subdomain}))


@require_GET
def store_geo_reverse(request, subdomain: str):
    """
    Same-origin proxy for reverse geocoding (OpenStreetMap Nominatim).

    Browser-to-nominatim often fails due to CORS on localhost origins. This endpoint avoids that.
    """
    _ = _resolve_vendor_from_path(subdomain)  # validate vendor exists
    lat = (request.GET.get("lat") or "").strip()
    lng = (request.GET.get("lng") or request.GET.get("lon") or "").strip()
    if not lat or not lng:
        return JsonResponse({"error": "missing_lat_lng"}, status=400)

    cache_key = f"storefront:nominatim:rev:{lat}:{lng}"
    cached = cache.get(cache_key)
    if cached is not None:
        return JsonResponse(cached)

    import json
    import urllib.parse
    import urllib.request

    params = {"format": "jsonv2", "addressdetails": "1", "lat": lat, "lon": lng}
    url = "https://nominatim.openstreetmap.org/reverse?" + urllib.parse.urlencode(params)
    payload = {}
    try:
        req = urllib.request.Request(
            url,
            headers={"Accept": "application/json", "User-Agent": "khatapro-storefront/1.0 (reverse; localhost)"},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
            if not isinstance(payload, dict):
                payload = {}
    except Exception:
        payload = {}

    cache.set(cache_key, payload, 60 * 60)
    return JsonResponse(payload)


@require_GET
def store_geo_search(request, subdomain: str):
    """
    Same-origin proxy for search autocomplete (OpenStreetMap Nominatim).
    """
    _ = _resolve_vendor_from_path(subdomain)  # validate vendor exists
    q = (request.GET.get("q") or "").strip()
    if len(q) < 3:
        return JsonResponse([], safe=False)

    limit_raw = (request.GET.get("limit") or "6").strip()
    try:
        limit = max(1, min(10, int(limit_raw)))
    except Exception:
        limit = 6

    cache_key = f"storefront:nominatim:search:{limit}:{q.lower()}"
    cached = cache.get(cache_key)
    if cached is not None:
        return JsonResponse(cached, safe=False)

    import json
    import urllib.parse
    import urllib.request

    params = {"format": "jsonv2", "addressdetails": "1", "limit": str(limit), "q": q}
    url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(params)
    payload = []
    try:
        req = urllib.request.Request(
            url,
            headers={"Accept": "application/json", "User-Agent": "khatapro-storefront/1.0 (search; localhost)"},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
            if not isinstance(payload, list):
                payload = []
    except Exception:
        payload = []

    cache.set(cache_key, payload, 15 * 60)
    return JsonResponse(payload, safe=False)


@require_POST
def store_app_lead_capture(request, subdomain: str):
    """
    Storefront app endpoint (Lead capture popup).

    Creates a CRM lead attached to the vendor's company (if available).
    """

    vendor = _resolve_vendor_from_path(subdomain)
    try:
        import json

        payload = json.loads((request.body or b"{}").decode("utf-8", errors="ignore") or "{}")
        if not isinstance(payload, dict):
            payload = {}
    except Exception:
        payload = {}

    mobile = str(payload.get("mobile") or "").strip()[:20]
    name = str(payload.get("name") or "").strip()[:160]
    if not mobile:
        return JsonResponse({"ok": False, "error": "mobile required"}, status=400)

    try:
        from leads.models import Lead

        company = None
        try:
            company = getattr(getattr(vendor.owner, "userprofile", None), "company", None)
        except Exception:
            company = None

        lead, _ = Lead.objects.get_or_create(
            company=company,
            mobile=mobile,
            defaults={
                "name": name,
                "source": Lead.Source.WEBSITE,
                "status": Lead.Status.NEW,
                "metadata": {"vendor_id": vendor.id, "subdomain": vendor.subdomain, "app": "lead_capture_popup"},
            },
        )
        if name and not (lead.name or "").strip():
            lead.name = name
            lead.save(update_fields=["name", "updated_at"])
    except Exception as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=500)

    return JsonResponse({"ok": True})


@require_GET
def store_track(request, subdomain: str, token: str):
    vendor = _resolve_vendor_from_path(subdomain)
    order = get_object_or_404(
        StoreOrder.objects.select_related("vendor", "address", "customer").prefetch_related("items", "status_events"),
        vendor=vendor,
        public_token=token,
    )
    wishlist_view = build_wishlist_view(vendor=vendor, session=request.session)
    cart_view = build_cart_view(vendor=vendor, session=request.session, user=(request.user if request.user.is_authenticated else None))
    return render(
        request,
        "storefront/store_track.html",
        {
            "vendor": vendor,
            "order": order,
            "cart": cart_view,
            "wishlist": wishlist_view,
            "can_manage_vendor": can_manage_vendor(user=request.user, vendor=vendor),
            "can_access_billing": _can_access_billing_dashboard(request.user),
            "hide_sidebar": True,
            "payment_url": reverse(
                "store-payment-start",
                kwargs={"subdomain": vendor.subdomain, "token": str(order.public_token)},
            ),
        },
    )


@login_required
def store_me_orders(request, subdomain: str):
    vendor = _resolve_vendor_from_path(subdomain)
    qs = (
        StoreOrder.objects.select_related("vendor", "address")
        .prefetch_related("items", "items__product")
        .filter(vendor=vendor, customer=request.user)
        .order_by("-created_at")
    )
    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(Q(order_number__icontains=q) | Q(payment_status__icontains=q) | Q(status__icontains=q))

    orders = list(qs[:200])
    wishlist_view = build_wishlist_view(vendor=vendor, session=request.session)
    cart_view = build_cart_view(vendor=vendor, session=request.session, user=request.user)
    return render(
        request,
        "storefront/store_me_orders.html",
        {
            "vendor": vendor,
            "orders": orders,
            "cart": cart_view,
            "wishlist": wishlist_view,
            "can_manage_vendor": can_manage_vendor(user=request.user, vendor=vendor),
            "can_access_billing": _can_access_billing_dashboard(request.user),
            "hide_sidebar": True,
        },
    )


@login_required
def store_me_order_view(request, subdomain: str, order_id: int):
    vendor = _resolve_vendor_from_path(subdomain)
    order = get_object_or_404(
        StoreOrder.objects.select_related("vendor", "address").prefetch_related("items", "items__product", "status_events"),
        id=order_id,
        vendor=vendor,
        customer=request.user,
    )
    wishlist_view = build_wishlist_view(vendor=vendor, session=request.session)
    cart_view = build_cart_view(vendor=vendor, session=request.session, user=request.user)
    return render(
        request,
        "storefront/store_me_order_view.html",
        {
            "vendor": vendor,
            "order": order,
            "cart": cart_view,
            "wishlist": wishlist_view,
            "can_manage_vendor": can_manage_vendor(user=request.user, vendor=vendor),
            "can_access_billing": _can_access_billing_dashboard(request.user),
            "hide_sidebar": True,
            "track_url": reverse("store-track", kwargs={"subdomain": vendor.subdomain, "token": str(order.public_token)}),
            "payment_url": reverse("store-payment-start", kwargs={"subdomain": vendor.subdomain, "token": str(order.public_token)}),
        },
    )


@require_GET
def store_payment_start(request, subdomain: str, token: str):
    vendor = _resolve_vendor_from_path(subdomain)
    order = get_object_or_404(StoreOrder.objects.select_related("vendor"), vendor=vendor, public_token=token)

    if order.payment_status == StoreOrder.PaymentStatus.PAID:
        messages.info(request, "Payment already completed.")
        return redirect(reverse("store-track", kwargs={"subdomain": vendor.subdomain, "token": str(order.public_token)}))

    gateway = vendor.payment_gateways.filter(is_active=True).order_by("provider").first()
    provider = (getattr(gateway, "provider", "") or "").strip().lower() or "demo"

    return render(
        request,
        "storefront/store_payment.html",
        {
            "vendor": vendor,
            "order": order,
            "provider": provider,
            "gateway_configured": bool(gateway),
            "can_manage_vendor": can_manage_vendor(user=request.user, vendor=vendor),
            "can_access_billing": _can_access_billing_dashboard(request.user),
            "pay_success_url": reverse(
                "store-payment-demo-success",
                kwargs={"subdomain": vendor.subdomain, "token": str(order.public_token)},
            ),
            "pay_fail_url": reverse(
                "store-payment-demo-fail",
                kwargs={"subdomain": vendor.subdomain, "token": str(order.public_token)},
            ),
            "hide_sidebar": True,
        },
    )


@transaction.atomic
@require_POST
def store_payment_demo_success(request, subdomain: str, token: str):
    vendor = _resolve_vendor_from_path(subdomain)
    order = get_object_or_404(StoreOrder.objects.select_related("vendor"), vendor=vendor, public_token=token)

    if order.payment_status != StoreOrder.PaymentStatus.PAID:
        attempt = StorePaymentAttempt.objects.create(
            order=order,
            provider="demo",
            status=StorePaymentAttempt.Status.SUCCESS,
            amount=Decimal(str(order.total_amount or "0.00")),
            external_ref=f"DEMO-{timezone.now().strftime('%Y%m%d%H%M%S')}",
            payload={"mode": "demo", "result": "success"},
        )
        order.payment_status = StoreOrder.PaymentStatus.PAID
        order.save(update_fields=["payment_status", "updated_at"])
        StoreOrderStatusEvent.objects.create(
            order=order,
            status=order.status,
            note=f"Payment success (demo). Ref={attempt.external_ref}",
        )
        messages.success(request, "Payment successful (demo).")
    else:
        messages.info(request, "Payment already completed.")
    return redirect(reverse("store-track", kwargs={"subdomain": vendor.subdomain, "token": str(order.public_token)}))


@transaction.atomic
@require_POST
def store_payment_demo_fail(request, subdomain: str, token: str):
    vendor = _resolve_vendor_from_path(subdomain)
    order = get_object_or_404(StoreOrder.objects.select_related("vendor"), vendor=vendor, public_token=token)

    StorePaymentAttempt.objects.create(
        order=order,
        provider="demo",
        status=StorePaymentAttempt.Status.FAILED,
        amount=Decimal(str(order.total_amount or "0.00")),
        external_ref=f"DEMO-{timezone.now().strftime('%Y%m%d%H%M%S')}",
        payload={"mode": "demo", "result": "failed"},
    )
    order.payment_status = StoreOrder.PaymentStatus.FAILED
    order.save(update_fields=["payment_status", "updated_at"])
    StoreOrderStatusEvent.objects.create(order=order, status=order.status, note="Payment failed (demo).")
    messages.error(request, "Payment failed (demo). Try again.")
    return redirect(reverse("store-payment-start", kwargs={"subdomain": vendor.subdomain, "token": str(order.public_token)}))


@require_GET
def store_wishlist_view(request, subdomain: str):
    vendor = _resolve_vendor_from_path(subdomain)
    wishlist_view = build_wishlist_view(vendor=vendor, session=request.session)
    cart_view = build_cart_view(vendor=vendor, session=request.session, user=(request.user if request.user.is_authenticated else None))
    return render(
        request,
        "storefront/store_wishlist.html",
        {
            "vendor": vendor,
            "wishlist": wishlist_view,
            "wishlist_ids": wishlist_view["ids"],
            "cart": cart_view,
            "can_manage_vendor": can_manage_vendor(user=request.user, vendor=vendor),
            "can_access_billing": _can_access_billing_dashboard(request.user),
            "hide_sidebar": True,
        },
    )


@require_POST
def store_wishlist_toggle(request, subdomain: str):
    vendor = _resolve_vendor_from_path(subdomain)
    listing_id = int(request.POST.get("listing_id") or 0)
    get_object_or_404(VendorProductListing, vendor=vendor, id=listing_id, is_online=True)
    added = toggle_wishlist(request.session, vendor_id=vendor.id, listing_id=listing_id)
    if request.headers.get("HX-Request") == "true":
        return HttpResponse("ok")
    messages.success(request, "Added to wishlist." if added else "Removed from wishlist.")
    return redirect(request.META.get("HTTP_REFERER") or reverse("store-home", kwargs={"subdomain": vendor.subdomain}))


# ---------------- Vendor UI ----------------


@login_required
def vendor_dashboard(request, subdomain: str):
    vendor = _resolve_vendor_from_path(subdomain)
    ensure_vendor_access(request=request, vendor=vendor)
    store_settings, _ = VendorStoreSettings.objects.get_or_create(vendor=vendor)
    recent_orders = StoreOrder.objects.filter(vendor=vendor).order_by("-created_at")[:25]
    base_orders = StoreOrder.objects.filter(vendor=vendor)

    counts = base_orders.aggregate(
        pending=Count("id", filter=Q(status=StoreOrder.Status.PENDING)),
        accepted=Count("id", filter=Q(status=StoreOrder.Status.ACCEPTED)),
        shipped=Count("id", filter=Q(status=StoreOrder.Status.SHIPPED)),
        delivered=Count("id", filter=Q(status=StoreOrder.Status.DELIVERED)),
        rejected=Count("id", filter=Q(status=StoreOrder.Status.REJECTED)),
        unpaid=Count("id", filter=Q(payment_status=StoreOrder.PaymentStatus.UNPAID)),
        initiated=Count("id", filter=Q(payment_status=StoreOrder.PaymentStatus.INITIATED)),
        paid=Count("id", filter=Q(payment_status=StoreOrder.PaymentStatus.PAID)),
        failed=Count("id", filter=Q(payment_status=StoreOrder.PaymentStatus.FAILED)),
        total=Count("id"),
    )

    paid_orders = base_orders.filter(payment_status=StoreOrder.PaymentStatus.PAID)
    sales_total = paid_orders.aggregate(total=Coalesce(Sum("total_amount"), Decimal("0.00")))["total"]

    today = timezone.localdate()
    start_7d = today - timedelta(days=6)
    start_30d = today - timedelta(days=29)
    sales_today = paid_orders.filter(created_at__date=today).aggregate(total=Coalesce(Sum("total_amount"), Decimal("0.00")))[
        "total"
    ]
    sales_7d = paid_orders.filter(created_at__date__gte=start_7d).aggregate(total=Coalesce(Sum("total_amount"), Decimal("0.00")))[
        "total"
    ]
    sales_30d = paid_orders.filter(created_at__date__gte=start_30d).aggregate(
        total=Coalesce(Sum("total_amount"), Decimal("0.00"))
    )["total"]
    paid_30d_count = paid_orders.filter(created_at__date__gte=start_30d).count()
    aov_30d = (Decimal(str(sales_30d or "0.00")) / Decimal(paid_30d_count)) if paid_30d_count else Decimal("0.00")

    # Shipping status snapshot (if shipments created).
    shipment_counts = StoreShipment.objects.filter(order__vendor=vendor).aggregate(
        created=Count("id", filter=Q(status=StoreShipment.Status.CREATED)),
        pickup=Count("id", filter=Q(status=StoreShipment.Status.PICKUP_REQUESTED)),
        transit=Count("id", filter=Q(status=StoreShipment.Status.IN_TRANSIT)),
        delivered=Count("id", filter=Q(status=StoreShipment.Status.DELIVERED)),
        failed=Count("id", filter=Q(status=StoreShipment.Status.FAILED)),
        total=Count("id"),
    )

    # Inventory alerts (primary warehouse only).
    low_stock_count = 0
    if vendor.primary_warehouse_id:
        sellable_expr = ExpressionWrapper(F("available_qty") - F("reserved_qty"), output_field=IntegerField())
        low_stock_count = (
            WarehouseInventory.objects.filter(
                warehouse_id=vendor.primary_warehouse_id,
                product__vendor_listings__vendor=vendor,
            )
            .annotate(sellable=sellable_expr)
            .filter(sellable__lte=F("product__low_stock_threshold"))
            .count()
        )

    # Last 14 days trend (paid orders only).
    start_14d = today - timedelta(days=13)
    raw_series = (
        paid_orders.filter(created_at__date__gte=start_14d)
        .annotate(d=TruncDate("created_at"))
        .values("d")
        .annotate(order_count=Count("id"), revenue=Coalesce(Sum("total_amount"), Decimal("0.00")))
        .order_by("d")
    )
    by_date = {row["d"]: row for row in raw_series}
    series_days = [start_14d + timedelta(days=i) for i in range(14)]
    series = []
    for d in series_days:
        row = by_date.get(d) or {}
        series.append(
            {
                "date": d,
                "label": d.strftime("%d %b"),
                "order_count": int(row.get("order_count") or 0),
                "revenue": Decimal(str(row.get("revenue") or "0.00")),
            }
        )

    def _spark_points(values: list[Decimal | int], *, width: int = 120, height: int = 34) -> str:
        if not values:
            return ""
        max_v = max([Decimal(str(v)) for v in values]) if values else Decimal("0")
        if max_v <= 0:
            max_v = Decimal("1")
        n = len(values)
        if n == 1:
            return f"0,{height/2:.1f}"
        pts = []
        for idx, v in enumerate(values):
            x = (idx * width) / (n - 1)
            y = height - (Decimal(str(v)) / max_v * Decimal(str(height)))
            pts.append(f"{float(x):.1f},{float(y):.1f}")
        return " ".join(pts)

    revenue_points = _spark_points([row["revenue"] for row in series])
    orders_points = _spark_points([row["order_count"] for row in series])

    top_products = (
        StoreOrderItem.objects.filter(order__vendor=vendor)
        .values("product__name", "product__slug")
        .annotate(qty=Coalesce(Sum("qty"), 0))
        .order_by("-qty")[:6]
    )

    # Action center
    pending_orders = (
        base_orders.filter(status=StoreOrder.Status.PENDING)
        .order_by("created_at")
        .only("id", "order_number", "created_at", "total_amount", "status", "payment_status")[:6]
    )
    ready_to_ship_count = base_orders.filter(status=StoreOrder.Status.ACCEPTED, shipment__isnull=True).count()
    recent_events = (
        StoreOrderStatusEvent.objects.select_related("order")
        .filter(order__vendor=vendor)
        .order_by("-created_at", "-id")[:10]
    )

    # Config health (do not expose secrets)
    active_payment = vendor.payment_gateways.filter(is_active=True).order_by("provider").first()
    shiprocket_cfg = vendor.shipping_providers.filter(provider="shiprocket", is_active=True).first()
    shiprocket_ok = False
    if shiprocket_cfg:
        try:
            shiprocket_ok = bool((shiprocket_cfg.config or {}).get("email")) and bool((shiprocket_cfg.config or {}).get("password"))
        except Exception:
            shiprocket_ok = False

    try:
        from vendors.services.store_settings import build_settings_summary

        settings_summary = build_settings_summary(store_settings)
    except Exception:
        settings_summary = {}
    return render(
        request,
        "storefront/vendor_dashboard.html",
        {
            **_vendor_admin_context(request=request, vendor=vendor, page="dashboard", breadcrumb="Admin > Overview"),
            "orders": recent_orders,
            "counts": counts,
            "shipment_counts": shipment_counts,
            "sales_total": sales_total,
            "sales_today": sales_today,
            "sales_7d": sales_7d,
            "sales_30d": sales_30d,
            "paid_30d_count": paid_30d_count,
            "aov_30d": aov_30d.quantize(Decimal("0.01")),
            "low_stock_count": low_stock_count,
            "series": series,
            "spark_revenue_points": revenue_points,
            "spark_orders_points": orders_points,
            "top_products": list(top_products),
            "pending_orders": pending_orders,
            "ready_to_ship_count": ready_to_ship_count,
            "recent_events": recent_events,
            "active_payment": active_payment,
            "shiprocket_ok": shiprocket_ok,
            "store_settings": store_settings,
            "store_settings_summary": settings_summary,
        },
    )


@login_required
def vendor_settings_general(request, subdomain: str):
    vendor = _resolve_vendor_from_path(subdomain)
    ensure_vendor_access(request=request, vendor=vendor)
    settings_obj, _ = VendorStoreSettings.objects.get_or_create(vendor=vendor)

    if request.method == "POST":
        section = (request.POST.get("_section") or "").strip().lower()
        if section not in {"", "all", "contact", "defaults"}:
            section = ""

        store_name = (request.POST.get("store_name") or "").strip()
        if store_name and section in {"", "all", "contact"}:
            vendor.name = store_name
            vendor.save(update_fields=["name", "updated_at"])

        # Split saves: the new UI posts partial forms, so only update the relevant fields.
        if section in {"", "all", "contact"}:
            for f in [
                "support_email",
                "support_phone",
                "address_line1",
                "address_line2",
                "city",
                "state",
                "pincode",
                "country",
            ]:
                if f in request.POST:
                    setattr(settings_obj, f, (request.POST.get(f) or "").strip())

        if section in {"", "all", "defaults"}:
            for f in ["timezone", "currency"]:
                if f in request.POST:
                    setattr(settings_obj, f, (request.POST.get(f) or "").strip())

            # Extensible Shopify-like settings (backend-only, future UI can post these keys).
            try:
                from vendors.services.store_settings import update_settings_from_post

                update_settings_from_post(settings_obj, request.POST)
            except Exception:
                pass

        settings_obj.save()
        messages.success(request, "General settings saved.")
        return redirect(reverse("vendor-settings-general", kwargs={"subdomain": vendor.subdomain}))

    return render(
        request,
        "storefront/vendor_settings_general.html",
        {
            **_vendor_admin_context(request=request, vendor=vendor, page="settings_general", breadcrumb="Settings > General"),
            "settings": settings_obj,
            "settings_summary": getattr(settings_obj, "settings_json", None) or {},
            "store_url": request.build_absolute_uri(reverse("store-home", kwargs={"subdomain": vendor.subdomain})),
        },
    )


@login_required
def vendor_settings_payments(request, subdomain: str):
    vendor = _resolve_vendor_from_path(subdomain)
    ensure_vendor_access(request=request, vendor=vendor)

    provider = (request.GET.get("provider") or "razorpay").strip().lower()
    allowed = {c[0] for c in VendorPaymentGatewayConfig.Provider.choices}
    if provider not in allowed:
        provider = "razorpay"

    cfg, _ = VendorPaymentGatewayConfig.objects.get_or_create(vendor=vendor, provider=provider)
    active = vendor.payment_gateways.filter(is_active=True).order_by("provider").first()

    provider_fields = {
        "razorpay": [
            ("key_id", "Key ID"),
            ("key_secret", "Key Secret"),
            ("webhook_secret", "Webhook Secret (optional)"),
            ("api_base", "API Base (optional)"),
        ],
        "paytm": [
            ("merchant_id", "Merchant ID"),
            ("merchant_key", "Merchant Key"),
        ],
        "stripe": [
            ("publishable_key", "Publishable Key"),
            ("secret_key", "Secret Key"),
            ("webhook_secret", "Webhook Secret (optional)"),
        ],
    }

    if request.method == "POST":
        provider_post = (request.POST.get("provider") or provider).strip().lower()
        if provider_post not in allowed:
            provider_post = provider
        cfg, _ = VendorPaymentGatewayConfig.objects.get_or_create(vendor=vendor, provider=provider_post)

        is_active = (request.POST.get("is_active") or "").strip().lower() in {"1", "true", "yes", "on"}
        config = dict(cfg.config or {})
        for key, _label in provider_fields.get(provider_post, []):
            config[key] = (request.POST.get(f"cfg_{key}") or "").strip()
        cfg.config = config
        if is_active:
            vendor.payment_gateways.update(is_active=False)
        cfg.is_active = bool(is_active)
        cfg.save()
        messages.success(request, "Payment settings saved.")
        return redirect(reverse("vendor-settings-payments", kwargs={"subdomain": vendor.subdomain}) + f"?provider={provider_post}")

    render_fields = []
    try:
        cfg_config = cfg.config or {}
    except Exception:
        cfg_config = {}
    for key, label in provider_fields.get(provider, []):
        render_fields.append({"key": key, "label": label, "value": str(cfg_config.get(key) or "")})

    return render(
        request,
        "storefront/vendor_settings_payments.html",
        {
            **_vendor_admin_context(request=request, vendor=vendor, page="settings_payments", breadcrumb="Settings > Payments"),
            "provider": provider,
            "providers": list(VendorPaymentGatewayConfig.Provider.choices),
            "cfg": cfg,
            "active_provider": (active.provider if active else ""),
            "provider_fields": render_fields,
        },
    )


@login_required
def vendor_settings_shipping(request, subdomain: str):
    import secrets

    vendor = _resolve_vendor_from_path(subdomain)
    ensure_vendor_access(request=request, vendor=vendor)

    provider = (request.GET.get("provider") or "shiprocket").strip().lower()
    allowed = {c[0] for c in VendorShippingProviderConfig.Provider.choices}
    if provider not in allowed:
        provider = "shiprocket"

    cfg, _ = VendorShippingProviderConfig.objects.get_or_create(vendor=vendor, provider=provider)
    active = vendor.shipping_providers.filter(is_active=True).order_by("provider").first()

    provider_fields = {
        "shiprocket": [
            ("email", "Email"),
            ("password", "Password"),
            ("api_base", "API Base (optional)"),
            ("pickup_location", "Pickup Location Name/Code (optional)"),
            ("webhook_secret", "Webhook Token (x-api-key)"),
            ("demo_mode", "Demo mode (true/false)"),
        ],
        "delhivery": [
            ("api_key", "API Key"),
            ("client_id", "Client ID (optional)"),
        ],
        "bluedart": [
            ("api_key", "API Key"),
            ("client_id", "Client ID (optional)"),
        ],
    }

    if request.method == "POST":
        provider_post = (request.POST.get("provider") or provider).strip().lower()
        if provider_post not in allowed:
            provider_post = provider
        cfg, _ = VendorShippingProviderConfig.objects.get_or_create(vendor=vendor, provider=provider_post)

        is_active = (request.POST.get("is_active") or "").strip().lower() in {"1", "true", "yes", "on"}
        config = dict(cfg.config or {})
        for key, _label in provider_fields.get(provider_post, []):
            config[key] = (request.POST.get(f"cfg_{key}") or "").strip()

        if provider_post == "shiprocket" and not str(config.get("webhook_secret") or "").strip():
            config["webhook_secret"] = secrets.token_urlsafe(24)

        cfg.config = config
        if is_active:
            vendor.shipping_providers.update(is_active=False)
        cfg.is_active = bool(is_active)
        cfg.save()
        messages.success(request, "Shipping settings saved.")
        return redirect(reverse("vendor-settings-shipping", kwargs={"subdomain": vendor.subdomain}) + f"?provider={provider_post}")

    webhook_url = ""
    try:
        webhook_url = request.build_absolute_uri(reverse("shiprocket-webhook", kwargs={"vendor_id": vendor.id}))
    except Exception:
        webhook_url = ""

    return render(
        request,
        "storefront/vendor_settings_shipping.html",
        {
            **_vendor_admin_context(request=request, vendor=vendor, page="settings_shipping", breadcrumb="Settings > Shipping"),
            "provider": provider,
            "providers": list(VendorShippingProviderConfig.Provider.choices),
            "cfg": cfg,
            "active_provider": (active.provider if active else ""),
            "provider_fields": [
                {"key": k, "label": lbl, "value": str((cfg.config or {}).get(k) or "")} for k, lbl in provider_fields.get(provider, [])
            ],
            "shiprocket_webhook_url": webhook_url,
        },
    )


@login_required
def vendor_settings_plan(request, subdomain: str):
    vendor = _resolve_vendor_from_path(subdomain)
    ensure_vendor_access(request=request, vendor=vendor)

    plan_name = "Free"
    plan_status = "active"
    plan_ends_on = ""
    enabled_features = []
    try:
        from billing.services import get_effective_plan, get_effective_features_for_user

        owner = getattr(vendor, "owner", None)
        plan = get_effective_plan(owner) if owner else None
        if plan:
            plan_name = plan.name
        try:
            enabled_features = sorted(list(get_effective_features_for_user(owner))) if owner else []
        except Exception:
            enabled_features = []
    except Exception:
        pass

    try:
        from billing.models import Subscription as BillingSubscription

        owner = getattr(vendor, "owner", None)
        sub = BillingSubscription.objects.filter(user=owner).order_by("-created_at").first() if owner else None
        if sub:
            plan_status = getattr(sub, "status", "") or "active"
            end = getattr(sub, "end_date", None) or getattr(sub, "trial_end", None)
            if end:
                plan_ends_on = end.strftime("%Y-%m-%d")
    except Exception:
        pass

    return render(
        request,
        "storefront/vendor_settings_plan.html",
        {
            **_vendor_admin_context(request=request, vendor=vendor, page="settings_plan", breadcrumb="Settings > Plan"),
            "plan_name": plan_name,
            "plan_status": plan_status,
            "plan_ends_on": plan_ends_on,
            "enabled_features": enabled_features,
        },
    )


@login_required
def vendor_settings_billing(request, subdomain: str):
    vendor = _resolve_vendor_from_path(subdomain)
    ensure_vendor_access(request=request, vendor=vendor)
    return render(
        request,
        "storefront/vendor_settings_billing.html",
        {
            **_vendor_admin_context(request=request, vendor=vendor, page="settings_billing", breadcrumb="Settings > Billing"),
        },
    )


@login_required
def vendor_settings_checkout(request, subdomain: str):
    vendor = _resolve_vendor_from_path(subdomain)
    ensure_vendor_access(request=request, vendor=vendor)
    settings_obj, _ = VendorStoreSettings.objects.get_or_create(vendor=vendor)

    from vendors.services.store_settings import build_settings_summary, get_settings_blob, set_settings_blob

    if request.method == "POST":
        blob = get_settings_blob(settings_obj)
        blob["customer_accounts"] = (request.POST.get("customer_accounts") or "optional").strip().lower()
        blob["guest_checkout_enabled"] = bool(request.POST.get("guest_checkout_enabled"))
        set_settings_blob(settings_obj, blob)
        settings_obj.save(update_fields=["settings_json", "updated_at"])
        messages.success(request, "Checkout settings saved.")
        return redirect(reverse("vendor-settings-checkout", kwargs={"subdomain": vendor.subdomain}))

    return render(
        request,
        "storefront/vendor_settings_checkout.html",
        {
            **_vendor_admin_context(request=request, vendor=vendor, page="settings_checkout", breadcrumb="Settings > Checkout"),
            "settings_obj": settings_obj,
            "settings_summary": build_settings_summary(settings_obj),
        },
    )


@login_required
def vendor_settings_customer_accounts(request, subdomain: str):
    vendor = _resolve_vendor_from_path(subdomain)
    ensure_vendor_access(request=request, vendor=vendor)
    return render(
        request,
        "storefront/vendor_settings_customer_accounts.html",
        {
            **_vendor_admin_context(
                request=request, vendor=vendor, page="settings_customer_accounts", breadcrumb="Settings > Customer accounts"
            ),
        },
    )


@login_required
def vendor_settings_taxes(request, subdomain: str):
    vendor = _resolve_vendor_from_path(subdomain)
    ensure_vendor_access(request=request, vendor=vendor)
    settings_obj, _ = VendorStoreSettings.objects.get_or_create(vendor=vendor)

    from vendors.services.store_settings import get_settings_blob, set_settings_blob

    if request.method == "POST":
        blob = get_settings_blob(settings_obj)
        blob["tax_included_in_prices"] = bool(request.POST.get("tax_included_in_prices"))
        set_settings_blob(settings_obj, blob)
        settings_obj.save(update_fields=["settings_json", "updated_at"])
        messages.success(request, "Tax settings saved.")
        return redirect(reverse("vendor-settings-taxes", kwargs={"subdomain": vendor.subdomain}))

    blob = get_settings_blob(settings_obj)
    return render(
        request,
        "storefront/vendor_settings_taxes.html",
        {
            **_vendor_admin_context(request=request, vendor=vendor, page="settings_taxes", breadcrumb="Settings > Taxes & duties"),
            "tax_included_in_prices": bool(blob.get("tax_included_in_prices")),
        },
    )


@login_required
def vendor_settings_locations(request, subdomain: str):
    vendor = _resolve_vendor_from_path(subdomain)
    ensure_vendor_access(request=request, vendor=vendor)

    if request.method == "POST":
        raw = (request.POST.get("primary_warehouse_id") or "").strip()
        if not raw:
            vendor.primary_warehouse_id = None
        else:
            try:
                vendor.primary_warehouse_id = int(raw)
            except Exception:
                vendor.primary_warehouse_id = None
        vendor.save(update_fields=["primary_warehouse", "updated_at"])
        messages.success(request, "Location settings saved.")
        return redirect(reverse("vendor-settings-locations", kwargs={"subdomain": vendor.subdomain}))

    vendor_warehouses = list(vendor.warehouses.all().order_by("name"))
    return render(
        request,
        "storefront/vendor_settings_locations.html",
        {
            **_vendor_admin_context(request=request, vendor=vendor, page="settings_locations", breadcrumb="Settings > Locations"),
            "vendor_warehouses": vendor_warehouses,
        },
    )


@login_required
def vendor_settings_markets(request, subdomain: str):
    vendor = _resolve_vendor_from_path(subdomain)
    ensure_vendor_access(request=request, vendor=vendor)
    settings_obj, _ = VendorStoreSettings.objects.get_or_create(vendor=vendor)
    from vendors.services.store_settings import build_settings_summary

    return render(
        request,
        "storefront/vendor_settings_markets.html",
        {
            **_vendor_admin_context(request=request, vendor=vendor, page="settings_markets", breadcrumb="Settings > Markets"),
            "settings_summary": build_settings_summary(settings_obj),
        },
    )


@login_required
def vendor_settings_apps(request, subdomain: str):
    vendor = _resolve_vendor_from_path(subdomain)
    ensure_vendor_access(request=request, vendor=vendor)

    from vendors.models import MarketplaceApp
    from vendors.services.marketplace_apps import (
        get_vendor_installs_map,
        install_app,
        list_marketplace_apps,
        uninstall_app,
        update_app_config,
    )
    from vendors.services.shopify_oauth import get_shopify_client_id

    if request.method == "POST":
        action = (request.POST.get("_action") or "").strip().lower()
        code = (request.POST.get("app_code") or "").strip().lower()
        app = MarketplaceApp.objects.filter(code=code, is_active=True).first() if code else None
        if action in {"install", "toggle", "uninstall", "save_config"} and not app:
            messages.error(request, "App not found.")
            return redirect(reverse("vendor-settings-apps", kwargs={"subdomain": vendor.subdomain}))

        if action == "install":
            install_app(vendor=vendor, app=app)
            messages.success(request, "App installed.")
            return redirect(reverse("vendor-settings-apps", kwargs={"subdomain": vendor.subdomain}))

        if action == "uninstall":
            uninstall_app(vendor=vendor, app=app)
            messages.success(request, "App uninstalled.")
            return redirect(reverse("vendor-settings-apps", kwargs={"subdomain": vendor.subdomain}))

        if action == "toggle":
            from vendors.models import VendorAppInstall

            inst = VendorAppInstall.objects.filter(vendor=vendor, app=app).first()
            if inst and inst.is_installed:
                inst.is_enabled = not bool(inst.is_enabled)
                inst.save(update_fields=["is_enabled", "updated_at"])
                messages.success(request, "App updated.")
            return redirect(reverse("vendor-settings-apps", kwargs={"subdomain": vendor.subdomain}))

        if action == "save_config":
            from vendors.models import VendorAppInstall

            inst = VendorAppInstall.objects.filter(vendor=vendor, app=app).first()
            if not inst or not inst.is_installed:
                messages.error(request, "Install the app first.")
                return redirect(reverse("vendor-settings-apps", kwargs={"subdomain": vendor.subdomain}))

            raw = (request.POST.get("config_json") or "").strip()
            try:
                import json

                blob = json.loads(raw or "{}")
                if not isinstance(blob, dict):
                    raise ValueError("Config must be a JSON object")
                update_app_config(install=inst, config_updates=blob)
                messages.success(request, "App config saved.")
            except Exception as exc:
                messages.error(request, f"Invalid JSON: {exc}")
            return redirect(reverse("vendor-settings-apps", kwargs={"subdomain": vendor.subdomain}))

    installs_map = get_vendor_installs_map(vendor)
    apps = list_marketplace_apps()
    # Build view-model list
    view_apps = []
    try:
        import json
    except Exception:
        json = None
    for a in apps:
        inst = installs_map.get(a.code)
        cfg_text = "{}"
        if inst and json:
            try:
                cfg_text = json.dumps(inst.config or {}, ensure_ascii=False)
            except Exception:
                cfg_text = "{}"
        view_apps.append(
            {
                "code": a.code,
                "name": a.name,
                "category": a.category,
                "short_description": a.short_description,
                "rating": a.rating,
                "install": inst,
                "config_json_text": cfg_text,
            }
        )
    from vendors.services.shopify_recommendations import get_shopify_app_recommendations

    shopify_catalog = get_shopify_app_recommendations()
    shopify_conn = VendorShopifyConnection.objects.filter(vendor=vendor, is_active=True).first()
    return render(
        request,
        "storefront/vendor_settings_apps.html",
        {
            **_vendor_admin_context(request=request, vendor=vendor, page="settings_apps", breadcrumb="Settings > Apps"),
            "apps": view_apps,
            "shopify_apps": shopify_catalog.get("apps") or [],
            "shopify_categories": shopify_catalog.get("categories") or [],
            "shopify_client_configured": bool(get_shopify_client_id()),
            "shopify_connection": shopify_conn,
        },
    )


@login_required
@require_POST
def vendor_shopify_connect_start(request, subdomain: str):
    vendor = _resolve_vendor_from_path(subdomain)
    ensure_vendor_access(request=request, vendor=vendor)

    from vendors.services.shopify_oauth import (
        build_authorize_url,
        get_shopify_client_id,
        is_valid_shop_domain,
        normalize_shop_domain,
        sign_oauth_state,
    )

    if not get_shopify_client_id():
        messages.error(request, "Shopify client credentials are not configured by admin yet.")
        return redirect(reverse("vendor-settings-apps", kwargs={"subdomain": vendor.subdomain}))

    shop = normalize_shop_domain(request.POST.get("shop_domain") or "")
    if not is_valid_shop_domain(shop):
        messages.error(request, "Please enter a valid shop domain like yourstore.myshopify.com")
        return redirect(reverse("vendor-settings-apps", kwargs={"subdomain": vendor.subdomain}))

    state = sign_oauth_state({"vendor_id": vendor.id, "subdomain": vendor.subdomain, "user_id": request.user.id})
    redirect_uri = request.build_absolute_uri(reverse("shopify-oauth-callback"))
    auth_url = build_authorize_url(shop_domain=shop, redirect_uri=redirect_uri, state=state)
    return redirect(auth_url)


@login_required
@require_POST
def vendor_shopify_disconnect(request, subdomain: str):
    vendor = _resolve_vendor_from_path(subdomain)
    ensure_vendor_access(request=request, vendor=vendor)

    VendorShopifyConnection.objects.filter(vendor=vendor).delete()
    messages.success(request, "Shopify disconnected.")
    return redirect(reverse("vendor-settings-apps", kwargs={"subdomain": vendor.subdomain}))


@login_required
def vendor_settings_users(request, subdomain: str):
    vendor = _resolve_vendor_from_path(subdomain)
    ensure_vendor_access(request=request, vendor=vendor)

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip().lower()
        if action == "add_member":
            identifier = (request.POST.get("identifier") or "").strip()
            role = (request.POST.get("role") or "staff").strip().lower()
            if role not in {c[0] for c in VendorMembership.Role.choices}:
                role = "staff"
            if not identifier:
                messages.error(request, "Please enter user email or mobile.")
            else:
                user = None
                try:
                    user = User.objects.filter(email__iexact=identifier).first()
                except Exception:
                    user = None
                if not user:
                    try:
                        user = User.objects.filter(mobile=identifier).first()
                    except Exception:
                        user = None
                if not user:
                    messages.error(request, "User not found. Create the user first, then add to store.")
                else:
                    obj, created = VendorMembership.objects.get_or_create(vendor=vendor, user=user, defaults={"role": role})
                    if not created:
                        obj.role = role
                        obj.is_active = True
                        obj.save(update_fields=["role", "is_active"])
                    messages.success(request, "User added to store.")
            return redirect(reverse("vendor-settings-users", kwargs={"subdomain": vendor.subdomain}))

        if action == "toggle_member":
            mid = (request.POST.get("member_id") or "").strip()
            try:
                m = VendorMembership.objects.select_related("user").filter(vendor=vendor, id=int(mid)).first()
            except Exception:
                m = None
            if not m:
                messages.error(request, "Member not found.")
            else:
                m.is_active = not bool(m.is_active)
                m.save(update_fields=["is_active"])
                messages.success(request, "Member updated.")
            return redirect(reverse("vendor-settings-users", kwargs={"subdomain": vendor.subdomain}))

    memberships = VendorMembership.objects.select_related("user").filter(vendor=vendor).order_by("-is_active", "role", "-id")
    return render(
        request,
        "storefront/vendor_settings_users.html",
        {
            **_vendor_admin_context(request=request, vendor=vendor, page="settings_users", breadcrumb="Settings > Users & permissions"),
            "memberships": memberships,
        },
    )


@login_required
def vendor_settings_notifications(request, subdomain: str):
    vendor = _resolve_vendor_from_path(subdomain)
    ensure_vendor_access(request=request, vendor=vendor)

    fields = {
        "whatsapp": [("from_number", "From number (optional)")],
        "sms": [
            ("provider", "Provider (demo/google/fast2sms/custom_http)"),
            ("api_key", "Google/Provider API key (optional)"),
            ("sender_id", "Sender ID (optional)"),
            ("api_url", "API URL (optional)"),
        ],
        "email": [("from_email", "From email (optional)")],
    }

    providers_map = {p[0]: p[1] for p in VendorMarketingProviderConfig.Provider.choices}
    keys = ["whatsapp", "sms", "email"]

    if request.method == "POST" and (request.POST.get("_action") or "").strip().lower() != "test_send":
        for key in keys:
            cfg, _ = VendorMarketingProviderConfig.objects.get_or_create(vendor=vendor, provider=key)
            cfg.is_active = bool(request.POST.get(f"provider_active_{key}"))
            blob = dict(cfg.config or {})
            for fkey, _label in fields.get(key, []):
                blob[fkey] = (request.POST.get(f"cfg_{key}__{fkey}") or "").strip()
            cfg.config = blob
            cfg.save()
        messages.success(request, "Notification settings saved.")
        return redirect(reverse("vendor-settings-notifications", kwargs={"subdomain": vendor.subdomain}))

    if request.method == "POST" and (request.POST.get("_action") or "").strip().lower() == "test_send":
        channel = (request.POST.get("test_channel") or "whatsapp").strip().lower()
        destination = (request.POST.get("test_destination") or "").strip()
        text = (request.POST.get("test_message") or "").strip()
        if not destination or not text:
            messages.error(request, "Destination and message are required for test send.")
            return redirect(reverse("vendor-settings-notifications", kwargs={"subdomain": vendor.subdomain}))

        from storefront.services.vendor_messaging import (
            send_vendor_email,
            send_vendor_sms,
            send_vendor_whatsapp,
            vendor_channel_enabled,
        )

        if not vendor_channel_enabled(vendor, channel):
            messages.error(request, f"{channel.title()} is OFF. Enable it first, then send test.")
            return redirect(reverse("vendor-settings-notifications", kwargs={"subdomain": vendor.subdomain}))

        if channel == "sms":
            res = send_vendor_sms(vendor=vendor, to=destination, message=text)
        elif channel == "email":
            res = send_vendor_email(vendor=vendor, to=destination, subject=f"Test: {vendor.name}", message=text)
        else:
            res = send_vendor_whatsapp(vendor=vendor, to=destination, message=text)

        if res.ok:
            messages.success(request, f"Test sent via {channel}.")
        else:
            messages.error(request, f"Test failed: {res.error or 'unknown error'}")
        return redirect(reverse("vendor-settings-notifications", kwargs={"subdomain": vendor.subdomain}))

    providers = []
    for key in keys:
        cfg, _ = VendorMarketingProviderConfig.objects.get_or_create(vendor=vendor, provider=key)
        cfg_blob = cfg.config or {}
        providers.append(
            {
                "key": key,
                "label": providers_map.get(key, key.title()),
                "help": "Enabled for campaigns and automated events.",
                "is_active": bool(cfg.is_active),
                "updated_at": cfg.updated_at,
                "fields": [{"key": fkey, "label": label, "value": str(cfg_blob.get(fkey) or "")} for fkey, label in fields.get(key, [])],
            }
        )

    return render(
        request,
        "storefront/vendor_settings_notifications.html",
        {
            **_vendor_admin_context(request=request, vendor=vendor, page="settings_notifications", breadcrumb="Settings > Notifications"),
            "providers": providers,
        },
    )


@login_required
def vendor_settings_sales_channels(request, subdomain: str):
    vendor = _resolve_vendor_from_path(subdomain)
    ensure_vendor_access(request=request, vendor=vendor)
    keys = ["facebook", "instagram", "google", "ott", "influencer"]
    fields = {
        "facebook": [
            ("access_token", "Access token"),
            ("ad_account_id", "Ad account id"),
            ("page_id", "Page id (optional)"),
        ],
        "instagram": [
            ("access_token", "Access token"),
            ("ig_account_id", "Instagram account id"),
            ("ad_account_id", "Ad account id (optional)"),
        ],
        "google": [
            ("developer_token", "Developer token"),
            ("customer_id", "Customer id"),
            ("refresh_token", "Refresh token"),
        ],
        "ott": [
            ("platform", "Platform (hotstar/jio/zee/sony etc.)"),
            ("account_id", "Account id"),
            ("api_key", "API key/token"),
        ],
        "influencer": [
            ("contact_name", "Contact name"),
            ("contact_phone", "Contact phone"),
            ("notes", "Notes (optional)"),
        ],
    }
    providers_map = {p[0]: p[1] for p in VendorMarketingProviderConfig.Provider.choices}

    if request.method == "POST":
        for key in keys:
            cfg, _ = VendorMarketingProviderConfig.objects.get_or_create(vendor=vendor, provider=key)
            cfg.is_active = bool(request.POST.get(f"provider_active_{key}"))
            blob = dict(cfg.config or {})
            for fkey, _label in fields.get(key, []):
                blob[fkey] = (request.POST.get(f"cfg_{key}__{fkey}") or "").strip()
            cfg.config = blob
            cfg.save()
        messages.success(request, "Sales channel settings saved.")
        return redirect(reverse("vendor-settings-sales-channels", kwargs={"subdomain": vendor.subdomain}))

    providers = []
    for key in keys:
        cfg, _ = VendorMarketingProviderConfig.objects.get_or_create(vendor=vendor, provider=key)
        cfg_blob = cfg.config or {}
        providers.append(
            {
                "key": key,
                "label": providers_map.get(key, key.title()),
                "help": "Enable connection for this channel.",
                "is_active": bool(cfg.is_active),
                "updated_at": cfg.updated_at,
                "fields": [
                    {
                        "key": fkey,
                        "label": label,
                        "value": str(cfg_blob.get(fkey) or ""),
                        "placeholder": "",
                    }
                    for fkey, label in fields.get(key, [])
                ],
            }
        )
    return render(
        request,
        "storefront/vendor_settings_sales_channels.html",
        {
            **_vendor_admin_context(request=request, vendor=vendor, page="settings_sales_channels", breadcrumb="Settings > Sales channels"),
            "providers": providers,
        },
    )


@login_required
def vendor_settings_domains(request, subdomain: str):
    vendor = _resolve_vendor_from_path(subdomain)
    ensure_vendor_access(request=request, vendor=vendor)
    settings_obj, _ = VendorStoreSettings.objects.get_or_create(vendor=vendor)

    from vendors.services.store_settings import get_settings_blob, set_settings_blob

    if request.method == "POST":
        blob = get_settings_blob(settings_obj)
        blob["custom_domain"] = (request.POST.get("custom_domain") or "").strip()
        set_settings_blob(settings_obj, blob)
        settings_obj.save(update_fields=["settings_json", "updated_at"])
        messages.success(request, "Domain settings saved.")
        return redirect(reverse("vendor-settings-domains", kwargs={"subdomain": vendor.subdomain}))

    blob = get_settings_blob(settings_obj)
    return render(
        request,
        "storefront/vendor_settings_domains.html",
        {
            **_vendor_admin_context(request=request, vendor=vendor, page="settings_domains", breadcrumb="Settings > Domains"),
            "custom_domain": blob.get("custom_domain") or "",
        },
    )


@login_required
def vendor_settings_customer_events(request, subdomain: str):
    vendor = _resolve_vendor_from_path(subdomain)
    ensure_vendor_access(request=request, vendor=vendor)
    recent_orders = StoreOrder.objects.filter(vendor=vendor).order_by("-created_at")[:50]
    return render(
        request,
        "storefront/vendor_settings_customer_events.html",
        {
            **_vendor_admin_context(request=request, vendor=vendor, page="settings_customer_events", breadcrumb="Settings > Customer events"),
            "recent_orders": recent_orders,
        },
    )


@login_required
def vendor_settings_metafields(request, subdomain: str):
    vendor = _resolve_vendor_from_path(subdomain)
    ensure_vendor_access(request=request, vendor=vendor)
    settings_obj, _ = VendorStoreSettings.objects.get_or_create(vendor=vendor)

    from vendors.services.store_settings import get_settings_blob, set_settings_blob

    blob = get_settings_blob(settings_obj)
    metafields = blob.get("metafields") or []
    if not isinstance(metafields, list):
        metafields = []

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip().lower()
        if action == "add":
            ns = (request.POST.get("namespace") or "").strip()[:64] or "storefront"
            key = (request.POST.get("key") or "").strip()[:120]
            val = (request.POST.get("value") or "").strip()[:500]
            if not key:
                messages.error(request, "Key is required.")
            else:
                metafields.append({"namespace": ns, "key": key, "value": val})
                blob["metafields"] = metafields
                set_settings_blob(settings_obj, blob)
                settings_obj.save(update_fields=["settings_json", "updated_at"])
                messages.success(request, "Metafield added.")
            return redirect(reverse("vendor-settings-metafields", kwargs={"subdomain": vendor.subdomain}))

        if action == "delete":
            try:
                idx = int((request.POST.get("idx") or "").strip())
            except Exception:
                idx = -1
            if 0 <= idx < len(metafields):
                metafields.pop(idx)
                blob["metafields"] = metafields
                set_settings_blob(settings_obj, blob)
                settings_obj.save(update_fields=["settings_json", "updated_at"])
                messages.success(request, "Metafield deleted.")
            return redirect(reverse("vendor-settings-metafields", kwargs={"subdomain": vendor.subdomain}))

    return render(
        request,
        "storefront/vendor_settings_metafields.html",
        {
            **_vendor_admin_context(request=request, vendor=vendor, page="settings_metafields", breadcrumb="Settings > Metafields"),
            "metafields": metafields,
        },
    )


def _vendor_company(vendor: Vendor):
    try:
        return getattr(getattr(vendor.owner, "userprofile", None), "company", None)
    except Exception:
        return None


def _vendor_leads_queryset(*, vendor: Vendor):
    from leads.models import Lead

    company = _vendor_company(vendor)
    qs = Lead.objects.all()
    if company:
        qs = qs.filter(company=company)
    else:
        qs = qs.filter(created_by=vendor.owner)
    return qs


@login_required
def vendor_marketing_campaigns(request, subdomain: str):
    from marketing.models import Campaign

    vendor = _resolve_vendor_from_path(subdomain)
    ensure_vendor_access(request=request, vendor=vendor)
    company = _vendor_company(vendor)
    qs = Campaign.objects.all()
    if company:
        qs = qs.filter(company=company)
    else:
        qs = qs.filter(created_by=vendor.owner)
    qs = qs.order_by("-created_at")[:100]
    return render(
        request,
        "storefront/vendor_marketing_campaigns.html",
        {**_vendor_admin_context(request=request, vendor=vendor, page="settings_marketing", breadcrumb="Marketing > Campaigns"), "campaigns": qs},
    )


@login_required
def vendor_marketing_campaign_create(request, subdomain: str):
    from marketing.models import Campaign
    from marketing.services import generate_ad_copy

    vendor = _resolve_vendor_from_path(subdomain)
    ensure_vendor_access(request=request, vendor=vendor)
    company = _vendor_company(vendor)

    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()[:140]
        channel = (request.POST.get("channel") or "whatsapp").strip().lower()
        language = (request.POST.get("language") or "auto").strip().lower()[:16]
        objective = (request.POST.get("objective") or "promote").strip()[:80]
        product = (request.POST.get("product") or "").strip()[:160]
        ad_copy = (request.POST.get("ad_copy") or "").strip()
        if not ad_copy:
            ad_copy = generate_ad_copy(objective=objective, product=(product or vendor.name), language=("hi" if language == "hi" else "en"))

        audience = {}
        lead_status = (request.POST.get("lead_status") or "").strip()
        if lead_status:
            audience["lead_status"] = [s.strip() for s in lead_status.split(",") if s.strip()]
        pincode = (request.POST.get("pincode") or "").strip()
        if pincode:
            audience["pincode_text"] = pincode
            try:
                from location.models import Pincode

                pc = Pincode.objects.filter(code__iexact=pincode).first()
                if pc:
                    audience["pincode"] = pc.id
            except Exception:
                pass

        scheduled_at = (request.POST.get("scheduled_at") or "").strip()
        sched_dt = None
        if scheduled_at:
            try:
                from datetime import datetime

                sched_dt = datetime.strptime(scheduled_at, "%Y-%m-%d %H:%M")
            except Exception:
                sched_dt = None

        status = Campaign.Status.DRAFT
        if sched_dt:
            status = Campaign.Status.SCHEDULED

        camp = Campaign.objects.create(
            company=company,
            created_by=request.user,
            channel=channel,
            status=status,
            name=name or "Campaign",
            audience=audience,
            language=language,
            ad_copy=ad_copy,
            scheduled_at=sched_dt,
            metadata={"vendor_id": vendor.id},
        )
        messages.success(request, "Campaign created.")
        return redirect(reverse("vendor-marketing-campaign-view", kwargs={"subdomain": vendor.subdomain, "campaign_id": camp.id}))

    return render(
        request,
        "storefront/vendor_marketing_campaign_create.html",
        {**_vendor_admin_context(request=request, vendor=vendor, page="settings_marketing", breadcrumb="Marketing > New campaign")},
    )


@login_required
def vendor_marketing_campaign_view(request, subdomain: str, campaign_id: int):
    from marketing.models import Campaign, CampaignMessage, PaidAdRun

    vendor = _resolve_vendor_from_path(subdomain)
    ensure_vendor_access(request=request, vendor=vendor)
    company = _vendor_company(vendor)
    qs = Campaign.objects.all()
    if company:
        qs = qs.filter(company=company)
    camp = qs.filter(id=campaign_id).first()
    if not camp:
        raise Http404("Campaign not found")
    msgs = CampaignMessage.objects.filter(campaign=camp).order_by("-created_at")[:200]
    paid_runs = PaidAdRun.objects.filter(campaign=camp).order_by("-queued_at")[:5]
    return render(
        request,
        "storefront/vendor_marketing_campaign_view.html",
        {
            **_vendor_admin_context(request=request, vendor=vendor, page="settings_marketing", breadcrumb="Marketing > Campaign"),
            "campaign": camp,
            "messages": msgs,
            "paid_runs": paid_runs,
        },
    )


@login_required
def vendor_marketing_campaign_start(request, subdomain: str, campaign_id: int):
    from marketing.models import Campaign
    from marketing.services import start_campaign

    vendor = _resolve_vendor_from_path(subdomain)
    ensure_vendor_access(request=request, vendor=vendor)
    company = _vendor_company(vendor)
    qs = Campaign.objects.all()
    if company:
        qs = qs.filter(company=company)
    camp = qs.filter(id=campaign_id).first()
    if not camp:
        raise Http404("Campaign not found")

    if request.method != "POST":
        return redirect(reverse("vendor-marketing-campaign-view", kwargs={"subdomain": vendor.subdomain, "campaign_id": camp.id}))

    try:
        start_campaign(campaign=camp, actor=request.user)
        paid_channels = {"facebook", "instagram", "google", "ott"}
        if camp.channel in paid_channels:
            try:
                from marketing.tasks import process_paid_ad_runs

                process_paid_ad_runs.delay()
            except Exception:
                pass
            messages.success(request, "Paid ads campaign started (demo). Reports will update shortly.")
        else:
            try:
                from marketing.tasks import process_pending_campaign_messages

                process_pending_campaign_messages.delay()
            except Exception:
                pass
            messages.success(request, "Campaign started. Messages are queued for delivery.")
    except Exception as exc:
        camp.mark_failed(str(exc))
        messages.error(request, f"Campaign failed: {exc}")

    return redirect(reverse("vendor-marketing-campaign-view", kwargs={"subdomain": vendor.subdomain, "campaign_id": camp.id}))


def _vendor_products_for_creatives(vendor: Vendor):
    from storefront.models import VendorProductListing

    return (
        VendorProductListing.objects.select_related("product")
        .filter(vendor=vendor)
        .order_by("product__name")[:500]
    )


def _build_creative_gif(*, vendor: Vendor, product: Product, caption: str = "", frame_limit: int = 6):
    """
    Server-side GIF generator (no ffmpeg required).

    Produces a vertical 720x1280 animated GIF using product images.
    """

    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception as exc:
        raise RuntimeError("Pillow is required for GIF generation.") from exc

    from io import BytesIO

    from products.models import ProductMedia

    frame_limit = max(2, min(int(frame_limit or 6), 12))
    media_qs = ProductMedia.objects.filter(product=product, media_type=ProductMedia.MediaType.IMAGE).order_by("sort_order", "id")[:frame_limit]
    items = list(media_qs)
    if not items:
        raise ValueError("No product images found to generate a reel GIF.")

    frames = []
    font = ImageFont.load_default()
    w, h = 720, 1280

    brand_hex = ""
    try:
        settings_json = getattr(getattr(vendor, "store_settings", None), "settings_json", None) or {}
        brand_hex = (settings_json.get("theme_color") or settings_json.get("brand_color") or "").strip()
    except Exception:
        brand_hex = ""

    header_color = brand_hex if (brand_hex.startswith("#") and len(brand_hex) in {4, 7}) else "#111827"

    for pm in items:
        with pm.media.open("rb") as f:
            img = Image.open(f)
            img = img.convert("RGB")

        canvas = Image.new("RGB", (w, h), "white")
        # Fit image into area below header.
        target_box = (0, 140, w, h)
        tw, th = target_box[2] - target_box[0], target_box[3] - target_box[1]
        img_ratio = img.width / max(1, img.height)
        box_ratio = tw / max(1, th)
        if img_ratio > box_ratio:
            new_w = tw
            new_h = int(tw / img_ratio)
        else:
            new_h = th
            new_w = int(th * img_ratio)
        img = img.resize((max(1, new_w), max(1, new_h)))
        x = (w - img.width) // 2
        y = 140 + (th - img.height) // 2
        canvas.paste(img, (x, y))

        draw = ImageDraw.Draw(canvas)
        # Header bar
        draw.rectangle((0, 0, w, 140), fill=header_color)
        draw.text((24, 24), vendor.name[:26], fill="white", font=font)
        draw.text((24, 64), product.name[:36], fill="white", font=font)
        if caption:
            draw.text((24, 104), caption[:60], fill="white", font=font)

        frames.append(canvas)

    out = BytesIO()
    frames[0].save(
        out,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        duration=900,
        loop=0,
        optimize=True,
    )
    out.seek(0)
    return out.getvalue()


@login_required
def vendor_marketing_creatives(request, subdomain: str):
    from marketing.models import CreativeAsset

    vendor = _resolve_vendor_from_path(subdomain)
    ensure_vendor_access(request=request, vendor=vendor)

    kind = (request.GET.get("kind") or "").strip().lower()
    q = (request.GET.get("q") or "").strip()

    qs = CreativeAsset.objects.filter(vendor=vendor).order_by("-created_at")
    if kind in {"image", "reel", "gif"}:
        qs = qs.filter(kind=kind)
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(caption__icontains=q))

    creatives = list(qs[:200])
    return render(
        request,
        "storefront/vendor_marketing_creatives.html",
        {
            **_vendor_admin_context(request=request, vendor=vendor, page="settings_marketing", breadcrumb="Marketing > Creatives"),
            "creatives": creatives,
        },
    )


@login_required
def vendor_marketing_creative_create(request, subdomain: str):
    from django.core.files.base import ContentFile

    from marketing.models import CreativeAsset

    vendor = _resolve_vendor_from_path(subdomain)
    ensure_vendor_access(request=request, vendor=vendor)

    listings = _vendor_products_for_creatives(vendor)

    if request.method == "POST":
        mode = (request.POST.get("_mode") or "upload").strip().lower()
        title = (request.POST.get("title") or "").strip()[:160]
        caption = (request.POST.get("caption") or "").strip()
        template = (request.POST.get("template") or "").strip()[:60]

        if mode == "generate_gif":
            product_id = (request.POST.get("product_id") or "").strip()
            frame_limit = (request.POST.get("frame_limit") or "6").strip()
            listing = None
            try:
                from storefront.models import VendorProductListing

                listing = VendorProductListing.objects.select_related("product").filter(vendor=vendor, product_id=int(product_id)).first()
            except Exception:
                listing = None
            if not listing:
                messages.error(request, "Select a valid product for generating a reel GIF.")
                return redirect(reverse("vendor-marketing-creative-create", kwargs={"subdomain": vendor.subdomain}))

            product = listing.product
            data = _build_creative_gif(vendor=vendor, product=product, caption=caption, frame_limit=frame_limit)
            fname = f"reel_{vendor.subdomain}_{product.sku or product.id}.gif"
            asset = CreativeAsset.objects.create(
                vendor=vendor,
                product=product,
                kind=CreativeAsset.Kind.GIF,
                title=title or f"Reel GIF - {product.name}",
                caption=caption,
                template=template or "simple_gif",
                metadata={"generated": True, "frame_limit": int(frame_limit or 6)},
            )
            asset.file.save(fname, ContentFile(data), save=True)
            messages.success(request, "Reel GIF created.")
            return redirect(reverse("vendor-marketing-creatives", kwargs={"subdomain": vendor.subdomain}))

        # Default: upload
        kind = (request.POST.get("kind") or CreativeAsset.Kind.REEL).strip().lower()
        if kind not in {"image", "reel"}:
            kind = CreativeAsset.Kind.REEL

        upload = request.FILES.get("file")
        if not upload:
            messages.error(request, "Select a file to upload.")
            return redirect(reverse("vendor-marketing-creative-create", kwargs={"subdomain": vendor.subdomain}))

        product = None
        product_id = (request.POST.get("product_id") or "").strip()
        if product_id:
            try:
                from storefront.models import VendorProductListing

                listing = VendorProductListing.objects.select_related("product").filter(vendor=vendor, product_id=int(product_id)).first()
                product = listing.product if listing else None
            except Exception:
                product = None

        asset = CreativeAsset.objects.create(
            vendor=vendor,
            product=product,
            kind=(CreativeAsset.Kind.IMAGE if kind == "image" else CreativeAsset.Kind.REEL),
            title=title or (upload.name[:160]),
            caption=caption,
            template=template,
            metadata={"uploaded": True, "content_type": getattr(upload, "content_type", "")},
        )
        asset.file.save(upload.name, upload, save=True)
        messages.success(request, "Creative uploaded.")
        return redirect(reverse("vendor-marketing-creatives", kwargs={"subdomain": vendor.subdomain}))

    return render(
        request,
        "storefront/vendor_marketing_creative_create.html",
        {
            **_vendor_admin_context(request=request, vendor=vendor, page="settings_marketing", breadcrumb="Marketing > New creative"),
            "listings": listings,
        },
    )


@login_required
def vendor_marketing_creative_delete(request, subdomain: str, creative_id: int):
    from marketing.models import CreativeAsset

    vendor = _resolve_vendor_from_path(subdomain)
    ensure_vendor_access(request=request, vendor=vendor)

    asset = CreativeAsset.objects.filter(vendor=vendor, id=creative_id).first()
    if not asset:
        raise Http404("Creative not found")

    if request.method == "POST":
        try:
            if asset.file:
                asset.file.delete(save=False)
        except Exception:
            pass
        asset.delete()
        messages.success(request, "Creative deleted.")
        return redirect(reverse("vendor-marketing-creatives", kwargs={"subdomain": vendor.subdomain}))

    return redirect(reverse("vendor-marketing-creatives", kwargs={"subdomain": vendor.subdomain}))


@login_required
def vendor_marketing_leads(request, subdomain: str):
    from leads.models import Lead

    vendor = _resolve_vendor_from_path(subdomain)
    ensure_vendor_access(request=request, vendor=vendor)

    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip().lower()
    assigned = (request.GET.get("assigned") or "").strip().lower()
    followup = (request.GET.get("followup") or "").strip().lower()

    qs = _vendor_leads_queryset(vendor=vendor).order_by("-created_at")
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(mobile__icontains=q) | Q(email__icontains=q))
    if status and status in {c[0] for c in Lead.Status.choices}:
        qs = qs.filter(status=status)
    if assigned == "me":
        qs = qs.filter(assigned_to=request.user)
    if followup == "due":
        qs = qs.filter(next_followup_at__isnull=False, next_followup_at__lte=timezone.now())
    if followup == "scheduled":
        qs = qs.filter(next_followup_at__isnull=False)

    leads = list(qs[:200])
    due_count = _vendor_leads_queryset(vendor=vendor).filter(next_followup_at__isnull=False, next_followup_at__lte=timezone.now()).count()

    return render(
        request,
        "storefront/vendor_marketing_leads.html",
        {
            **_vendor_admin_context(request=request, vendor=vendor, page="settings_marketing", breadcrumb="Marketing > Leads"),
            "leads": leads,
            "q": q,
            "status": status,
            "assigned": assigned,
            "followup": followup,
            "due_count": due_count,
        },
    )


@login_required
def vendor_marketing_lead_view(request, subdomain: str, lead_id: int):
    from leads.models import Lead, LeadActivity

    vendor = _resolve_vendor_from_path(subdomain)
    ensure_vendor_access(request=request, vendor=vendor)

    lead = get_object_or_404(_vendor_leads_queryset(vendor=vendor), id=lead_id)
    activities = list(LeadActivity.objects.filter(lead=lead).order_by("-created_at")[:120])
    return render(
        request,
        "storefront/vendor_marketing_lead_view.html",
        {
            **_vendor_admin_context(request=request, vendor=vendor, page="settings_marketing", breadcrumb="Marketing > Lead"),
            "lead": lead,
            "activities": activities,
        },
    )


@login_required
@require_POST
def vendor_marketing_lead_update(request, subdomain: str, lead_id: int):
    from leads.models import Lead, LeadActivity

    vendor = _resolve_vendor_from_path(subdomain)
    ensure_vendor_access(request=request, vendor=vendor)

    lead = get_object_or_404(_vendor_leads_queryset(vendor=vendor), id=lead_id)
    status = (request.POST.get("status") or "").strip().lower()
    note = (request.POST.get("note") or "").strip()
    followup_at = (request.POST.get("followup_at") or "").strip()

    updated_fields = []
    if status and status in {c[0] for c in Lead.Status.choices} and status != lead.status:
        lead.status = status
        updated_fields.append("status")

    if followup_at:
        try:
            from datetime import datetime

            dt = datetime.strptime(followup_at, "%Y-%m-%d %H:%M")
            lead.next_followup_at = dt
            updated_fields.append("next_followup_at")
        except Exception:
            messages.error(request, "Invalid followup date. Use YYYY-MM-DD HH:MM")
    elif request.POST.get("clear_followup") == "1":
        lead.next_followup_at = None
        updated_fields.append("next_followup_at")

    if updated_fields:
        updated_fields.append("updated_at")
        lead.save(update_fields=list(dict.fromkeys(updated_fields)))

    if note:
        LeadActivity.objects.create(lead=lead, actor=request.user, activity_type="note", note=note)

    messages.success(request, "Lead updated.")
    return redirect(reverse("vendor-marketing-lead-view", kwargs={"subdomain": vendor.subdomain, "lead_id": lead.id}))


@login_required
@require_POST
def vendor_marketing_lead_send(request, subdomain: str, lead_id: int):
    from leads.models import LeadActivity

    vendor = _resolve_vendor_from_path(subdomain)
    ensure_vendor_access(request=request, vendor=vendor)

    lead = get_object_or_404(_vendor_leads_queryset(vendor=vendor), id=lead_id)
    channel = (request.POST.get("channel") or "whatsapp").strip().lower()
    text = (request.POST.get("message") or "").strip()

    if not text:
        messages.error(request, "Message is required.")
        return redirect(reverse("vendor-marketing-lead-view", kwargs={"subdomain": vendor.subdomain, "lead_id": lead.id}))

    from storefront.services.vendor_messaging import (
        send_vendor_email,
        send_vendor_sms,
        send_vendor_whatsapp,
        vendor_channel_enabled,
    )

    dest = ""
    ok = False
    provider = ""
    error = ""
    try:
        if channel == "sms":
            if not vendor_channel_enabled(vendor, "sms"):
                raise ValueError("SMS is OFF in Settings > Notifications.")
            dest = lead.mobile
            if not dest:
                raise ValueError("Lead mobile is missing.")
            res = send_vendor_sms(vendor=vendor, to=dest, message=text)
            ok = bool(res.ok)
            provider = res.provider
            if not ok:
                error = res.error
        elif channel == "email":
            if not vendor_channel_enabled(vendor, "email"):
                raise ValueError("Email is OFF in Settings > Notifications.")
            dest = lead.email
            if not dest:
                raise ValueError("Lead email is missing.")
            res = send_vendor_email(vendor=vendor, to=dest, subject=f"Follow-up: {vendor.name}", message=text)
            ok = bool(res.ok)
            provider = res.provider
            if not ok:
                error = res.error
        else:
            if not vendor_channel_enabled(vendor, "whatsapp"):
                raise ValueError("WhatsApp is OFF in Settings > Notifications.")
            dest = lead.mobile
            if not dest:
                raise ValueError("Lead mobile is missing.")
            res = send_vendor_whatsapp(vendor=vendor, to=dest, message=text)
            ok = bool(res.ok)
            provider = res.provider
            if not ok:
                error = res.error
    except Exception as exc:
        ok = False
        error = f"{type(exc).__name__}: {exc}"

    LeadActivity.objects.create(
        lead=lead,
        actor=request.user,
        activity_type="message",
        note=text[:2000],
        payload={"channel": channel, "destination": dest, "ok": ok, "provider": provider, "error": error},
    )
    try:
        lead.touch_contacted()
    except Exception:
        pass

    if ok:
        messages.success(request, f"Sent via {channel}.")
    else:
        messages.error(request, f"Send failed: {error or 'unknown error'}")
    return redirect(reverse("vendor-marketing-lead-view", kwargs={"subdomain": vendor.subdomain, "lead_id": lead.id}))


@login_required
def vendor_catalogs(request, subdomain: str):
    from vendors.models import VendorCatalog
    from vendors.services.catalogs import get_default_catalog_id, set_default_catalog

    vendor = _resolve_vendor_from_path(subdomain)
    ensure_vendor_access(request=request, vendor=vendor)

    if request.method == "POST":
        action = (request.POST.get("_action") or "").strip().lower()
        cid = (request.POST.get("catalog_id") or "").strip()
        catalog = None
        try:
            if cid:
                catalog = VendorCatalog.objects.filter(vendor=vendor, id=int(cid)).first()
        except Exception:
            catalog = None

        if action == "set_default":
            if catalog:
                set_default_catalog(vendor, catalog)
                messages.success(request, "Default catalog set.")
            else:
                set_default_catalog(vendor, None)
                messages.success(request, "Default catalog cleared.")
            return redirect(reverse("vendor-catalogs", kwargs={"subdomain": vendor.subdomain}))

        if action == "toggle_active" and catalog:
            catalog.is_active = not bool(catalog.is_active)
            catalog.save(update_fields=["is_active", "updated_at"])
            messages.success(request, "Catalog updated.")
            return redirect(reverse("vendor-catalogs", kwargs={"subdomain": vendor.subdomain}))

    catalogs = VendorCatalog.objects.filter(vendor=vendor).order_by("-updated_at", "-id")[:200]
    default_id = get_default_catalog_id(vendor)
    return render(
        request,
        "storefront/vendor_catalogs.html",
        {
            **_vendor_admin_context(request=request, vendor=vendor, page="catalogs", breadcrumb="Products > Catalogs"),
            "catalogs": catalogs,
            "default_catalog_id": default_id,
        },
    )


@login_required
def vendor_catalog_create(request, subdomain: str):
    from vendors.models import VendorCatalog

    vendor = _resolve_vendor_from_path(subdomain)
    ensure_vendor_access(request=request, vendor=vendor)

    if request.method == "POST":
        title = (request.POST.get("title") or "").strip()[:255]
        is_active = bool(int((request.POST.get("is_active") or "1").strip() or "1"))
        markets = (request.POST.get("markets") or "").strip()
        markets_json = [m.strip() for m in markets.split(",") if m.strip()][:40]
        currency = (request.POST.get("currency") or "INR").strip()[:8]
        auto_include = bool(int((request.POST.get("auto_include_new_products") or "1").strip() or "1"))
        direction = (request.POST.get("price_adjustment_direction") or "decrease").strip().lower()
        include_compare = bool(int((request.POST.get("include_compare_at_price") or "0").strip() or "0"))
        try:
            pct = Decimal(str((request.POST.get("price_adjustment_percent") or "0").strip() or "0"))
        except Exception:
            pct = Decimal("0")

        c = VendorCatalog.objects.create(
            vendor=vendor,
            title=title or "Catalog",
            is_active=is_active,
            markets_json=markets_json,
            currency=currency or "INR",
            auto_include_new_products=auto_include,
            price_adjustment_direction=direction if direction in {"increase", "decrease"} else "decrease",
            price_adjustment_percent=max(Decimal("0"), pct),
            include_compare_at_price=include_compare,
        )
        messages.success(request, "Catalog created.")
        return redirect(reverse("vendor-catalog-edit", kwargs={"subdomain": vendor.subdomain, "catalog_id": c.id}))

    return render(
        request,
        "storefront/vendor_catalog_create.html",
        {**_vendor_admin_context(request=request, vendor=vendor, page="catalogs", breadcrumb="Products > New catalog")},
    )


@login_required
def vendor_catalog_edit(request, subdomain: str, catalog_id: int):
    from vendors.models import VendorCatalog, VendorCatalogProduct

    vendor = _resolve_vendor_from_path(subdomain)
    ensure_vendor_access(request=request, vendor=vendor)

    catalog = VendorCatalog.objects.filter(vendor=vendor, id=catalog_id).first()
    if not catalog:
        raise Http404("Catalog not found")

    if request.method == "POST":
        action = (request.POST.get("_action") or "").strip().lower()
        if action == "save_settings":
            title = (request.POST.get("title") or "").strip()[:255]
            catalog.title = title or catalog.title
            catalog.is_active = bool(int((request.POST.get("is_active") or "1").strip() or "1"))
            markets = (request.POST.get("markets") or "").strip()
            catalog.markets_json = [m.strip() for m in markets.split(",") if m.strip()][:40]
            catalog.currency = (request.POST.get("currency") or "INR").strip()[:8] or "INR"
            catalog.auto_include_new_products = bool(int((request.POST.get("auto_include_new_products") or "1").strip() or "1"))
            direction = (request.POST.get("price_adjustment_direction") or "decrease").strip().lower()
            catalog.price_adjustment_direction = direction if direction in {"increase", "decrease"} else "decrease"
            catalog.include_compare_at_price = bool(int((request.POST.get("include_compare_at_price") or "0").strip() or "0"))
            try:
                pct = Decimal(str((request.POST.get("price_adjustment_percent") or "0").strip() or "0"))
            except Exception:
                pct = Decimal("0")
            catalog.price_adjustment_percent = max(Decimal("0"), pct)
            catalog.save()
            messages.success(request, "Catalog saved.")
            return redirect(reverse("vendor-catalog-edit", kwargs={"subdomain": vendor.subdomain, "catalog_id": catalog.id}))

        if action == "set_mode":
            lid = (request.POST.get("listing_id") or "").strip()
            mode = (request.POST.get("mode") or "").strip().lower()
            try:
                lid_int = int(lid)
            except Exception:
                lid_int = None

            if not lid_int:
                messages.error(request, "Invalid product.")
                return redirect(reverse("vendor-catalog-edit", kwargs={"subdomain": vendor.subdomain, "catalog_id": catalog.id}))

            listing = VendorProductListing.objects.filter(vendor=vendor, id=lid_int).first()
            if not listing:
                messages.error(request, "Product not found.")
                return redirect(reverse("vendor-catalog-edit", kwargs={"subdomain": vendor.subdomain, "catalog_id": catalog.id}))

            if mode == "clear":
                VendorCatalogProduct.objects.filter(catalog=catalog, listing=listing).delete()
                messages.success(request, "Cleared rule.")
            elif mode in {"include", "exclude"}:
                obj, _ = VendorCatalogProduct.objects.get_or_create(catalog=catalog, listing=listing)
                obj.mode = mode
                obj.save(update_fields=["mode"])
                messages.success(request, "Updated rule.")
            else:
                messages.error(request, "Invalid mode.")

            # Keep current tab/q in redirect.
            tab = (request.GET.get("tab") or "all").strip().lower()
            q = (request.GET.get("q") or "").strip()
            url = reverse("vendor-catalog-edit", kwargs={"subdomain": vendor.subdomain, "catalog_id": catalog.id})
            params = []
            if tab:
                params.append(f"tab={tab}")
            if q:
                params.append(f"q={q}")
            if params:
                url = url + "?" + "&".join(params)
            return redirect(url)

    tab = (request.GET.get("tab") or "all").strip().lower()
    if tab not in {"all", "included", "excluded"}:
        tab = "all"
    q = (request.GET.get("q") or "").strip()

    base = VendorProductListing.objects.select_related("product").filter(vendor=vendor).order_by("product__name")
    if q:
        base = base.filter(Q(product__name__icontains=q) | Q(product__sku__icontains=q))

    item_map = {
        it.listing_id: it.mode
        for it in VendorCatalogProduct.objects.filter(catalog=catalog).only("listing_id", "mode")
    }

    rows = []
    for l in base[:600]:
        mode = item_map.get(l.id)
        if tab == "included" and mode != "include":
            continue
        if tab == "excluded" and mode != "exclude":
            continue
        rows.append({"listing_id": l.id, "name": l.product.name, "sku": l.product.sku, "mode": mode})

    return render(
        request,
        "storefront/vendor_catalog_edit.html",
        {
            **_vendor_admin_context(request=request, vendor=vendor, page="catalogs", breadcrumb="Products > Catalog"),
            "catalog": catalog,
            "tab": tab,
            "rows": rows,
        },
    )


@login_required
def vendor_catalog_export(request, subdomain: str, catalog_id: int):
    from vendors.models import VendorCatalog, VendorCatalogProduct

    vendor = _resolve_vendor_from_path(subdomain)
    ensure_vendor_access(request=request, vendor=vendor)

    catalog = VendorCatalog.objects.filter(vendor=vendor, id=catalog_id).first()
    if not catalog:
        raise Http404("Catalog not found")

    items = (
        VendorCatalogProduct.objects.select_related("listing", "listing__product")
        .filter(catalog=catalog)
        .order_by("mode", "-created_at")[:5000]
    )

    resp = HttpResponse(content_type="text/csv")
    resp["Content-Disposition"] = f'attachment; filename="catalog_{catalog.id}.csv"'
    writer = csv.writer(resp)
    writer.writerow(["sku", "mode"])
    for it in items:
        try:
            writer.writerow([it.listing.product.sku, it.mode])
        except Exception:
            continue
    return resp


@login_required
def vendor_catalog_import(request, subdomain: str, catalog_id: int):
    from vendors.models import VendorCatalog, VendorCatalogProduct

    vendor = _resolve_vendor_from_path(subdomain)
    ensure_vendor_access(request=request, vendor=vendor)

    catalog = VendorCatalog.objects.filter(vendor=vendor, id=catalog_id).first()
    if not catalog:
        raise Http404("Catalog not found")

    if request.method == "POST":
        f = request.FILES.get("file")
        if not f:
            messages.error(request, "Select a CSV file.")
            return redirect(reverse("vendor-catalog-import", kwargs={"subdomain": vendor.subdomain, "catalog_id": catalog.id}))

        try:
            data = f.read().decode("utf-8", errors="ignore").splitlines()
        except Exception:
            messages.error(request, "Could not read file.")
            return redirect(reverse("vendor-catalog-import", kwargs={"subdomain": vendor.subdomain, "catalog_id": catalog.id}))

        reader = csv.DictReader(data)
        updated = 0
        for row in reader:
            sku = (row.get("sku") or row.get("SKU") or "").strip()
            mode = (row.get("mode") or row.get("MODE") or "").strip().lower()
            if not sku:
                continue
            listing = VendorProductListing.objects.select_related("product").filter(vendor=vendor, product__sku__iexact=sku).first()
            if not listing:
                continue
            if mode == "clear":
                VendorCatalogProduct.objects.filter(catalog=catalog, listing=listing).delete()
                updated += 1
            elif mode in {"include", "exclude"}:
                obj, _ = VendorCatalogProduct.objects.get_or_create(catalog=catalog, listing=listing)
                obj.mode = mode
                obj.save(update_fields=["mode"])
                updated += 1
        messages.success(request, f"Imported {updated} rows.")
        return redirect(reverse("vendor-catalog-edit", kwargs={"subdomain": vendor.subdomain, "catalog_id": catalog.id}))

    return render(
        request,
        "storefront/vendor_catalog_import.html",
        {**_vendor_admin_context(request=request, vendor=vendor, page="catalogs", breadcrumb="Products > Import"), "catalog": catalog},
    )


@login_required
def vendor_catalog_rollouts(request, subdomain: str):
    from vendors.models import VendorCatalogRollout

    vendor = _resolve_vendor_from_path(subdomain)
    ensure_vendor_access(request=request, vendor=vendor)

    rollouts = (
        VendorCatalogRollout.objects.select_related("catalog")
        .filter(vendor=vendor)
        .order_by("-created_at")[:200]
    )
    return render(
        request,
        "storefront/vendor_catalog_rollouts.html",
        {
            **_vendor_admin_context(request=request, vendor=vendor, page="catalog_rollouts", breadcrumb="Catalogs > Rollouts"),
            "rollouts": rollouts,
        },
    )


@login_required
def vendor_catalog_rollout_create(request, subdomain: str):
    from vendors.models import VendorCatalog, VendorCatalogRollout

    vendor = _resolve_vendor_from_path(subdomain)
    ensure_vendor_access(request=request, vendor=vendor)

    catalogs = VendorCatalog.objects.filter(vendor=vendor).order_by("-updated_at", "-id")[:200]

    if request.method == "POST":
        title = (request.POST.get("title") or "").strip()[:255]
        cid = (request.POST.get("catalog_id") or "").strip()
        status = (request.POST.get("status") or "scheduled").strip().lower()
        markets = (request.POST.get("markets") or "").strip()
        markets_json = [m.strip() for m in markets.split(",") if m.strip()][:40]
        revert = bool(int((request.POST.get("revert_on_end") or "1").strip() or "1"))

        catalog = None
        try:
            catalog = VendorCatalog.objects.filter(vendor=vendor, id=int(cid)).first()
        except Exception:
            catalog = None
        if not catalog:
            messages.error(request, "Select a valid catalog.")
            return redirect(reverse("vendor-catalog-rollout-create", kwargs={"subdomain": vendor.subdomain}))

        starts_at_raw = (request.POST.get("starts_at") or "").strip()
        ends_at_raw = (request.POST.get("ends_at") or "").strip()
        starts_at = None
        ends_at = None
        try:
            from datetime import datetime

            starts_at = datetime.strptime(starts_at_raw, "%Y-%m-%d %H:%M") if starts_at_raw else None
            ends_at = datetime.strptime(ends_at_raw, "%Y-%m-%d %H:%M") if ends_at_raw else None
        except Exception:
            starts_at = None
            ends_at = None
        if not starts_at:
            messages.error(request, "Starts at must be in format YYYY-MM-DD HH:MM")
            return redirect(reverse("vendor-catalog-rollout-create", kwargs={"subdomain": vendor.subdomain}))

        if status not in {"draft", "scheduled"}:
            status = "scheduled"

        r = VendorCatalogRollout.objects.create(
            vendor=vendor,
            catalog=catalog,
            title=title or f"Rollout - {catalog.title}",
            status=status,
            markets_json=markets_json,
            starts_at=starts_at,
            ends_at=ends_at,
            revert_on_end=revert,
        )
        messages.success(request, "Rollout created.")
        return redirect(reverse("vendor-catalog-rollout-view", kwargs={"subdomain": vendor.subdomain, "rollout_id": r.id}))

    return render(
        request,
        "storefront/vendor_catalog_rollout_create.html",
        {**_vendor_admin_context(request=request, vendor=vendor, page="catalog_rollouts", breadcrumb="Catalogs > New rollout"), "catalogs": catalogs},
    )


@login_required
def vendor_catalog_rollout_view(request, subdomain: str, rollout_id: int):
    from vendors.models import VendorCatalog, VendorCatalogRollout

    vendor = _resolve_vendor_from_path(subdomain)
    ensure_vendor_access(request=request, vendor=vendor)

    rollout = VendorCatalogRollout.objects.select_related("catalog").filter(vendor=vendor, id=rollout_id).first()
    if not rollout:
        raise Http404("Rollout not found")

    catalogs = VendorCatalog.objects.filter(vendor=vendor).order_by("-updated_at", "-id")[:200]

    if request.method == "POST":
        action = (request.POST.get("_action") or "save").strip().lower()
        if action == "cancel":
            rollout.status = "cancelled"
            rollout.save(update_fields=["status", "updated_at"])
            messages.success(request, "Rollout cancelled.")
            return redirect(reverse("vendor-catalog-rollout-view", kwargs={"subdomain": vendor.subdomain, "rollout_id": rollout.id}))

        title = (request.POST.get("title") or "").strip()[:255]
        cid = (request.POST.get("catalog_id") or "").strip()
        status = (request.POST.get("status") or rollout.status).strip().lower()
        markets = (request.POST.get("markets") or "").strip()
        markets_json = [m.strip() for m in markets.split(",") if m.strip()][:40]
        revert = bool(int((request.POST.get("revert_on_end") or ("1" if rollout.revert_on_end else "0")).strip() or "0"))
        starts_at_raw = (request.POST.get("starts_at") or "").strip()
        ends_at_raw = (request.POST.get("ends_at") or "").strip()

        catalog = rollout.catalog
        try:
            maybe = VendorCatalog.objects.filter(vendor=vendor, id=int(cid)).first()
            if maybe:
                catalog = maybe
        except Exception:
            pass

        starts_at = rollout.starts_at
        ends_at = rollout.ends_at
        try:
            from datetime import datetime

            if starts_at_raw:
                starts_at = datetime.strptime(starts_at_raw, "%Y-%m-%d %H:%M")
            else:
                starts_at = None
            if ends_at_raw:
                ends_at = datetime.strptime(ends_at_raw, "%Y-%m-%d %H:%M")
            else:
                ends_at = None
        except Exception:
            pass

        if status not in {"draft", "scheduled", "active", "completed", "cancelled"}:
            status = rollout.status

        rollout.title = title or rollout.title
        rollout.catalog = catalog
        rollout.status = status
        rollout.markets_json = markets_json
        rollout.starts_at = starts_at
        rollout.ends_at = ends_at
        rollout.revert_on_end = revert
        rollout.save()
        messages.success(request, "Rollout saved.")
        return redirect(reverse("vendor-catalog-rollout-view", kwargs={"subdomain": vendor.subdomain, "rollout_id": rollout.id}))

    return render(
        request,
        "storefront/vendor_catalog_rollout_view.html",
        {
            **_vendor_admin_context(request=request, vendor=vendor, page="catalog_rollouts", breadcrumb="Catalogs > Rollout"),
            "rollout": rollout,
            "catalogs": catalogs,
        },
    )


@login_required
def vendor_catalog_rollouts_run_now(request, subdomain: str):
    vendor = _resolve_vendor_from_path(subdomain)
    ensure_vendor_access(request=request, vendor=vendor)
    if request.method != "POST":
        return redirect(reverse("vendor-catalog-rollouts", kwargs={"subdomain": vendor.subdomain}))

    try:
        from vendors.tasks import process_catalog_rollouts

        try:
            process_catalog_rollouts.delay()
            messages.success(request, "Rollout scheduler queued.")
        except Exception:
            # Fallback: run inline (desktop/dev).
            process_catalog_rollouts()
            messages.success(request, "Rollout scheduler ran.")
    except Exception as exc:
        messages.error(request, f"Scheduler error: {exc}")

    return redirect(reverse("vendor-catalog-rollouts", kwargs={"subdomain": vendor.subdomain}))


@login_required
def vendor_customer_segments(request, subdomain: str):
    from vendors.models import VendorCustomerSegment

    vendor = _resolve_vendor_from_path(subdomain)
    ensure_vendor_access(request=request, vendor=vendor)

    segments = VendorCustomerSegment.objects.filter(vendor=vendor).order_by("-updated_at", "-id")[:200]
    return render(
        request,
        "storefront/vendor_customer_segments.html",
        {
            **_vendor_admin_context(request=request, vendor=vendor, page="customer_segments", breadcrumb="Customers > Segments"),
            "segments": segments,
        },
    )


@login_required
def vendor_customer_segment_create(request, subdomain: str):
    from vendors.models import VendorCustomerSegment

    vendor = _resolve_vendor_from_path(subdomain)
    ensure_vendor_access(request=request, vendor=vendor)

    if request.method == "POST":
        title = (request.POST.get("title") or "").strip()[:200]
        is_active = bool(int((request.POST.get("is_active") or "1").strip() or "1"))
        rules = {}
        pincode = (request.POST.get("pincode") or "").strip()
        if pincode:
            rules["pincode"] = pincode
        min_orders = (request.POST.get("min_orders") or "").strip()
        if min_orders:
            rules["min_orders"] = min_orders
        min_spent = (request.POST.get("min_spent") or "").strip()
        if min_spent:
            rules["min_spent"] = min_spent
        has_company = (request.POST.get("has_company") or "").strip()
        if has_company in {"1", "0"}:
            rules["has_company"] = True if has_company == "1" else False

        notes = (request.POST.get("notes") or "").strip()
        seg = VendorCustomerSegment.objects.create(vendor=vendor, title=title or "Segment", is_active=is_active, rules_json=rules, notes=notes)
        messages.success(request, "Segment created.")
        return redirect(reverse("vendor-customer-segment-view", kwargs={"subdomain": vendor.subdomain, "segment_id": seg.id}))

    return render(
        request,
        "storefront/vendor_customer_segment_create.html",
        {**_vendor_admin_context(request=request, vendor=vendor, page="customer_segments", breadcrumb="Customers > New segment")},
    )


@login_required
def vendor_customer_segment_view(request, subdomain: str, segment_id: int):
    from vendors.models import VendorCustomerSegment
    from vendors.services.customer_segments import preview_segment, segment_count

    vendor = _resolve_vendor_from_path(subdomain)
    ensure_vendor_access(request=request, vendor=vendor)

    seg = VendorCustomerSegment.objects.filter(vendor=vendor, id=segment_id).first()
    if not seg:
        raise Http404("Segment not found")

    if request.method == "POST":
        action = (request.POST.get("_action") or "save").strip().lower()
        if action == "save":
            seg.title = (request.POST.get("title") or "").strip()[:200] or seg.title
            seg.is_active = bool(int((request.POST.get("is_active") or ("1" if seg.is_active else "0")).strip() or "0"))
            rules = dict(seg.rules_json or {})
            pincode = (request.POST.get("pincode") or "").strip()
            if pincode:
                rules["pincode"] = pincode
            else:
                rules.pop("pincode", None)
            min_orders = (request.POST.get("min_orders") or "").strip()
            if min_orders:
                rules["min_orders"] = min_orders
            else:
                rules.pop("min_orders", None)
            min_spent = (request.POST.get("min_spent") or "").strip()
            if min_spent:
                rules["min_spent"] = min_spent
            else:
                rules.pop("min_spent", None)
            has_company = (request.POST.get("has_company") or "").strip()
            if has_company in {"1", "0"}:
                rules["has_company"] = True if has_company == "1" else False
            else:
                rules.pop("has_company", None)
            seg.rules_json = rules
            seg.notes = (request.POST.get("notes") or "").strip()
            seg.save()
            messages.success(request, "Segment saved.")
        return redirect(reverse("vendor-customer-segment-view", kwargs={"subdomain": vendor.subdomain, "segment_id": seg.id}))

    preview = list(preview_segment(segment=seg, limit=50))
    match_count = segment_count(segment=seg)
    return render(
        request,
        "storefront/vendor_customer_segment_view.html",
        {
            **_vendor_admin_context(request=request, vendor=vendor, page="customer_segments", breadcrumb="Customers > Segment"),
            "segment": seg,
            "preview": preview,
            "match_count": match_count,
        },
    )


@login_required
def vendor_customer_companies(request, subdomain: str):
    from vendors.models import VendorCustomerCompany

    vendor = _resolve_vendor_from_path(subdomain)
    ensure_vendor_access(request=request, vendor=vendor)

    if request.method == "POST":
        action = (request.POST.get("_action") or "").strip().lower()
        if action == "create_company":
            name = (request.POST.get("name") or "").strip()[:200]
            if not name:
                messages.error(request, "Company name is required.")
                return redirect(reverse("vendor-customer-companies", kwargs={"subdomain": vendor.subdomain}))
            c = VendorCustomerCompany.objects.create(
                vendor=vendor,
                name=name,
                gstin=(request.POST.get("gstin") or "").strip()[:32],
                phone=(request.POST.get("phone") or "").strip()[:20],
                email=(request.POST.get("email") or "").strip(),
                address=(request.POST.get("address") or "").strip(),
            )
            messages.success(request, "Company added.")
            return redirect(reverse("vendor-customer-company-view", kwargs={"subdomain": vendor.subdomain, "company_id": c.id}))

    companies = VendorCustomerCompany.objects.filter(vendor=vendor).order_by("-updated_at", "-id")[:200]
    return render(
        request,
        "storefront/vendor_customer_companies.html",
        {
            **_vendor_admin_context(request=request, vendor=vendor, page="customer_companies", breadcrumb="Customers > Companies"),
            "companies": companies,
        },
    )


@login_required
def vendor_customer_company_view(request, subdomain: str, company_id: int):
    User = get_user_model()
    from vendors.models import VendorCustomerCompany, VendorCustomerCompanyMember

    vendor = _resolve_vendor_from_path(subdomain)
    ensure_vendor_access(request=request, vendor=vendor)

    company = VendorCustomerCompany.objects.filter(vendor=vendor, id=company_id).first()
    if not company:
        raise Http404("Company not found")

    if request.method == "POST":
        action = (request.POST.get("_action") or "").strip().lower()
        if action == "save_company":
            company.name = (request.POST.get("name") or "").strip()[:200] or company.name
            company.phone = (request.POST.get("phone") or "").strip()[:20]
            company.gstin = (request.POST.get("gstin") or "").strip()[:32]
            company.email = (request.POST.get("email") or "").strip()
            company.address = (request.POST.get("address") or "").strip()
            company.is_active = bool(int((request.POST.get("is_active") or ("1" if company.is_active else "0")).strip() or "0"))
            company.save()
            messages.success(request, "Company saved.")
            return redirect(reverse("vendor-customer-company-view", kwargs={"subdomain": vendor.subdomain, "company_id": company.id}))

        if action == "add_member":
            email = (request.POST.get("email") or "").strip()
            mobile = (request.POST.get("mobile") or "").strip()
            role = (request.POST.get("role") or "").strip()[:60]
            user = None
            if email:
                user = User.objects.filter(email__iexact=email).first()
            if not user and mobile:
                user = User.objects.filter(mobile__iexact=mobile).first()
            if not user:
                messages.error(request, "User not found. Create/login the customer first, then add.")
                return redirect(reverse("vendor-customer-company-view", kwargs={"subdomain": vendor.subdomain, "company_id": company.id}))
            m, _ = VendorCustomerCompanyMember.objects.get_or_create(company=company, user=user)
            m.role = role
            m.is_active = True
            m.save()
            messages.success(request, "Member linked.")
            return redirect(reverse("vendor-customer-company-view", kwargs={"subdomain": vendor.subdomain, "company_id": company.id}))

        if action == "toggle_member":
            mid = (request.POST.get("member_id") or "").strip()
            m = None
            try:
                m = VendorCustomerCompanyMember.objects.select_related("user").filter(company=company, id=int(mid)).first()
            except Exception:
                m = None
            if not m:
                messages.error(request, "Member not found.")
            else:
                m.is_active = not bool(m.is_active)
                m.save(update_fields=["is_active"])
                messages.success(request, "Member updated.")
            return redirect(reverse("vendor-customer-company-view", kwargs={"subdomain": vendor.subdomain, "company_id": company.id}))

    members = VendorCustomerCompanyMember.objects.select_related("user").filter(company=company).order_by("-is_active", "-id")[:500]
    return render(
        request,
        "storefront/vendor_customer_company_view.html",
        {
            **_vendor_admin_context(request=request, vendor=vendor, page="customer_companies", breadcrumb="Customers > Company"),
            "company": company,
            "members": members,
        },
    )


@login_required
def vendor_coupons(request, subdomain: str):
    """
    Vendor-facing coupon enable/disable screen.

    Coupons are created centrally in Billing/Commerce (`commerce.Coupon`).
    Vendor can decide which codes appear in their store checkout/cart.

    Smart behavior:
    - If vendor has no overrides, storefront uses "admin defaults" (all active discount coupons).
    - If vendor has overrides, only enabled VendorCoupon rows are allowed.
    """
    vendor = _resolve_vendor_from_path(subdomain)
    ensure_vendor_access(request=request, vendor=vendor)

    from commerce.models import Coupon

    now = timezone.now()
    q = (request.GET.get("q") or "").strip()
    base = Coupon.objects.filter(is_active=True, valid_from__lte=now).filter(Q(valid_until__isnull=True) | Q(valid_until__gte=now))
    if q:
        base = base.filter(Q(code__icontains=q) | Q(title__icontains=q) | Q(description__icontains=q))

    coupons = list(base.order_by("-created_at")[:200])

    has_overrides = VendorCoupon.objects.filter(vendor=vendor).exists()
    enabled_ids = set(VendorCoupon.objects.filter(vendor=vendor, is_active=True).values_list("coupon_id", flat=True))

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip().lower()
        if action == "reset":
            VendorCoupon.objects.filter(vendor=vendor).delete()
            messages.success(request, "Coupon settings reset to admin defaults.")
            return redirect(reverse("vendor-coupons", kwargs={"subdomain": vendor.subdomain}))

        if action == "enable_all":
            for c in coupons:
                VendorCoupon.objects.update_or_create(vendor=vendor, coupon=c, defaults={"is_active": True})
            messages.success(request, "Enabled all active coupons for your store.")
            return redirect(reverse("vendor-coupons", kwargs={"subdomain": vendor.subdomain}))

        if action == "disable_all":
            for c in coupons:
                VendorCoupon.objects.update_or_create(vendor=vendor, coupon=c, defaults={"is_active": False})
            messages.success(request, "Disabled all coupons for your store.")
            return redirect(reverse("vendor-coupons", kwargs={"subdomain": vendor.subdomain}))

        coupon_id = int(request.POST.get("coupon_id") or 0)
        is_active = (request.POST.get("is_active") or "").strip().lower() in {"1", "true", "yes", "on"}
        coupon = Coupon.objects.filter(id=coupon_id).first()
        if not coupon:
            messages.error(request, "Coupon not found.")
            return redirect(reverse("vendor-coupons", kwargs={"subdomain": vendor.subdomain}))

        VendorCoupon.objects.update_or_create(vendor=vendor, coupon=coupon, defaults={"is_active": is_active})
        messages.success(request, f"{'Enabled' if is_active else 'Disabled'}: {coupon.code}")
        return redirect(reverse("vendor-coupons", kwargs={"subdomain": vendor.subdomain}) + (f"?q={q}" if q else ""))

    # Rows for template
    rows = []
    for c in coupons:
        enabled = (c.id in enabled_ids) if has_overrides else (c.coupon_type == "discount")
        rows.append({"coupon": c, "enabled": enabled})

    return render(
        request,
        "storefront/vendor_coupons.html",
        {
            **_vendor_admin_context(request=request, vendor=vendor, page="coupons", breadcrumb="Admin > Discounts"),
            "rows": rows,
            "q": q,
            "has_overrides": has_overrides,
            "referral_bonus_customer": Decimal("25.00"),
            "referral_bonus_referrer": Decimal("25.00"),
        },
    )


@login_required
@require_GET
def vendor_orders_report_csv(request, subdomain: str):
    vendor = _resolve_vendor_from_path(subdomain)
    ensure_vendor_access(request=request, vendor=vendor)

    try:
        days = int(request.GET.get("days") or 30)
    except Exception:
        days = 30
    days = max(1, min(days, 365))
    start_date = timezone.localdate() - timedelta(days=days - 1)

    status_q = (request.GET.get("status") or "").strip().lower()
    pay_q = (request.GET.get("payment") or "").strip().lower()
    paid_only = str(request.GET.get("paid_only") or "").strip().lower() in {"1", "true", "yes", "on"}

    qs = StoreOrder.objects.filter(vendor=vendor, created_at__date__gte=start_date).order_by("-created_at")
    if status_q:
        qs = qs.filter(status=status_q)
    if pay_q:
        qs = qs.filter(payment_status=pay_q)
    if paid_only:
        qs = qs.filter(payment_status=StoreOrder.PaymentStatus.PAID)

    resp = HttpResponse(content_type="text/csv")
    resp["Content-Disposition"] = f'attachment; filename="{vendor.subdomain}_orders_{days}d.csv"'
    w = csv.writer(resp)
    w.writerow(
        [
            "order_number",
            "created_at",
            "status",
            "payment_status",
            "total_amount",
            "shipment_provider",
            "shipment_status",
            "tracking_number",
        ]
    )
    for o in qs.iterator(chunk_size=500):
        shipment = getattr(o, "shipment", None)
        w.writerow(
            [
                o.order_number,
                o.created_at.isoformat() if o.created_at else "",
                o.status,
                o.payment_status,
                str(o.total_amount),
                getattr(shipment, "provider", "") if shipment else "",
                getattr(shipment, "status", "") if shipment else "",
                getattr(shipment, "tracking_number", "") if shipment else "",
            ]
        )
    return resp


@login_required
def vendor_orders(request, subdomain: str):
    vendor = _resolve_vendor_from_path(subdomain)
    ensure_vendor_access(request=request, vendor=vendor)
    status_q = (request.GET.get("status") or "").strip().lower()
    q = (request.GET.get("q") or "").strip()
    pay_q = (request.GET.get("payment") or "").strip().lower()
    qs = StoreOrder.objects.filter(vendor=vendor).order_by("-created_at")
    if status_q:
        qs = qs.filter(status=status_q)
    if pay_q:
        qs = qs.filter(payment_status=pay_q)
    if q:
        qs = qs.filter(order_number__icontains=q)
    return render(
        request,
        "storefront/vendor_orders.html",
        {
            **_vendor_admin_context(request=request, vendor=vendor, page="orders", breadcrumb="Admin > Orders"),
            "orders": qs[:200],
        },
    )


@login_required
def vendor_products(request, subdomain: str):
    vendor = _resolve_vendor_from_path(subdomain)
    ensure_vendor_access(request=request, vendor=vendor)

    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip().lower()  # online/draft/all

    qs = VendorProductListing.objects.select_related("product", "product__category").filter(vendor=vendor)
    if q:
        qs = qs.filter(
            Q(product__name__icontains=q) | Q(product__sku__icontains=q) | Q(title__icontains=q) | Q(description__icontains=q)
        )
    if status == "online":
        qs = qs.filter(is_online=True)
    elif status == "draft":
        qs = qs.filter(is_online=False)

    qs = qs.order_by("-is_featured", "-updated_at", "-id")
    paginator = Paginator(qs, 30)
    page_obj = paginator.get_page(request.GET.get("page") or 1)

    # Inventory snapshot for primary warehouse.
    inv_map = {}
    try:
        wh_id = vendor.primary_warehouse_id
        if wh_id:
            inv = WarehouseInventory.objects.filter(warehouse_id=wh_id, product_id__in=[l.product_id for l in page_obj.object_list])
            inv_map = {row.product_id: row.sellable_qty for row in inv}
    except Exception:
        inv_map = {}

    return render(
        request,
        "storefront/vendor_products.html",
        {
            **_vendor_admin_context(request=request, vendor=vendor, page="products", breadcrumb="Admin > Products"),
            "listings": page_obj.object_list,
            "page_obj": page_obj,
            "q": q,
            "status": status,
            "inv_map": inv_map,
        },
    )


@login_required
def vendor_products_bulk_import(request, subdomain: str):
    """
    Shopify-like bulk add/update products:
    - Upserts billing `commerce.Product` scoped by vendor owner.
    - Syncs to storefront catalog (`products.Product`) and creates draft vendor listings.
    - Optionally loads images/videos from a ZIP and stores them as `products.ProductMedia`.

    CSV columns:
      required: sku,name,price,stock
      optional: category,description,gst_rate,hsn_code,unit,image,video,tags,is_b2b_only
    Media columns can contain one or multiple filenames separated by ';'.
    """

    vendor = _resolve_vendor_from_path(subdomain)
    ensure_vendor_access(request=request, vendor=vendor)

    result = None
    if request.method == "POST":
        errors = []
        created = 0
        updated = 0
        media_added = 0
        skipped = 0

        default_listing_online = bool(int((request.POST.get("default_listing_online") or "0").strip() or "0"))

        csv_file = request.FILES.get("csv_file")
        if not csv_file:
            messages.error(request, "CSV file is required.")
            return redirect(reverse("vendor-products-bulk-import", kwargs={"subdomain": vendor.subdomain}))

        media_map = {}
        media_zip = request.FILES.get("media_zip")
        if media_zip:
            try:
                import zipfile

                with zipfile.ZipFile(media_zip) as zf:
                    for info in zf.infolist():
                        if info.is_dir():
                            continue
                        name = (info.filename or "").replace("\\", "/").split("/")[-1].strip()
                        if not name:
                            continue
                        # Soft limit to avoid huge zips in dev.
                        if info.file_size and int(info.file_size) > 25 * 1024 * 1024:
                            continue
                        media_map[name] = zf.read(info)
            except Exception as exc:
                errors.append(f"ZIP read error: {exc}")
                media_map = {}

        try:
            raw = csv_file.read().decode("utf-8-sig", errors="ignore").splitlines()
        except Exception:
            raw = []
        if not raw:
            messages.error(request, "CSV is empty/unreadable.")
            return redirect(reverse("vendor-products-bulk-import", kwargs={"subdomain": vendor.subdomain}))

        reader = csv.DictReader(raw)
        rows = list(reader)
        if not rows:
            messages.error(request, "CSV has no rows.")
            return redirect(reverse("vendor-products-bulk-import", kwargs={"subdomain": vendor.subdomain}))

        from django.core.files.base import ContentFile

        from commerce.models import Category as BillingCategory
        from commerce.models import Product as BillingProduct
        from products.models import Product as CatalogProduct
        from products.models import ProductMedia
        from storefront.models import VendorProductListing
        from storefront.services.commerce_product_sync import sync_commerce_product_to_storefront

        owner = vendor.owner

        def _split_files(v: str):
            v = (v or "").strip()
            if not v:
                return []
            parts = []
            for chunk in v.replace(",", ";").split(";"):
                c = chunk.strip()
                if c:
                    parts.append(c)
            return parts[:12]

        for idx, row in enumerate(rows, start=2):  # header line is 1
            try:
                sku = (row.get("sku") or row.get("SKU") or "").strip()
                name = (row.get("name") or row.get("title") or row.get("Name") or "").strip()
                price_raw = (row.get("price") or row.get("Price") or "0").strip()
                stock_raw = (row.get("stock") or row.get("Stock") or "0").strip()
                if not sku or not name:
                    skipped += 1
                    continue

                try:
                    price = Decimal(str(price_raw or "0"))
                except Exception:
                    price = Decimal("0")
                try:
                    stock = int(str(stock_raw or "0"))
                except Exception:
                    stock = 0

                cat_name = (row.get("category") or row.get("Category") or "").strip()
                cat_obj = None
                if cat_name:
                    cat_obj, _ = BillingCategory.objects.get_or_create(owner=owner, name=cat_name[:100])

                description = (row.get("description") or row.get("Description") or "").strip()
                unit = (row.get("unit") or "pcs").strip()[:50] or "pcs"
                hsn_code = (row.get("hsn_code") or row.get("hsn") or "").strip()[:20] or None
                gst_rate_raw = (row.get("gst_rate") or row.get("gst") or "").strip()
                try:
                    gst_rate = Decimal(str(gst_rate_raw or "0"))
                except Exception:
                    gst_rate = Decimal("0")
                is_b2b_only_raw = (row.get("is_b2b_only") or "").strip()
                is_b2b_only = is_b2b_only_raw in {"1", "true", "yes", "on"}

                bp = BillingProduct.objects.filter(sku=sku).first()
                if bp:
                    BillingProduct.objects.filter(id=bp.id).update(
                        name=name[:100],
                        category=cat_obj,
                        price=price,
                        stock=max(0, stock),
                        description=description,
                        unit=unit,
                        hsn_code=hsn_code,
                        gst_rate=gst_rate,
                        owner=owner,
                    )
                    bp.refresh_from_db()
                    updated += 1
                else:
                    bp = BillingProduct.objects.create(
                        sku=sku,
                        name=name[:100],
                        category=cat_obj,
                        price=price,
                        stock=max(0, stock),
                        description=description,
                        unit=unit,
                        hsn_code=hsn_code,
                        gst_rate=gst_rate,
                        owner=owner,
                    )
                    created += 1

                # Sync to catalog + inventory + listing.
                sync_commerce_product_to_storefront(commerce_product=bp)

                cp = CatalogProduct.objects.filter(sku=sku).first()
                if cp:
                    # Store optional tags/type/vendor_name
                    tags = (row.get("tags") or "").strip()
                    if tags:
                        cp.tags_json = [t.strip() for t in tags.split(",") if t.strip()][:50]
                    cp.is_b2b_only = bool(is_b2b_only)
                    cp.save(update_fields=["tags_json", "is_b2b_only"])

                    # Optional media from zip.
                    img_files = _split_files(row.get("image") or row.get("images") or "")
                    vid_files = _split_files(row.get("video") or row.get("videos") or "")
                    sort_base = (ProductMedia.objects.filter(product=cp).order_by("-sort_order", "-id").values_list("sort_order", flat=True).first() or 0) + 1
                    for fn in img_files:
                        data = media_map.get(fn)
                        if not data:
                            continue
                        sort_base += 1
                        ProductMedia.objects.create(
                            product=cp,
                            media_type="image",
                            media=ContentFile(data, name=fn),
                            alt_text=cp.name[:200],
                            sort_order=int(sort_base),
                        )
                        media_added += 1
                    for fn in vid_files:
                        data = media_map.get(fn)
                        if not data:
                            continue
                        sort_base += 1
                        ProductMedia.objects.create(
                            product=cp,
                            media_type="video",
                            media=ContentFile(data, name=fn),
                            alt_text=cp.name[:200],
                            sort_order=int(sort_base),
                        )
                        media_added += 1

                # Default listing online toggle.
                try:
                    listing = VendorProductListing.objects.filter(vendor=vendor, product__sku=sku).first()
                    if listing and default_listing_online:
                        if not listing.is_online:
                            listing.is_online = True
                            listing.save(update_fields=["is_online", "updated_at"])
                except Exception:
                    pass
            except Exception as exc:
                errors.append(f"Line {idx}: {type(exc).__name__}: {exc}")

        if errors:
            messages.warning(request, "Imported with some errors.")
        else:
            messages.success(request, "Bulk import completed.")

        result = {
            "created": created,
            "updated": updated,
            "media_added": media_added,
            "skipped": skipped,
            "errors": errors[:30],
        }

    return render(
        request,
        "storefront/vendor_products_bulk_import.html",
        {
            **_vendor_admin_context(request=request, vendor=vendor, page="products", breadcrumb="Admin > Products > Bulk import"),
            "result": result,
        },
    )


@login_required
def vendor_product_edit(request, subdomain: str, listing_id: int):
    vendor = _resolve_vendor_from_path(subdomain)
    ensure_vendor_access(request=request, vendor=vendor)
    listing = get_object_or_404(
        VendorProductListing.objects.select_related("product", "product__category"),
        vendor=vendor,
        id=listing_id,
    )
    if request.method == "POST":
        form = VendorProductListingForm(request.POST, instance=listing)
        if form.is_valid():
            form.save()
            messages.success(request, "Listing updated.")
            return redirect(reverse("vendor-products", kwargs={"subdomain": vendor.subdomain}))
    else:
        form = VendorProductListingForm(instance=listing)

    inv_qty = None
    try:
        if vendor.primary_warehouse_id:
            inv = WarehouseInventory.objects.filter(warehouse_id=vendor.primary_warehouse_id, product_id=listing.product_id).first()
            inv_qty = inv.sellable_qty if inv else None
    except Exception:
        inv_qty = None

    return render(
        request,
        "storefront/vendor_product_edit.html",
        {
            **_vendor_admin_context(request=request, vendor=vendor, page="products", breadcrumb="Admin > Products > Edit"),
            "listing": listing,
            "form": form,
            "inv_qty": inv_qty,
        },
    )


@login_required
@require_POST
def vendor_product_media_upload(request, subdomain: str, listing_id: int):
    vendor = _resolve_vendor_from_path(subdomain)
    ensure_vendor_access(request=request, vendor=vendor)
    listing = get_object_or_404(VendorProductListing.objects.select_related("product"), vendor=vendor, id=listing_id)

    files = request.FILES.getlist("media_files")
    alt_text = (request.POST.get("alt_text") or "").strip()
    if not files:
        messages.error(request, "Please choose image/video files to upload.")
        return redirect(reverse("vendor-product-edit", kwargs={"subdomain": vendor.subdomain, "listing_id": listing.id}))

    max_sort = (
        ProductMedia.objects.filter(product_id=listing.product_id)
        .order_by("-sort_order", "-id")
        .values_list("sort_order", flat=True)
        .first()
        or 0
    )
    created = 0
    for f in files[:10]:
        try:
            ctype = (getattr(f, "content_type", "") or "").lower()
            media_type = "video" if ctype.startswith("video/") else "image"
            max_sort += 1
            ProductMedia.objects.create(
                product_id=listing.product_id,
                media_type=media_type,
                media=f,
                alt_text=alt_text[:200],
                sort_order=int(max_sort),
            )
            created += 1
        except Exception:
            continue

    messages.success(request, f"Uploaded {created} file(s).")
    return redirect(reverse("vendor-product-edit", kwargs={"subdomain": vendor.subdomain, "listing_id": listing.id}))


def _vendor_media_upload(*, request, vendor, listing, forced_media_type: str):
    files = request.FILES.getlist("media_files")
    alt_text = (request.POST.get("alt_text") or "").strip()
    if not files:
        messages.error(request, "Please choose files to upload.")
        return redirect(reverse("vendor-product-edit", kwargs={"subdomain": vendor.subdomain, "listing_id": listing.id}))

    max_sort = (
        ProductMedia.objects.filter(product_id=listing.product_id)
        .order_by("-sort_order", "-id")
        .values_list("sort_order", flat=True)
        .first()
        or 0
    )
    created = 0
    for f in files[:10]:
        try:
            ctype = (getattr(f, "content_type", "") or "").lower()
            if forced_media_type == "image" and not ctype.startswith("image/"):
                continue
            if forced_media_type == "video" and not ctype.startswith("video/"):
                continue
            max_sort += 1
            ProductMedia.objects.create(
                product_id=listing.product_id,
                media_type=forced_media_type,
                media=f,
                alt_text=alt_text[:200],
                sort_order=int(max_sort),
            )
            created += 1
        except Exception:
            continue

    if created <= 0:
        messages.error(request, f"No valid {forced_media_type} files uploaded.")
    else:
        messages.success(request, f"Uploaded {created} {forced_media_type}(s).")
    return redirect(reverse("vendor-product-edit", kwargs={"subdomain": vendor.subdomain, "listing_id": listing.id}))


@login_required
@require_POST
def vendor_product_media_upload_images(request, subdomain: str, listing_id: int):
    vendor = _resolve_vendor_from_path(subdomain)
    ensure_vendor_access(request=request, vendor=vendor)
    listing = get_object_or_404(VendorProductListing.objects.select_related("product"), vendor=vendor, id=listing_id)
    return _vendor_media_upload(request=request, vendor=vendor, listing=listing, forced_media_type="image")


@login_required
@require_POST
def vendor_product_media_upload_videos(request, subdomain: str, listing_id: int):
    vendor = _resolve_vendor_from_path(subdomain)
    ensure_vendor_access(request=request, vendor=vendor)
    listing = get_object_or_404(VendorProductListing.objects.select_related("product"), vendor=vendor, id=listing_id)
    return _vendor_media_upload(request=request, vendor=vendor, listing=listing, forced_media_type="video")


@login_required
@require_POST
def vendor_product_media_delete(request, subdomain: str, listing_id: int, media_id: int):
    vendor = _resolve_vendor_from_path(subdomain)
    ensure_vendor_access(request=request, vendor=vendor)
    listing = get_object_or_404(VendorProductListing.objects.select_related("product"), vendor=vendor, id=listing_id)
    media = get_object_or_404(ProductMedia, id=media_id, product_id=listing.product_id)
    try:
        media.delete()
        messages.success(request, "Media deleted.")
    except Exception:
        messages.error(request, "Unable to delete media.")
    return redirect(reverse("vendor-product-edit", kwargs={"subdomain": vendor.subdomain, "listing_id": listing.id}))

@login_required
def vendor_order_view(request, subdomain: str, order_id: int):
    vendor = _resolve_vendor_from_path(subdomain)
    ensure_vendor_access(request=request, vendor=vendor)
    order = get_object_or_404(
        StoreOrder.objects.select_related("vendor", "address", "customer", "commerce_order"),
        vendor=vendor,
        id=order_id,
    )
    return render(
        request,
        "storefront/vendor_order_view.html",
        {
            **_vendor_admin_context(request=request, vendor=vendor, page="orders", breadcrumb=f"Admin > Orders > {order.order_number}"),
            "order": order,
        },
    )


@login_required
@require_POST
def vendor_order_accept(request, subdomain: str, order_id: int):
    vendor = _resolve_vendor_from_path(subdomain)
    ensure_vendor_access(request=request, vendor=vendor)
    order = get_object_or_404(StoreOrder, vendor=vendor, id=order_id)
    # Centralized acceptance: route to Billing (commerce) order accept so ledger/voucher stays centralized.
    try:
        co = ensure_commerce_order_for_store_order(store_order=order)
    except Exception:
        messages.error(request, "Unable to sync this order to billing. Please try again.")
        return redirect(reverse("vendor-order-view", kwargs={"subdomain": vendor.subdomain, "order_id": order.id}))
    return redirect(reverse("commerce:order_action", kwargs={"order_id": co.id, "action": "accept"}))


@login_required
@require_POST
def vendor_order_reject(request, subdomain: str, order_id: int):
    vendor = _resolve_vendor_from_path(subdomain)
    ensure_vendor_access(request=request, vendor=vendor)
    order = get_object_or_404(StoreOrder, vendor=vendor, id=order_id)
    try:
        co = ensure_commerce_order_for_store_order(store_order=order)
    except Exception:
        # Fallback: still allow rejection in storefront.
        if order.status == StoreOrder.Status.PENDING:
            order.status = StoreOrder.Status.REJECTED
            order.save(update_fields=["status", "updated_at"])
            StoreOrderStatusEvent.objects.create(order=order, status=order.status, note="Rejected by vendor")
        messages.success(request, "Order rejected.")
        return redirect(reverse("vendor-order-view", kwargs={"subdomain": vendor.subdomain, "order_id": order.id}))

    return redirect(reverse("commerce:order_action", kwargs={"order_id": co.id, "action": "reject"}))


@login_required
@require_POST
def vendor_order_sync_billing(request, subdomain: str, order_id: int):
    vendor = _resolve_vendor_from_path(subdomain)
    ensure_vendor_access(request=request, vendor=vendor)
    order = get_object_or_404(StoreOrder, vendor=vendor, id=order_id)
    try:
        co = ensure_commerce_order_for_store_order(store_order=order)
    except Exception:
        messages.error(request, "Unable to sync this order to billing.")
        return redirect(reverse("vendor-order-view", kwargs={"subdomain": vendor.subdomain, "order_id": order.id}))
    messages.success(request, "Synced to billing.")
    return redirect(reverse("commerce:view_order", kwargs={"order_id": co.id}))


@login_required
@require_POST
def vendor_order_shipping_create(request, subdomain: str, order_id: int):
    vendor = _resolve_vendor_from_path(subdomain)
    ensure_vendor_access(request=request, vendor=vendor)
    order = get_object_or_404(StoreOrder, vendor=vendor, id=order_id)
    if order.status not in [StoreOrder.Status.ACCEPTED, StoreOrder.Status.PACKED, StoreOrder.Status.SHIPPED]:
        messages.error(request, "Order must be accepted before creating shipment.")
        return redirect(reverse("vendor-order-view", kwargs={"subdomain": vendor.subdomain, "order_id": order.id}))

    provider = (request.POST.get("provider") or "").strip().lower()
    if provider:
        cfg = vendor.shipping_providers.filter(provider=provider, is_active=True).first()
    else:
        cfg = vendor.shipping_providers.filter(is_active=True).order_by("provider").first()
        provider = (cfg.provider if cfg else "manual")

    shipment, created = StoreShipment.objects.get_or_create(
        order=order,
        defaults={"provider": provider, "payload": {"config": (cfg.config if cfg else {})}},
    )
    if not created and shipment.provider != provider:
        shipment.provider = provider
        shipment.save(update_fields=["provider", "updated_at"])

    try:
        from .services.shipping.provider import create_shipment

        res = create_shipment(order=order, provider=provider, config=(cfg.config if cfg else {}))
        if isinstance(res, dict):
            shipment.payload = {**(shipment.payload or {}), **{"provider_result": res}}
            tn = str(res.get("tracking_number") or "").strip()
            if tn:
                shipment.tracking_number = tn
            ext = str(res.get("external_ref") or "").strip()
            if ext:
                shipment.external_ref = ext
            cn = str(res.get("courier_name") or "").strip()
            if cn:
                shipment.courier_name = cn
            shipment.save(update_fields=["payload", "tracking_number", "external_ref", "courier_name", "updated_at"])
        messages.success(request, f"Shipment created ({provider}).")
    except Exception as exc:
        messages.error(request, f"Shipment create failed: {exc}")

    return redirect(reverse("vendor-order-view", kwargs={"subdomain": vendor.subdomain, "order_id": order.id}))


@login_required
@require_POST
def vendor_order_shipping_pickup(request, subdomain: str, order_id: int):
    vendor = _resolve_vendor_from_path(subdomain)
    ensure_vendor_access(request=request, vendor=vendor)
    order = get_object_or_404(StoreOrder, vendor=vendor, id=order_id)
    shipment = getattr(order, "shipment", None)
    if not shipment:
        messages.error(request, "No shipment found. Create shipment first.")
        return redirect(reverse("vendor-order-view", kwargs={"subdomain": vendor.subdomain, "order_id": order.id}))
    if shipment.provider != "shiprocket":
        messages.error(request, "Pickup request is available for Shiprocket only in this demo.")
        return redirect(reverse("vendor-order-view", kwargs={"subdomain": vendor.subdomain, "order_id": order.id}))
    if not shipment.external_ref:
        messages.error(request, "Missing Shiprocket shipment id. Recreate shipment.")
        return redirect(reverse("vendor-order-view", kwargs={"subdomain": vendor.subdomain, "order_id": order.id}))

    pickup_date = (request.POST.get("pickup_date") or "").strip()
    retry = str(request.POST.get("retry") or "").strip().lower() in {"1", "true", "yes", "on"}
    cfg = vendor.shipping_providers.filter(provider="shiprocket", is_active=True).first()
    if not cfg:
        messages.error(request, "Shiprocket is not configured for this vendor.")
        return redirect(reverse("vendor-order-view", kwargs={"subdomain": vendor.subdomain, "order_id": order.id}))

    try:
        from .services.shipping.shiprocket import get_token_cached, request_pickup

        api_base = str((cfg.config or {}).get("api_base") or "https://apiv2.shiprocket.in").strip()
        email = str((cfg.config or {}).get("email") or "").strip()
        password = str((cfg.config or {}).get("password") or "").strip()
        token = get_token_cached(api_base=api_base, email=email, password=password)
        if not token:
            messages.error(request, "Shiprocket auth failed (check credentials).")
            return redirect(reverse("vendor-order-view", kwargs={"subdomain": vendor.subdomain, "order_id": order.id}))

        res = request_pickup(
            api_base=api_base,
            token=token,
            shipment_ids=[shipment.external_ref],
            pickup_date=pickup_date,
            retry=retry,
        )
        shipment.payload = {**(shipment.payload or {}), **{"pickup": res}}
        if res.get("ok"):
            shipment.status = StoreShipment.Status.PICKUP_REQUESTED
            shipment.save(update_fields=["payload", "status", "updated_at"])
            messages.success(request, "Pickup requested.")
        else:
            shipment.save(update_fields=["payload", "updated_at"])
            messages.error(request, "Pickup request failed. Check payload for details.")
    except Exception as exc:
        messages.error(request, f"Pickup request failed: {exc}")

    return redirect(reverse("vendor-order-view", kwargs={"subdomain": vendor.subdomain, "order_id": order.id}))


@login_required
@require_POST
def vendor_order_shipping_track(request, subdomain: str, order_id: int):
    vendor = _resolve_vendor_from_path(subdomain)
    ensure_vendor_access(request=request, vendor=vendor)
    order = get_object_or_404(StoreOrder, vendor=vendor, id=order_id)
    shipment = getattr(order, "shipment", None)
    if not shipment:
        messages.error(request, "No shipment found.")
        return redirect(reverse("vendor-order-view", kwargs={"subdomain": vendor.subdomain, "order_id": order.id}))
    if not shipment.tracking_number:
        messages.error(request, "Missing tracking number. Create shipment first.")
        return redirect(reverse("vendor-order-view", kwargs={"subdomain": vendor.subdomain, "order_id": order.id}))

    try:
        cfg = vendor.shipping_providers.filter(provider=shipment.provider, is_active=True).first()
        config = (cfg.config if cfg else {})
        from .services.shipping.provider import track_shipment

        live = track_shipment(provider=shipment.provider, config=config, tracking_number=shipment.tracking_number)
        shipment.payload = {**(shipment.payload or {}), **{"live_track": live}}
        shipment.last_tracked_at = timezone.now()
        try:
            resp = live.get("response") or {}
            if isinstance(resp, dict):
                cur = str(resp.get("current_status") or resp.get("status") or "").strip().lower()
            else:
                cur = ""
        except Exception:
            cur = ""
        if cur in {"delivered"}:
            shipment.status = StoreShipment.Status.DELIVERED
        shipment.save(update_fields=["payload", "last_tracked_at", "status", "updated_at"])
        messages.success(request, "Tracking refreshed.")
    except Exception as exc:
        messages.error(request, f"Tracking refresh failed: {exc}")

    return redirect(reverse("vendor-order-view", kwargs={"subdomain": vendor.subdomain, "order_id": order.id}))
