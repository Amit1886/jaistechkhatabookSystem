from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db.models import Sum

from accounts.models import UserProfile, DailySummary
from billing.models import Plan, Subscription
from core_settings.models import CompanySettings
from khataapp.models import Transaction
from django.db.models.signals import post_migrate

User = get_user_model()

@receiver(post_migrate)
def create_default_superadmin(sender, **kwargs):
    User = get_user_model()
    if not User.objects.filter(username="admin").exists():
        User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="Admin@123"
        )
        print("Default superadmin created: admin / Admin@123")

# ------------------------------------------------
# CREATE USER PROFILE + COMPANY + SUBSCRIPTION
# ------------------------------------------------
# DISABLED: Causing FK constraint issues during signup
# Profile creation is now handled in signup_view
# ------------------------------------------------
# @receiver(post_save, sender=User)
# def create_user_business(sender, instance, created, **kwargs):
#     """
#     Create UserProfile, CompanySettings & Subscription
#     when user becomes ACTIVE (OTP verified)
#     """
#     pass

# ------------------------------------------------
# UPDATE DAILY SUMMARY WHEN A TRANSACTION IS CREATED
# ------------------------------------------------
@receiver(post_save, sender=Transaction)
def update_daily_summary(sender, instance, created, **kwargs):
    if not created:
        return

    # Ignore if transaction has no owner
    if not hasattr(instance.party, "owner") or not instance.party.owner:
        return

    user = instance.party.owner

    # Ignore inactive users
    if not user.is_active:
        return

    today = timezone.now().date()

    # Aggregate today's transactions
    txns = Transaction.objects.filter(party__owner=user, date=today)
    total_credit = txns.filter(txn_type="credit").aggregate(total=Sum("amount"))["total"] or 0
    total_debit = txns.filter(txn_type="debit").aggregate(total=Sum("amount"))["total"] or 0
    balance = total_debit - total_credit

    # Update or create daily summary
    summary, _ = DailySummary.objects.get_or_create(user=user, date=today)
    summary.total_credit = total_credit
    summary.total_debit = total_debit
    summary.balance = balance
    summary.total_transactions = txns.count()
    summary.save()
