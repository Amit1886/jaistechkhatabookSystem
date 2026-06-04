#!/usr/bin/env python
"""
Test script to verify stock summary functionality
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'khatapro.settings')
django.setup()

from commerce.models import Product, StockEntry
from reports.views import stock_summary
from django.test import RequestFactory
from django.contrib.auth.models import User

def test_stock_entry_model():
    """Test that StockEntry model can be imported and queried"""
    try:
        # Check if table exists by trying to get count
        count = StockEntry.objects.count()
        print(f"✓ StockEntry table exists. Current records: {count}")
        return True
    except Exception as e:
        print(f"✗ StockEntry model error: {e}")
        return False

def test_stock_summary_view():
    """Test that stock_summary view can be called without errors"""
    try:
        # Create a mock request
        factory = RequestFactory()
        request = factory.get('/reports/stock-summary/')

        # Try to call the view
        response = stock_summary(request)
        print("✓ stock_summary view executed successfully")
        print(f"✓ Response status: {response.status_code}")
        return True
    except Exception as e:
        print(f"✗ stock_summary view error: {e}")
        return False

def test_product_query():
    """Test that Product query with annotations works"""
    try:
        from django.db.models import Sum, F, Case, When, Value, DecimalField

        products = Product.objects.annotate(
            total_in=Sum(
                Case(
                    When(stockentry__entry_type='IN', then=F('stockentry__quantity')),
                    default=Value(0),
                    output_field=DecimalField(max_digits=10, decimal_places=2)
                )
            ),
            total_out=Sum(
                Case(
                    When(stockentry__entry_type='OUT', then=F('stockentry__quantity')),
                    default=Value(0),
                    output_field=DecimalField(max_digits=10, decimal_places=2)
                )
            ),
            net_stock=F('total_in') - F('total_out')
        )

        # Try to evaluate the queryset
        product_list = list(products.values('name', 'total_in', 'total_out', 'net_stock')[:5])
        print(f"✓ Product query executed successfully. Sample products: {len(product_list)}")
        return True
    except Exception as e:
        print(f"✗ Product query error: {e}")
        return False

if __name__ == '__main__':
    print("Testing Stock Summary Fix...")
    print("=" * 50)

    tests = [
        test_stock_entry_model,
        test_product_query,
        test_stock_summary_view,
    ]

    passed = 0
    total = len(tests)

    for test in tests:
        if test():
            passed += 1
        print()

    print("=" * 50)
    print(f"Test Results: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All tests passed! Stock summary fix is working correctly.")
        sys.exit(0)
    else:
        print("❌ Some tests failed. Please check the errors above.")
        sys.exit(1)
