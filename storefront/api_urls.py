from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    CartViewSet,
    CustomerProfileViewSet,
    PaymentsViewSet,
    ProductPublicViewSet,
    ShippingViewSet,
    StoreOrderViewSet,
    VendorPublicViewSet,
    VendorDashboardViewSet,
    VendorListingViewSet,
    VendorPaymentGatewayConfigViewSet,
    VendorShippingProviderConfigViewSet,
    MarketplaceAdminViewSet,
    WishlistViewSet,
    auth_start_otp,
    auth_verify_otp,
    razorpay_webhook,
    shiprocket_webhook,
    vendor_register,
)

router = DefaultRouter()
router.register("vendor", VendorPublicViewSet, basename="vendor-public")
router.register("products", ProductPublicViewSet, basename="store-products")
router.register("cart", CartViewSet, basename="store-cart")
router.register("wishlist", WishlistViewSet, basename="store-wishlist")
router.register("orders", StoreOrderViewSet, basename="store-orders")
router.register("payments", PaymentsViewSet, basename="store-payments")
router.register("shipping", ShippingViewSet, basename="store-shipping")
router.register("vendor-dashboard", VendorDashboardViewSet, basename="vendor-dashboard")
router.register("customer", CustomerProfileViewSet, basename="store-customer")

vendor_router = DefaultRouter()
vendor_router.register("listings", VendorListingViewSet, basename="vendor-listings")
vendor_router.register("payment-gateways", VendorPaymentGatewayConfigViewSet, basename="vendor-payment-gateways")
vendor_router.register("shipping-providers", VendorShippingProviderConfigViewSet, basename="vendor-shipping-providers")

admin_router = DefaultRouter()
admin_router.register("marketplace", MarketplaceAdminViewSet, basename="admin-marketplace")

urlpatterns = [
    path("auth/otp/start/", auth_start_otp, name="store-auth-otp-start"),
    path("auth/otp/verify/", auth_verify_otp, name="store-auth-otp-verify"),
    path("vendor/register/", vendor_register, name="vendor-register"),
    path("payments/razorpay/webhook/<int:vendor_id>/", razorpay_webhook, name="razorpay-webhook"),
    path("shipping/shiprocket/webhook/<int:vendor_id>/", shiprocket_webhook, name="shiprocket-webhook"),
    path("vendor/", include(vendor_router.urls)),
    path("admin/", include(admin_router.urls)),
    path("", include(router.urls)),
]
