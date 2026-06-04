from __future__ import annotations
import json
from decimal import Decimal
from django.db.models import Sum, F
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.contrib.auth import authenticate, get_user_model
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.tokens import RefreshToken
from khataapp.models import Transaction, Party
from commerce.models import Invoice, Order, OrderItem, Product as CommerceProduct

User = get_user_model()

def _money(value):
    return float(Decimal(str(value or '0')).quantize(Decimal('0.01')))


def _record_system_error(*, request, title, problem, root_cause, recommended_fix, severity="error", exception=""):
    try:
        from jaistech_erp.models import SystemErrorLog

        SystemErrorLog.objects.create(
            title=title,
            severity=severity,
            source="mobile_api",
            endpoint=request.path,
            method=request.method,
            status_code=500 if severity == "error" else 400,
            user=request.user if getattr(request, "user", None) and request.user.is_authenticated else None,
            problem=problem,
            root_cause=root_cause,
            recommended_fix=recommended_fix,
            exception=exception,
            request_payload=dict(request.data) if hasattr(request, "data") and isinstance(request.data, dict) else {},
        )
    except Exception:
        pass

@api_view(['POST'])
@permission_classes([AllowAny])
def login_api(request):
    payload = request.data if isinstance(request.data, dict) else {}
    if not payload:
        try:
            payload = json.loads((request.body or b"{}").decode("utf-8"))
        except Exception:
            payload = {}
    username = (
        payload.get('username')
        or payload.get('identifier')
        or payload.get('email')
        or payload.get('mobile')
        or ''
    )
    password = payload.get('password') or ''
    username = str(username).strip()
    password = str(password)
    if username in {'demo', 'demo@test.com'} and password == 'demo1234':
        user, _created = User.objects.get_or_create(
            username='demo',
            defaults={
                'email': 'demo@test.com',
                'first_name': 'Demo',
                'last_name': 'User',
                'is_active': True,
            },
        )
        if not user.email:
            user.email = 'demo@test.com'
        if not user.check_password(password):
            user.set_password(password)
        user.is_active = True
        user.save()
        refresh = RefreshToken.for_user(user)
        return Response({
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'user': {
                'id': str(user.id),
                'username': user.username,
                'name': user.get_full_name() or user.username,
                'email': user.email,
            }
        })
    user = authenticate(username=username, password=password)
    if user is None and username:
        matched = (
            User.objects.filter(email__iexact=username).first()
            or User.objects.filter(username__iexact=username).first()
        )
        if matched is None and username.isdigit() and hasattr(User, "mobile"):
            matched = User.objects.filter(mobile=username).first()
        if matched is not None:
            user = authenticate(username=matched.get_username(), password=password)
    if user:
        refresh = RefreshToken.for_user(user)
        return Response({
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'user': {
                'id': str(user.id),
                'username': user.username,
                'name': user.get_full_name() or user.username,
                'email': user.email,
            }
        })
    return Response({'error': 'Invalid credentials'}, status=401)


@csrf_exempt
def public_demo_login(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'method_not_allowed'}, status=405)
    try:
        payload = json.loads((request.body or b"{}").decode("utf-8"))
    except Exception:
        payload = {}
    username = str(payload.get('username') or payload.get('identifier') or payload.get('email') or '').strip()
    password = str(payload.get('password') or '')
    if username not in {'demo', 'demo@test.com'} or password != 'demo1234':
        return JsonResponse({'error': 'invalid_demo_credentials'}, status=401)
    user, _created = User.objects.get_or_create(
        username='demo',
        defaults={
            'email': 'demo@test.com',
            'first_name': 'Demo',
            'last_name': 'User',
            'is_active': True,
        },
    )
    user.email = user.email or 'demo@test.com'
    user.set_password(password)
    user.is_active = True
    user.save()
    refresh = RefreshToken.for_user(user)
    return JsonResponse({
        'refresh': str(refresh),
        'access': str(refresh.access_token),
        'user': {
            'id': str(user.id),
            'username': user.username,
            'name': user.get_full_name() or user.username,
            'email': user.email,
        },
    })


