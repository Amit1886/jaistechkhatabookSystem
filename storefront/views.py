from __future__ import annotations

from datetime import timedelta

from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET
from django.utils import timezone
from django.conf import settings
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django.http import HttpResponse
from django.core.files.base import ContentFile
import hmac
import hashlib
import json
import requests

from accounts.models import OTP, User
from products.models import Product
from vendors.models import Vendor

from .models import (
    Cart,
    CartItem,
    CustomerAddress,
    CustomerProfile,
    StoreOrder,
    VendorProductListing,
    Wishlist,
    WishlistItem,
)
from vendors.models import VendorPaymentGatewayConfig, VendorShippingProviderConfig
from .permissions import IsVendorUser
from .serializers import (
    CartSerializer,
    CustomerAddressSerializer,
    CustomerProfileSerializer,
    StoreOrderSerializer,
    VendorProductListingSerializer,
    VendorProductListingWriteSerializer,
    VendorSerializer,
    WishlistSerializer,
    VendorPaymentGatewayConfigSerializer,
    VendorShippingProviderConfigSerializer,
    ProductMediaSerializer,
    PlatformSettingsSerializer,
    StoreSettlementSerializer,
)
from .services.vendor_context import get_vendor_from_request
from .services.invoices import render_store_order_invoice_pdf_bytes
from .services.whatsapp_notifications import notify_order_status
from .services.recommendations import recommend_for_listing
from .services.access import ensure_vendor_access
from .services.settlements import get_platform_settings, settle_paid_order


@require_GET
def vendor_storefront_home(request):
    vendor = getattr(request, "vendor", None)
    if not vendor:
        return render(request, "storefront/no_vendor.html", status=404)
    # Render the same UI as `/store/<subdomain>/` but on vendor subdomain root.
    listings = (
        VendorProductListing.objects.select_related("product", "product__category")
        .filter(vendor=vendor, is_online=True)
        .order_by("-is_featured", "-updated_at")[:72]
    )
    from .services.session_cart import build_cart_view

    cart_view = build_cart_view(vendor=vendor, session=request.session)
    return render(
        request,
        "storefront/store_home.html",
        {"vendor": vendor, "listings": listings, "cart": cart_view, "hide_sidebar": True},
    )


@require_GET
def product_detail(request, slug):
    vendor = getattr(request, "vendor", None)
    if not vendor:
        return render(request, "storefront/no_vendor.html", status=404)
    product = get_object_or_404(Product.objects.select_related("category"), slug=slug, is_online=True)
    listing = VendorProductListing.objects.filter(vendor=vendor, product=product, is_online=True).first()
    from .services.session_cart import build_cart_view

    cart_view = build_cart_view(vendor=vendor, session=request.session)
    return render(
        request,
        "storefront/store_product_detail.html",
        {"vendor": vendor, "product": product, "listing": listing, "cart": cart_view, "hide_sidebar": True},
    )


class VendorPublicViewSet(mixins.RetrieveModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    queryset = Vendor.objects.filter(is_active=True)
    serializer_class = VendorSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        qs = super().get_queryset()
        sub = (self.request.query_params.get("subdomain") or "").strip().lower()
        if sub:
            qs = qs.filter(subdomain=sub)
        return qs.order_by("id")


class ProductPublicViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = VendorProductListingSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        vendor = get_vendor_from_request(self.request)
        qs = (
            VendorProductListing.objects.select_related("vendor", "product", "product__category")
            .filter(vendor=vendor, is_online=True)
        )
        q = (self.request.query_params.get("q") or "").strip()
        if q:
            qs = qs.filter(product__name__icontains=q)
        cat = (self.request.query_params.get("category") or "").strip()
        if cat:
            qs = qs.filter(product__category__slug=cat)
        price_min = (self.request.query_params.get("min_price") or "").strip()
        price_max = (self.request.query_params.get("max_price") or "").strip()
        if price_min:
            qs = qs.filter(product__b2c_price__gte=price_min)
        if price_max:
            qs = qs.filter(product__b2c_price__lte=price_max)
        return qs.order_by("-is_featured", "-updated_at")

    @action(detail=True, methods=["get"], permission_classes=[AllowAny])
    def recommendations(self, request, pk=None):
        vendor = get_vendor_from_request(request)
        listing = get_object_or_404(VendorProductListing, id=pk, vendor=vendor, is_online=True)
        recs = recommend_for_listing(listing=listing, limit=12)
        return Response(VendorProductListingSerializer(recs, many=True).data)


class VendorListingViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsVendorUser]
    queryset = VendorProductListing.objects.select_related("vendor", "product", "product__category").all()

    def get_serializer_class(self):
        if self.action in {"create", "update", "partial_update"}:
            return VendorProductListingWriteSerializer
        return VendorProductListingSerializer

    def get_queryset(self):
        vendor = get_vendor_from_request(self.request)
        ensure_vendor_access(request=self.request, vendor=vendor)
        qs = super().get_queryset().filter(vendor=vendor)
        is_online = (self.request.query_params.get("is_online") or "").strip().lower()
        if is_online in {"1", "true", "yes", "on"}:
            qs = qs.filter(is_online=True)
        if is_online in {"0", "false", "no", "off"}:
            qs = qs.filter(is_online=False)
        q = (self.request.query_params.get("q") or "").strip()
        if q:
            qs = qs.filter(product__name__icontains=q)
        return qs.order_by("-updated_at", "-id")

    def perform_create(self, serializer):
        vendor = get_vendor_from_request(self.request)
        ensure_vendor_access(request=self.request, vendor=vendor)
        serializer.save(vendor=vendor)

    @action(detail=True, methods=["post"])
    def set_online(self, request, pk=None):
        listing = self.get_object()
        value = request.data.get("is_online")
        listing.is_online = bool(value) if isinstance(value, bool) else str(value).strip().lower() in {"1", "true", "yes", "on"}
        listing.save(update_fields=["is_online", "updated_at"])
        return Response(VendorProductListingSerializer(listing).data)

    @action(detail=True, methods=["post"])
    def set_featured(self, request, pk=None):
        listing = self.get_object()
        value = request.data.get("is_featured")
        listing.is_featured = bool(value) if isinstance(value, bool) else str(value).strip().lower() in {"1", "true", "yes", "on"}
        listing.save(update_fields=["is_featured", "updated_at"])
        return Response(VendorProductListingSerializer(listing).data)

    @action(detail=True, methods=["post"])
    def upload_media(self, request, pk=None):
        listing = self.get_object()
        f = request.FILES.get("file")
        if not f:
            return Response({"ok": False, "error": "file is required"}, status=400)
        media_type = (request.data.get("media_type") or "image").strip().lower()
        alt_text = (request.data.get("alt_text") or "").strip()
        try:
            sort_order = int(request.data.get("sort_order") or 0)
        except Exception:
            sort_order = 0

        from products.models import ProductMedia

        pm = ProductMedia.objects.create(
            product=listing.product,
            media_type=media_type if media_type in {"image", "video"} else "image",
            media=f,
            alt_text=alt_text,
            sort_order=max(sort_order, 0),
        )
        return Response({"ok": True, "media": ProductMediaSerializer(pm).data}, status=201)


class CartViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def _get_or_create_cart(self, request, vendor):
        cart = Cart.objects.filter(vendor=vendor, customer=request.user, status=Cart.Status.ACTIVE).first()
        if cart:
            return cart
        return Cart.objects.create(vendor=vendor, customer=request.user, status=Cart.Status.ACTIVE)

    def list(self, request):
        vendor = get_vendor_from_request(request)
        cart = self._get_or_create_cart(request, vendor)
        return Response(CartSerializer(cart).data)

    @action(detail=False, methods=["post"])
    def add(self, request):
        vendor = get_vendor_from_request(request)
        cart = self._get_or_create_cart(request, vendor)
        listing_id = request.data.get("listing_id")
        qty = int(request.data.get("qty") or 1)
        listing = get_object_or_404(VendorProductListing, id=listing_id, vendor=vendor, is_online=True)
        item, created = CartItem.objects.get_or_create(
            cart=cart, listing=listing, defaults={"qty": max(qty, 1), "unit_price": listing.effective_price}
        )
        if not created:
            item.qty = item.qty + max(qty, 1)
            item.unit_price = listing.effective_price
            item.save(update_fields=["qty", "unit_price", "updated_at"])
        return Response(CartSerializer(cart).data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"])
    def update_item(self, request):
        vendor = get_vendor_from_request(request)
        cart = self._get_or_create_cart(request, vendor)
        item_id = request.data.get("item_id")
        qty = int(request.data.get("qty") or 1)
        item = get_object_or_404(CartItem, id=item_id, cart=cart)
        item.qty = max(qty, 1)
        item.save(update_fields=["qty", "updated_at"])
        return Response(CartSerializer(cart).data)

    @action(detail=False, methods=["post"])
    def remove_item(self, request):
        vendor = get_vendor_from_request(request)
        cart = self._get_or_create_cart(request, vendor)
        item_id = request.data.get("item_id")
        CartItem.objects.filter(id=item_id, cart=cart).delete()
        return Response(CartSerializer(cart).data)


class WishlistViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def list(self, request):
        vendor = get_vendor_from_request(request)
        wishlist, _ = Wishlist.objects.get_or_create(vendor=vendor, customer=request.user)
        return Response(WishlistSerializer(wishlist).data)

    @action(detail=False, methods=["post"])
    def add(self, request):
        vendor = get_vendor_from_request(request)
        listing_id = request.data.get("listing_id")
        wishlist, _ = Wishlist.objects.get_or_create(vendor=vendor, customer=request.user)
        listing = get_object_or_404(VendorProductListing, id=listing_id, vendor=vendor, is_online=True)
        WishlistItem.objects.get_or_create(wishlist=wishlist, listing=listing)
        return Response(WishlistSerializer(wishlist).data)

    @action(detail=False, methods=["post"])
    def remove(self, request):
        vendor = get_vendor_from_request(request)
        listing_id = request.data.get("listing_id")
        wishlist, _ = Wishlist.objects.get_or_create(vendor=vendor, customer=request.user)
        WishlistItem.objects.filter(wishlist=wishlist, listing_id=listing_id).delete()
        return Response(WishlistSerializer(wishlist).data)


class CustomerProfileViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def list(self, request):
        profile, _ = CustomerProfile.objects.get_or_create(user=request.user)
        return Response(CustomerProfileSerializer(profile).data)

    @action(detail=False, methods=["post"])
    def add_address(self, request):
        profile, _ = CustomerProfile.objects.get_or_create(user=request.user)
        ser = CustomerAddressSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        addr = CustomerAddress.objects.create(profile=profile, **ser.validated_data)
        if addr.is_default:
            CustomerAddress.objects.filter(profile=profile).exclude(id=addr.id).update(is_default=False)
        return Response(CustomerProfileSerializer(profile).data)


class StoreOrderViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    serializer_class = StoreOrderSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        vendor = get_vendor_from_request(self.request)
        qs = (
            StoreOrder.objects.select_related("vendor", "customer", "address")
            .prefetch_related("items", "status_events")
            .filter(vendor=vendor)
        )
        if self.request.user.groups.filter(name__in=["Vendor", "Vendor Staff", "Super Admin"]).exists():
            return qs.order_by("-created_at")
        return qs.filter(customer=self.request.user).order_by("-created_at")

    def perform_create(self, serializer):
        vendor = get_vendor_from_request(self.request)
        serializer.save(vendor=vendor, customer=self.request.user)

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated, IsVendorUser])
    def accept(self, request, pk=None):
        vendor = get_vendor_from_request(request)
        order = get_object_or_404(StoreOrder, id=pk, vendor=vendor)
        erp_order = order.accept_and_create_erp_order()
        # Attach GST invoice PDF (best-effort; renderer may be unavailable).
        if not order.invoice_pdf:
            pdf_bytes = render_store_order_invoice_pdf_bytes(order=order, request=request)
            if pdf_bytes:
                order.invoice_pdf.save(f"{order.order_number}.pdf", ContentFile(pdf_bytes), save=True)
        try:
            notify_order_status(order=order, status_label="Accepted")
        except Exception:
            pass
        return Response({"ok": True, "order_number": order.order_number, "erp_order_id": getattr(erp_order, "id", None)})

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated, IsVendorUser])
    def reject(self, request, pk=None):
        vendor = get_vendor_from_request(request)
        order = get_object_or_404(StoreOrder, id=pk, vendor=vendor)
        if order.status != StoreOrder.Status.PENDING:
            return Response({"ok": False, "error": "Only pending orders can be rejected."}, status=400)
        order.status = StoreOrder.Status.REJECTED
        order.save(update_fields=["status", "updated_at"])
        try:
            notify_order_status(order=order, status_label="Rejected")
        except Exception:
            pass
        return Response({"ok": True})

    @action(detail=True, methods=["get"], permission_classes=[IsAuthenticated])
    def invoice(self, request, pk=None):
        vendor = get_vendor_from_request(request)
        order = get_object_or_404(StoreOrder, id=pk, vendor=vendor)
        # Allow customer or vendor.
        if not request.user.groups.filter(name__in=["Vendor", "Vendor Staff", "Super Admin"]).exists():
            if order.customer_id != request.user.id:
                return Response({"ok": False, "error": "Forbidden"}, status=403)

        pdf_bytes = render_store_order_invoice_pdf_bytes(order=order, request=request)
        if not pdf_bytes:
            return Response({"ok": False, "error": "PDF renderer unavailable"}, status=501)
        resp = HttpResponse(pdf_bytes, content_type="application/pdf")
        resp["Content-Disposition"] = f'attachment; filename="{order.order_number}.pdf"'
        return resp


class PaymentsViewSet(viewsets.ViewSet):
    """
    Dynamic per-vendor payment gateway loader.
    This is a production-safe skeleton: it stores attempts and returns provider metadata,
    while real provider SDK calls can be added behind the same interface.
    """

    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=["post"])
    def initiate(self, request):
        vendor = get_vendor_from_request(request)
        order_id = request.data.get("order_id")
        provider = (request.data.get("provider") or "").strip().lower()
        order = get_object_or_404(StoreOrder, id=order_id, vendor=vendor, customer=request.user)

        if not provider:
            cfg = vendor.payment_gateways.filter(is_active=True).order_by("provider").first()
            provider = (cfg.provider if cfg else "dummy")
        else:
            cfg = vendor.payment_gateways.filter(provider=provider, is_active=True).first()

        from .models import StorePaymentAttempt

        attempt = StorePaymentAttempt.objects.create(
            order=order,
            provider=provider,
            amount=order.total_amount,
            payload={"config": (cfg.config if cfg else {})},
        )
        order.payment_status = StoreOrder.PaymentStatus.INITIATED
        order.save(update_fields=["payment_status", "updated_at"])

        init_payload = {}
        try:
            from .services.payments.provider import initiate_payment

            init_payload = initiate_payment(order=order, provider=provider, config=(cfg.config if cfg else {}))
            attempt.payload = {**(attempt.payload or {}), **{"init": init_payload}}
            # Capture provider order id for webhook reconciliation.
            try:
                rz_order_id = str((init_payload.get("razorpay_order") or {}).get("id") or "").strip()
            except Exception:
                rz_order_id = ""
            if rz_order_id:
                attempt.external_ref = rz_order_id
                attempt.save(update_fields=["payload", "external_ref"])
            else:
                attempt.save(update_fields=["payload"])
        except Exception:
            init_payload = {}

        return Response(
            {"ok": True, "attempt_id": attempt.id, "provider": provider, "amount": str(order.total_amount), "init": init_payload}
        )


class ShippingViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated, IsVendorUser]

    @action(detail=False, methods=["post"])
    def create_shipment(self, request):
        vendor = get_vendor_from_request(request)
        order_id = request.data.get("order_id")
        provider = (request.data.get("provider") or "").strip().lower()
        order = get_object_or_404(StoreOrder, id=order_id, vendor=vendor)

        if order.status not in [StoreOrder.Status.ACCEPTED, StoreOrder.Status.PACKED, StoreOrder.Status.SHIPPED]:
            return Response({"ok": False, "error": "Order must be accepted before shipping."}, status=400)

        if not provider:
            cfg = vendor.shipping_providers.filter(is_active=True).order_by("provider").first()
            provider = (cfg.provider if cfg else "manual")
        else:
            cfg = vendor.shipping_providers.filter(provider=provider, is_active=True).first()

        from .models import StoreShipment

        shipment, created = StoreShipment.objects.get_or_create(
            order=order, defaults={"provider": provider, "payload": {"config": (cfg.config if cfg else {})}}
        )
        if not created and shipment.provider != provider:
            shipment.provider = provider
            shipment.save(update_fields=["provider", "updated_at"])

        try:
            from .services.shipping.provider import create_shipment

            res = create_shipment(order=order, provider=provider, config=(cfg.config if cfg else {}))
            if isinstance(res, dict):
                shipment.payload = {**(shipment.payload or {}), **{"provider_result": res}}
                tn = (res.get("tracking_number") or "").strip()
                if tn:
                    shipment.tracking_number = tn
                ext = (res.get("external_ref") or "").strip()
                if ext:
                    shipment.external_ref = ext
                cn = (res.get("courier_name") or "").strip()
                if cn:
                    shipment.courier_name = cn
                shipment.save(update_fields=["payload", "tracking_number", "external_ref", "courier_name", "updated_at"])
        except Exception:
            pass
        return Response({"ok": True, "shipment_id": shipment.id, "provider": shipment.provider})

    @action(detail=False, methods=["get"])
    def track(self, request):
        vendor = get_vendor_from_request(request)
        order_id = request.query_params.get("order_id")
        order = get_object_or_404(StoreOrder, id=order_id, vendor=vendor)
        shipment = getattr(order, "shipment", None)
        if not shipment:
            return Response({"ok": False, "error": "No shipment"}, status=404)

        live = {}
        try:
            cfg = vendor.shipping_providers.filter(provider=shipment.provider, is_active=True).first()
            config = (cfg.config if cfg else {})
            from .services.shipping.provider import track_shipment

            if shipment.tracking_number:
                live = track_shipment(provider=shipment.provider, config=config, tracking_number=shipment.tracking_number)
                shipment.payload = {**(shipment.payload or {}), **{"live_track": live}}
                shipment.last_tracked_at = timezone.now()
                # Best-effort map status if response provides it.
                try:
                    resp = live.get("response") or {}
                    if isinstance(resp, dict):
                        cur = str(resp.get("current_status") or resp.get("status") or "").strip().lower()
                    else:
                        cur = ""
                except Exception:
                    cur = ""
                if cur in {"delivered"}:
                    shipment.status = "delivered"
                shipment.save(update_fields=["payload", "last_tracked_at", "status", "updated_at"])
        except Exception:
            live = {}

        return Response(
            {
                "ok": True,
                "provider": shipment.provider,
                "status": shipment.status,
                "tracking_number": shipment.tracking_number,
                "external_ref": shipment.external_ref,
                "courier_name": shipment.courier_name,
                "last_tracked_at": shipment.last_tracked_at.isoformat() if shipment.last_tracked_at else None,
                "payload": shipment.payload,
                "live": live,
            }
        )

    @action(detail=False, methods=["post"])
    def shiprocket_label(self, request):
        vendor = get_vendor_from_request(request)
        order_id = request.data.get("order_id")
        order = get_object_or_404(StoreOrder, id=order_id, vendor=vendor)
        shipment = getattr(order, "shipment", None)
        if not shipment or shipment.provider != "shiprocket":
            return Response({"ok": False, "error": "Shiprocket shipment not found"}, status=404)
        if not shipment.external_ref:
            return Response({"ok": False, "error": "Missing Shiprocket shipment_id (external_ref)"}, status=400)

        cfg = vendor.shipping_providers.filter(provider="shiprocket", is_active=True).first()
        if not cfg:
            return Response({"ok": False, "error": "Shiprocket not configured"}, status=400)
        from storefront.services.shipping.shiprocket import generate_label, get_token_cached

        api_base = str((cfg.config or {}).get("api_base") or "https://apiv2.shiprocket.in").strip()
        email = str((cfg.config or {}).get("email") or "").strip()
        password = str((cfg.config or {}).get("password") or "").strip()
        token = get_token_cached(api_base=api_base, email=email, password=password)
        if token == "DEMO":
            res = {"ok": True, "status": "demo", "response": {"demo": True, "note": "Label generation skipped in demo mode."}}
            shipment.payload = {**(shipment.payload or {}), **{"label": res}}
            shipment.save(update_fields=["payload", "updated_at"])
            return Response({"ok": True, "result": res})
        if not token:
            return Response({"ok": False, "error": "Shiprocket auth failed"}, status=400)

        res = generate_label(api_base=api_base, token=token, shipment_ids=[shipment.external_ref])
        shipment.payload = {**(shipment.payload or {}), **{"label": res}}
        shipment.save(update_fields=["payload", "updated_at"])
        return Response({"ok": True, "result": res})

    @action(detail=False, methods=["get"])
    def shiprocket_label_download(self, request):
        vendor = get_vendor_from_request(request)
        order_id = request.query_params.get("order_id")
        order = get_object_or_404(StoreOrder, id=order_id, vendor=vendor)
        shipment = getattr(order, "shipment", None)
        if not shipment or shipment.provider != "shiprocket":
            return HttpResponse("Shiprocket shipment not found", status=404, content_type="text/plain")

        # Demo mode: allow offline testing when credentials are placeholders.
        cfg = vendor.shipping_providers.filter(provider="shiprocket", is_active=True).first()
        demo_mode = False
        if cfg:
            try:
                demo_mode = str((cfg.config or {}).get("mode") or "").strip().lower() == "demo"
                if not demo_mode:
                    pw = str((cfg.config or {}).get("password") or "").strip()
                    demo_mode = pw == "DEMO_PASSWORD_CHANGE_ME"
            except Exception:
                demo_mode = False

        if demo_mode:
            pdf_bytes = _render_demo_shipping_pdf_bytes(
                title="Shiprocket Label (DEMO)",
                vendor=vendor,
                order=order,
                shipment=shipment,
            )
            resp = HttpResponse(pdf_bytes, content_type="application/pdf")
            resp["Content-Disposition"] = f'attachment; filename="{order.order_number}_label.pdf"'
            return resp

        # Try existing payload url first.
        url = ""
        try:
            url = _find_pdf_url((shipment.payload or {}).get("label") or {})
        except Exception:
            url = ""

        if not url:
            # Generate label and retry url extraction.
            cfg = vendor.shipping_providers.filter(provider="shiprocket", is_active=True).first()
            if not cfg:
                return HttpResponse("Shiprocket not configured", status=400, content_type="text/plain")
            from storefront.services.shipping.shiprocket import generate_label, get_token_cached

            api_base = str((cfg.config or {}).get("api_base") or "https://apiv2.shiprocket.in").strip()
            email = str((cfg.config or {}).get("email") or "").strip()
            password = str((cfg.config or {}).get("password") or "").strip()
            token = get_token_cached(api_base=api_base, email=email, password=password)
            if token == "DEMO":
                pdf_bytes = _render_demo_shipping_pdf_bytes(
                    title="Shiprocket Label (DEMO)",
                    vendor=vendor,
                    order=order,
                    shipment=shipment,
                )
                resp = HttpResponse(pdf_bytes, content_type="application/pdf")
                resp["Content-Disposition"] = f'attachment; filename="{order.order_number}_label.pdf"'
                return resp
            if not token:
                # Dev-friendly fallback for local demos without real credentials.
                if getattr(settings, "DEBUG", False):
                    pdf_bytes = _render_demo_shipping_pdf_bytes(
                        title="Shiprocket Label (DEMO)",
                        vendor=vendor,
                        order=order,
                        shipment=shipment,
                    )
                    resp = HttpResponse(pdf_bytes, content_type="application/pdf")
                    resp["Content-Disposition"] = f'attachment; filename="{order.order_number}_label.pdf"'
                    return resp
                return HttpResponse("Shiprocket auth failed", status=400, content_type="text/plain")
            res = generate_label(api_base=api_base, token=token, shipment_ids=[shipment.external_ref] if shipment.external_ref else [])
            shipment.payload = {**(shipment.payload or {}), **{"label": res}}
            shipment.save(update_fields=["payload", "updated_at"])
            url = _find_pdf_url(res)

        return _proxy_pdf_download(url, filename=f"{order.order_number}_label.pdf")

    @action(detail=False, methods=["post"])
    def shiprocket_pickup(self, request):
        vendor = get_vendor_from_request(request)
        order_id = request.data.get("order_id")
        pickup_date = (request.data.get("pickup_date") or "").strip()  # YYYY-MM-DD
        retry = str(request.data.get("retry") or "").strip().lower() in {"1", "true", "yes", "on"}
        order = get_object_or_404(StoreOrder, id=order_id, vendor=vendor)
        shipment = getattr(order, "shipment", None)
        if not shipment or shipment.provider != "shiprocket":
            return Response({"ok": False, "error": "Shiprocket shipment not found"}, status=404)
        if not shipment.external_ref:
            return Response({"ok": False, "error": "Missing Shiprocket shipment_id (external_ref)"}, status=400)

        cfg = vendor.shipping_providers.filter(provider="shiprocket", is_active=True).first()
        if not cfg:
            return Response({"ok": False, "error": "Shiprocket not configured"}, status=400)
        from storefront.services.shipping.shiprocket import request_pickup, get_token_cached

        api_base = str((cfg.config or {}).get("api_base") or "https://apiv2.shiprocket.in").strip()
        email = str((cfg.config or {}).get("email") or "").strip()
        password = str((cfg.config or {}).get("password") or "").strip()
        token = get_token_cached(api_base=api_base, email=email, password=password)
        if token == "DEMO":
            res = {
                "ok": True,
                "status": "demo",
                "response": {"demo": True, "pickup_date": pickup_date or "auto", "retry": retry},
            }
            shipment.payload = {**(shipment.payload or {}), **{"pickup": res}}
            shipment.save(update_fields=["payload", "updated_at"])
            return Response({"ok": True, "result": res})
        if not token:
            return Response({"ok": False, "error": "Shiprocket auth failed"}, status=400)

        res = request_pickup(api_base=api_base, token=token, shipment_ids=[shipment.external_ref], pickup_date=pickup_date, retry=retry)
        shipment.payload = {**(shipment.payload or {}), **{"pickup": res}}
        shipment.save(update_fields=["payload", "updated_at"])
        return Response({"ok": True, "result": res})

    @action(detail=False, methods=["post"])
    def shiprocket_manifest(self, request):
        vendor = get_vendor_from_request(request)
        order_id = request.data.get("order_id")
        order = get_object_or_404(StoreOrder, id=order_id, vendor=vendor)
        shipment = getattr(order, "shipment", None)
        if not shipment or shipment.provider != "shiprocket":
            return Response({"ok": False, "error": "Shiprocket shipment not found"}, status=404)
        if not shipment.external_ref:
            return Response({"ok": False, "error": "Missing Shiprocket shipment_id (external_ref)"}, status=400)

        cfg = vendor.shipping_providers.filter(provider="shiprocket", is_active=True).first()
        if not cfg:
            return Response({"ok": False, "error": "Shiprocket not configured"}, status=400)
        from storefront.services.shipping.shiprocket import generate_manifest, get_token_cached

        api_base = str((cfg.config or {}).get("api_base") or "https://apiv2.shiprocket.in").strip()
        email = str((cfg.config or {}).get("email") or "").strip()
        password = str((cfg.config or {}).get("password") or "").strip()
        token = get_token_cached(api_base=api_base, email=email, password=password)
        if token == "DEMO":
            res = {"ok": True, "status": "demo", "response": {"demo": True, "note": "Manifest generation skipped in demo mode."}}
            shipment.payload = {**(shipment.payload or {}), **{"manifest": res}}
            shipment.save(update_fields=["payload", "updated_at"])
            return Response({"ok": True, "result": res})
        if not token:
            return Response({"ok": False, "error": "Shiprocket auth failed"}, status=400)

        res = generate_manifest(api_base=api_base, token=token, shipment_ids=[shipment.external_ref])
        shipment.payload = {**(shipment.payload or {}), **{"manifest": res}}
        shipment.save(update_fields=["payload", "updated_at"])
        return Response({"ok": True, "result": res})

    @action(detail=False, methods=["post"])
    def shiprocket_manifest_print(self, request):
        vendor = get_vendor_from_request(request)
        order_id = request.data.get("order_id")
        order = get_object_or_404(StoreOrder, id=order_id, vendor=vendor)
        shipment = getattr(order, "shipment", None)
        if not shipment or shipment.provider != "shiprocket":
            return Response({"ok": False, "error": "Shiprocket shipment not found"}, status=404)

        # Try to find order_id stored in payload from create call.
        shiprocket_order_id = ""
        try:
            shiprocket_order_id = str((shipment.payload or {}).get("provider_result", {}).get("shiprocket_order_id") or "").strip()
        except Exception:
            shiprocket_order_id = ""
        if not shiprocket_order_id:
            # Demo/backfill: allow printing even if older demo data missed storing shiprocket_order_id.
            try:
                shiprocket_order_id = str(100000 + int(order.id))
            except Exception:
                shiprocket_order_id = ""
            if not shiprocket_order_id:
                return Response({"ok": False, "error": "Missing Shiprocket order_id in shipment payload"}, status=400)

        cfg = vendor.shipping_providers.filter(provider="shiprocket", is_active=True).first()
        if not cfg:
            return Response({"ok": False, "error": "Shiprocket not configured"}, status=400)
        from storefront.services.shipping.shiprocket import print_manifest, get_token_cached

        api_base = str((cfg.config or {}).get("api_base") or "https://apiv2.shiprocket.in").strip()
        email = str((cfg.config or {}).get("email") or "").strip()
        password = str((cfg.config or {}).get("password") or "").strip()
        token = get_token_cached(api_base=api_base, email=email, password=password)
        if token == "DEMO":
            res = {"ok": True, "status": "demo", "response": {"demo": True, "order_ids": [shiprocket_order_id]}}
            shipment.payload = {**(shipment.payload or {}), **{"manifest_print": res}}
            shipment.save(update_fields=["payload", "updated_at"])
            return Response({"ok": True, "result": res})
        if not token:
            return Response({"ok": False, "error": "Shiprocket auth failed"}, status=400)

        res = print_manifest(api_base=api_base, token=token, order_ids=[shiprocket_order_id])
        shipment.payload = {**(shipment.payload or {}), **{"manifest_print": res}}
        shipment.save(update_fields=["payload", "updated_at"])
        return Response({"ok": True, "result": res})

    @action(detail=False, methods=["get"])
    def shiprocket_manifest_download(self, request):
        vendor = get_vendor_from_request(request)
        order_id = request.query_params.get("order_id")
        order = get_object_or_404(StoreOrder, id=order_id, vendor=vendor)
        shipment = getattr(order, "shipment", None)
        if not shipment or shipment.provider != "shiprocket":
            return HttpResponse("Shiprocket shipment not found", status=404, content_type="text/plain")

        cfg = vendor.shipping_providers.filter(provider="shiprocket", is_active=True).first()
        demo_mode = False
        if cfg:
            try:
                demo_mode = str((cfg.config or {}).get("mode") or "").strip().lower() == "demo"
                if not demo_mode:
                    pw = str((cfg.config or {}).get("password") or "").strip()
                    demo_mode = pw == "DEMO_PASSWORD_CHANGE_ME"
            except Exception:
                demo_mode = False

        if demo_mode:
            pdf_bytes = _render_demo_shipping_pdf_bytes(
                title="Shiprocket Manifest (DEMO)",
                vendor=vendor,
                order=order,
                shipment=shipment,
            )
            resp = HttpResponse(pdf_bytes, content_type="application/pdf")
            resp["Content-Disposition"] = f'attachment; filename="{order.order_number}_manifest.pdf"'
            return resp

        url = ""
        try:
            url = _find_pdf_url((shipment.payload or {}).get("manifest_print") or {})
        except Exception:
            url = ""

        if not url:
            # Attempt manifest print and retry.
            if not cfg:
                return HttpResponse("Shiprocket not configured", status=400, content_type="text/plain")
            shiprocket_order_id = ""
            try:
                shiprocket_order_id = str((shipment.payload or {}).get("provider_result", {}).get("shiprocket_order_id") or "").strip()
            except Exception:
                shiprocket_order_id = ""
            if not shiprocket_order_id:
                # Demo fallback, else try manifest generation by shipment_id (some flows don't return order_id).
                if demo_mode:
                    pdf_bytes = _render_demo_shipping_pdf_bytes(
                        title="Shiprocket Manifest (DEMO)",
                        vendor=vendor,
                        order=order,
                        shipment=shipment,
                    )
                    resp = HttpResponse(pdf_bytes, content_type="application/pdf")
                    resp["Content-Disposition"] = f'attachment; filename="{order.order_number}_manifest.pdf"'
                    return resp
                if shipment.external_ref:
                    from storefront.services.shipping.shiprocket import generate_manifest, get_token_cached

                    api_base = str((cfg.config or {}).get("api_base") or "https://apiv2.shiprocket.in").strip()
                    email = str((cfg.config or {}).get("email") or "").strip()
                    password = str((cfg.config or {}).get("password") or "").strip()
                    token = get_token_cached(api_base=api_base, email=email, password=password)
                    if token == "DEMO" or (not token and getattr(settings, "DEBUG", False)):
                        pdf_bytes = _render_demo_shipping_pdf_bytes(
                            title="Shiprocket Manifest (DEMO)",
                            vendor=vendor,
                            order=order,
                            shipment=shipment,
                        )
                        resp = HttpResponse(pdf_bytes, content_type="application/pdf")
                        resp["Content-Disposition"] = f'attachment; filename="{order.order_number}_manifest.pdf"'
                        return resp
                    if not token:
                        if getattr(settings, "DEBUG", False):
                            pdf_bytes = _render_demo_shipping_pdf_bytes(
                                title="Shiprocket Manifest (DEMO)",
                                vendor=vendor,
                                order=order,
                                shipment=shipment,
                            )
                            resp = HttpResponse(pdf_bytes, content_type="application/pdf")
                            resp["Content-Disposition"] = f'attachment; filename="{order.order_number}_manifest.pdf"'
                            return resp
                        return HttpResponse("Shiprocket auth failed", status=400, content_type="text/plain")
                    gen = generate_manifest(api_base=api_base, token=token, shipment_ids=[shipment.external_ref])
                    shipment.payload = {**(shipment.payload or {}), **{"manifest": gen}}
                    shipment.save(update_fields=["payload", "updated_at"])
                    url = _find_pdf_url(gen)
                    if url:
                        return _proxy_pdf_download(url, filename=f"{order.order_number}_manifest.pdf")
                return HttpResponse("Missing Shiprocket order_id for manifest print", status=400, content_type="text/plain")

            from storefront.services.shipping.shiprocket import print_manifest, get_token_cached

            api_base = str((cfg.config or {}).get("api_base") or "https://apiv2.shiprocket.in").strip()
            email = str((cfg.config or {}).get("email") or "").strip()
            password = str((cfg.config or {}).get("password") or "").strip()
            token = get_token_cached(api_base=api_base, email=email, password=password)
            if token == "DEMO":
                pdf_bytes = _render_demo_shipping_pdf_bytes(
                    title="Shiprocket Manifest (DEMO)",
                    vendor=vendor,
                    order=order,
                    shipment=shipment,
                )
                resp = HttpResponse(pdf_bytes, content_type="application/pdf")
                resp["Content-Disposition"] = f'attachment; filename="{order.order_number}_manifest.pdf"'
                return resp
            if not token:
                if getattr(settings, "DEBUG", False):
                    pdf_bytes = _render_demo_shipping_pdf_bytes(
                        title="Shiprocket Manifest (DEMO)",
                        vendor=vendor,
                        order=order,
                        shipment=shipment,
                    )
                    resp = HttpResponse(pdf_bytes, content_type="application/pdf")
                    resp["Content-Disposition"] = f'attachment; filename="{order.order_number}_manifest.pdf"'
                    return resp
                return HttpResponse("Shiprocket auth failed", status=400, content_type="text/plain")
            res = print_manifest(api_base=api_base, token=token, order_ids=[shiprocket_order_id])
            shipment.payload = {**(shipment.payload or {}), **{"manifest_print": res}}
            shipment.save(update_fields=["payload", "updated_at"])
            url = _find_pdf_url(res)

        return _proxy_pdf_download(url, filename=f"{order.order_number}_manifest.pdf")


class VendorDashboardViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated, IsVendorUser]

    def list(self, request):
        from django.db.models import Count, Sum
        from django.db.models.functions import TruncDate
        from django.db.models import F, ExpressionWrapper, IntegerField, Q
        from products.models import WarehouseInventory
        from vendors.models import VendorWarehouse
        from decimal import Decimal as D
        from vendors.models import VendorPaymentGatewayConfig, VendorShippingProviderConfig

        vendor = get_vendor_from_request(request)
        qs = StoreOrder.objects.filter(vendor=vendor)

        totals = qs.aggregate(
            total_sales=Sum("total_amount"),
            total_orders=Count("id"),
        )
        status_counts = dict(qs.values_list("status").annotate(c=Count("id")).order_by())
        payment_counts = dict(qs.values_list("payment_status").annotate(c=Count("id")).order_by())

        revenue_by_day = (
            qs.filter(created_at__gte=timezone.now() - timedelta(days=30))
            .annotate(d=TruncDate("created_at"))
            .values("d")
            .annotate(revenue=Sum("total_amount"), orders=Count("id"))
            .order_by("d")
        )

        shipment_counts = {}
        try:
            shipment_counts = dict(qs.filter(shipment__isnull=False).values_list("shipment__status").annotate(c=Count("id")).order_by())
        except Exception:
            shipment_counts = {}

        # Period KPIs (paid orders)
        now = timezone.now()
        today = timezone.localdate()
        start_7d = now - timedelta(days=7)
        start_30d = now - timedelta(days=30)
        paid = qs.filter(payment_status=StoreOrder.PaymentStatus.PAID)
        sales_today = paid.filter(created_at__date=today).aggregate(total=Sum("total_amount")).get("total") or 0
        sales_7d = paid.filter(created_at__gte=start_7d).aggregate(total=Sum("total_amount")).get("total") or 0
        sales_30d = paid.filter(created_at__gte=start_30d).aggregate(total=Sum("total_amount")).get("total") or 0
        paid_30d_count = paid.filter(created_at__gte=start_30d).count()
        aov_30d = (D(str(sales_30d or 0)) / D(paid_30d_count)) if paid_30d_count else D("0.00")

        ready_to_ship = qs.filter(status=StoreOrder.Status.ACCEPTED, shipment__isnull=True).count()

        warehouse_ids = list(VendorWarehouse.objects.filter(vendor=vendor, is_active=True).values_list("warehouse_id", flat=True))
        if vendor.primary_warehouse_id and vendor.primary_warehouse_id not in warehouse_ids:
            warehouse_ids.append(vendor.primary_warehouse_id)

        low_stock = []
        if warehouse_ids:
            sellable = ExpressionWrapper(F("available_qty") - F("reserved_qty"), output_field=IntegerField())
            inv_qs = (
                WarehouseInventory.objects.select_related("product", "warehouse")
                .filter(warehouse_id__in=warehouse_ids)
                .annotate(sellable_qty=sellable)
                .filter(Q(sellable_qty__lte=F("product__low_stock_threshold")))
                .order_by("sellable_qty")[:25]
            )
            low_stock = [
                {
                    "warehouse": str(i.warehouse),
                    "product_id": i.product_id,
                    "product": str(i.product),
                    "sellable_qty": int(getattr(i, "sellable_qty", 0) or 0),
                    "threshold": int(getattr(i.product, "low_stock_threshold", 0) or 0),
                }
                for i in inv_qs
            ]

        integrations = {
            "active_payment_provider": None,
            "shiprocket_configured": False,
        }
        try:
            active_pay = VendorPaymentGatewayConfig.objects.filter(vendor=vendor, is_active=True).order_by("provider").first()
            integrations["active_payment_provider"] = getattr(active_pay, "provider", None)
        except Exception:
            integrations["active_payment_provider"] = None
        try:
            sr = VendorShippingProviderConfig.objects.filter(vendor=vendor, provider="shiprocket", is_active=True).first()
            cfg = (sr.config if sr else {}) or {}
            integrations["shiprocket_configured"] = bool(cfg.get("email")) and bool(cfg.get("password"))
        except Exception:
            integrations["shiprocket_configured"] = False

        return Response(
            {
                "vendor_id": vendor.id,
                "last_updated": timezone.now().isoformat(),
                "totals": {
                    "total_sales": str(totals.get("total_sales") or 0),
                    "total_orders": int(totals.get("total_orders") or 0),
                },
                "periods": {
                    "sales_today": str(sales_today),
                    "sales_7d": str(sales_7d),
                    "sales_30d": str(sales_30d),
                    "paid_30d_count": int(paid_30d_count),
                    "aov_30d": str(aov_30d.quantize(D("0.01"))),
                },
                "ready_to_ship_count": int(ready_to_ship),
                "orders_by_status": status_counts,
                "payments_by_status": payment_counts,
                "shipments_by_status": shipment_counts,
                "revenue_last_30_days": [{"date": str(r["d"]), "revenue": str(r["revenue"] or 0), "orders": r["orders"]} for r in revenue_by_day],
                "inventory_alerts": low_stock,
                "integrations": integrations,
            }
        )


class VendorPaymentGatewayConfigViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsVendorUser]
    serializer_class = VendorPaymentGatewayConfigSerializer

    def get_queryset(self):
        vendor = get_vendor_from_request(self.request)
        ensure_vendor_access(request=self.request, vendor=vendor)
        return vendor.payment_gateways.all().order_by("provider")

    def perform_create(self, serializer):
        vendor = get_vendor_from_request(self.request)
        ensure_vendor_access(request=self.request, vendor=vendor)
        serializer.save(vendor=vendor)


class VendorShippingProviderConfigViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsVendorUser]
    serializer_class = VendorShippingProviderConfigSerializer

    def get_queryset(self):
        vendor = get_vendor_from_request(self.request)
        ensure_vendor_access(request=self.request, vendor=vendor)
        return vendor.shipping_providers.all().order_by("provider")

    def perform_create(self, serializer):
        vendor = get_vendor_from_request(self.request)
        ensure_vendor_access(request=self.request, vendor=vendor)
        serializer.save(vendor=vendor)


class MarketplaceAdminViewSet(viewsets.ViewSet):
    """
    Super Admin controls:
    - Platform commission settings
    - View all vendors/orders/settlements
    """

    permission_classes = [IsAuthenticated]

    def _require_superadmin(self, request):
        if request.user.groups.filter(name="Super Admin").exists() or getattr(request.user, "is_superuser", False):
            return
        return Response({"ok": False, "error": "Forbidden"}, status=403)

    def list(self, request):
        forbid = self._require_superadmin(request)
        if forbid:
            return forbid
        from django.db.models import Count, Sum
        from vendors.models import Vendor
        from storefront.models import StoreSettlement

        totals = StoreOrder.objects.aggregate(
            orders=Count("id"),
            gmv=Sum("total_amount"),
        )
        settlements = StoreSettlement.objects.aggregate(
            vendor_payout=Sum("vendor_amount"),
            commission=Sum("commission_amount"),
        )
        vendors_count = Vendor.objects.count()
        return Response(
            {
                "ok": True,
                "totals": {"orders": totals.get("orders") or 0, "gmv": str(totals.get("gmv") or 0), "vendors": vendors_count},
                "settlements": {"vendor_payout": str(settlements.get("vendor_payout") or 0), "commission": str(settlements.get("commission") or 0)},
            }
        )

    @action(detail=False, methods=["get", "post"])
    def settings(self, request):
        forbid = self._require_superadmin(request)
        if forbid:
            return forbid
        obj = get_platform_settings()
        if request.method == "POST":
            ser = PlatformSettingsSerializer(obj, data=request.data, partial=True)
            ser.is_valid(raise_exception=True)
            ser.save()
        return Response(PlatformSettingsSerializer(obj).data)

    @action(detail=False, methods=["post"])
    def settle_order(self, request):
        forbid = self._require_superadmin(request)
        if forbid:
            return forbid
        order_id = request.data.get("order_id")
        order = get_object_or_404(StoreOrder, id=order_id)
        if order.payment_status != StoreOrder.PaymentStatus.PAID:
            return Response({"ok": False, "error": "Order not paid"}, status=400)
        settlement = settle_paid_order(order=order)
        return Response({"ok": True, "settlement": StoreSettlementSerializer(settlement).data})

    @action(detail=False, methods=["get", "post"])
    def vendor_shipping_provider(self, request):
        """
        Super Admin: configure courier/shipping providers per vendor.

        POST body:
        - vendor_id (required)
        - provider (required): shiprocket|delhivery|bluedart|...
        - is_active (optional)
        - config (optional dict): provider-specific keys, e.g. {"mode":"demo", ...}
        """
        forbid = self._require_superadmin(request)
        if forbid:
            return forbid

        if request.method == "GET":
            vendor_id = request.query_params.get("vendor_id")
            qs = VendorShippingProviderConfig.objects.select_related("vendor").all().order_by("vendor_id", "provider")
            if vendor_id:
                qs = qs.filter(vendor_id=vendor_id)
            data = VendorShippingProviderConfigSerializer(qs, many=True).data
            return Response({"ok": True, "items": data})

        vendor_id = request.data.get("vendor_id")
        provider = (request.data.get("provider") or "").strip().lower()
        if not vendor_id or not provider:
            return Response({"ok": False, "error": "vendor_id and provider are required"}, status=400)
        vendor = get_object_or_404(Vendor, id=vendor_id)
        is_active = request.data.get("is_active", True)
        config = request.data.get("config") or {}
        obj, _ = VendorShippingProviderConfig.objects.update_or_create(
            vendor=vendor,
            provider=provider,
            defaults={"is_active": bool(is_active), "config": config},
        )
        return Response({"ok": True, "item": VendorShippingProviderConfigSerializer(obj).data})


