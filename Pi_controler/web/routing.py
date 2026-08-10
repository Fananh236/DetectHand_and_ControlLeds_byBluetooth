"""WebSocket URL routing."""

from django.urls import re_path

from .consumers import DeviceConsumer


websocket_urlpatterns = [
    re_path(r"^ws/devices/(?P<device_id>\d+)/$", DeviceConsumer.as_asgi()),
]
