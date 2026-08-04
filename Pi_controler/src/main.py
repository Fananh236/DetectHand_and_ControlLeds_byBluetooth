"""Application entry point for camera hand gestures and Arduino LEDs."""

from __future__ import annotations

import logging
import sys
import time

import cv2

from .communication import ArduinoBluetoothController, ArduinoConnectionError
from .config import (
    BLUETOOTH_COMMAND_RESEND_INTERVAL_SECONDS,
    BLUETOOTH_RECONNECT_INTERVAL_SECONDS,
    BLUETOOTH_SERIAL_BAUDRATE,
    BLUETOOTH_SERIAL_PORT,
    BLINK_INTERVAL_SECONDS,
    CAMERA_HEIGHT,
    CAMERA_INDEX,
    CAMERA_WIDTH,
    HAND_LANDMARKER_MODEL,
    LOG_LEVEL,
    SERIAL_TIMEOUT_SECONDS,
)
from .services import GestureLedService
from .vision import HandDetector


LOGGER = logging.getLogger(__name__)
WINDOW_NAME = "Hand Gesture LED Controller"
NO_HAND_FINGERS = (False, False, False, False, False)


class HandGestureApplication:
    """Coordinate camera capture, gesture recognition and Arduino output."""

    def __init__(self) -> None:
        self._camera = None
        self._last_detection_timestamp_ms = -1
        self._detector = HandDetector(HAND_LANDMARKER_MODEL)
        self._gesture_service = GestureLedService(BLINK_INTERVAL_SECONDS)
        self._arduino = None
        if BLUETOOTH_SERIAL_PORT:
            try:
                self._arduino = ArduinoBluetoothController(
                    BLUETOOTH_SERIAL_PORT,
                    BLUETOOTH_SERIAL_BAUDRATE,
                    SERIAL_TIMEOUT_SECONDS,
                    reconnect_interval=BLUETOOTH_RECONNECT_INTERVAL_SECONDS,
                    command_resend_interval=BLUETOOTH_COMMAND_RESEND_INTERVAL_SECONDS,
                )
            except ArduinoConnectionError as exc:
                LOGGER.warning("Arduino control disabled; camera will still run: %s", exc)

    def run(self) -> None:
        try:
            self._initialize_camera()
            self._detector.start()
            cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
            LOGGER.info("Application started. Press q to quit.")
            while True:
                success, frame = self._camera.read()
                if not success:
                    raise RuntimeError("Cannot read a frame from the configured camera.")

                frame = cv2.flip(frame, 1)

                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                results = self._detector.detect(
                    frame_rgb,
                    self._next_detection_timestamp_ms(),
                )

                gesture = "NO_HAND"
                fingers = NO_HAND_FINGERS
                if results.hand_landmarks:
                    landmarks = results.hand_landmarks[0]
                    fingers = self._detector.detect_fingers(landmarks)
                    update = self._gesture_service.update(fingers)
                    gesture = update.gesture
                    self._detector.draw_landmarks(frame, landmarks)

                self._draw_overlay(frame, gesture, fingers)
                if self._arduino is not None:
                    self._arduino.send_led_states(self._gesture_service.led_states)

                cv2.imshow(WINDOW_NAME, frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
        finally:
            self.close()

    def _initialize_camera(self) -> None:
        # Media Foundation can report a Windows webcam as open but still fail
        # on the first frame. DirectShow is more reliable for this project.
        backend = cv2.CAP_DSHOW if sys.platform.startswith("win") else cv2.CAP_ANY
        self._camera = cv2.VideoCapture(CAMERA_INDEX, backend)
        if not self._camera.isOpened():
            raise RuntimeError(
                f"Cannot open camera index {CAMERA_INDEX}. Check the webcam or CAMERA_INDEX."
            )
        self._camera.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
        self._camera.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)

    def _next_detection_timestamp_ms(self) -> int:
        """Return a strictly increasing timestamp required by MediaPipe VIDEO mode."""
        timestamp_ms = int(time.monotonic() * 1000)
        self._last_detection_timestamp_ms = max(
            timestamp_ms,
            self._last_detection_timestamp_ms + 1,
        )
        return self._last_detection_timestamp_ms

    def _draw_overlay(self, frame, gesture: str, fingers) -> None:
        cv2.rectangle(frame, (10, 10), (310, 150), (0, 0, 0), -1)
        cv2.putText(
            frame, "LED Status", (20, 35), cv2.FONT_HERSHEY_SIMPLEX,
            0.6, (255, 255, 255), 1,
        )
        for index, state in enumerate(self._gesture_service.led_states, start=1):
            color = (0, 255, 0) if state else (0, 0, 255)
            cv2.putText(
                frame, f"LED{index}: {'ON' if state else 'OFF'}", (20, 60 + (index - 1) * 25),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 1,
            )
        cv2.putText(
            frame, f"Finger Count: {sum(fingers)}", (20, 120),
            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1,
        )
        cv2.putText(
            frame, f"Gesture: {gesture}", (20, 145),
            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1,
        )
        cv2.putText(
            frame, "Press q to quit", (10, frame.shape[0] - 10),
            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1,
        )

    def close(self) -> None:
        self._detector.close()
        if self._camera is not None:
            self._camera.release()
            self._camera = None
        if self._arduino is not None:
            self._arduino.close()
        cv2.destroyAllWindows()


def main() -> int:
    logging.basicConfig(
        level=LOG_LEVEL,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    )
    try:
        HandGestureApplication().run()
    except Exception:
        LOGGER.exception("Application stopped because of an error.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