@api_view(["POST"])
@permission_classes([AllowAny])
def auth_start_otp(request):
    mobile = (request.data.get("mobile") or "").strip()
    email = (request.data.get("email") or "").strip().lower()
    purpose = (request.data.get("purpose") or "login").strip()
    if not mobile and not email:
        return Response({"ok": False, "error": "mobile or email is required"}, status=400)

    if email:
        user, _ = User.objects.get_or_create(email=email, defaults={"username": email.split("@")[0]})
        otp = OTP.create_for(user, purpose=purpose, email=email, minutes=10)
        try:
            user.email_user("Your OTP", f"Your OTP is {otp.code}")
        except Exception:
            pass
        return Response({"ok": True, "otp_id": otp.id})

    user = User.objects.filter(mobile=mobile).first()
    if not user:
        user = User.objects.create(email=f"{mobile}@otp.local", mobile=mobile, username=mobile)
    otp = OTP.create_for(user, purpose=purpose, mobile=mobile, minutes=10)
    try:
        from sms_center.sms_service import send_fast2sms_sms

        send_fast2sms_sms(mobile=mobile, text_message=f"Your OTP is {otp.code}", purpose="otp_login")
    except Exception:
        pass
    return Response({"ok": True, "otp_id": otp.id})


@api_view(["POST"])
@permission_classes([AllowAny])
def auth_verify_otp(request):
    otp_id = request.data.get("otp_id")
    code = (request.data.get("code") or "").strip()
    if not otp_id or not code:
        return Response({"ok": False, "error": "otp_id and code are required"}, status=400)
    otp = OTP.objects.select_related("user").filter(id=otp_id).first()
    if not otp or not otp.is_valid(code):
        return Response({"ok": False, "error": "Invalid or expired OTP"}, status=400)
    otp.mark_verified()
    token = RefreshToken.for_user(otp.user)
    return Response({"ok": True, "access": str(token.access_token), "refresh": str(token), "user_id": otp.user_id})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def vendor_register(request):
    """
    Vendor registration (SaaS retailer onboarding).
    Creates a Vendor profile for the authenticated user.
    """
    if hasattr(request.user, "vendor"):
        v = request.user.vendor
        return Response({"ok": True, "vendor_id": v.id, "subdomain": v.subdomain})

    name = (request.data.get("name") or "").strip()
    subdomain = (request.data.get("subdomain") or "").strip().lower()
    primary_warehouse_id = request.data.get("primary_warehouse_id")
    if not name or not subdomain:
        return Response({"ok": False, "error": "name and subdomain are required"}, status=400)

    vendor = Vendor.objects.create(owner=request.user, name=name, subdomain=subdomain, primary_warehouse_id=primary_warehouse_id or None)
    try:
        from vendors.models import VendorMembership, VendorWarehouse

        VendorMembership.objects.get_or_create(vendor=vendor, user=request.user, defaults={"role": VendorMembership.Role.OWNER})
        if primary_warehouse_id:
            VendorWarehouse.objects.get_or_create(vendor=vendor, warehouse_id=primary_warehouse_id)
    except Exception:
        pass
    return Response({"ok": True, "vendor_id": vendor.id, "subdomain": vendor.subdomain}, status=201)


