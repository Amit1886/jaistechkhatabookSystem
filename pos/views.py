from decimal import Decimal
from difflib import SequenceMatcher
from uuid import uuid4

from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone
from django.views.generic import TemplateView
from rest_framework import decorators, permissions, response, status, viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from commerce.models import Category as CommerceCategory
from commerce.models import Invoice as CommerceInvoice
from commerce.models import Order as CommerceOrder
from commerce.models import OrderItem as CommerceOrderItem
from commerce.models import Payment as CommercePayment
from commerce.models import Product as CommerceProduct
from khataapp.models import Party
from orders.models import Order, POSBill
from orders.services.order_engine import place_order
from products.models import Category, Product, WarehouseInventory

from .models import POSHoldBill, POSReprintLog, POSSession, POSTerminal
from .serializers import POSHoldBillSerializer, POSReprintLogSerializer, POSSessionSerializer, POSTerminalSerializer
from .services.pos_engine import hold_bill, retrieve_hold_bill


class POSView(TemplateView):
    template_name = "pos/terminal.html"


class POSTerminalViewSet(viewsets.ModelViewSet):
    queryset = POSTerminal.objects.select_related("user").all()
    serializer_class = POSTerminalSerializer
    permission_classes = [permissions.IsAuthenticated]


class POSSessionViewSet(viewsets.ModelViewSet):
    queryset = POSSession.objects.select_related("terminal", "cashier").all()
    serializer_class = POSSessionSerializer
    permission_classes = [permissions.IsAuthenticated]


class POSHoldBillViewSet(viewsets.ModelViewSet):
    queryset = POSHoldBill.objects.select_related("session").all()
    serializer_class = POSHoldBillSerializer
    permission_classes = [permissions.IsAuthenticated]

    @decorators.action(detail=False, methods=["post"])
    def hold(self, request):
        session_id = request.data.get("session_id")
        # If session_id not provided, try to find an open session for the current user
        if not session_id:
            open_session = POSSession.objects.filter(cashier=request.user, is_open=True).first()
            if open_session:
                session_id = open_session.id
        if not session_id:
            return response.Response({"detail": "session_id is required or an open session must exist for the user."}, status=400)

        bill = hold_bill(session_id, request.data.get("payload", {}))
        return response.Response(self.get_serializer(bill).data)

    @decorators.action(detail=False, methods=["get"], url_path="retrieve-hold")
    def retrieve_hold(self, request):
        code = request.query_params.get("hold_code", "")
        bill = retrieve_hold_bill(code)
        return response.Response(self.get_serializer(bill).data if bill else {})


class POSReprintLogViewSet(viewsets.ModelViewSet):
    queryset = POSReprintLog.objects.select_related("order", "cashier").all()
    serializer_class = POSReprintLogSerializer
    permission_classes = [permissions.IsAuthenticated]


def _money(value):
    return Decimal(str(value or "0")).quantize(Decimal("0.01"))


def _product_payload(product):
    stock = (
        WarehouseInventory.objects.filter(product=product)
        .aggregate(total=Sum("available_qty"))["total"]
        or 0
    )
    return {
        "id": product.id,
        "name": product.name,
        "sku": product.sku,
        "barcode": product.barcode,
        "category": product.category.name if product.category else "General",
        "mrp": str(product.mrp),
        "b2c_price": str(product.b2c_price),
        "b2b_price": str(product.b2b_price),
        "wholesale_price": str(product.wholesale_price),
        "gst_percent": str(product.gst_percent),
        "stock": stock,
        "image": product.primary_image_url,
        "allow_oos": product.allow_oos,
    }


def _catalog_match_score(product, query):
    query = (query or "").strip().lower()
    if not query:
        return 0
    name = (getattr(product, "name", "") or "").lower()
    sku = (getattr(product, "sku", "") or "").lower()
    barcode = (getattr(product, "barcode", "") or "").lower()
    haystack = " ".join([name, sku, barcode]).strip()
    if not haystack:
        return 0
    if query in {sku, barcode, str(getattr(product, "id", ""))}:
        return 100
    if name.startswith(query) or sku.startswith(query) or barcode.startswith(query):
        return 92
    if query in haystack:
        return 82
    best_word = max((SequenceMatcher(None, query, word).ratio() for word in haystack.split()), default=0)
    full_score = SequenceMatcher(None, query, haystack[: max(len(query) + 8, 12)]).ratio()
    return int(max(best_word, full_score) * 70)


