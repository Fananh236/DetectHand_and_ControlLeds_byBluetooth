"""One control path shared by Django, WebSockets and gesture recognition."""

from __future__ import annotations

import logging
import threading
from typing import Any

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction

from src.communication import BluetoothClient, BluetoothConnectionError
from src.config import Settings
from src.services import GestureDecision, GestureService, LedService, LedStates
from src.vision import Gesture

from .models import ControlEvent, ControlMode, Device, LedState, Scene


LOGGER = logging.getLogger(__name__)


class ControlRejected(RuntimeError):
    """Raised when an action is not permitted by the current control mode."""


def ensure_device_records(device: Device) -> Device:
    """Ensure every device has its current state, mode and built-in scenes."""
    LedState.objects.get_or_create(device=device)
    ControlMode.objects.get_or_create(device=device)
    for name, states in {"All On": (True, True, True), "All Off": (False, False, False)}.items():
        Scene.objects.get_or_create(
            device=device,
            name=name,
            defaults={"led1": states[0], "led2": states[1], "led3": states[2]},
        )
    return device


def get_default_device() -> Device:
    """Return the local Arduino gateway created for a first-time installation."""
    device, _ = Device.objects.get_or_create(name="Lab LED 01")
    return ensure_device_records(device)


def publish_device_event(device_id: int, event_type: str, payload: dict[str, Any]) -> None:
    """Broadcast a compact event to all authenticated dashboard clients."""
    layer = get_channel_layer()
    if layer is None:
        return
    async_to_sync(layer.group_send)(
        f"device_{device_id}",
        {
            "type": "dashboard.event",
            "event": {"type": event_type, "payload": payload},
        },
    )


