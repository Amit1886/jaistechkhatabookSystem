# mobileapi/dashboard_apis.py
"""
Complete Dashboard APIs for Flutter App
Provides all data visible in web dashboard through JSON APIs
"""

from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.response import Response
from django.db.models import Sum, Count, Q
from django.utils import timezone
from decimal import Decimal
from datetime import timedelta

from khataapp.models import Party, Transaction
from commerce.models import Invoice, Payment, Product, Order
from billing.models import Plan, Subscription


def _money(value):
    """Format decimal to money string"""
    try:
        return str(Decimal(str(value or "0")).quantize(Decimal("0.01")))
    except:
        return "0.00"


@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def api_recent_parties(request):
    """Get recent parties (customers and suppliers)"""
    user = request.user
    limit = int(request.GET.get('limit', 12))
    party_type = request.GET.get('type', '')  # customer, supplier, or all
    
    qs = Party.objects.filter(owner=user).order_by('-created_at')
    if party_type and party_type != 'all':
        qs = qs.filter(party_type=party_type)
    
    parties = qs[:limit]
    
    return Response({
        'success': True,
        'count': min(len(parties), limit),
        'results': [
            {
                'id': p.id,
                'name': p.name,
                'type': p.party_type or 'customer',
                'phone': getattr(p, 'phone', '') or '',
                'email': getattr(p, 'email', '') or '',
                'address': getattr(p, 'address', '') or '',
                'grade': getattr(p, 'grade', '') or '-',
                'created_at': p.created_at.isoformat() if p.created_at else None,
            }
            for p in parties
        ]
    })


@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def api_recent_transactions(request):
    """Get recent transactions (today and recent days)"""
    user = request.user
    limit = int(request.GET.get('limit', 12))
    days = int(request.GET.get('days', 0))  # 0 = today only
    
    qs = Transaction.objects.filter(
        party__owner=user, is_deleted=False
    ).select_related('party').order_by('-created_at')
    
    if days > 0:
        since = timezone.now() - timedelta(days=days)
        qs = qs.filter(created_at__gte=since)
    else:
        today = timezone.localdate()
        qs = qs.filter(created_at__date=today)
    
    transactions = qs[:limit]
    
    return Response({
        'success': True,
        'count': min(len(transactions), limit),
        'results': [
            {
                'id': t.id,
                'party_id': t.party_id,
                'party_name': t.party.name,
                'type': t.txn_type,
                'amount': _money(t.amount),
                'date': t.created_at.isoformat() if t.created_at else None,
                'notes': t.description or '',
                'reference': getattr(t, 'reference', '') or '',
            }
            for t in transactions
        ]
    })


@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def api_today_summary(request):
    """Get today's summary: credits, debits, balance"""
    user = request.user
    today = timezone.localdate()
    
    # Today's transactions
    credits = Transaction.objects.filter(
        party__owner=user, txn_type="credit", 
        is_deleted=False, created_at__date=today
    ).aggregate(total=Sum("amount"))["total"] or Decimal("0")
    
    debits = Transaction.objects.filter(
        party__owner=user, txn_type="debit", 
        is_deleted=False, created_at__date=today
    ).aggregate(total=Sum("amount"))["total"] or Decimal("0")
    
    balance = debits - credits
    
    # Today's payments
    payments_received = Payment.objects.filter(
        invoice__order__owner=user, 
        created_at__date=today, 
        is_deleted=False
    ).aggregate(total=Sum("amount"))["total"] or Decimal("0")
    
    # Today's sales
    sales = Invoice.objects.filter(
        order__owner=user, 
        created_at__date=today
    ).aggregate(total=Sum("amount"))["total"] or Decimal("0")
    
    return Response({
        'success': True,
        'date': str(today),
        'summary': {
            'total_credit': _money(credits),
            'total_debit': _money(debits),
            'balance': _money(balance),
            'balance_type': 'positive' if balance >= 0 else 'negative',
            'payments_received': _money(payments_received),
            'total_sales': _money(sales),
        }
    })


