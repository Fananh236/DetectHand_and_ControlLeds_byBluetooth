"""Integration tests for the authenticated Django control surface."""

from __future__ import annotations

import os
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from .models import ControlEvent, ControlMode, LedState, Scene
from .services import get_default_device, reset_controller


class InitialSetupTests(TestCase):
    """A fresh installation must not need a command-line superuser step."""

    def test_readiness_endpoint_is_public(self) -> None:
        response = self.client.get("/healthz/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_first_run_creates_and_logs_in_the_local_administrator(self) -> None:
        response = self.client.get("/")
        self.assertRedirects(response, "/setup/")

        response = self.client.post(
            "/setup/",
            {
                "username": "owner",
                "password1": "A-safe-test-password-2026",
                "password2": "A-safe-test-password-2026",
            },
        )

        user = get_user_model().objects.get(username="owner")
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.is_staff)
        self.assertRedirects(response, "/")


class DashboardApiTests(TestCase):
    """Verify web commands share one guarded, persistent control path."""

    def setUp(self) -> None:
        self.bluetooth_environment = patch.dict(
            os.environ,
            {"BLUETOOTH_SERIAL_PORT": ""},
        )
        self.bluetooth_environment.start()
        reset_controller()
        self.user = get_user_model().objects.create_user("operator", password="test-pass-123")
        self.client.force_login(self.user)
        self.device = get_default_device()
        self.device_id = self.device.id

    def tearDown(self) -> None:
        reset_controller()
        self.bluetooth_environment.stop()

    def test_dashboard_requires_login(self) -> None:
        self.client.logout()

        response = self.client.get("/")

        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_manual_api_command_persists_led_state_and_event(self) -> None:
        response = self.client.put(
            f"/api/v1/devices/{self.device_id}/leds/",
            data={"led1": True, "led2": False, "led3": True},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["leds"]["command"], "LED:101")
        self.assertEqual(LedState.objects.get(device=self.device).as_tuple(), (True, False, True))
        self.assertEqual(ControlEvent.objects.filter(device=self.device).count(), 1)

    def test_locked_mode_rejects_manual_control(self) -> None:
        mode_response = self.client.put(
            f"/api/v1/devices/{self.device_id}/control-mode/",
            data={"mode": "locked"},
            content_type="application/json",
        )
        command_response = self.client.patch(
            f"/api/v1/devices/{self.device_id}/leds/",
            data={"led1": True},
            content_type="application/json",
        )

        self.assertEqual(mode_response.status_code, 200)
        self.assertEqual(command_response.status_code, 409)
        self.assertEqual(ControlMode.objects.get(device=self.device).mode, "locked")

    def test_scene_uses_the_same_control_service(self) -> None:
        scene = Scene.objects.get(device=self.device, name="All On")

        response = self.client.post(
            f"/api/v1/devices/{self.device_id}/scenes/{scene.id}/apply/",
            data={},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["leds"]["command"], "LED:111")
        self.assertEqual(LedState.objects.get(device=self.device).last_source, "scene")

    def test_camera_snapshot_get_reaches_snapshot_view(self) -> None:
        response = self.client.get(
            f"/api/v1/devices/{self.device_id}/camera/snapshot/"
        )

        # No camera is running in this test, but GET must reach the snapshot
        # endpoint instead of being captured by the POST-only action route.
        self.assertEqual(response.status_code, 404)

    def test_camera_stream_get_reaches_mjpeg_view(self) -> None:
        response = self.client.get(
            f"/api/v1/devices/{self.device_id}/camera/stream/"
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.streaming)
        self.assertEqual(
            response["Content-Type"],
            "multipart/x-mixed-replace; boundary=frame",
        )
        response.close()
