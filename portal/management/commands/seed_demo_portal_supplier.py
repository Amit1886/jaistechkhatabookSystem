from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Seeds a demo portal supplier (Party + PortalUser) for local testing."

    def add_arguments(self, parser):
        parser.add_argument("--mobile", default="8888888888")
        parser.add_argument("--username", default="demo.supplier")
        parser.add_argument("--password", default="Demo@12345")

    def handle(self, *args, **options):
        mobile = str(options["mobile"] or "").strip()
        username = str(options["username"] or "").strip()
        password = str(options["password"] or "").strip()

        if len(password) < 8:
            self.stderr.write(self.style.ERROR("Password must be at least 8 characters."))
            return
        if not mobile:
            self.stderr.write(self.style.ERROR("Mobile is required."))
            return

        User = get_user_model()
        owner = User.objects.filter(is_superuser=True).order_by("id").first() or User.objects.filter(is_staff=True).order_by("id").first()
        if not owner:
            self.stderr.write(self.style.ERROR("No staff/superuser found. Create an admin user first."))
            return

        from khataapp.models import Party
        from portal.models import PortalUser
        from portal.services import ensure_default_permissions

        party, _ = Party.objects.get_or_create(
            mobile=mobile,
            defaults={
                "name": "Demo Supplier",
                "party_type": "supplier",
                "owner": owner,
            },
        )
        if getattr(party, "owner_id", None) is None:
            party.owner = owner
            party.save(update_fields=["owner"])

        portal_user = PortalUser.objects.filter(party=party).first()
        if portal_user and portal_user.username != username:
            username = portal_user.username

        if not portal_user:
            portal_user = PortalUser(owner=owner, party=party, role=PortalUser.Role.SUPPLIER, username=username)
        portal_user.set_password(password)
        portal_user.is_active = True
        portal_user.must_change_password = False
        portal_user.created_by = owner
        portal_user.save()

        try:
            ensure_default_permissions(portal_user)
        except Exception:
            pass

        self.stdout.write(self.style.SUCCESS("Demo portal supplier ready."))
        self.stdout.write(f"Manage: /portal/manage/suppliers/  (Party: {party.name} / {party.mobile})")
        self.stdout.write("Login:")
        self.stdout.write("  URL: /accounts/login/?role=supplier")
        self.stdout.write(f"  Username: {portal_user.username}")
        self.stdout.write(f"  Password: {password}")
        self.stdout.write("Dashboards:")
        self.stdout.write("  /portal/supplier/purchases/")
        self.stdout.write("  /portal/supplier/billing/")

