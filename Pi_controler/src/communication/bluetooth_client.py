"""Non-blocking HC-05 Bluetooth Classic serial client."""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Sequence

try:
    import serial
except ImportError as exc:  # pragma: no cover - depends on the local environment
    serial = None
    SERIAL_IMPORT_ERROR = exc
else:
    SERIAL_IMPORT_ERROR = None


LOGGER = logging.getLogger(__name__)


class BluetoothConnectionError(RuntimeError):
    """Raised when the HC-05 serial client cannot be initialised."""


class BluetoothClient:
    """Send the latest LED state without blocking the camera thread.

    The worker owns the RFCOMM serial port. It caches the latest requested
    command so a command issued while disconnected is sent as soon as the
    HC-05 becomes available. A failed read or write closes the port and the
    client retries every ``reconnect_interval`` seconds.
    """

    def __init__(
        self,
        port: str,
        baudrate: int = 9600,
        timeout: float = 0.5,
        reconnect_interval: float = 5.0,
    ) -> None:
        if serial is None:
            raise BluetoothConnectionError(
                "pyserial is not installed for the Python interpreter in use."
            ) from SERIAL_IMPORT_ERROR
        if baudrate <= 0:
            raise ValueError("baudrate must be greater than zero.")
        if timeout <= 0:
            raise ValueError("timeout must be greater than zero.")
        if reconnect_interval <= 0:
            raise ValueError("reconnect_interval must be greater than zero.")

        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.reconnect_interval = reconnect_interval
        self._connection = None
        self._desired_command: str | None = None
        self._last_sent_command: str | None = None
        self._last_response = ""
        self._lock = threading.RLock()
        self._wake_event = threading.Event()
        self._stop_event = threading.Event()
        self._worker = threading.Thread(
            target=self._run,
            name="hc05-bluetooth-worker",
            daemon=True,
        )
        self._worker.start()

    @property
    def is_connected(self) -> bool:
        """Whether the RFCOMM port is currently open."""
        with self._lock:
            return bool(self._connection and self._connection.is_open)

    @property
    def last_response(self) -> str:
        with self._lock:
            return self._last_response

    def send_led_states(self, states: Sequence[bool]) -> None:
        """Schedule a newline-terminated ``LED:xyz`` command and return."""
        if len(states) != 3:
            raise ValueError("Expected exactly three LED states.")
        command = "LED:" + "".join("1" if state else "0" for state in states)
        with self._lock:
            if command == self._desired_command:
                return
            self._desired_command = command
            self._wake_event.set()

    def close(self) -> None:
        """Stop the background worker and close the serial port."""
        self._stop_event.set()
        self._wake_event.set()
        self._worker.join(timeout=max(self.timeout + 0.5, 1.0))
        self._disconnect()

    def _run(self) -> None:
        try:
            while not self._stop_event.is_set():
                command = self._get_desired_command()
                if command is None:
                    self._wait(None)
                    continue

                if not self.is_connected:
                    if not self._connect_once():
                        self._wait(self.reconnect_interval)
                    continue

                if command == self._last_sent_command:
                    self._wait(None)
                    continue

                try:
                    self._send_command(command)
                except (serial.SerialException, OSError, BluetoothConnectionError) as exc:
                    LOGGER.warning(
                        "HC-05 link lost while sending %s; retrying in %.1f seconds (%s).",
                        command,
                        self.reconnect_interval,
                        exc,
                    )
                    self._disconnect()
                    self._wait(self.reconnect_interval)
        finally:
            self._disconnect()

    def _get_desired_command(self) -> str | None:
        with self._lock:
            return self._desired_command

    def _wait(self, timeout: float | None) -> None:
        self._wake_event.wait(timeout)
        self._wake_event.clear()

    def _connect_once(self) -> bool:
        try:
            connection = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.timeout,
                write_timeout=self.timeout,
            )
        except (serial.SerialException, OSError) as exc:
            LOGGER.warning(
                "HC-05 on %s is unavailable; retrying in %.1f seconds (%s).",
                self.port,
                self.reconnect_interval,
                exc,
            )
            return False

        if self._stop_event.is_set():
            self._close_connection(connection)
            return False
        with self._lock:
            self._connection = connection
            self._last_sent_command = None
        LOGGER.info("Connected to Arduino HC-05 on RFCOMM port %s.", self.port)
        return True

    def _send_command(self, command: str) -> None:
        with self._lock:
            connection = self._connection
        if connection is None or not connection.is_open:
            raise BluetoothConnectionError("HC-05 serial port is not open.")

        payload = f"{command}\n".encode("ascii")
        written = connection.write(payload)
        if written != len(payload):
            raise BluetoothConnectionError(
                f"Incomplete HC-05 write: {written}/{len(payload)} bytes."
            )

        with self._lock:
            self._last_sent_command = command
        LOGGER.info("Arduino <- %s", command)

        response = self._read_available_response(connection)
        if response:
            with self._lock:
                self._last_response = response
            LOGGER.info("Arduino -> %s", response)

    @staticmethod
    def _read_available_response(connection) -> str:
        """Read already-buffered response bytes without delaying video frames."""
        time.sleep(0.02)
        available = connection.in_waiting
        if not available:
            return ""
        return connection.read(available).decode("ascii", errors="replace").strip()

    def _disconnect(self) -> None:
        with self._lock:
            connection = self._connection
            self._connection = None
            self._last_sent_command = None
        if connection is not None:
            self._close_connection(connection)

    @staticmethod
    def _close_connection(connection) -> None:
        if not connection.is_open:
            return
        try:
            connection.close()
        except (serial.SerialException, OSError) as exc:
            LOGGER.debug("Error while closing the HC-05 port: %s", exc)