class ControllerService:
    """Coordinate durable state, Bluetooth commands and realtime updates."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._device_id: int | None = None
        self._led_service: LedService | None = None
        self._gesture_service: GestureService | None = None
        self._bluetooth: BluetoothClient | None = None
        self._mode = ControlMode.Mode.MANUAL

    def close(self) -> None:
        """Stop the Bluetooth worker when the process or tests shut down."""
        with self._lock:
            bluetooth = self._bluetooth
            self._bluetooth = None
            self._device_id = None
            self._led_service = None
            self._gesture_service = None
        if bluetooth is not None:
            bluetooth.close()

    def get_status(self, device: Device) -> dict[str, Any]:
        """Return the state the dashboard should render now."""
        self._ensure_runtime(device)
        led_state = LedState.objects.get(device=device)
        control_mode = ControlMode.objects.get(device=device)
        with self._lock:
            self._mode = control_mode.mode
            connected = bool(self._bluetooth and self._bluetooth.is_connected)
        return {
            "device": {
                "id": device.id,
                "name": device.name,
                "enabled": device.is_enabled,
                "serial_port": device.serial_port or "environment default",
            },
            "leds": {
                "led1": led_state.led1,
                "led2": led_state.led2,
                "led3": led_state.led3,
                "command": self._command(led_state.as_tuple()),
                "last_source": led_state.last_source,
                "updated_at": led_state.updated_at.isoformat(),
            },
            "control_mode": control_mode.mode,
            "bluetooth": {"connected": connected},
        }

    def set_leds(
        self,
        device: Device,
        states: tuple[bool, bool, bool],
        *,
        source: str,
        user=None,
        require_manual_mode: bool = True,
        event_type: str = "leds.changed",
    ) -> dict[str, Any]:
        """Persist and queue a full LED state through the one allowed path."""
        if len(states) != 3:
            raise ValueError("Exactly three LED states are required.")
        self._ensure_runtime(device)
        with self._lock:
            if require_manual_mode and self._mode != ControlMode.Mode.MANUAL:
                raise ControlRejected(
                    "Switch to Manual mode before sending dashboard or scene commands."
                )
            if self._led_service is None:  # pragma: no cover - guarded by _ensure_runtime
                raise RuntimeError("LED controller is not initialised.")
            update = self._led_service.set_states(LedStates(*states))
            bluetooth = self._bluetooth

        with transaction.atomic():
            led_state = LedState.objects.select_for_update().get(device=device)
            led_state.led1, led_state.led2, led_state.led3 = states
            led_state.last_source = source
            led_state.save(update_fields=["led1", "led2", "led3", "last_source", "updated_at"])
            ControlEvent.objects.create(
                device=device,
                source=source,
                event_type=event_type,
                user=user if getattr(user, "is_authenticated", False) else None,
                payload={
                    "command": update.states.command,
                    "leds": list(states),
                    "changed": update.changed,
                },
            )

        if bluetooth is not None:
            bluetooth.send_led_states(states)
        status = self.get_status(device)
        publish_device_event(device.id, "device.state_changed", status)
        return status

    def set_mode(self, device: Device, mode: str, *, user=None) -> dict[str, Any]:
        """Change the active control source and clear stale gesture latches."""
        valid_modes = set(ControlMode.Mode.values)
        if mode not in valid_modes:
            raise ValueError(f"Unknown control mode: {mode}.")
        self._ensure_runtime(device)
        with transaction.atomic():
            control_mode = ControlMode.objects.select_for_update().get(device=device)
            control_mode.mode = mode
            control_mode.changed_by = user if getattr(user, "is_authenticated", False) else None
            control_mode.save(update_fields=["mode", "changed_by", "updated_at"])
            ControlEvent.objects.create(
                device=device,
                source=ControlEvent.Source.WEB,
                event_type="control_mode.changed",
                user=control_mode.changed_by,
                payload={"mode": mode},
            )

        with self._lock:
            self._mode = mode
            if self._gesture_service is not None:
                self._gesture_service.reset()
        status = self.get_status(device)
        publish_device_event(device.id, "device.state_changed", status)
        return status

    def apply_scene(self, device: Device, scene: Scene, *, user=None) -> dict[str, Any]:
        """Apply a named scene through the same validation as manual control."""
        return self.set_leds(
            device,
            scene.as_tuple(),
            source=ControlEvent.Source.SCENE,
            user=user,
            event_type="scene.applied",
        )

    def observe_gesture(self, device: Device, gesture: Gesture) -> GestureDecision | None:
        """Allow only gesture mode to turn a recognised pose into a command."""
        self._ensure_runtime(device)
        with self._lock:
            if self._mode != ControlMode.Mode.GESTURE:
                if self._gesture_service is not None:
                    self._gesture_service.reset()
                return None
            if self._gesture_service is None:  # pragma: no cover - guarded by _ensure_runtime
                return None
            decision = self._gesture_service.observe(gesture)
            bluetooth = self._bluetooth

        if not decision.triggered:
            return decision

        states = decision.states.as_tuple()
        with transaction.atomic():
            led_state = LedState.objects.select_for_update().get(device=device)
            led_state.led1, led_state.led2, led_state.led3 = states
            led_state.last_source = LedState.Source.GESTURE
            led_state.save(update_fields=["led1", "led2", "led3", "last_source", "updated_at"])
            ControlEvent.objects.create(
                device=device,
                source=ControlEvent.Source.GESTURE,
                event_type="gesture.confirmed",
                payload={
                    "gesture": decision.stable_gesture.value,
                    "command": decision.states.command,
                    "leds": list(states),
                },
            )
        if bluetooth is not None:
            bluetooth.send_led_states(states)
        status = self.get_status(device)
        publish_device_event(device.id, "device.state_changed", status)
        return decision

    def _ensure_runtime(self, device: Device) -> None:
        with self._lock:
            if self._device_id == device.id and self._led_service is not None:
                return
        ensure_device_records(device)
        with self._lock:
            if self._device_id == device.id and self._led_service is not None:
                return
            previous_bluetooth = self._bluetooth
            self._bluetooth = None
            led_state = LedState.objects.get(device=device)
            control_mode = ControlMode.objects.get(device=device)
            self._led_service = LedService(LedStates(*led_state.as_tuple()))
            self._gesture_service = GestureService(self._led_service)
            self._mode = control_mode.mode
            self._device_id = device.id

            configured_port = device.serial_port.strip()
            if not configured_port:
                configured_port = Settings.from_environment().bluetooth_serial_port or ""
            if configured_port and device.is_enabled:
                try:
                    self._bluetooth = BluetoothClient(
                        configured_port,
                        baudrate=device.serial_baudrate,
                        timeout=Settings.from_environment().serial_timeout_seconds,
                        reconnect_interval=Settings.from_environment().bluetooth_reconnect_interval_seconds,
                    )
                    self._bluetooth.send_led_states(led_state.as_tuple())
                except BluetoothConnectionError as exc:
                    LOGGER.warning("Bluetooth control is unavailable: %s", exc)
        if previous_bluetooth is not None:
            previous_bluetooth.close()

    @staticmethod
    def _command(states: tuple[bool, bool, bool]) -> str:
        return "LED:" + "".join("1" if state else "0" for state in states)


_controller_lock = threading.Lock()
_controller: ControllerService | None = None


def get_controller() -> ControllerService:
    """Return the process-wide control service used by all request handlers."""
    global _controller
    with _controller_lock:
        if _controller is None:
            _controller = ControllerService()
        return _controller


def reset_controller() -> None:
    """Dispose the singleton; primarily useful during Django test teardown."""
    global _controller
    with _controller_lock:
        controller = _controller
        _controller = None
    if controller is not None:
        controller.close()