@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def api_business_snapshot(request):
    """Get business snapshot: revenue, purchases, profit, cash flow"""
    user = request.user
    today = timezone.localdate()
    
    # Today's data
    total_sales = Invoice.objects.filter(
        order__owner=user, created_at__date=today
    ).aggregate(total=Sum("amount"))["total"] or Decimal("0")
    
    sales_count = Order.objects.filter(
        owner=user, created_at__date=today
    ).count()
    
    total_purchase = Transaction.objects.filter(
        party__owner=user, txn_type="debit",
        is_deleted=False, created_at__date=today
    ).aggregate(total=Sum("amount"))["total"] or Decimal("0")
    
    purchase_count = Transaction.objects.filter(
        party__owner=user, txn_type="debit",
        is_deleted=False, created_at__date=today
    ).count()
    
    profit = total_sales - total_purchase
    
    # Cash flow
    payment_received = Payment.objects.filter(
        invoice__order__owner=user,
        created_at__date=today, is_deleted=False
    ).aggregate(total=Sum("amount"))["total"] or Decimal("0")
    
    payment_given = Transaction.objects.filter(
        party__owner=user, txn_type="debit",
        is_deleted=False, created_at__date=today
    ).aggregate(total=Sum("amount"))["total"] or Decimal("0")
    
    # Receivables/Payables
    receivable = Transaction.objects.filter(
        party__owner=user, txn_type="credit",
        is_deleted=False, created_at__date=today
    ).aggregate(total=Sum("amount"))["total"] or Decimal("0")
    
    payable = Transaction.objects.filter(
        party__owner=user, txn_type="debit",
        is_deleted=False
    ).exclude(created_at__date=today).aggregate(total=Sum("amount"))["total"] or Decimal("0")
    
    return Response({
        'success': True,
        'date': str(today),
        'revenue': {
            'total_sales': _money(total_sales),
            'orders': sales_count,
        },
        'purchases': {
            'total_purchase': _money(total_purchase),
            'orders': purchase_count,
        },
        'profit': {
            'amount': _money(profit),
            'status': 'positive' if profit >= 0 else 'negative',
        },
        'cash_flow': {
            'cash_in': _money(payment_received),
            'cash_out': _money(payment_given),
            'receivable': _money(receivable),
            'payable': _money(payable),
        }
    })


@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def api_party_ledger_summary(request):
    """Get party ledger summary with high-due customers"""
    user = request.user
    limit = int(request.GET.get('limit', 12))
    
    # Get all customers with their balances
    customers = Party.objects.filter(
        owner=user, party_type='customer'
    ).order_by('-created_at')
    
    ledger_data = []
    for party in customers[:limit]:
        balance = Transaction.objects.filter(
            party=party, is_deleted=False
        ).aggregate(
            total=Sum("amount")
        )["total"] or Decimal("0")
        
        due = max(balance, Decimal("0"))  # Only show positive balances as due
        credit_score = min(100, max(0, 100 - int(due / 1000)))  # Simple scoring
        
        if due > 0:
            ledger_data.append({
                'party_id': party.id,
                'name': party.name,
                'due': _money(due),
                'credit_score': credit_score,
                'last_reminder': None,
                'type': 'customer',
            })
    
    # Sort by due amount descending
    ledger_data.sort(key=lambda x: float(x['due']), reverse=True)
    
    return Response({
        'success': True,
        'count': len(ledger_data),
        'results': ledger_data[:limit]
    })


