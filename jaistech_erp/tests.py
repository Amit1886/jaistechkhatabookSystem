from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from .models import Business, Module, Permission, Role, UserBusinessMembership


class AppBootstrapRBACTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email="cashier@example.com",
            username="cashier",
            mobile="9000000001",
            password="pass12345",
        )
        self.business = Business.objects.create(name="Demo Business")
        self.pos = Module.objects.create(key="pos", name="POS", order=10)
        self.accounting = Module.objects.create(key="accounting", name="Accounting", order=20)
        self.pos_list = Permission.objects.create(module=self.pos, action="list")
        self.pos_create = Permission.objects.create(module=self.pos, action="create")
        self.accounting_list = Permission.objects.create(module=self.accounting, action="list")
        self.role = Role.objects.create(business=self.business, key="cashier", name="Cashier")
        self.role.permissions.add(self.pos_list, self.pos_create)
        UserBusinessMembership.objects.create(user=self.user, business=self.business, role=self.role)
        self.client.force_authenticate(self.user)

    def test_bootstrap_filters_modules_permissions_and_actions_by_role(self):
        response = self.client.get("/api/app/bootstrap/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["key"] for item in response.data["menus"]], ["pos"])
        self.assertEqual(response.data["ui"]["modules"], {"pos": True})
        self.assertEqual(response.data["ui"]["actions"]["pos"], {"list": True, "create": True})
        self.assertEqual(
            {item["key"] for item in response.data["permissions"]},
            {self.pos_list.key, self.pos_create.key},
        )

    def test_menu_filters_modules_by_role(self):
        response = self.client.get("/api/menu/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["key"] for item in response.data], ["pos"])

    def test_staff_user_gets_all_enabled_modules(self):
        self.user.is_staff = True
        self.user.save(update_fields=["is_staff"])

        response = self.client.get("/api/app/bootstrap/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["key"] for item in response.data["menus"]], ["pos", "accounting"])
