from django.test import TestCase
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient


@override_settings(SECURE_SSL_REDIRECT=False, SYNC_API_TOKEN="test-sync-token")
class MobileOfflineSyncAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION="Token test-sync-token")

    def test_push_then_pull_customers(self):
        now = timezone.now().isoformat()
        user_id = "mobile-user-1"

        push_res = self.client.post(
            "/api/v1/mobile/sync/push/",
            data={
                "user_id": user_id,
                "table": "customers",
                "rows": [
                    {
                        "id": "c1",
                        "user_id": user_id,
                        "name": "Rahul Sharma",
                        "phone": "9000000000",
                        "address": "Demo Street",
                        "created_at": now,
                        "updated_at": now,
                        "is_synced": 0,
                    }
                ],
            },
            format="json",
            HTTP_AUTHORIZATION="Token test-sync-token",
        )
        self.assertEqual(push_res.status_code, 200)
        self.assertEqual(push_res.data.get("ok"), True)

        pull_res = self.client.post(
            "/api/v1/mobile/sync/pull/",
            data={"user_id": user_id},
            format="json",
            HTTP_AUTHORIZATION="Token test-sync-token",
        )
        self.assertEqual(pull_res.status_code, 200)
        self.assertEqual(pull_res.data.get("ok"), True)
        data = pull_res.data.get("data") or {}
        customers = data.get("customers") or []
        self.assertEqual(len(customers), 1)
        self.assertEqual(customers[0]["id"], "c1")
        self.assertEqual(customers[0]["name"], "Rahul Sharma")

    def test_unauthorized_without_token(self):
        client = APIClient()
        res = client.post(
            "/api/v1/mobile/sync/push/",
            data={"user_id": "u1", "table": "customers", "rows": []},
            format="json",
        )
        self.assertEqual(res.status_code, 401)