@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def api_inventory_status(request):
    """Get inventory status: products, categories, stock levels"""
    user = request.user
    
    total_products = Product.objects.filter(owner=user).count()
    
    low_stock = Product.objects.filter(
        owner=user,
        stock__lte=F('min_stock') if hasattr(Product, 'min_stock') else 10
    ).count() if hasattr(Product, 'min_stock') else 0
    
    # Recent products
    recent = Product.objects.filter(owner=user).order_by('-created_at')[:5]
    
    categories = Product.objects.filter(
        owner=user
    ).values('category').distinct().count()
    
    return Response({
        'success': True,
        'inventory': {
            'total_products': total_products,
            'low_stock_items': low_stock,
            'categories': categories,
            'status': 'synced',
        },
        'recent_products': [
            {
                'id': p.id,
                'name': p.name,
                'sku': p.sku or '',
                'stock': getattr(p, 'stock', 0) or 0,
                'price': str(p.price or 0),
            }
            for p in recent
        ]
    })


@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def api_reports_summary(request):
    """Get available reports and their data"""
    user = request.user
    today = timezone.localdate()
    
    # Trial Balance
    all_txns = Transaction.objects.filter(
        party__owner=user, is_deleted=False
    )
    debit_total = all_txns.filter(txn_type="debit").aggregate(
        total=Sum("amount")
    )["total"] or Decimal("0")
    credit_total = all_txns.filter(txn_type="credit").aggregate(
        total=Sum("amount")
    )["total"] or Decimal("0")
    
    return Response({
        'success': True,
        'reports': {
            'trial_balance': {
                'debit': _money(debit_total),
                'credit': _money(credit_total),
                'status': 'balanced' if abs(debit_total - credit_total) < 1 else 'unbalanced',
            },
            'day_book': {
                'today_transactions': all_txns.filter(created_at__date=today).count(),
                'url': '/api/reports/day-book/',
            },
            'profit_loss': {
                'sales': _money(Invoice.objects.filter(order__owner=user).aggregate(total=Sum("amount"))["total"] or 0),
                'expenses': _money(debit_total),
                'url': '/api/reports/profit-loss/',
            },
            'sales_report': {
                'total_sales': _money(Invoice.objects.filter(order__owner=user).aggregate(total=Sum("amount"))["total"] or 0),
                'orders': Order.objects.filter(owner=user).count(),
                'url': '/api/reports/sales/',
            },
            'inventory_summary': {
                'total_products': Product.objects.filter(owner=user).count(),
                'url': '/api/reports/inventory/',
            },
            'gst_report': {
                'url': '/api/reports/gst/',
            },
        }
    })


@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def api_settings_summary(request):
    """Get user settings and configurations"""
    user = request.user
    
    # Get subscription
    subscription = None
    try:
        subscription = Subscription.objects.filter(user=user, active=True).first()
    except:
        pass
    
    plan_name = "Free"
    if subscription and subscription.plan:
        plan_name = subscription.plan.name
    
    return Response({
        'success': True,
        'user': {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'name': user.get_full_name() or user.username,
        },
        'subscription': {
            'plan': plan_name,
            'status': 'active',
        },
        'settings': {
            'language': 'en',
            'timezone': 'Asia/Kolkata',
            'currency': 'INR',
            'date_format': 'DD-MM-YYYY',
        },
        'features': {
            'pos_mode': True,
            'multi_device': True,
            'whatsapp_orders': True,
            'ai_insights': True,
            'loyalty_program': True,
            'advance_reports': True,
        }
    })


@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def api_commerce_actions(request):
    """Get quick commerce actions for dashboard"""
    user = request.user
    
    return Response({
        'success': True,
        'actions': [
            {
                'id': 'add_product',
                'label': 'Add Product',
                'icon': 'product',
                'url': '/api/products/create/',
                'method': 'POST',
            },
            {
                'id': 'add_order',
                'label': 'Add Order',
                'icon': 'shopping_cart',
                'url': '/api/orders/create/',
                'method': 'POST',
            },
            {
                'id': 'add_invoice',
                'label': 'Add Invoice',
                'icon': 'invoice',
                'url': '/api/invoices/create/',
                'method': 'POST',
            },
            {
                'id': 'add_quotation',
                'label': 'Add Quotation',
                'icon': 'quote',
                'url': '/api/quotations/create/',
                'method': 'POST',
            },
            {
                'id': 'add_payment',
                'label': 'Add Payment',
                'icon': 'payment',
                'url': '/api/payments/create/',
                'method': 'POST',
            },
            {
                'id': 'add_party',
                'label': 'Add Party',
                'icon': 'people',
                'url': '/api/crm/parties/create/',
                'method': 'POST',
            },
            {
                'id': 'add_expense',
                'label': 'Add Expense',
                'icon': 'expense',
                'url': '/api/expenses/create/',
                'method': 'POST',
            },
        ]
    })