def _txn_mode(mode):
    mode = (mode or "cash").lower()
    if mode in {"cash", "upi", "bank", "cheque", "online"}:
        return mode
    return "online"


def _commerce_product_for(platform_product, owner):
    product = CommerceProduct.objects.filter(sku=platform_product.sku).first()
    if product:
        return product
    category = None
    if platform_product.category:
        category = CommerceCategory.objects.filter(owner=owner, name=platform_product.category.name).first()
        if not category:
            category = CommerceCategory.objects.create(
                owner=owner,
                name=platform_product.category.name,
                description="Synced from POS catalog",
            )
    return CommerceProduct.objects.create(
        owner=owner,
        name=platform_product.name,
        category=category,
        price=platform_product.b2c_price,
        stock=0,
        min_stock=0,
        sku=platform_product.sku,
        description=platform_product.description,
        unit="pcs",
        hsn_code=platform_product.hs_code or "",
        gst_rate=platform_product.gst_percent,
    )


def _custom_commerce_product(*, owner, name, price, gst_percent):
    sku = f"POS-CUSTOM-{uuid4().hex[:10].upper()}"
    category = CommerceCategory.objects.filter(owner=owner, name="POS Custom").first()
    if not category:
        category = CommerceCategory.objects.create(owner=owner, name="POS Custom", description="Loose/custom POS items")
    return CommerceProduct.objects.create(
        owner=owner,
        name=name[:100] or "Custom Item",
        category=category,
        price=price,
        stock=0,
        min_stock=0,
        sku=sku,
        description="Created from POS custom item",
        unit="pcs",
        gst_rate=gst_percent,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def catalog(request):
    q = (request.GET.get("q") or "").strip()
    category = (request.GET.get("category") or "").strip()
    mode = (request.GET.get("mode") or "retail").strip().lower()

    products = Product.objects.select_related("category").filter(is_active=True).order_by("name")
    if category and category != "all":
        products = products.filter(category__name__iexact=category)
    if q:
        if len(q) >= 3:
            broad_qs = products.filter(Q(name__icontains=q) | Q(sku__icontains=q) | Q(barcode__icontains=q))[:350]
            broad_products = list(broad_qs)
            if len(broad_products) < 12:
                broad_products = list(products[:600])
            scored = [
                (score, product)
                for product in broad_products
                if (score := _catalog_match_score(product, q)) >= 30
            ]
            scored.sort(key=lambda row: (-row[0], row[1].name.lower(), row[1].id))
            products = [product for _, product in scored[:120]]
        else:
            products = products.filter(Q(name__icontains=q) | Q(sku__icontains=q) | Q(barcode__icontains=q))

    if not isinstance(products, list):
        products = list(products[:120])
    categories = list(
        Category.objects.filter(is_active=True, products__is_active=True)
        .distinct()
        .order_by("name")
        .values_list("name", flat=True)
    )
    payload = [_product_payload(product) for product in products]
    return response.Response(
        {
            "mode": mode,
            "categories": categories,
            "products": payload,
            "terminal": {
                "currency": "INR",
                "payment_modes": ["cash", "upi", "card", "wallet", "split"],
                "price_modes": ["retail", "wholesale", "b2b"],
                "hardware": {
                    "barcode_keyboard": True,
                    "web_serial": True,
                    "thermal_print": True,
                    "offline_queue": True,
                    "touch": True,
                },
            },
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def customers(request):
    q = (request.GET.get("q") or "").strip()
    parties = Party.objects.filter(owner=request.user, party_type="customer", is_active=True).order_by("name")
    if q:
        parties = parties.filter(Q(name__icontains=q) | Q(mobile__icontains=q) | Q(email__icontains=q) | Q(gst__icontains=q))
    return response.Response(
        {
            "customers": [
                {
                    "id": party.id,
                    "name": party.name,
                    "mobile": party.mobile,
                    "email": party.email,
                    "gst": party.gst,
                    "address": party.address,
                    "balance": str(party.balance()),
                }
                for party in parties[:100]
            ]
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def checkout(request):
    items = request.data.get("items") or []
    if not items:
        return response.Response({"detail": "No items in cart."}, status=status.HTTP_400_BAD_REQUEST)

    client_ref = (request.data.get("client_ref") or "").strip()
    if client_ref:
        existing_payment = (
            CommercePayment.objects.select_related("invoice", "invoice__order")
            .filter(invoice__order__owner=request.user, reference=client_ref, is_deleted=False)
            .order_by("-id")
            .first()
        )
        if existing_payment:
            invoice = existing_payment.invoice
            order = invoice.order
            return response.Response(
                {
                    "ok": True,
                    "duplicate": True,
                    "commerce_order_id": order.id,
                    "invoice_id": invoice.id,
                    "invoice_number": invoice.number,
                    "bill_number": client_ref,
                    "total": str(invoice.amount),
                    "paid": str(existing_payment.amount),
                    "change": "0.00",
                    "created_at": timezone.localtime(invoice.created_at).strftime("%d %b %Y %H:%M"),
                }
            )

    discount_total = _money(request.data.get("discount_total"))
    payments = request.data.get("payments") or []
    tender_total = sum((_money(p.get("amount")) for p in payments), Decimal("0.00"))

    order_items = []
    subtotal = Decimal("0.00")
    for item in items:
        product_id = item.get("product_id") or item.get("id")
        qty = int(Decimal(str(item.get("qty") or "1")))
        if qty <= 0:
            continue
        if product_id:
            product = Product.objects.filter(id=product_id, is_active=True).first()
            if not product:
                return response.Response({"detail": f"Product not found: {product_id}"}, status=status.HTTP_400_BAD_REQUEST)
            unit_price = _money(item.get("unit_price") or item.get("price") or product.b2c_price)
        else:
            unit_price = _money(item.get("unit_price") or item.get("price"))
            category, _ = Category.objects.get_or_create(slug="pos-custom", defaults={"name": "POS Custom"})
            sku = f"POS-CUSTOM-{uuid4().hex[:10].upper()}"
            product = Product.objects.create(
                name=(item.get("name") or "Custom Item")[:200],
                category=category,
                sku=sku,
                barcode=sku,
                gst_percent=_money(item.get("gst_percent")),
                mrp=unit_price,
                b2b_price=unit_price,
                b2c_price=unit_price,
                wholesale_price=unit_price,
                track_inventory=False,
                allow_oos=True,
                is_active=True,
            )
        line_discount = _money(item.get("discount"))
        subtotal += (unit_price * qty) - line_discount
        order_items.append(
            {
                "product_id": product.id,
                "qty": qty,
                "unit_price": str(unit_price),
                "discount": str(line_discount),
                "unit_cost": str(item.get("unit_cost") or "0.00"),
            }
        )

    total = subtotal - discount_total
    if total < 0:
        total = Decimal("0.00")
    if tender_total and tender_total < total:
        return response.Response({"detail": "Tender amount is less than payable total."}, status=status.HTTP_400_BAD_REQUEST)

    with transaction.atomic():
        price_mode = (request.data.get("price_mode") or "retail").strip().lower()
        channel = "b2c" if price_mode == "retail" else "b2b" if price_mode == "b2b" else "pos"
        platform_order = place_order(
            {
                "channel": channel,
                "order_type": Order.OrderType.POS,
                "items": order_items,
                "walk_in_customer_name": request.data.get("customer_name", "") or "Walk-in Customer",
                "notes": request.data.get("notes", ""),
            },
            actor=request.user,
        )
        if discount_total:
            platform_order.discount_amount = (platform_order.discount_amount or Decimal("0.00")) + discount_total
            platform_order.total_amount = max((platform_order.total_amount or Decimal("0.00")) - discount_total, Decimal("0.00"))
            platform_order.save(update_fields=["discount_amount", "total_amount", "updated_at"])

        bill = POSBill.objects.create(
            order=platform_order,
            bill_number=f"POS-{timezone.now():%y%m%d}-{uuid4().hex[:6].upper()}",
            cashier=request.user,
            terminal_id=request.data.get("terminal_id") or "WEB-POS",
            payment_mode=(payments[0].get("mode") if payments else request.data.get("payment_mode") or "cash"),
            printed_at=timezone.now() if request.data.get("printed") else None,
        )

        party_id = request.data.get("party_id") or request.data.get("customer_id")
        customer_name = (request.data.get("customer_name") or "").strip()
        party = None
        if party_id:
            party = Party.objects.filter(id=party_id, owner=request.user, party_type="customer").first()
        if not party:
            party = Party.objects.filter(
                owner=request.user,
                party_type="customer",
                name=customer_name or "Walk-in Customer",
            ).first()
        if not party:
            party = Party.objects.create(
                owner=request.user,
                party_type="customer",
                name=customer_name or "Walk-in Customer",
                mobile=request.data.get("customer_mobile") or "",
            )

        commerce_order = CommerceOrder.objects.create(
            owner=request.user,
            party=party,
            placed_by="user",
            status="completed",
            order_type="SALE",
            order_source="POS",
            notes=f"POS Bill {bill.bill_number}; platform order {platform_order.order_number}",
            discount_type="flat" if discount_total else "none",
            discount_value=discount_total,
            discount_amount=discount_total,
        )

        commerce_tax_percent = Decimal("0.00")
        for item in items:
            product_id = item.get("product_id") or item.get("id")
            qty = int(Decimal(str(item.get("qty") or "1")))
            if qty <= 0:
                continue
            unit_price = _money(item.get("unit_price") or item.get("price"))
            line_gst = _money(item.get("gst_percent"))
            commerce_product = None
            if product_id:
                platform_product = Product.objects.filter(id=product_id).first()
                if platform_product:
                    commerce_product = _commerce_product_for(platform_product, request.user)
                    line_gst = platform_product.gst_percent or line_gst
                    if not unit_price:
                        unit_price = platform_product.b2c_price
            if not commerce_product:
                commerce_product = _custom_commerce_product(
                    owner=request.user,
                    name=item.get("name") or "Custom Item",
                    price=unit_price,
                    gst_percent=line_gst,
                )
            commerce_tax_percent = max(commerce_tax_percent, Decimal(str(line_gst or "0")))
            CommerceOrderItem.objects.create(
                order=commerce_order,
                product=commerce_product,
                qty=qty,
                price=unit_price,
                tax_percent=line_gst,
                raw_name=item.get("name") or "",
            )

        commerce_order.tax_percent = commerce_tax_percent
        commerce_order.save()
        commerce_invoice = CommerceInvoice.objects.create(
            order=commerce_order,
            gst_type="GST" if commerce_tax_percent > 0 else "NON_GST",
            amount=commerce_order.total_amount(),
            status="paid",
        )
        payment_mode = (payments[0].get("mode") if payments else request.data.get("payment_mode") or "cash")
        payment_reference = client_ref or bill.bill_number
        existing_commerce_payment = CommercePayment.objects.filter(
            invoice=commerce_invoice,
            amount=commerce_invoice.amount,
            reference=payment_reference,
            is_deleted=False,
        ).first()
        commerce_payment = existing_commerce_payment or CommercePayment.objects.create(
            invoice=commerce_invoice,
            amount=commerce_invoice.amount,
            method=payment_mode,
            reference=payment_reference,
            note="Auto-created from POS checkout",
        )

    return response.Response(
        {
            "ok": True,
            "order_id": platform_order.id,
            "order_number": platform_order.order_number,
            "commerce_order_id": commerce_order.id,
            "invoice_id": commerce_invoice.id,
            "invoice_number": commerce_invoice.number,
            "bill_number": bill.bill_number,
            "subtotal": str(platform_order.subtotal),
            "discount": str(platform_order.discount_amount),
            "tax": str(platform_order.tax_amount),
            "total": str(commerce_invoice.amount),
            "paid": str(tender_total or commerce_invoice.amount),
            "change": str(max((tender_total or commerce_invoice.amount) - commerce_invoice.amount, Decimal("0.00"))),
            "created_at": timezone.localtime(platform_order.created_at).strftime("%d %b %Y %H:%M"),
        },
        status=status.HTTP_201_CREATED,
    )
