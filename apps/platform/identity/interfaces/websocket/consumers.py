import json

try:
    from channels.generic.websocket import AsyncWebsocketConsumer
except Exception:  # Channels is optional in desktop/lightweight deployments.
    AsyncWebsocketConsumer = object


class IdentityActivityConsumer(AsyncWebsocketConsumer):
    group_name = "identity_activity"

    async def connect(self):
        user = self.scope.get("user")
        if not getattr(user, "is_authenticated", False):
            await self.close()
            return
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        try:
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
        except Exception:
            pass

    async def identity_event(self, event):
        await self.send(text_data=json.dumps(event.get("payload", {})))
