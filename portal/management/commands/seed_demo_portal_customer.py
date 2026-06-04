from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Seeds a demo portal customer (Party + PortalUser) for local testing."

    def add_arguments(self, parser):
        parser.add_argument("--mobile", default="9999999999")
        parser.add_argument("--username", default="demo.customer")
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
                "name": "Demo Customer",
                "party_type": "customer",
                "owner": owner,
            },
        )
        # Ensure party is owned by admin for visibility in manage screens (unless already set).
        if getattr(party, "owner_id", None) is None:
            party.owner = owner
            party.save(update_fields=["owner"])

        portal_user = PortalUser.objects.filter(party=party).first()
        if portal_user and portal_user.username != username:
            # Keep existing username to avoid surprises.
            username = portal_user.username

        if not portal_user:
            portal_user = PortalUser(owner=owner, party=party, role=PortalUser.Role.CUSTOMER, username=username)
        portal_user.set_password(password)
        portal_user.is_active = True
        portal_user.must_change_password = False
        portal_user.created_by = owner
        portal_user.save()

        try:
            ensure_default_permissions(portal_user)
        except Exception:
            pass

        self.stdout.write(self.style.SUCCESS("Demo portal customer ready."))
        self.stdout.write(f"Manage: /portal/manage/customers/  (Party: {party.name} / {party.mobile})")
        self.stdout.write("Login:")
        self.stdout.write(f"  URL: /accounts/login/?role=customer")
        self.stdout.write(f"  Username: {portal_user.username}")
        self.stdout.write(f"  Password: {password}")
        self.stdout.write("Dashboards:")
        self.stdout.write("  /portal/customer/ecommerce/")
        self.stdout.write("  /portal/customer/billing/")

