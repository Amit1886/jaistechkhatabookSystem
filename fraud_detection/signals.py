from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from fraud_detection.services import check_user_referral_integrity

User = get_user_model()


@receiver(post_save, sender=User)
def detect_basic_signup_fraud(sender, instance, created, **kwargs):
    if not created:
        return
    try:
        check_user_referral_integrity(user=instance)
    except Exception:
        return

