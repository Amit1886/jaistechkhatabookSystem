try:
    from channels.generic.websocket import AsyncJsonWebsocketConsumer
except Exception:
    AsyncJsonWebsocketConsumer = object


class CoreEventConsumer(AsyncJsonWebsocketConsumer):
    group_name = "platform_core_events"

    async def connect(self):
        if getattr(self.scope.get("user"), "is_authenticated", False):
            await self.channel_layer.group_add(self.group_name, self.channel_name)
            await self.accept()
        else:
            await self.close()

    async def disconnect(self, close_code):
        if hasattr(self, "channel_layer"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def core_event(self, event):
        await self.send_json(event.get("payload", {}))