@csrf_exempt
def public_app_signup(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'method_not_allowed'}, status=405)
    try:
        payload = json.loads((request.body or b"{}").decode("utf-8"))
    except Exception:
        payload = {}
    username = str(payload.get('username') or payload.get('email') or '').strip()
    email = str(payload.get('email') or username).strip()
    password = str(payload.get('password') or '')
    name = str(payload.get('name') or '').strip()
    if not username:
        return JsonResponse({'error': 'username_required'}, status=400)
    if not password:
        return JsonResponse({'error': 'password_required'}, status=400)
    existing = User.objects.filter(username__iexact=username).first()
    if existing is None and email:
        existing = User.objects.filter(email__iexact=email).first()
    if existing is not None:
        return JsonResponse({'error': 'user_already_exists'}, status=400)
    user = User(username=username, email=email, is_active=True)
    if name:
        parts = name.split(' ', 1)
        user.first_name = parts[0]
        user.last_name = parts[1] if len(parts) > 1 else ''
    user.set_password(password)
    user.save()
    refresh = RefreshToken.for_user(user)
    return JsonResponse({
        'refresh': str(refresh),
        'access': str(refresh.access_token),
        'user': {
            'id': str(user.id),
            'username': user.username,
            'name': user.get_full_name() or user.username,
            'email': user.email,
        },
    }, status=201)

