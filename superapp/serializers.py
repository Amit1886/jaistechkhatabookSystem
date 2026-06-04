from rest_framework import serializers

from superapp import models


class BusinessUnitSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.BusinessUnit
        fields = "__all__"
        read_only_fields = ["owner"]


class SuperAppModuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.SuperAppModule
        fields = "__all__"


class CustomerWalletSerializer(serializers.ModelSerializer):
    usable_balance = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = models.CustomerWallet
        fields = "__all__"
        read_only_fields = ["customer"]


class WalletTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.WalletTransaction
        fields = "__all__"


class RewardPointSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.RewardPoint
        fields = "__all__"


class CashbackRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.CashbackRule
        fields = "__all__"


class GiftCardSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.GiftCard
        fields = "__all__"


class EMIPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.EMIPlan
        fields = "__all__"
        read_only_fields = ["customer", "monthly_installment"]


class ReferralBonusSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.ReferralBonus
        fields = "__all__"


class TaxRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.TaxRule
        fields = "__all__"


class GSTCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = models.GSTCategory
        fields = "__all__"


class EInvoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.EInvoice
        fields = "__all__"


class TaxAlertSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.TaxAlert
        fields = "__all__"


class TaxReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.TaxReport
        fields = "__all__"


class ExpenseScanSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.ExpenseScan
        fields = "__all__"
        read_only_fields = ["owner", "duplicate_of"]


class OCRResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.OCRResult
        fields = "__all__"


class VendorMatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.VendorMatch
        fields = "__all__"


class ExpenseApprovalSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.ExpenseApproval
        fields = "__all__"


class ExpenseAttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.ExpenseAttachment
        fields = "__all__"


class RestaurantTableSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.RestaurantTable
        fields = "__all__"


class MenuCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = models.MenuCategory
        fields = "__all__"


class MenuItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.MenuItem
        fields = "__all__"


class TableOrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.TableOrder
        fields = "__all__"


class KitchenQueueSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.KitchenQueue
        fields = "__all__"


class OrderStatusLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.OrderStatusLog
        fields = "__all__"


class SuperDashboardSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.SuperDashboardSnapshot
        fields = "__all__"


class ActivityAuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.ActivityAuditLog
        fields = "__all__"
