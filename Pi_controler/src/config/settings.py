"""Typed runtime settings loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _environment_int(name: str, default: int) -> int:
    """Read a positive integer setting with a useful error message."""
    value = os.getenv(name, str(default))
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, received {value!r}.") from exc


def _environment_float(name: str, default: float) -> float:
    """Read a positive floating-point setting with a useful error message."""
    value = os.getenv(name, str(default))
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number, received {value!r}.") from exc


@dataclass(frozen=True)
class Settings:
    """All values needed by the desktop or Raspberry Pi application."""

    project_root: Path
    hand_landmarker_model: Path
    camera_index: int
    camera_width: int
    camera_height: int
    bluetooth_serial_port: str | None
    bluetooth_serial_baudrate: int
    serial_timeout_seconds: float
    bluetooth_reconnect_interval_seconds: float
    gesture_confirmation_seconds: float
    gesture_confirmation_frames: int
    gesture_cooldown_seconds: float
    log_level: str

    @classmethod
    def from_environment(cls) -> "Settings":
        """Build settings without importing platform-specific configuration."""
        project_root = Path(__file__).resolve().parents[2]
        bluetooth_port = os.getenv(
            "BLUETOOTH_SERIAL_PORT",
            "COM10" if os.name == "nt" else "/dev/rfcomm0",
        ).strip() or None

        settings = cls(
            project_root=project_root,
            hand_landmarker_model=project_root / "model" / "hand_landmarker.task",
            camera_index=_environment_int("CAMERA_INDEX", 0),
            camera_width=_environment_int("CAMERA_WIDTH", 640),
            camera_height=_environment_int("CAMERA_HEIGHT", 480),
            bluetooth_serial_port=bluetooth_port,
            bluetooth_serial_baudrate=_environment_int(
                "BLUETOOTH_SERIAL_BAUDRATE", 9600
            ),
            serial_timeout_seconds=_environment_float("SERIAL_TIMEOUT_SECONDS", 0.5),
            bluetooth_reconnect_interval_seconds=_environment_float(
                "BLUETOOTH_RECONNECT_INTERVAL_SECONDS", 5.0
            ),
            gesture_confirmation_seconds=_environment_float(
                "GESTURE_CONFIRMATION_SECONDS", 0.5
            ),
            gesture_confirmation_frames=_environment_int(
                "GESTURE_CONFIRMATION_FRAMES", 10
            ),
            gesture_cooldown_seconds=_environment_float(
                "GESTURE_COOLDOWN_SECONDS", 1.0
            ),
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        )
        settings._validate()
        return settings

    def _validate(self) -> None:
        if self.camera_index < 0:
            raise ValueError("CAMERA_INDEX must be zero or greater.")
        if self.camera_width <= 0 or self.camera_height <= 0:
            raise ValueError("CAMERA_WIDTH and CAMERA_HEIGHT must be greater than zero.")
        if self.bluetooth_serial_baudrate <= 0:
            raise ValueError("BLUETOOTH_SERIAL_BAUDRATE must be greater than zero.")
        if self.serial_timeout_seconds <= 0:
            raise ValueError("SERIAL_TIMEOUT_SECONDS must be greater than zero.")
        if self.bluetooth_reconnect_interval_seconds <= 0:
            raise ValueError(
                "BLUETOOTH_RECONNECT_INTERVAL_SECONDS must be greater than zero."
            )
        if self.gesture_confirmation_seconds < 0:
            raise ValueError("GESTURE_CONFIRMATION_SECONDS cannot be negative.")
        if self.gesture_confirmation_frames <= 0:
            raise ValueError("GESTURE_CONFIRMATION_FRAMES must be greater than zero.")
        if self.gesture_cooldown_seconds < 0:
            raise ValueError("GESTURE_COOLDOWN_SECONDS cannot be negative.")