def _safe_json(request) -> dict:
    try:
        return request.data if isinstance(request.data, dict) else {}
    except Exception:
        try:
            raw = request.body or b""
            return json.loads(raw.decode("utf-8") or "{}")
        except Exception:
            return {}


@api_view(["POST"])
@permission_classes([AllowAny])
def razorpay_webhook(request, vendor_id: int):
    """
    Razorpay webhook receiver (per-vendor).

    Configure in VendorPaymentGatewayConfig.config:
    - webhook_secret
    """
    vendor = Vendor.objects.filter(id=vendor_id, is_active=True).first()
    if not vendor:
        return Response({"ok": False, "error": "Vendor not found"}, status=404)

    cfg = vendor.payment_gateways.filter(provider="razorpay", is_active=True).first()
    secret = str((cfg.config or {}).get("webhook_secret") or "").strip() if cfg else ""
    if not secret:
        return Response({"ok": False, "error": "Webhook secret not configured"}, status=400)

    signature = (request.headers.get("X-Razorpay-Signature") or "").strip()
    if not signature:
        return Response({"ok": False, "error": "Missing signature"}, status=400)

    body = request.body or b""
    dedupe_key = hashlib.sha256(body).hexdigest()
    try:
        from .models import StoreWebhookDelivery

        existing = StoreWebhookDelivery.objects.filter(provider="razorpay", vendor=vendor, dedupe_key=dedupe_key).first()
        if existing:
            return Response({"ok": True, "status": "duplicate"})
        delivery = StoreWebhookDelivery.objects.create(
            provider="razorpay",
            vendor=vendor,
            dedupe_key=dedupe_key,
            payload={"headers": {"X-Razorpay-Signature": signature}},
        )
    except Exception:
        delivery = None

    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        if delivery:
            try:
                delivery.status = "rejected"
                delivery.save(update_fields=["status"])
            except Exception:
                pass
        return Response({"ok": False, "error": "Invalid signature"}, status=401)

    payload = _safe_json(request)
    event = str(payload.get("event") or "").strip()

    # Extract ids (best-effort across events)
    entity = (((payload.get("payload") or {}).get("payment") or {}).get("entity") or {}) if isinstance(payload.get("payload"), dict) else {}
    rz_order_id = str(entity.get("order_id") or "").strip()
    rz_payment_id = str(entity.get("id") or "").strip()
    status_value = str(entity.get("status") or "").strip().lower()

    # Fallback extraction from order entity
    order_entity = (((payload.get("payload") or {}).get("order") or {}).get("entity") or {}) if isinstance(payload.get("payload"), dict) else {}
    if not rz_order_id:
        rz_order_id = str(order_entity.get("id") or "").strip()

    from .models import StorePaymentAttempt, StoreOrder, StoreOrderStatusEvent

    attempt = None
    if rz_order_id:
        attempt = (
            StorePaymentAttempt.objects.select_related("order")
            .filter(order__vendor=vendor, provider="razorpay", external_ref=rz_order_id)
            .order_by("-id")
            .first()
        )
    if not attempt:
        # Accept webhook (idempotent) even if attempt not found yet.
        if delivery:
            try:
                delivery.status = "ignored"
                delivery.payload = {**(delivery.payload or {}), **{"event": event, "payload": payload}}
                delivery.save(update_fields=["status", "payload"])
            except Exception:
                pass
        return Response({"ok": True, "status": "ignored", "event": event})

    attempt.payload = {**(attempt.payload or {}), **{"webhook": payload}}
    if rz_payment_id:
        attempt.payload = {**attempt.payload, **{"razorpay_payment_id": rz_payment_id}}

    # Map events -> statuses
    if event in {"payment.captured", "order.paid"} or status_value in {"captured"}:
        attempt.status = StorePaymentAttempt.Status.SUCCESS
        attempt.save(update_fields=["status", "payload"])
        order = attempt.order
        if order and order.payment_status != StoreOrder.PaymentStatus.PAID:
            order.payment_status = StoreOrder.PaymentStatus.PAID
            order.save(update_fields=["payment_status", "updated_at"])
            StoreOrderStatusEvent.objects.create(order=order, status=order.status, note="Payment received (Razorpay)")
            try:
                notify_order_status(order=order, status_label="Payment received")
            except Exception:
                pass
        if delivery:
            try:
                delivery.status = "processed"
                delivery.payload = {**(delivery.payload or {}), **{"event": event, "payload": payload}}
                delivery.save(update_fields=["status", "payload"])
            except Exception:
                pass
        return Response({"ok": True})

    if event in {"payment.failed"} or status_value in {"failed"}:
        attempt.status = StorePaymentAttempt.Status.FAILED
        attempt.save(update_fields=["status", "payload"])
        order = attempt.order
        if order and order.payment_status != StoreOrder.PaymentStatus.FAILED:
            order.payment_status = StoreOrder.PaymentStatus.FAILED
            order.save(update_fields=["payment_status", "updated_at"])
        if delivery:
            try:
                delivery.status = "processed"
                delivery.payload = {**(delivery.payload or {}), **{"event": event, "payload": payload}}
                delivery.save(update_fields=["status", "payload"])
            except Exception:
                pass
        return Response({"ok": True})

    attempt.save(update_fields=["payload"])
    if delivery:
        try:
            delivery.status = "processed"
            delivery.payload = {**(delivery.payload or {}), **{"event": event, "payload": payload}}
            delivery.save(update_fields=["status", "payload"])
        except Exception:
            pass
    return Response({"ok": True, "status": "unhandled", "event": event})


