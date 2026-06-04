from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async

from core_settings.admin_realtime import build_admin_dashboard_realtime_payload


class EnterpriseStreamConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.stream = self.scope["url_route"]["kwargs"]["stream"]
        self.group_name = f"enterprise_{self.stream}"
        user = self.scope.get("user")
        if not user or not user.is_authenticated:
            await self.close(code=4401)
            return
        if self.stream == "dashboard" and not (getattr(user, "is_staff", False) or getattr(user, "is_superuser", False)):
            await self.close(code=4403)
            return
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self.send_json({"type": "connected", "stream": self.stream})
        if self.stream == "dashboard":
            await self.send_json(await _dashboard_payload())

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content, **kwargs):
        user = self.scope.get("user")
        if not getattr(user, "is_staff", False) and not getattr(user, "is_superuser", False):
            return
        await self.channel_layer.group_send(
            self.group_name,
            {"type": "enterprise.broadcast", "payload": content},
        )

    async def enterprise_broadcast(self, event):
        await self.send_json(event["payload"])


@database_sync_to_async
def _dashboard_payload():
    return build_admin_dashboard_realtime_payload()
