from django.urls import include, path
from rest_framework.routers import DefaultRouter

from superapp import views

router = DefaultRouter()
router.register("business-units", views.BusinessUnitViewSet, basename="super-business-units")
router.register("modules", views.SuperAppModuleViewSet, basename="super-modules")
router.register("wallets", views.CustomerWalletViewSet, basename="super-wallets")
router.register("wallet-transactions", views.WalletTransactionViewSet, basename="super-wallet-transactions")
router.register("cashback-rules", views.CashbackRuleViewSet, basename="super-cashback-rules")
router.register("gift-cards", views.GiftCardViewSet, basename="super-gift-cards")
router.register("emi-plans", views.EMIPlanViewSet, basename="super-emi-plans")
router.register("referral-bonuses", views.ReferralBonusViewSet, basename="super-referral-bonuses")
router.register("tax-rules", views.TaxRuleViewSet, basename="super-tax-rules")
router.register("gst-categories", views.GSTCategoryViewSet, basename="super-gst-categories")
router.register("e-invoices", views.EInvoiceViewSet, basename="super-e-invoices")
router.register("tax-alerts", views.TaxAlertViewSet, basename="super-tax-alerts")
router.register("tax-reports", views.TaxReportViewSet, basename="super-tax-reports")
router.register("expense-scans", views.ExpenseScanViewSet, basename="super-expense-scans")
router.register("expense-approvals", views.ExpenseApprovalViewSet, basename="super-expense-approvals")
router.register("restaurant-tables", views.RestaurantTableViewSet, basename="super-restaurant-tables")
router.register("menu-categories", views.MenuCategoryViewSet, basename="super-menu-categories")
router.register("menu-items", views.MenuItemViewSet, basename="super-menu-items")
router.register("table-orders", views.TableOrderViewSet, basename="super-table-orders")
router.register("kitchen-queue", views.KitchenQueueViewSet, basename="super-kitchen-queue")
router.register("dashboard", views.SuperDashboardViewSet, basename="super-dashboard")
router.register("audit-logs", views.ActivityAuditLogViewSet, basename="super-audit-logs")

urlpatterns = [path("", include(router.urls))]

