"""Non-blocking Bluetooth Classic RFCOMM communication with an Arduino HC-05."""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Sequence

try:
    import serial
except ImportError as exc:  # pragma: no cover - depends on local environment
    serial = None
    SERIAL_IMPORT_ERROR = exc
else:
    SERIAL_IMPORT_ERROR = None


LOGGER = logging.getLogger(__name__)


class ArduinoConnectionError(RuntimeError):
    """Raised when the configured Arduino Bluetooth connection cannot be used."""


class ArduinoBluetoothController:
    """Send the latest LED state without ever blocking the camera thread.

    ``send_led_states`` only records the most recent requested state. A daemon
    worker owns the serial port, reconnects when necessary, and periodically
    re-sends the latest state so that an HC-05 which reconnects while idle is
    synchronised again. A serial write may still time out, but it can only
    pause the worker thread -- never OpenCV's event loop.
    """

    def __init__(
        self,
        port: str,
        baudrate: int = 9600,
        timeout: float = 0.5,
        connection_timeout: float = 0,
        reconnect_interval: float = 2,
        command_resend_interval: float = 1,
    ) -> None:
        if serial is None:
            raise ArduinoConnectionError(
                "pyserial is not installed for the Python interpreter in use."
            ) from SERIAL_IMPORT_ERROR
        if connection_timeout < 0:
            raise ValueError("connection_timeout cannot be negative.")
        if reconnect_interval <= 0:
            raise ValueError("reconnect_interval must be greater than zero.")
        if command_resend_interval <= 0:
            raise ValueError("command_resend_interval must be greater than zero.")

        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        # Retained for callers of the previous API. Reconnection now happens
        # exclusively in the background, so this must never block start-up.
        self.connection_timeout = connection_timeout
        self.reconnect_interval = reconnect_interval
        self.command_resend_interval = command_resend_interval

        self.connection = None
        self.last_command: str | None = None
        self._desired_command: str | None = None
        self._last_sent_at = 0.0
        self._connection_error_logged = False
        self._lock = threading.RLock()
        self._wake_event = threading.Event()
        self._stop_event = threading.Event()
        self._worker = threading.Thread(
            target=self._run,
            name="arduino-bluetooth-worker",
            daemon=True,
        )
        self._worker.start()

    @property
    def is_connected(self) -> bool:
        with self._lock:
            return bool(self.connection and self.connection.is_open)

    def send_led_states(self, states: Sequence[bool]) -> None:
        """Schedule a LED command and return immediately.

        The response is logged by the worker when one is already available.
        Repeated commands are intentionally coalesced; the worker sends a
        heartbeat at ``command_resend_interval`` instead of on every frame.
        """
        if len(states) != 3:
            raise ValueError("Expected exactly three LED states.")

        command = "LED:" + "".join("1" if state else "0" for state in states)
        with self._lock:
            if command == self._desired_command:
                return
            self._desired_command = command
            self._wake_event.set()

    def close(self) -> None:
        """Stop the worker without holding up application shutdown."""
        self._stop_event.set()
        self._wake_event.set()
        self._worker.join(timeout=max(self.timeout + 0.5, 1.0))

    def _run(self) -> None:
        try:
            while not self._stop_event.is_set():
                command, wait_seconds = self._next_command()
                if command is None:
                    self._wait(wait_seconds)
                    continue

                if not self.is_connected:
                    if not self._connect_once():
                        self._wait(self.reconnect_interval)
                        continue

                try:
                    self._send_command(command)
                except (serial.SerialException, OSError, ArduinoConnectionError) as exc:
                    LOGGER.warning(
                        "Arduino Bluetooth link lost while sending %s; "
                        "camera will continue while reconnecting (%s).",
                        command,
                        exc,
                    )
                    self._connection_error_logged = True
                    self._disconnect()
                    self._wait(self.reconnect_interval)
        finally:
            self._disconnect()

    def _next_command(self) -> tuple[str | None, float | None]:
        """Return an immediately due command or the time until the next one."""
        with self._lock:
            command = self._desired_command
            last_command = self.last_command
            last_sent_at = self._last_sent_at

        if command is None:
            return None, None
        if command != last_command:
            return command, 0

        wait_seconds = self.command_resend_interval - (time.monotonic() - last_sent_at)
        if wait_seconds > 0:
            return None, wait_seconds
        return command, 0

    def _wait(self, timeout: float | None) -> None:
        self._wake_event.wait(timeout)
        self._wake_event.clear()

    def _connect_once(self) -> bool:
        """Try one RFCOMM connection attempt in the worker thread."""
        try:
            connection = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.timeout,
                write_timeout=1,
            )
        except (serial.SerialException, OSError) as exc:
            if not self._connection_error_logged:
                LOGGER.warning(
                    "Arduino HC-05 on %s is unavailable; camera will keep running "
                    "while Bluetooth reconnects (%s).",
                    self.port,
                    exc,
                )
                self._connection_error_logged = True
            return False

        if self._stop_event.is_set():
            self._close_connection(connection)
            return False

        with self._lock:
            self.connection = connection
        self._connection_error_logged = False
        LOGGER.info("Connected to Arduino HC-05 on RFCOMM port %s.", self.port)
        return True

    def _send_command(self, command: str) -> None:
        with self._lock:
            connection = self.connection
        if connection is None or not connection.is_open:
            raise ArduinoConnectionError("Arduino Bluetooth port is not open.")

        payload = f"{command}\n".encode("ascii")
        written = connection.write(payload)
        if written != len(payload):
            raise ArduinoConnectionError(
                f"Incomplete Arduino write: {written}/{len(payload)} bytes."
            )

        with self._lock:
            is_heartbeat = command == self.last_command
            self.last_command = command
            self._last_sent_at = time.monotonic()

        response = self._read_available_response(connection)
        log = LOGGER.debug if is_heartbeat else LOGGER.info
        log("Arduino <- %s", command)
        if response:
            log("Arduino -> %s", response)

    @staticmethod
    def _read_available_response(connection) -> str:
        """Read only bytes already buffered, so a partial line cannot block."""
        available = connection.in_waiting
        if not available:
            return ""
        return connection.read(available).decode("ascii", errors="replace").strip()

    def _disconnect(self) -> None:
        with self._lock:
            connection = self.connection
            self.connection = None
        if connection is not None:
            self._close_connection(connection)

    @staticmethod
    def _close_connection(connection) -> None:
        if not connection.is_open:
            return
        try:
            connection.close()
        except (serial.SerialException, OSError) as exc:
            LOGGER.debug("Error while closing Arduino Bluetooth port: %s", exc)
