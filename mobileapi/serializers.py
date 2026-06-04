# mobileapi/serializers.py
from rest_framework import serializers
from django.contrib.auth import get_user_model
from khataapp.models import Party, Transaction, UserProfile
from commerce.models import Product, Invoice, Payment, Order
from django.db.models import Sum, Count
from decimal import Decimal

User = get_user_model()


class UserProfileSerializer(serializers.ModelSerializer):
    """Minimal user profile for mobile app."""
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'is_staff', 'is_superuser', 'is_active'
        ]
    
    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Add full name
        data['name'] = instance.get_full_name() or instance.username or instance.email
        return data


class PermissionSerializer(serializers.Serializer):
    """Dynamic permissions from user groups and roles."""
    
    def to_representation(self, instance):
        """
        Build permission dictionary based on user's groups and roles.
        instance = User object
        """
        user = instance
        perms = {}
        
        # Check standard groups
        user_groups = set(user.groups.values_list('name', flat=True))
        is_admin = user.is_superuser or user.is_staff
        
        # Define permission mapping
        perms['dashboard'] = True  # Everyone can view
        perms['inventory'] = is_admin or 'manager' in user_groups or 'store_manager' in user_groups
        perms['billing'] = is_admin or 'accountant' in user_groups or 'manager' in user_groups
        perms['crm'] = is_admin or 'sales' in user_groups or 'manager' in user_groups
        perms['reports'] = is_admin or 'analyst' in user_groups or 'manager' in user_groups
        perms['settings'] = is_admin
        perms['users'] = is_admin
        perms['pos'] = is_admin or 'cashier' in user_groups or 'store_manager' in user_groups
        perms['payments'] = is_admin or 'accountant' in user_groups
        perms['products'] = is_admin or 'manager' in user_groups
        
        return perms


class PartySerializer(serializers.ModelSerializer):
    """Customer/Party data for mobile."""
    
    class Meta:
        model = Party
        fields = [
            'id', 'name', 'phone', 'email', 'address',
            'city', 'state', 'pincode', 'gstin',
            'created_at', 'updated_at'
        ]


class ProductSerializer(serializers.ModelSerializer):
    """Product data for inventory."""
    
    sku = serializers.CharField(source='product_code', read_only=True)
    
    class Meta:
        model = Product
        fields = [
            'id', 'name', 'sku', 'description', 'price',
            'cost', 'category', 'stock', 'unit',
            'created_at', 'updated_at'
        ]


class InvoiceSerializer(serializers.ModelSerializer):
    """Invoice/Order data for billing."""
    
    party_name = serializers.CharField(source='party.name', read_only=True)
    
    class Meta:
        model = Invoice
        fields = [
            'id', 'order_id', 'invoice_number', 'party_name',
            'amount', 'tax', 'total', 'status',
            'due_date', 'created_at', 'updated_at'
        ]


class TransactionSerializer(serializers.ModelSerializer):
    """Transaction data for ledger."""
    
    party_name = serializers.CharField(source='party.name', read_only=True)
    
    class Meta:
        model = Transaction
        fields = [
            'id', 'party_id', 'party_name', 'amount',
            'txn_type', 'description', 'created_at', 'updated_at'
        ]


class DashboardMetricSerializer(serializers.Serializer):
    """Dashboard metrics card."""
    key = serializers.CharField()
    label = serializers.CharField()
    value = serializers.CharField()
    tone = serializers.CharField()  # neutral, success, warning, danger, info


class DashboardDataSerializer(serializers.Serializer):
    """Complete dashboard data for mobile."""
    total_revenue = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_expense = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_parties = serializers.IntegerField()
    total_products = serializers.IntegerField()
    pending_invoices = serializers.IntegerField()
    low_stock_items = serializers.IntegerField()
    cards = DashboardMetricSerializer(many=True)
