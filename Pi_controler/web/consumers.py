"""Authenticated WebSocket consumer for dashboard status updates."""

from __future__ import annotations

from channels.generic.websocket import AsyncJsonWebsocketConsumer


class DeviceConsumer(AsyncJsonWebsocketConsumer):
    """Forward server-generated state and vision events to one device dashboard."""

    async def connect(self) -> None:
        user = self.scope.get("user")
        if user is None or not user.is_authenticated:
            await self.close(code=4401)
            return
        self.device_id = self.scope["url_route"]["kwargs"]["device_id"]
        self.group_name = f"device_{self.device_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, _close_code: int) -> None:
        group_name = getattr(self, "group_name", None)
        if group_name:
            await self.channel_layer.group_discard(group_name, self.channel_name)

    async def receive_json(self, _content, **_kwargs) -> None:
        """Keep the socket read-only; mutations always pass CSRF-protected REST views."""
        await self.send_json({"type": "socket.read_only"})

    async def dashboard_event(self, event) -> None:
        await self.send_json(event["event"])
