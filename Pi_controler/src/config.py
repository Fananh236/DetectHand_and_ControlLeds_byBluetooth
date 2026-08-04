"""Runtime configuration and project paths."""

from __future__ import annotations

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODEL_DIR = PROJECT_ROOT / "model"
DATA_DIR = PROJECT_ROOT / "data"
HAND_LANDMARKER_MODEL = MODEL_DIR / "hand_landmarker.task"

CAMERA_INDEX = int(os.getenv("CAMERA_INDEX", "0"))
CAMERA_WIDTH = int(os.getenv("CAMERA_WIDTH", "640"))
CAMERA_HEIGHT = int(os.getenv("CAMERA_HEIGHT", "480"))

# The HC-05 uses Bluetooth Classic Serial Port Profile (RFCOMM), not BLE.
# The paired Windows endpoint for this project is explicitly COM10 (Outgoing).
# On Raspberry Pi, create /dev/rfcomm0 with the `rfcomm bind` command in README.
BLUETOOTH_SERIAL_PORT = os.getenv(
    "BLUETOOTH_SERIAL_PORT",
    "COM10" if os.name == "nt" else "/dev/rfcomm0",
).strip() or None
BLUETOOTH_SERIAL_BAUDRATE = int(os.getenv("BLUETOOTH_SERIAL_BAUDRATE", "9600"))
SERIAL_TIMEOUT_SECONDS = float(os.getenv("SERIAL_TIMEOUT_SECONDS", "0.5"))
BLUETOOTH_RECONNECT_INTERVAL_SECONDS = float(
    os.getenv("BLUETOOTH_RECONNECT_INTERVAL_SECONDS", "2")
)
BLUETOOTH_COMMAND_RESEND_INTERVAL_SECONDS = float(
    os.getenv("BLUETOOTH_COMMAND_RESEND_INTERVAL_SECONDS", "1")
)

BLINK_INTERVAL_SECONDS = float(os.getenv("BLINK_INTERVAL_SECONDS", "0.2"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
