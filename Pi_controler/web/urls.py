"""HTTP routes owned by the LED dashboard app."""

from django.urls import path

from .views import (
    CameraControlAPIView,
    CameraSnapshotAPIView,
    CameraStreamView,
    ControlModeAPIView,
    DashboardView,
    DeviceStatusAPIView,
    EventListAPIView,
    HealthAPIView,
    InitialSetupView,
    LedStateAPIView,
    SceneAPIView,
)


urlpatterns = [
    path("", DashboardView.as_view(), name="dashboard"),
    path("setup/", InitialSetupView.as_view(), name="initial-setup"),
    path("api/v1/health/", HealthAPIView.as_view(), name="health"),
    path("api/v1/devices/<int:device_id>/", DeviceStatusAPIView.as_view(), name="device-status"),
    path("api/v1/devices/<int:device_id>/leds/", LedStateAPIView.as_view(), name="device-leds"),
    path(
        "api/v1/devices/<int:device_id>/control-mode/",
        ControlModeAPIView.as_view(),
        name="device-control-mode",
    ),
    path("api/v1/devices/<int:device_id>/scenes/", SceneAPIView.as_view(), name="device-scenes"),
    path(
        "api/v1/devices/<int:device_id>/scenes/<int:scene_id>/apply/",
        SceneAPIView.as_view(),
        name="device-scene-apply",
    ),
    path("api/v1/devices/<int:device_id>/events/", EventListAPIView.as_view(), name="device-events"),
    path(
        "api/v1/devices/<int:device_id>/camera/stream/",
        CameraStreamView.as_view(),
        name="camera-stream",
    ),
    path(
        "api/v1/devices/<int:device_id>/camera/snapshot/",
        CameraSnapshotAPIView.as_view(),
        name="camera-snapshot",
    ),
    path(
        "api/v1/devices/<int:device_id>/camera/<str:action>/",
        CameraControlAPIView.as_view(),
        name="camera-control",
    ),
]
