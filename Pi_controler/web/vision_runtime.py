"""Background camera worker that feeds recognised gestures to the controller."""

from __future__ import annotations

import logging
import sys
import threading
import time
from typing import Any

import cv2

from src.config import Settings
from src.vision import (
    FaceAuthenticationResult,
    FaceAuthenticationStatus,
    FaceAuthenticator,
    FingerStates,
    Gesture,
    GestureClassifier,
    HandDetector,
)

from .models import Device
from .services import get_controller, publish_device_event


LOGGER = logging.getLogger(__name__)


class VisionRuntime:
    """Own one optional camera loop and expose a privacy-conscious JPEG preview."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._snapshot_ready = threading.Condition(self._lock)
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._device_id: int | None = None
        self._snapshot: bytes | None = None
        self._snapshot_version = 0
        self._status: dict[str, Any] = {
            "running": False,
            "gesture": Gesture.UNKNOWN.value,
            "finger_count": 0,
            "face_status": FaceAuthenticationStatus.DISABLED.value,
            "face_confidence": None,
            "authorized": False,
            "fps": 0.0,
            "error": "",
        }

    @property
    def status(self) -> dict[str, Any]:
        """Return the most recent recognition and worker state."""
        with self._lock:
            return dict(self._status)

    def snapshot(self) -> bytes | None:
        """Return the latest in-memory preview; never persist camera frames."""
        with self._lock:
            return self._snapshot

    def wait_for_snapshot(
        self,
        last_version: int,
        timeout: float = 1.0,
    ) -> tuple[int, bytes | None, bool]:
        """Wait for a newer JPEG without busy-polling the camera thread."""
        with self._snapshot_ready:
            self._snapshot_ready.wait_for(
                lambda: self._snapshot_version > last_version
                or not self._status["running"],
                timeout=timeout,
            )
            return (
                self._snapshot_version,
                self._snapshot,
                bool(self._status["running"]),
            )

    def start(self, device: Device) -> dict[str, Any]:
        """Start the camera worker once for the selected device."""
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                if self._device_id != device.id:
                    raise RuntimeError("The camera is already assigned to another device.")
                return self.status
            self._device_id = device.id
            self._snapshot = None
            self._snapshot_version = 0
            self._stop_event = threading.Event()
            self._status = {
                "running": True,
                "gesture": Gesture.UNKNOWN.value,
                "finger_count": 0,
                "face_status": "STARTING",
                "face_confidence": None,
                "authorized": False,
                "fps": 0.0,
                "error": "",
            }
            self._thread = threading.Thread(
                target=self._run,
                args=(device.id,),
                name="gesture-camera-worker",
                daemon=True,
            )
            self._thread.start()
        self._publish(device.id)
        return self.status

    def stop(self) -> dict[str, Any]:
        """Ask the worker to release the camera without blocking a request forever."""
        with self._lock:
            worker = self._thread
            self._stop_event.set()
        if worker is not None:
            worker.join(timeout=2.5)
        return self.status

    def _run(self, device_id: int) -> None:
        camera = None
        detector = HandDetector(Settings.from_environment().hand_landmarker_model)
        authenticator = None
        classifier = GestureClassifier()
        device = Device.objects.get(pk=device_id)
        last_detection_timestamp_ms = -1
        last_frame_at: float | None = None
        smoothed_fps = 0.0
        auth_result: FaceAuthenticationResult | None = None
        frame_count = 0
        last_publish_at = 0.0
        try:
            runtime_settings = Settings.from_environment()
            if runtime_settings.face_auth_enabled:
                authenticator = FaceAuthenticator(
                    runtime_settings.face_auth_reference_directory,
                    threshold=runtime_settings.face_auth_threshold,
                    model_path=runtime_settings.face_auth_model_path,
                )
            backend = cv2.CAP_DSHOW if sys.platform.startswith("win") else cv2.CAP_ANY
            camera = cv2.VideoCapture(runtime_settings.camera_index, backend)
            if not camera.isOpened():
                raise RuntimeError(
                    f"Cannot open camera index {runtime_settings.camera_index}."
                )
            camera.set(cv2.CAP_PROP_FRAME_WIDTH, runtime_settings.camera_width)
            camera.set(cv2.CAP_PROP_FRAME_HEIGHT, runtime_settings.camera_height)
            camera.set(
                cv2.CAP_PROP_FOURCC,
                cv2.VideoWriter_fourcc(*"MJPG"),
            )
            camera.set(cv2.CAP_PROP_FPS, runtime_settings.camera_fps)
            camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            detector.start()

            while not self._stop_event.is_set():
                success, frame = camera.read()
                if not success:
                    raise RuntimeError("Cannot read a frame from the configured camera.")
                frame = cv2.flip(frame, 1)
                frame_count += 1

                if authenticator is None:
                    auth_result = FaceAuthenticationResult(FaceAuthenticationStatus.DISABLED)
                elif (
                    auth_result is None
                    or frame_count % runtime_settings.face_auth_check_interval_frames == 0
                ):
                    auth_result = authenticator.authenticate(frame)
                if authenticator is not None and auth_result is not None:
                    authenticator.draw_result(frame, auth_result)

                gesture = Gesture.UNKNOWN
                fingers = FingerStates(False, False, False, False, False)
                if auth_result is not None and auth_result.authorized:
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    timestamp_ms = max(
                        int(time.monotonic() * 1000),
                        last_detection_timestamp_ms + 1,
                    )
                    last_detection_timestamp_ms = timestamp_ms
                    result = detector.detect(frame_rgb, timestamp_ms)
                    if result.hand_landmarks:
                        landmarks = result.hand_landmarks[0]
                        handedness = self._handedness(result)
                        gesture = classifier.classify(landmarks, handedness)
                        fingers = classifier.finger_states(landmarks)
                        detector.draw_landmarks(frame, landmarks)

                get_controller().observe_gesture(device, gesture)
                smoothed_fps, last_frame_at = self._update_fps(smoothed_fps, last_frame_at)
                self._draw_overlay(frame, gesture, fingers, auth_result, smoothed_fps)
                self._store_snapshot(frame)

                now = time.monotonic()
                if now - last_publish_at >= 0.25:
                    self._set_status(
                        running=True,
                        gesture=gesture.value,
                        finger_count=fingers.count,
                        face_status=auth_result.status.value if auth_result else "STARTING",
                        face_confidence=(
                            round(auth_result.confidence, 1)
                            if auth_result and auth_result.confidence is not None
                            else None
                        ),
                        authorized=bool(auth_result and auth_result.authorized),
                        fps=round(smoothed_fps, 1),
                        error="",
                    )
                    self._publish(device_id)
                    last_publish_at = now
        except Exception as exc:  # noqa: BLE001 - report hardware setup errors to the UI
            LOGGER.exception("Gesture camera worker stopped: %s", exc)
            self._set_status(running=False, error=str(exc))
            self._publish(device_id)
        finally:
            detector.close()
            if camera is not None:
                camera.release()
            with self._lock:
                self._thread = None
                self._status["running"] = False
                self._snapshot_ready.notify_all()
            self._publish(device_id)

    def _set_status(self, **changes: Any) -> None:
        with self._lock:
            self._status.update(changes)

    def _publish(self, device_id: int) -> None:
        publish_device_event(device_id, "vision.update", self.status)

    def _store_snapshot(self, frame) -> None:
        success, encoded = cv2.imencode(
            ".jpg",
            frame,
            [int(cv2.IMWRITE_JPEG_QUALITY), 75],
        )
        if success:
            with self._snapshot_ready:
                self._snapshot = encoded.tobytes()
                self._snapshot_version += 1
                self._snapshot_ready.notify_all()

    @staticmethod
    def _handedness(result) -> str | None:
        if not result.handedness or not result.handedness[0]:
            return None
        return result.handedness[0][0].category_name

    @staticmethod
    def _update_fps(
        current_fps: float,
        previous_frame_at: float | None,
    ) -> tuple[float, float]:
        now = time.monotonic()
        if previous_frame_at is None:
            return 0.0, now
        instantaneous_fps = 1.0 / max(now - previous_frame_at, 1e-6)
        smoothed = instantaneous_fps if current_fps == 0 else (0.9 * current_fps) + (0.1 * instantaneous_fps)
        return smoothed, now

    @staticmethod
    def _draw_overlay(
        frame,
        gesture: Gesture,
        fingers: FingerStates,
        auth_result: FaceAuthenticationResult | None,
        fps: float,
    ) -> None:
        status = auth_result.status.value if auth_result else "STARTING"
        lines = [
            f"Face: {status}",
            f"Gesture: {gesture.value}",
            f"Fingers: {fingers.count}",
            f"FPS: {fps:.1f}",
        ]
        for index, text in enumerate(lines):
            cv2.putText(
                frame,
                text,
                (16, 28 + (index * 26)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.62,
                (255, 255, 255),
                2,
                cv2.LINE_AA,
            )


_runtime = VisionRuntime()


def get_camera_runtime() -> VisionRuntime:
    """Return the camera runtime singleton for API views and test cleanup."""
    return _runtime
