"""Camera application for gesture-driven Arduino LED control."""

from __future__ import annotations

import logging
import sys
import time

import cv2

from .communication import BluetoothClient, BluetoothConnectionError
from .config import Settings
from .services import GestureService, LedService
from .vision import (
    FaceAuthenticationResult,
    FaceAuthenticationStatus,
    FaceAuthenticator,
    FingerStates,
    Gesture,
    GestureClassifier,
    HandDetector,
)


LOGGER = logging.getLogger(__name__)
WINDOW_NAME = "Hand Gesture LED Controller"


class HandGestureApplication:
    """Coordinate camera capture, gesture recognition and HC-05 output."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._camera = None
        self._last_detection_timestamp_ms = -1
        self._last_frame_at: float | None = None
        self._fps = 0.0
        self._detector = HandDetector(settings.hand_landmarker_model)
        self._classifier = GestureClassifier()
        self._face_authenticator = (
            FaceAuthenticator(
                settings.face_auth_reference_directory,
                threshold=settings.face_auth_threshold,
            )
            if settings.face_auth_enabled
            else None
        )
        self._face_auth_result: FaceAuthenticationResult | None = None
        self._face_auth_frame_count = 0
        self._led_service = LedService()
        self._gesture_service = GestureService(
            self._led_service,
            confirmation_seconds=settings.gesture_confirmation_seconds,
            confirmation_frames=settings.gesture_confirmation_frames,
            cooldown_seconds=settings.gesture_cooldown_seconds,
        )
        self._bluetooth: BluetoothClient | None = None
        if settings.bluetooth_serial_port:
            try:
                self._bluetooth = BluetoothClient(
                    settings.bluetooth_serial_port,
                    baudrate=settings.bluetooth_serial_baudrate,
                    timeout=settings.serial_timeout_seconds,
                    reconnect_interval=settings.bluetooth_reconnect_interval_seconds,
                )
                # Ensure a newly connected Arduino receives the known initial state.
                self._bluetooth.send_led_states(self._led_service.states.as_tuple())
            except BluetoothConnectionError as exc:
                LOGGER.warning("Bluetooth control disabled; camera will still run: %s", exc)

    def run(self) -> None:
        """Run the camera loop until the user presses ``q``."""
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
                face_auth_result = self._authenticate_face(frame)

                gesture = Gesture.UNKNOWN
                fingers = FingerStates(False, False, False, False, False)
                if face_auth_result.authorized:
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    results = self._detector.detect(
                        frame_rgb,
                        self._next_detection_timestamp_ms(),
                    )
                    if results.hand_landmarks:
                        landmarks = results.hand_landmarks[0]
                        handedness = self._handedness(results)
                        gesture = self._classifier.classify(landmarks, handedness)
                        fingers = self._classifier.finger_states(landmarks)
                        self._detector.draw_landmarks(frame, landmarks)

                decision = self._gesture_service.observe(gesture)
                if decision.triggered:
                    LOGGER.info(
                        "Confirmed gesture %s; scheduling %s.",
                        decision.stable_gesture.value,
                        decision.states.command,
                    )
                    if self._bluetooth is not None:
                        self._bluetooth.send_led_states(decision.states.as_tuple())

                self._fps = self._update_fps()
                self._draw_overlay(frame, gesture, fingers, face_auth_result)
                cv2.imshow(WINDOW_NAME, frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
        finally:
            self.close()

    def _initialize_camera(self) -> None:
        # Media Foundation can open a webcam but fail on its first frame.
        backend = cv2.CAP_DSHOW if sys.platform.startswith("win") else cv2.CAP_ANY
        self._camera = cv2.VideoCapture(self._settings.camera_index, backend)
        if not self._camera.isOpened():
            raise RuntimeError(
                "Cannot open camera index "
                f"{self._settings.camera_index}. Check the webcam or CAMERA_INDEX."
            )
        self._camera.set(cv2.CAP_PROP_FRAME_WIDTH, self._settings.camera_width)
        self._camera.set(cv2.CAP_PROP_FRAME_HEIGHT, self._settings.camera_height)

    def _next_detection_timestamp_ms(self) -> int:
        """Return MediaPipe VIDEO timestamps that are strictly increasing."""
        timestamp_ms = int(time.monotonic() * 1000)
        self._last_detection_timestamp_ms = max(
            timestamp_ms,
            self._last_detection_timestamp_ms + 1,
        )
        return self._last_detection_timestamp_ms

    def _authenticate_face(self, frame) -> FaceAuthenticationResult:
        """Authenticate periodically; hand processing stays locked between failures."""
        if self._face_authenticator is None:
            # This development-only setting is explicit; production defaults to enabled.
            return FaceAuthenticationResult(FaceAuthenticationStatus.DISABLED)

        self._face_auth_frame_count += 1
        should_check = (
            self._face_auth_result is None
            or self._face_auth_frame_count
            % self._settings.face_auth_check_interval_frames
            == 0
        )
        if should_check:
            self._face_auth_result = self._face_authenticator.authenticate(frame)
        self._face_authenticator.draw_result(frame, self._face_auth_result)
        return self._face_auth_result

    def _update_fps(self) -> float:
        now = time.monotonic()
        if self._last_frame_at is None:
            self._last_frame_at = now
            return 0.0
        elapsed = max(now - self._last_frame_at, 1e-6)
        self._last_frame_at = now
        instantaneous_fps = 1.0 / elapsed
        return instantaneous_fps if self._fps == 0 else (0.9 * self._fps) + (0.1 * instantaneous_fps)

    @staticmethod
    def _handedness(results) -> str | None:
        """Extract MediaPipe's optional hand label without coupling to its type."""
        if not results.handedness or not results.handedness[0]:
            return None
        return results.handedness[0][0].category_name

    def _draw_overlay(
        self,
        frame,
        gesture: Gesture,
        fingers: FingerStates,
        face_auth_result: FaceAuthenticationResult,
    ) -> None:
        """Draw live gesture, LED, Bluetooth and performance status."""
        panel_left, panel_top, panel_right, panel_bottom = 10, 10, 365, 235
        cv2.rectangle(
            frame,
            (panel_left, panel_top),
            (panel_right, panel_bottom),
            (0, 0, 0),
            -1,
        )
        cv2.rectangle(
            frame,
            (panel_left, panel_top),
            (panel_right, panel_bottom),
            (80, 80, 80),
            1,
        )
        self._put_text(frame, "Gesture LED Controller", 35, (255, 255, 255), 0.62)
        face_color = (0, 255, 0) if face_auth_result.authorized else (0, 0, 255)
        self._put_text(frame, face_auth_result.display_text, 60, face_color)
        gesture_color = (0, 255, 255) if gesture is not Gesture.UNKNOWN else (180, 180, 180)
        self._put_text(frame, f"Gesture: {gesture.value}", 85, gesture_color)
        self._put_text(frame, f"Finger Count: {fingers.count}", 110, (255, 255, 255))

        states = self._led_service.states.as_tuple()
        for index, state in enumerate(states, start=1):
            color = (0, 255, 0) if state else (0, 0, 255)
            self._put_text(
                frame,
                f"L{index}: {'ON' if state else 'OFF'}",
                110 + (index * 25),
                color,
            )

        connected = bool(self._bluetooth and self._bluetooth.is_connected)
        bluetooth_color = (0, 255, 0) if connected else (0, 0, 255)
        bluetooth_text = "CONNECTED" if connected else "DISCONNECTED"
        self._put_text(frame, f"Bluetooth: {bluetooth_text}", 210, bluetooth_color)
        self._put_text(frame, f"FPS: {self._fps:.1f}", 230, (255, 255, 255))
        self._put_text(
            frame,
            "Press Q to exit",
            max(frame.shape[0] - 12, 20),
            (255, 255, 255),
        )

    @staticmethod
    def _put_text(frame, text: str, y: int, color, scale: float = 0.55) -> None:
        cv2.putText(
            frame,
            text,
            (20, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            scale,
            color,
            1,
            cv2.LINE_AA,
        )

    def close(self) -> None:
        """Release camera, MediaPipe and Bluetooth resources."""
        self._detector.close()
        if self._camera is not None:
            self._camera.release()
            self._camera = None
        if self._bluetooth is not None:
            self._bluetooth.close()
        cv2.destroyAllWindows()


def main() -> int:
    """Configure logging and run the application."""
    try:
        settings = Settings.from_environment()
        logging.basicConfig(
            level=settings.log_level,
            format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
        )
        HandGestureApplication(settings).run()
    except Exception:
        LOGGER.exception("Application stopped because of an error.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
