from django.urls import include, path
from rest_framework.routers import DefaultRouter

from wallet.views import WalletTransactionViewSet, WalletViewSet, WithdrawRequestViewSet

router = DefaultRouter()
router.register("wallets", WalletViewSet, basename="wallets")
router.register("transactions", WalletTransactionViewSet, basename="wallet-transactions")
router.register("withdraw-requests", WithdrawRequestViewSet, basename="wallet-withdraw-requests")

urlpatterns = [path("", include(router.urls))]

