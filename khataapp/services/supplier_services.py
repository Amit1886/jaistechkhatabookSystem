from django.db.models import Sum
from django.utils import timezone
from decimal import Decimal
from datetime import timedelta
from ..models import Party, SupplierPayment
from commerce.models import Order

class SupplierService:
    """Business logic service for supplier purchase and due management"""

    @staticmethod
    def get_supplier_summary(user):
        """Get comprehensive supplier summary for dashboard"""
        today = timezone.now().date()

        suppliers = Party.objects.filter(
            owner=user,
            party_type='supplier',
            is_active=True
        ).order_by("name")

        rows = []
        for supplier in suppliers:
            orders = Order.objects.filter(party=supplier, order_type='PURCHASE').prefetch_related("items")
            total_purchase = sum((order.total_amount() for order in orders), Decimal('0.00'))
            total_paid = SupplierPayment.objects.filter(supplier=supplier).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            outstanding = orders.aggregate(total=Sum('due_amount'))['total'] or Decimal('0.00')
            row = {
                'id': supplier.id,
                'name': supplier.name,
                'credit_period': supplier.credit_period,
                'opening_balance': supplier.opening_balance,
                'total_purchase': total_purchase,
                'total_paid': total_paid,
                'outstanding_amount': outstanding,
                'next_due_date': SupplierService.get_next_due_date(supplier.id),
            }
            row['status'] = SupplierService.get_supplier_status(row, today)
            rows.append(row)

        return rows

    @staticmethod
    def get_next_due_date(supplier_id):
        """Get the earliest due date for a supplier's outstanding purchases"""
        earliest_due = Order.objects.filter(
            party_id=supplier_id,
            order_type='PURCHASE',
            due_amount__gt=0,
            payment_due_date__isnull=False
        ).order_by('payment_due_date').values_list('payment_due_date', flat=True).first()

        return earliest_due

    @staticmethod
    def get_supplier_status(supplier_data, today):
        """Determine supplier status based on due dates"""
        next_due = supplier_data.get('next_due_date')
        outstanding = supplier_data.get('outstanding_amount') or Decimal('0.00')

        if outstanding <= 0:
            return 'green'  # No dues

        if not next_due:
            return 'yellow'  # Has dues but no due date set

        days_until_due = (next_due - today).days

        if days_until_due < 0:
            return 'red'  # Overdue
        elif days_until_due <= 7:
            return 'yellow'  # Due within 7 days
        else:
            return 'green'  # Due in future

    @staticmethod
    def calculate_order_due_amount(order):
        """Calculate due amount for a purchase order"""
        total_amount = order.total_amount()
        paid_amount = SupplierPayment.objects.filter(order=order).aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')

        return max(total_amount - paid_amount, Decimal('0.00'))

    @staticmethod
    def update_order_due_amount(order):
        """Update the due amount for an order"""
        due_amount = SupplierService.calculate_order_due_amount(order)
        order.due_amount = due_amount
        order.save(update_fields=['due_amount'])

    @staticmethod
    def get_payment_alerts(user):
        """Get alerts for upcoming and overdue payments"""
        today = timezone.now().date()
        alerts = []

        # Overdue payments
        overdue_orders = Order.objects.filter(
            owner=user,
            order_type='PURCHASE',
            due_amount__gt=0,
            payment_due_date__lt=today
        ).select_related('party')

        for order in overdue_orders:
            days_overdue = (today - order.payment_due_date).days
            alerts.append({
                'type': 'overdue',
                'supplier': order.party.name,
                'amount': order.due_amount,
                'due_date': order.payment_due_date,
                'days_overdue': days_overdue,
                'invoice_number': order.invoice_number,
                'order_id': order.id
            })

        # Upcoming payments. Each order appears once, with the most specific state.
        upcoming_orders = Order.objects.filter(
            owner=user,
            order_type='PURCHASE',
            due_amount__gt=0,
            payment_due_date__gte=today,
            payment_due_date__lte=today + timedelta(days=7)
        ).select_related('party')

        for order in upcoming_orders:
            days_remaining = (order.payment_due_date - today).days
            if days_remaining == 0:
                alert_type = 'due_today'
            elif days_remaining <= 3:
                alert_type = 'due_very_soon'
            else:
                alert_type = 'due_soon'
            alerts.append({
                'type': alert_type,
                'supplier': order.party.name,
                'amount': order.due_amount,
                'due_date': order.payment_due_date,
                'days_remaining': days_remaining,
                'invoice_number': order.invoice_number,
                'order_id': order.id
            })

        return alerts

    @staticmethod
    def get_dashboard_summary(user):
        """Get top summary cards for dashboard"""
        suppliers = Party.objects.filter(owner=user, party_type='supplier', is_active=True)

        total_purchase = Decimal('0.00')
        total_paid = Decimal('0.00')
        total_outstanding = Decimal('0.00')

        supplier_rows = SupplierService.get_supplier_summary(user)
        for supplier_data in supplier_rows:
            total_purchase += supplier_data.get('total_purchase') or Decimal('0.00')
            total_paid += supplier_data.get('total_paid') or Decimal('0.00')
            total_outstanding += supplier_data.get('outstanding_amount') or Decimal('0.00')

        return {
            'total_purchase': total_purchase,
            'total_paid': total_paid,
            'total_outstanding': total_outstanding,
            'suppliers_with_dues': suppliers.filter(
                orders__order_type='PURCHASE',
                orders__due_amount__gt=0
            ).distinct().count()
        }

    @staticmethod
    def process_supplier_payment(order, amount, payment_mode, reference=None, notes=None, payment_date=None):
        """Process a payment to supplier"""
        if payment_date is None:
            payment_date = timezone.now().date()

        payment = SupplierPayment.objects.create(
            supplier=order.party,
            order=order,
            amount=amount,
            payment_mode=payment_mode,
            reference=reference,
            notes=notes,
            payment_date=payment_date
        )

        # Update order due amount
        SupplierService.update_order_due_amount(order)

        return payment

    @staticmethod
    def get_supplier_ledger(supplier, start_date=None, end_date=None):
        """Get detailed ledger for a supplier"""
        transactions = []

        # Purchase transactions
        purchases = Order.objects.filter(
            party=supplier,
            order_type='PURCHASE'
        ).select_related('party')

        if start_date:
            purchases = purchases.filter(created_at__date__gte=start_date)
        if end_date:
            purchases = purchases.filter(created_at__date__lte=end_date)

        for purchase in purchases:
            transactions.append({
                'date': purchase.created_at.date(),
                'type': 'purchase',
                'description': f"Purchase - {purchase.invoice_number or 'N/A'}",
                'debit': purchase.total_amount(),
                'credit': Decimal('0.00'),
                'balance': Decimal('0.00')  # Will be calculated later
            })

        # Payment transactions
        payments = SupplierPayment.objects.filter(
            supplier=supplier
        ).select_related('order')

        if start_date:
            payments = payments.filter(payment_date__gte=start_date)
        if end_date:
            payments = payments.filter(payment_date__lte=end_date)

        for payment in payments:
            transactions.append({
                'date': payment.payment_date,
                'type': 'payment',
                'description': f"Payment - {payment.payment_mode} ({payment.reference or 'N/A'})",
                'debit': Decimal('0.00'),
                'credit': payment.amount,
                'balance': Decimal('0.00')  # Will be calculated later
            })

        # Sort by date
        transactions.sort(key=lambda x: x['date'])

        # Calculate running balance
        balance = supplier.opening_balance
        for transaction in transactions:
            balance += transaction['credit'] - transaction['debit']
            transaction['balance'] = balance

        return transactions