@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def api_menu_structure(request):
    """Get complete menu structure for app sidebar"""
    user = request.user
    is_admin = user.is_superuser or user.is_staff
    
    menu = {
        'success': True,
        'menus': [
            {
                'id': 'dashboard',
                'label': 'Dashboard',
                'icon': 'dashboard',
                'url': '/dashboard',
                'visible': True,
            },
            {
                'id': 'self_checkout',
                'label': 'Self Checkout',
                'icon': 'shopping_basket',
                'url': '/self-checkout',
                'visible': is_admin,
            },
            {
                'id': 'ecommerce',
                'label': 'E-commerce',
                'icon': 'store',
                'url': '/ecommerce',
                'visible': is_admin,
            },
            {
                'id': 'billing',
                'label': 'Billing',
                'icon': 'receipt',
                'submenu': [
                    {'label': 'Invoices', 'url': '/billing/invoices'},
                    {'label': 'Credit Notes', 'url': '/billing/credit-notes'},
                    {'label': 'Payments', 'url': '/billing/payments'},
                ],
                'visible': True,
            },
            {
                'id': 'inventory',
                'label': 'Inventory',
                'icon': 'inventory_2',
                'submenu': [
                    {'label': 'Products', 'url': '/inventory/products'},
                    {'label': 'Stock Transfer', 'url': '/inventory/transfer'},
                    {'label': 'Low Stock', 'url': '/inventory/low-stock'},
                ],
                'visible': True,
            },
            {
                'id': 'crm',
                'label': 'CRM',
                'icon': 'contacts',
                'submenu': [
                    {'label': 'Parties', 'url': '/crm/parties'},
                    {'label': 'Customers', 'url': '/crm/customers'},
                    {'label': 'Suppliers', 'url': '/crm/suppliers'},
                ],
                'visible': True,
            },
            {
                'id': 'reports',
                'label': 'Reports',
                'icon': 'assessment',
                'submenu': [
                    {'label': 'Trial Balance', 'url': '/reports/trial-balance'},
                    {'label': 'P&L Statement', 'url': '/reports/profit-loss'},
                    {'label': 'Sales Report', 'url': '/reports/sales'},
                    {'label': 'Purchase Report', 'url': '/reports/purchase'},
                    {'label': 'Inventory Summary', 'url': '/reports/inventory'},
                    {'label': 'GST Report', 'url': '/reports/gst'},
                ],
                'visible': True,
            },
            {
                'id': 'analytics',
                'label': 'Analytics',
                'icon': 'trending_up',
                'url': '/analytics',
                'visible': is_admin,
            },
            {
                'id': 'ai_tools',
                'label': 'AI Tools',
                'icon': 'smart_toy',
                'url': '/ai-tools',
                'visible': is_admin,
            },
            {
                'id': 'settings',
                'label': 'Settings',
                'icon': 'settings',
                'submenu': [
                    {'label': 'Profile', 'url': '/settings/profile'},
                    {'label': 'Business', 'url': '/settings/business'},
                    {'label': 'API Settings', 'url': '/settings/api'},
                    {'label': 'Integrations', 'url': '/settings/integrations'},
                ],
                'visible': True,
            },
        ]
    }
    
    return Response(menu)


# Import F for queryset
from django.db.models import F
