from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Grant ERP admin-level access to a user (sets is_staff + adds to 'admin' group)."

    def add_arguments(self, parser):
        parser.add_argument("username_or_email")

    def handle(self, *args, **options):
        ident = str(options["username_or_email"] or "").strip()
        if not ident:
            self.stderr.write(self.style.ERROR("username_or_email required"))
            return

        User = get_user_model()
        user = (
            User.objects.filter(username__iexact=ident).first()
            or User.objects.filter(email__iexact=ident).first()
        )
        if not user:
            self.stderr.write(self.style.ERROR(f"User not found: {ident}"))
            return

        group, _ = Group.objects.get_or_create(name="admin")
        try:
            user.groups.add(group)
        except Exception:
            pass

        if not getattr(user, "is_staff", False):
            user.is_staff = True
        if not getattr(user, "is_active", True):
            user.is_active = True
        user.save()

        self.stdout.write(self.style.SUCCESS(f"Full access granted to: {user.username}"))
        self.stdout.write("Auto Discount settings: /auto-discount/settings/")