@api_view(["POST"])
@permission_classes([AllowAny])
def shiprocket_webhook(request, vendor_id: int):
    """
    Shiprocket webhook receiver (per-vendor).

    Configure in VendorShippingProviderConfig.config:
    - webhook_secret (recommended)
    """
    vendor = Vendor.objects.filter(id=vendor_id, is_active=True).first()
    if not vendor:
        return Response({"ok": False, "error": "Vendor not found"}, status=404)

    cfg = vendor.shipping_providers.filter(provider="shiprocket", is_active=True).first()
    secret = str((cfg.config or {}).get("webhook_secret") or "").strip() if cfg else ""
    # Shiprocket's dashboard webhook "Token" is typically sent as `x-api-key`.
    # Support a few common header names for compatibility.
    provided = (
        request.headers.get("x-api-key")
        or request.headers.get("X-Api-Key")
        or request.headers.get("X-Shiprocket-Signature")
        or request.headers.get("X-Webhook-Secret")
        or ""
    ).strip()
    if secret and not provided:
        return Response({"ok": False, "error": "Missing webhook secret"}, status=400)
    if secret and provided != secret:
        return Response({"ok": False, "error": "Invalid webhook secret"}, status=401)

    body = request.body or b""
    dedupe_key = hashlib.sha256(body).hexdigest()
    try:
        from .models import StoreWebhookDelivery

        existing = StoreWebhookDelivery.objects.filter(provider="shiprocket", vendor=vendor, dedupe_key=dedupe_key).first()
        if existing:
            return Response({"ok": True, "status": "duplicate"})
        delivery = StoreWebhookDelivery.objects.create(
            provider="shiprocket",
            vendor=vendor,
            dedupe_key=dedupe_key,
            payload={"headers": {"x-api-key": provided or ""}},
        )
    except Exception:
        delivery = None

    payload = _safe_json(request)

    # Best-effort extraction (varies by Shiprocket webhook type)
    awb = str(payload.get("awb") or payload.get("awb_code") or payload.get("tracking_number") or "").strip()
    order_number = str(payload.get("order_id") or payload.get("order_number") or payload.get("channel_order_id") or "").strip()
    current_status = str(payload.get("current_status") or payload.get("status") or payload.get("shipment_status") or "").strip().lower()

    from .models import StoreOrder, StoreShipment, StoreOrderStatusEvent

    order = None
    if order_number:
        order = StoreOrder.objects.filter(vendor=vendor, order_number=order_number).first()
    shipment = None
    if order:
        shipment = getattr(order, "shipment", None)
    if not shipment and awb:
        shipment = StoreShipment.objects.select_related("order").filter(order__vendor=vendor, tracking_number=awb).first()
        order = shipment.order if shipment else order

    if not shipment and order:
        shipment, _ = StoreShipment.objects.get_or_create(order=order, defaults={"provider": "shiprocket"})

    if not shipment:
        if delivery:
            try:
                delivery.status = "ignored"
                delivery.payload = {**(delivery.payload or {}), **{"payload": payload}}
                delivery.save(update_fields=["status", "payload"])
            except Exception:
                pass
        return Response({"ok": True, "status": "ignored"})

    shipment.provider = shipment.provider or "shiprocket"
    if awb and not shipment.tracking_number:
        shipment.tracking_number = awb

    # Map statuses into our enum
    status_map = {
        "new": "created",
        "manifested": "pickup_requested",
        "pickup_scheduled": "pickup_requested",
        "picked_up": "in_transit",
        "in transit": "in_transit",
        "in_transit": "in_transit",
        "out for delivery": "in_transit",
        "delivered": "delivered",
        "rto": "failed",
        "cancelled": "failed",
        "canceled": "failed",
        "failed": "failed",
    }
    mapped = status_map.get(current_status, "")
    if mapped:
        shipment.status = mapped

    shipment.payload = {**(shipment.payload or {}), **{"webhook": payload}}
    shipment.save(update_fields=["provider", "tracking_number", "status", "payload", "updated_at"])

    # Also mirror to order status (optional, conservative)
    if order and mapped in {"in_transit", "delivered"}:
        if mapped == "in_transit" and order.status not in {StoreOrder.Status.SHIPPED, StoreOrder.Status.DELIVERED}:
            order.status = StoreOrder.Status.SHIPPED
            order.save(update_fields=["status", "updated_at"])
            StoreOrderStatusEvent.objects.create(order=order, status=order.status, note="Shipped (Shiprocket update)")
            try:
                notify_order_status(order=order, status_label="Shipped")
            except Exception:
                pass
        if mapped == "delivered" and order.status != StoreOrder.Status.DELIVERED:
            order.status = StoreOrder.Status.DELIVERED
            order.save(update_fields=["status", "updated_at"])
            StoreOrderStatusEvent.objects.create(order=order, status=order.status, note="Delivered (Shiprocket update)")
            try:
                notify_order_status(order=order, status_label="Delivered")
            except Exception:
                pass

    if delivery:
        try:
            delivery.status = "processed"
            delivery.payload = {**(delivery.payload or {}), **{"payload": payload}}
            delivery.save(update_fields=["status", "payload"])
        except Exception:
            pass
    return Response({"ok": True})


def _find_pdf_url(obj) -> str:
    if isinstance(obj, dict):
        # Common known keys first.
        for k in [
            "label_url",
            "manifest_url",
            "invoice_url",
            "url",
            "download_url",
            "file_url",
        ]:
            v = obj.get(k)
            if isinstance(v, str) and v.strip().lower().startswith("http"):
                return v.strip()
        for v in obj.values():
            u = _find_pdf_url(v)
            if u:
                return u
    if isinstance(obj, list):
        for v in obj:
            u = _find_pdf_url(v)
            if u:
                return u
    if isinstance(obj, str) and obj.strip().lower().startswith("http"):
        return obj.strip()
    return ""


def _render_demo_shipping_pdf_bytes(*, title: str, vendor, order, shipment) -> bytes:
    """
    Small demo PDF generator (offline) for label/manifest downloads.

    This intentionally does NOT call any external provider APIs.
    """
    from io import BytesIO

    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4

    y = h - 60
    c.setFont("Helvetica-Bold", 18)
    c.drawString(48, y, str(title or "Shipping Document"))

    y -= 34
    c.setFont("Helvetica", 11)
    c.drawString(48, y, f"Vendor: {getattr(vendor, 'name', '')} (#{getattr(vendor, 'id', '')})")
    y -= 18
    c.drawString(48, y, f"Order: {getattr(order, 'order_number', '')} (id={getattr(order, 'id', '')})")
    y -= 18
    c.drawString(48, y, f"Shipment Provider: {getattr(shipment, 'provider', '')}")
    y -= 18
    c.drawString(48, y, f"Tracking: {getattr(shipment, 'tracking_number', '') or 'N/A'}")
    y -= 18
    c.drawString(48, y, f"External Ref: {getattr(shipment, 'external_ref', '') or 'N/A'}")

    y -= 26
    c.setFont("Helvetica-Bold", 12)
    c.drawString(48, y, "Ship To")
    y -= 18
    c.setFont("Helvetica", 11)
    address = getattr(order, "address", None)
    customer = getattr(order, "customer", None)
    c.drawString(48, y, f"Customer: {getattr(customer, 'username', '') or getattr(customer, 'email', '') or 'Customer'}")
    y -= 16
    addr_lines = []
    if address:
        for k in ["line1", "line2", "city", "district", "state", "pincode"]:
            v = getattr(address, k, "") or ""
            if str(v).strip():
                addr_lines.append(str(v).strip())
    if not addr_lines:
        addr_lines = ["(Demo address)"]
    for line in addr_lines[:6]:
        c.drawString(48, y, line)
        y -= 14
        if y < 80:
            break

    y -= 12
    c.setFont("Helvetica-Bold", 12)
    c.drawString(48, y, "Items")
    y -= 18
    c.setFont("Helvetica", 10)
    try:
        items = list(order.items.select_related("product").all())
    except Exception:
        items = []
    if not items:
        c.drawString(48, y, "(No items)")
    else:
        for it in items[:12]:
            name = getattr(getattr(it, "product", None), "name", "") or "Item"
            qty = getattr(it, "qty", 1) or 1
            price = getattr(it, "unit_price", "") or ""
            c.drawString(48, y, f"- {name}  x{qty}  @ {price}")
            y -= 14
            if y < 80:
                break

    c.setFont("Helvetica-Oblique", 9)
    c.drawString(48, 48, "DEMO MODE: This document is generated locally for testing.")
    c.showPage()
    c.save()
    return buf.getvalue()


def _proxy_pdf_download(url: str, filename: str = "document.pdf") -> HttpResponse:
    url = (url or "").strip()
    if not url:
        return HttpResponse("Missing PDF url", status=400, content_type="text/plain")
    try:
        resp = requests.get(url, timeout=24)
        if not resp.ok:
            return HttpResponse(f"Provider download failed ({resp.status_code})", status=502, content_type="text/plain")
        content_type = (resp.headers.get("content-type") or "application/pdf").split(";")[0].strip()
        out = HttpResponse(resp.content, content_type=content_type or "application/pdf")
        out["Content-Disposition"] = f'attachment; filename="{filename}"'
        return out
    except Exception as exc:
        return HttpResponse(f"Download exception: {exc}", status=502, content_type="text/plain")
