"""Persistent dashboard, device and audit-log models."""

from __future__ import annotations

from django.conf import settings
from django.db import models


class Device(models.Model):
    """One Arduino/HC-05 gateway that can be controlled by the dashboard."""

    name = models.CharField(max_length=80, unique=True)
    serial_port = models.CharField(
        max_length=100,
        blank=True,
        help_text="Leave empty to use BLUETOOTH_SERIAL_PORT from the environment.",
    )
    serial_baudrate = models.PositiveIntegerField(default=9600)
    is_enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class LedState(models.Model):
    """The latest known desired state of a device's three LEDs."""

    class Source(models.TextChoices):
        WEB = "web", "Web dashboard"
        GESTURE = "gesture", "Hand gesture"
        SCENE = "scene", "Scene"
        SYSTEM = "system", "System"

    device = models.OneToOneField(Device, on_delete=models.CASCADE, related_name="led_state")
    led1 = models.BooleanField(default=False)
    led2 = models.BooleanField(default=False)
    led3 = models.BooleanField(default=False)
    last_source = models.CharField(max_length=16, choices=Source.choices, default=Source.SYSTEM)
    updated_at = models.DateTimeField(auto_now=True)

    def as_tuple(self) -> tuple[bool, bool, bool]:
        return self.led1, self.led2, self.led3

    def __str__(self) -> str:
        command = "".join("1" if value else "0" for value in self.as_tuple())
        return f"{self.device.name}: LED:{command}"


class ControlMode(models.Model):
    """The source currently permitted to change a device's LEDs."""

    class Mode(models.TextChoices):
        MANUAL = "manual", "Manual"
        GESTURE = "gesture", "Gesture"
        LOCKED = "locked", "Locked"

    device = models.OneToOneField(Device, on_delete=models.CASCADE, related_name="control_mode")
    mode = models.CharField(max_length=16, choices=Mode.choices, default=Mode.MANUAL)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="changed_control_modes",
    )
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.device.name}: {self.mode}"


class Scene(models.Model):
    """A named reusable state for all LEDs on one device."""

    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name="scenes")
    name = models.CharField(max_length=80)
    led1 = models.BooleanField(default=False)
    led2 = models.BooleanField(default=False)
    led3 = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["device", "name"], name="unique_scene_name_per_device"),
        ]
        ordering = ["name"]

    def as_tuple(self) -> tuple[bool, bool, bool]:
        return self.led1, self.led2, self.led3

    def __str__(self) -> str:
        return f"{self.device.name}: {self.name}"


class ControlEvent(models.Model):
    """An append-only audit event for dashboard, gesture and system actions."""

    class Source(models.TextChoices):
        WEB = "web", "Web dashboard"
        GESTURE = "gesture", "Hand gesture"
        SCENE = "scene", "Scene"
        SYSTEM = "system", "System"

    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name="events")
    source = models.CharField(max_length=16, choices=Source.choices)
    event_type = models.CharField(max_length=80)
    payload = models.JSONField(default=dict, blank=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="control_events",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.device.name}: {self.event_type} ({self.source})"
