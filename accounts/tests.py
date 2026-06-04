from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import LedgerEntry
from khataapp.models import CreditAccount, Party


class SignupUserLimitTests(TestCase):
    @override_settings(MAX_TEST_USERS=1)
    def test_signup_blocked_after_limit(self):
        User = get_user_model()
        User.objects.create_user(
            email="u1@example.com",
            password="pass12345",
            username="u1",
            mobile="9000000001",
        )

        resp = self.client.post(
            reverse("accounts:signup"),
            {
                "email": "u2@example.com",
                "username": "u2",
                "mobile": "9000000002",
                "password": "pass12345X",
            },
            follow=False,
            secure=True,
        )
        self.assertEqual(resp.status_code, 302)
        self.assertIn(reverse("accounts:login"), resp["Location"])

    @override_settings(MAX_TEST_USERS=1, DESKTOP_MODE=True, OTP_BYPASS=True)
    def test_signup_allowed_in_desktop_mode_even_after_limit(self):
        User = get_user_model()
        User.objects.create_user(
            email="u1@example.com",
            password="pass12345",
            username="u1",
            mobile="9000000001",
        )

        resp = self.client.post(
            reverse("accounts:signup"),
            {
                "email": "u2@example.com",
                "username": "u2",
                "mobile": "9000000002",
                "password": "pass12345X",
            },
            follow=False,
            secure=True,
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp["Location"], reverse("accounts:dashboard"))


class PasswordLoginTests(TestCase):
    def test_password_login_authenticates_by_email_username_field(self):
        User = get_user_model()
        User.objects.create_user(
            email="user@example.com",
            password="pass12345",
            username="not-an-email",
            mobile="9000000099",
            is_active=True,
        )

        resp = self.client.post(
            reverse("accounts:login"),
            {"identifier": "user@example.com", "password": "pass12345"},
            follow=False,
            secure=True,
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp["Location"], reverse("accounts:dashboard"))


class LedgerEntryBalanceRecalcTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            email="owner@example.com",
            password="pass12345",
            username="owner",
            mobile="9000000100",
        )
        self.party = Party.objects.create(owner=self.user, name="P1", party_type="customer")
        self.account = CreditAccount.objects.create(party=self.party, user=self.user, credit_limit=0, outstanding=0)

    def test_update_running_balance_does_not_recurse(self):
        e1 = LedgerEntry.objects.create(
            account=self.account,
            party=self.party,
            amount=Decimal("100.00"),
            txn_type="credit",
        )
        e2 = LedgerEntry.objects.create(
            account=self.account,
            party=self.party,
            amount=Decimal("40.00"),
            txn_type="debit",
        )
        e1.refresh_from_db()
        e2.refresh_from_db()

        # Running = +100 - 40
        self.assertEqual(e1.balance, Decimal("100.00"))
        self.assertEqual(e2.balance, Decimal("60.00"))