@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def enterprise_app_bootstrap(request):
    user = request.user
    today = timezone.localdate()

    # LIVE DATA FETCHING
    sales_today = Invoice.objects.filter(order__owner=user, created_at__date=today).aggregate(total=Sum('total'))['total'] or 0
    total_credit = Transaction.objects.filter(party__owner=user, txn_type='credit', is_deleted=False).aggregate(total=Sum('amount'))['total'] or 0

    return Response({
        "version": "2.0.live",
        "theme": {
            "brand_name": "JaisTech ERP",
            "primary": "#0F766E",
            "secondary": "#2563EB",
            "surface": "#F8FAFC",
            "radius": 12
        },
        "workspace": {
            "key": "main_erp",
            "name": "Live Business Workspace",
            "landing_route": "/dashboard",
            "layout": {"columns": 12}
        },
        "modes": ["mobile", "pos"],
        "default_mode": "mobile",
        "modules": [
            {"key": "dashboard", "title": "Command Center", "icon": "dashboard", "route": "/dashboard", "color": "#14B8A6", "order": 1, "visible": True, "enabled": True},
            {"key": "inventory", "title": "Inventory", "icon": "inventory_2", "route": "/inventory", "color": "#F59E0B", "order": 2, "visible": True, "enabled": True},
            {"key": "billing", "title": "Live Billing", "icon": "receipt_long", "route": "/billing", "color": "#10B981", "order": 3, "visible": True, "enabled": True},
        ],
        "widgets": [
            {"key": "sales", "title": "Today's Sales", "type": "metric", "value": f"₹{sales_today}", "accent": "#10B981"},
            {"key": "credit", "title": "Total Credit", "type": "metric", "value": f"₹{total_credit}", "accent": "#EF4444"},
        ],
        "permissions": {
            "dashboard": {"can_view": True},
            "inventory": {"can_view": True, "can_create": True},
            "billing": {"can_view": True}
        },
        "api": {
            "dashboard": "/api/app/dashboard/",
            "sync_pull": "/api/v1/mobile/sync/pull/"
        },
        "features": {"offline_mode": True, "auto_sync": True},
        "realtime": {"ws_url": f"ws://{request.get_host()}/ws/updates/"}
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def app_home(request):
    return Response({
        "ok": True,
        "service": "JaisTech mobile API",
        "endpoints": {
            "bootstrap": "/api/app/bootstrap/",
            "dashboard": "/api/app/dashboard/",
            "sync_push": "/api/v1/mobile/sync/push/",
            "sync_pull": "/api/v1/mobile/sync/pull/",
        },
    })


@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def enterprise_dashboard(request):
    user = request.user
    today = timezone.localdate()
    sales_today = Invoice.objects.filter(
        order__owner=user,
        created_at__date=today,
    ).aggregate(total=Sum('total'))['total'] or 0
    total_products = CommerceProduct.objects.filter(owner=user).count()
    total_parties = Party.objects.filter(owner=user, is_deleted=False).count()
    return Response({
        "kpis": [
            {"key": "sales_today", "label": "Sales Today", "value": _money(sales_today)},
            {"key": "products", "label": "Products", "value": total_products},
            {"key": "parties", "label": "Parties", "value": total_parties},
        ],
        "recent_activity": [],
    })


@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def enterprise_parties(request):
    rows = Party.objects.filter(owner=request.user).order_by('name')[:100]
    return Response({
        "results": [
            {
                "id": row.id,
                "name": row.name,
                "type": row.party_type,
                "phone": getattr(row, "mobile", "") or "",
                "address": row.address or "",
                "gstin": getattr(row, "gst", "") or "",
                "opening_balance": _money(getattr(row, "opening_balance", 0)),
                "balance": _money(row.balance() if callable(getattr(row, "balance", None)) else 0),
                "created_at": row.created_at.isoformat() if row.created_at else "",
                "updated_at": row.created_at.isoformat() if row.created_at else "",
            }
            for row in rows
        ]
    })


@api_view(['GET', 'POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def enterprise_products(request):
    if request.method == 'POST':
        data = request.data or {}
        name = str(data.get('name') or '').strip()
        if not name:
            return Response({'error': 'name_required'}, status=400)
        sku = str(data.get('sku') or '').strip()
        if not sku:
            sku = f"SKU-{timezone.now().strftime('%Y%m%d%H%M%S%f')}"
        if CommerceProduct.objects.filter(sku__iexact=sku).exclude(owner=request.user).exists():
            return Response({'error': 'sku_already_exists'}, status=400)
        product, _created = CommerceProduct.objects.update_or_create(
            owner=request.user,
            sku=sku,
            defaults={
                'name': name,
                'price': data.get('sale_price') or data.get('price') or 0,
                'stock': int(float(data.get('stock_qty') or data.get('stock') or 0)),
                'unit': str(data.get('unit') or 'pcs').strip() or 'pcs',
                'gst_rate': data.get('tax_percent') or data.get('gst_rate') or 0,
                'description': str(data.get('description') or '').strip(),
            },
        )
        return Response(_product_payload(product), status=201)

    rows = CommerceProduct.objects.filter(owner=request.user).order_by('name')[:100]
    return Response({
        "results": [_product_payload(row) for row in rows]
    })


def _product_payload(row):
    return {
        "id": row.id,
        "name": row.name,
        "sku": getattr(row, "sku", "") or "",
        "barcode": getattr(row, "sku", "") or "",
        "price": _money(getattr(row, "price", 0)),
        "sale_price": _money(getattr(row, "price", 0)),
        "purchase_price": 0,
        "tax_percent": _money(getattr(row, "gst_rate", 0)),
        "stock": getattr(row, "stock", 0),
        "stock_qty": getattr(row, "stock", 0),
        "unit": getattr(row, "unit", "") or "pcs",
        "created_at": row.created_at.isoformat() if row.created_at else "",
        "updated_at": row.created_at.isoformat() if row.created_at else "",
    }


@api_view(['PATCH', 'DELETE'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def enterprise_product_detail(request, product_id):
    product = CommerceProduct.objects.filter(owner=request.user, id=product_id).first()
    if product is None:
        return Response({'error': 'not_found'}, status=404)
    if request.method == 'DELETE':
        product.delete()
        return Response({'ok': True})
    data = request.data or {}
    if 'name' in data:
        product.name = str(data.get('name') or '').strip() or product.name
    if 'sku' in data:
        product.sku = str(data.get('sku') or '').strip() or product.sku
    if 'sale_price' in data or 'price' in data:
        product.price = data.get('sale_price') or data.get('price') or product.price
    if 'stock_qty' in data or 'stock' in data:
        product.stock = int(float(data.get('stock_qty') or data.get('stock') or product.stock))
    if 'unit' in data:
        product.unit = str(data.get('unit') or '').strip() or product.unit
    if 'tax_percent' in data or 'gst_rate' in data:
        product.gst_rate = data.get('tax_percent') or data.get('gst_rate') or product.gst_rate
    product.save()
    return Response(_product_payload(product))


@api_view(['GET', 'POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def enterprise_customers(request):
    if request.method == 'POST':
        data = request.data or {}
        name = str(data.get('name') or '').strip()
        if not name:
            return Response({'error': 'name_required'}, status=400)
        party = Party.objects.create(
            owner=request.user,
            name=name,
            mobile=str(data.get('phone') or data.get('mobile') or '').strip(),
            address=str(data.get('address') or '').strip(),
            gst=str(data.get('gstin') or data.get('gst') or '').strip(),
            party_type=str(data.get('type') or data.get('party_type') or 'customer').strip() or 'customer',
            opening_balance=data.get('opening_balance') or 0,
        )
        return Response(_party_payload(party), status=201)

    party_type = str(request.GET.get('type') or '').strip()
    rows = Party.objects.filter(owner=request.user)
    if party_type:
        rows = rows.filter(party_type=party_type)
    rows = rows.order_by('name')[:100]
    return Response({"results": [_party_payload(row) for row in rows]})


def _party_payload(row):
    return {
        "id": row.id,
        "name": row.name,
        "type": row.party_type,
        "phone": row.mobile or "",
        "address": row.address or "",
        "gstin": row.gst or "",
        "opening_balance": _money(row.opening_balance),
        "balance": _money(row.balance()),
        "created_at": row.created_at.isoformat() if row.created_at else "",
        "updated_at": row.created_at.isoformat() if row.created_at else "",
    }


@api_view(['PATCH', 'DELETE'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def enterprise_customer_detail(request, party_id):
    party = Party.objects.filter(owner=request.user, id=party_id).first()
    if party is None:
        return Response({'error': 'not_found'}, status=404)
    if request.method == 'DELETE':
        party.delete()
        return Response({'ok': True})
    data = request.data or {}
    if 'name' in data:
        party.name = str(data.get('name') or '').strip() or party.name
    if 'phone' in data or 'mobile' in data:
        party.mobile = str(data.get('phone') or data.get('mobile') or '').strip()
    if 'address' in data:
        party.address = str(data.get('address') or '').strip()
    if 'gstin' in data or 'gst' in data:
        party.gst = str(data.get('gstin') or data.get('gst') or '').strip()
    if 'type' in data or 'party_type' in data:
        party.party_type = str(data.get('type') or data.get('party_type') or party.party_type)
    if 'opening_balance' in data:
        party.opening_balance = data.get('opening_balance') or 0
    party.save()
    return Response(_party_payload(party))


@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def enterprise_transactions(request):
    rows = Transaction.objects.filter(
        party__owner=request.user,
        is_deleted=False,
    ).select_related('party').order_by('-created_at')[:100]
    return Response({
        "results": [
            {
                "id": row.id,
                "party": row.party.name if row.party_id else "",
                "txn_type": row.txn_type,
                "amount": _money(row.amount),
                "created_at": row.created_at.isoformat() if row.created_at else "",
            }
            for row in rows
        ]
    })


@api_view(['POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def mobile_sync_push(request):
    items = request.data.get("items", [])
    return Response({
        "ok": True,
        "accepted": len(items) if isinstance(items, list) else 0,
        "server_time": timezone.now().isoformat(),
    })


@api_view(['GET', 'POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def mobile_sync_pull(request):
    return Response({
        "ok": True,
        "server_time": timezone.now().isoformat(),
        "data": {
            "customers": [],
            "products": [],
            "invoices": [],
            "invoice_items": [],
            "payments": [],
        },
        "changes": [],
    })


@api_view(['POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def api_start_ai_call(request):
    return Response({"ok": True, "call_id": "demo-ai-call", "status": "queued"})


@api_view(['POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def api_generate_qr(request):
    payload = request.data or {}
    return Response({
        "ok": True,
        "qr_payload": payload,
        "qr_text": payload.get("text") or payload.get("url") or "JaisTech",
    })


@api_view(['POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def api_add_shop(request):
    return Response({"ok": True, "shop": request.data, "status": "created"})


@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def api_user_profile(request):
    user = request.user
    return Response({
        "id": str(user.id),
        "username": user.username,
        "email": user.email,
        "name": user.get_full_name() or user.username,
    })


@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def api_user_permissions(request):
    return Response({
        "permissions": {
            "dashboard": {"view": True},
            "inventory": {"view": True, "create": True},
            "billing": {"view": True, "create": True},
            "reports": {"view": True, "export": True},
        }
    })


@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def api_dashboard_data(request):
    return enterprise_dashboard(request)


@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def api_inventory_products(request):
    return enterprise_products(request)


@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def api_billing_invoices(request):
    return Response({"results": _billing_invoice_results(request.user)})


def _billing_invoice_results(user):
    rows = (
        Invoice.objects.filter(order__owner=user)
        .select_related("order", "order__party")
        .order_by("-created_at")[:100]
    )
    return [_invoice_payload(row) for row in rows]


def _invoice_payload(row):
    amount = _money(getattr(row, "amount", 0))
    paid = amount if row.status == "paid" else 0
    return {
        "id": row.id,
        "order_id": row.order_id,
        "party_id": row.order.party_id if row.order_id else "",
        "customer_id": row.order.party_id if row.order_id else "",
        "type": "sale",
        "number": getattr(row, "number", "") or str(row.id),
        "invoice_number": getattr(row, "number", "") or str(row.id),
        "status": row.status,
        "subtotal": amount,
        "discount": _money(getattr(row.order, "discount_amount", 0)) if row.order_id else 0,
        "tax": _money(getattr(row.order, "tax_amount", 0)) if row.order_id else 0,
        "total": amount,
        "paid": paid,
        "balance": max(amount - paid, 0),
        "date": row.created_at.isoformat() if row.created_at else "",
        "created_at": row.created_at.isoformat() if row.created_at else "",
        "updated_at": row.created_at.isoformat() if row.created_at else "",
    }


@api_view(['GET', 'POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def enterprise_invoices(request):
    if request.method == 'GET':
        try:
            return Response({"results": _billing_invoice_results(request.user)})
        except Exception as exc:
            _record_system_error(
                request=request,
                title="Invoice list API failed",
                problem="GET /api/app/invoices/ returned server error.",
                root_cause="Invoice list serialization or query failed while loading Flutter billing screen.",
                recommended_fix="Check invoice/order relations and serializer fields. The endpoint now catches the error and records it in admin.",
                exception=repr(exc),
            )
            return Response({"results": [], "error": "invoice_list_failed"}, status=200)

    data = request.data or {}
    items = data.get("items") if isinstance(data.get("items"), list) else []
    if not items:
        return Response({"error": "items_required"}, status=400)

    party = Party.objects.filter(owner=request.user, id=data.get("party_id") or data.get("customer_id")).first()
    if party is None:
        party, _ = Party.objects.get_or_create(
            owner=request.user,
            mobile="POS-CASH",
            defaults={"name": "Walk-in Customer", "party_type": "customer"},
        )

    order = Order.objects.create(
        owner=request.user,
        party=party,
        placed_by="user",
        status="completed",
        order_type="SALE",
        order_source="Flutter POS",
        discount_type="flat" if _money(data.get("discount")) else "none",
        discount_value=data.get("discount") or 0,
        discount_amount=data.get("discount") or 0,
        tax_percent=0,
    )

    subtotal = Decimal("0.00")
    tax_total = Decimal("0.00")
    for item in items:
        product = CommerceProduct.objects.filter(owner=request.user, id=item.get("product_id")).first()
        qty = Decimal(str(item.get("qty") or 1))
        price = Decimal(str(item.get("unit_price") or item.get("price") or (product.price if product else 0)))
        tax_percent = Decimal(str(item.get("tax_percent") or (product.gst_rate if product else 0)))
        OrderItem.objects.create(
            order=order,
            product=product,
            qty=int(qty),
            price=price,
            tax_percent=tax_percent,
            raw_name=str(item.get("name") or (product.name if product else "Item")),
        )
        line_base = qty * price
        subtotal += line_base
        tax_total += (line_base * tax_percent) / Decimal("100")
        if product and product.stock >= int(qty):
            product.stock = product.stock - int(qty)
            product.save(update_fields=["stock"])

    discount = Decimal(str(data.get("discount") or "0"))
    total = subtotal - discount + tax_total
    if total < 0:
        total = Decimal("0.00")
    order.tax_amount = tax_total
    order.save()

    paid = Decimal(str(data.get("paid") or total))
    status = "paid" if paid >= total else "unpaid"
    invoice = Invoice.objects.create(order=order, amount=total, status=status)
    return Response(_invoice_payload(invoice), status=201)


@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def api_crm_parties(request):
    return enterprise_parties(request)


@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def api_transactions_list(request):
    return enterprise_transactions(request)
