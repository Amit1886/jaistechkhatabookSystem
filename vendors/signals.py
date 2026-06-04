from django.contrib.auth.models import Group
from django.db.models.signals import post_migrate
from django.dispatch import receiver


@receiver(post_migrate)
def ensure_marketplace_groups(sender, **kwargs):
    for name in ["Super Admin", "Vendor", "Vendor Staff", "Customer"]:
        try:
            Group.objects.get_or_create(name=name)
        except Exception:
            pass

