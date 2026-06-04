import json

from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async

from .models import CheckoutSession
from .services import recalculate_session, session_payload


class SelfCheckoutConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.session_key = self.scope["url_route"]["kwargs"]["session_key"]
        self.group_name = f"selfcheckout_{self.session_key}"
        user = self.scope.get("user")
        if not user or not user.is_authenticated:
            await self.close()
            return
        self.store_group_name = f"selfcheckout_store_{user.id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.channel_layer.group_add(self.store_group_name, self.channel_name)
        await self.accept()
        payload = await self._cart_payload(user.id, self.session_key)
        await self.send(text_data=json.dumps({"type": "cart.snapshot", "cart": payload}))

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)
        if hasattr(self, "store_group_name"):
            await self.channel_layer.group_discard(self.store_group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        await self.send(text_data=json.dumps({"type": "pong"}))

    async def cart_update(self, event):
        await self.send(text_data=json.dumps({"type": "cart.update", "cart": event.get("cart", {})}))

    async def payment_update(self, event):
        await self.send(text_data=json.dumps({"type": "payment.update", "payload": event.get("payload", {})}))

    async def kiosk_event(self, event):
        await self.send(text_data=json.dumps({"type": event.get("event_type", "kiosk.event"), "payload": event.get("payload", {})}))

    async def store_event(self, event):
        await self.send(text_data=json.dumps({"type": event.get("event_type", "store.event"), "payload": event.get("payload", {})}))

    @database_sync_to_async
    def _cart_payload(self, user_id, session_key):
        session = CheckoutSession.objects.filter(owner_id=user_id, session_key=session_key).first()
        if not session:
            return {}
        recalculate_session(session)
        return session_payload(session)
