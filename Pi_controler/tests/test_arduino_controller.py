"""Protocol-level tests for the Arduino HC-05 Bluetooth adapter."""

import time
from unittest import TestCase
from unittest.mock import MagicMock, patch

from src.communication import arduino_controller


class ArduinoBluetoothControllerTests(TestCase):
    def _wait_for_command(
        self,
        controller: arduino_controller.ArduinoBluetoothController,
        command: str,
    ) -> None:
        deadline = time.monotonic() + 1
        while time.monotonic() < deadline:
            if controller.last_command == command:
                return
            time.sleep(0.01)
        self.fail(f"Timed out waiting for {command}.")

    def test_sends_newline_terminated_command_in_background(self) -> None:
        connection = MagicMock()
        connection.is_open = True
        connection.write.return_value = len(b"LED:101\n")
        connection.in_waiting = 0

        fake_serial = MagicMock()
        fake_serial.Serial.return_value = connection
        fake_serial.SerialException = OSError
        with patch.object(arduino_controller, "serial", fake_serial):
            controller = arduino_controller.ArduinoBluetoothController(
                "/dev/rfcomm0", command_resend_interval=10
            )
            try:
                self.assertIsNone(controller.send_led_states((True, False, True)))
                self._wait_for_command(controller, "LED:101")
                self.assertIsNone(controller.send_led_states((True, False, True)))
            finally:
                controller.close()

        connection.write.assert_called_once_with(b"LED:101\n")

    def test_reconnects_once_after_a_serial_error(self) -> None:
        first_connection = MagicMock()
        first_connection.is_open = True
        first_connection.write.side_effect = OSError("Bluetooth link dropped")

        second_connection = MagicMock()
        second_connection.is_open = True
        second_connection.write.return_value = len(b"LED:010\n")
        second_connection.in_waiting = 1
        second_connection.read.return_value = b"OK:010\r\n"

        fake_serial = MagicMock()
        fake_serial.Serial.side_effect = [first_connection, second_connection]
        fake_serial.SerialException = OSError
        with patch.object(arduino_controller, "serial", fake_serial):
            controller = arduino_controller.ArduinoBluetoothController(
                "COM10", reconnect_interval=0.01, command_resend_interval=10
            )
            try:
                self.assertIsNone(controller.send_led_states((False, True, False)))
                self._wait_for_command(controller, "LED:010")
            finally:
                controller.close()

        self.assertEqual(fake_serial.Serial.call_count, 2)

    def test_send_returns_immediately_when_bluetooth_is_unavailable(self) -> None:
        fake_serial = MagicMock()
        fake_serial.Serial.side_effect = OSError("HC-05 unavailable")
        fake_serial.SerialException = OSError
        with patch.object(arduino_controller, "serial", fake_serial):
            controller = arduino_controller.ArduinoBluetoothController(
                "COM10", reconnect_interval=0.01
            )
            try:
                started_at = time.monotonic()
                controller.send_led_states((False, False, False))
                self.assertLess(time.monotonic() - started_at, 0.05)
            finally:
                controller.close()
