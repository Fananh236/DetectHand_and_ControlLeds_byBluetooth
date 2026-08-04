"""MediaPipe hand-landmark detection and visualization."""

from __future__ import annotations

import logging
import urllib.request
from pathlib import Path
from typing import Final

import cv2
import mediapipe as mp


LOGGER = logging.getLogger(__name__)
MODEL_URL: Final = (
    "https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
    "hand_landmarker/float16/1/hand_landmarker.task"
)
HAND_CONNECTIONS: Final = (
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (0, 9), (9, 10), (10, 11), (11, 12),
    (0, 13), (13, 14), (14, 15), (15, 16),
    (0, 17), (17, 18), (18, 19), (19, 20),
    (5, 9), (9, 13), (13, 17),
)


class HandDetector:
    """Own a MediaPipe HandLandmarker model and its detection helpers."""

    def __init__(self, model_path: Path) -> None:
        self._model_path = model_path
        self._landmarker = None

    def start(self) -> None:
        """Load the task model, downloading it once when absent."""
        model_path = self._ensure_model()
        options = mp.tasks.vision.HandLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=str(model_path)),
            running_mode=mp.tasks.vision.RunningMode.VIDEO,
            num_hands=1,
            min_hand_detection_confidence=0.7,
            min_hand_presence_confidence=0.7,
            min_tracking_confidence=0.5,
        )
        self._landmarker = mp.tasks.vision.HandLandmarker.create_from_options(options)

    def detect(self, frame_rgb, timestamp_ms: int):
        """Return hand-landmark results for an RGB OpenCV frame."""
        if self._landmarker is None:
            raise RuntimeError("HandDetector.start() must be called before detect().")
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)
        return self._landmarker.detect_for_video(image, timestamp_ms)

    def close(self) -> None:
        if self._landmarker is not None:
            self._landmarker.close()
            self._landmarker = None

    def _ensure_model(self) -> Path:
        if self._model_path.exists():
            return self._model_path

        self._model_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self._model_path.with_suffix(".task.download")
        LOGGER.info("Downloading the Hand Landmarker model...")
        try:
            urllib.request.urlretrieve(MODEL_URL, temporary_path)
            temporary_path.replace(self._model_path)
        except Exception as exc:
            temporary_path.unlink(missing_ok=True)
            raise RuntimeError(
                f"Cannot download Hand Landmarker model from {MODEL_URL}."
            ) from exc
        return self._model_path

    @staticmethod
    def detect_fingers(landmarks) -> tuple[bool, bool, bool, bool, bool]:
        """Return thumb, index, middle, ring and pinky open states."""
        pinky_is_right_of_index = landmarks[17].x > landmarks[5].x
        thumb_open = (
            landmarks[4].x < landmarks[3].x
            if pinky_is_right_of_index
            else landmarks[4].x > landmarks[3].x
        )
        other_fingers = tuple(
            landmarks[tip_index].y < landmarks[pip_index].y
            for tip_index, pip_index in ((8, 6), (12, 10), (16, 14), (20, 18))
        )
        return (thumb_open, *other_fingers)

    @staticmethod
    def draw_landmarks(frame, landmarks) -> None:
        """Draw the detected hand skeleton over an OpenCV BGR frame."""
        frame_height, frame_width = frame.shape[:2]
        points = [
            (int(landmark.x * frame_width), int(landmark.y * frame_height))
            for landmark in landmarks
        ]
        for start, end in HAND_CONNECTIONS:
            cv2.line(frame, points[start], points[end], (0, 255, 0), 2)
        for point in points:
            cv2.circle(frame, point, 3, (0, 0, 255), -1)
