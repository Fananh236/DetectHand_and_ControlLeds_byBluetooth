"""Local owner authentication based on OpenCV face detection and LBPH matching."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import cv2
import numpy as np


LOGGER = logging.getLogger(__name__)
OWNER_LABEL = 0
FACE_SIZE = (200, 200)
IMAGE_SUFFIXES = frozenset({".bmp", ".jpeg", ".jpg", ".png", ".webp"})


class FaceAuthenticationSetupError(RuntimeError):
    """Raised when the local face-authentication gate cannot be initialised."""


class FaceAuthenticationStatus(str, Enum):
    """Current identity result for the camera frame."""

    AUTHORIZED = "AUTHORIZED"
    DISABLED = "DISABLED"
    NO_FACE = "NO_FACE"
    UNKNOWN_FACE = "UNKNOWN_FACE"
    MULTIPLE_FACES = "MULTIPLE_FACES"


@dataclass(frozen=True)
class FaceAuthenticationResult:
    """A face-authentication decision and optional face position."""

    status: FaceAuthenticationStatus
    confidence: float | None = None
    bounding_box: tuple[int, int, int, int] | None = None

    @property
    def authorized(self) -> bool:
        """Whether the hand-control gate may be opened."""
        return self.status in {
            FaceAuthenticationStatus.AUTHORIZED,
            FaceAuthenticationStatus.DISABLED,
        }

    @property
    def display_text(self) -> str:
        """Concise status text suited to the camera overlay."""
        if self.status is FaceAuthenticationStatus.DISABLED:
            return "Face: AUTH DISABLED"
        if self.status is FaceAuthenticationStatus.AUTHORIZED:
            return f"Face: AUTHORIZED ({self.confidence:.1f})"
        if self.status is FaceAuthenticationStatus.UNKNOWN_FACE:
            return f"Face: UNKNOWN ({self.confidence:.1f})"
        if self.status is FaceAuthenticationStatus.MULTIPLE_FACES:
            return "Face: MULTIPLE - LOCKED"
        return "Face: NOT FOUND - LOCKED"


class FaceAuthenticator:
    """Recognise the owner from images stored only on the local machine.

    Every image in ``reference_directory`` belongs to the one authorized owner.
    The recognizer first extracts its largest detected face from each reference
    image, then trains an OpenCV LBPH recognizer.  LBPH confidence is a
    distance, so smaller values indicate a closer match.
    """

    def __init__(
        self,
        reference_directory: Path,
        threshold: float = 55.0,
        min_face_size: int = 80,
    ) -> None:
        if threshold <= 0:
            raise ValueError("threshold must be greater than zero.")
        if min_face_size <= 0:
            raise ValueError("min_face_size must be greater than zero.")
        if not hasattr(cv2, "face") or not hasattr(
            cv2.face, "LBPHFaceRecognizer_create"
        ):
            raise FaceAuthenticationSetupError(
                "OpenCV face support is unavailable. Install opencv-contrib-python "
                "instead of opencv-python."
            )

        cascade_path = Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"
        self._face_detector = cv2.CascadeClassifier(str(cascade_path))
        if self._face_detector.empty():
            raise FaceAuthenticationSetupError(
                f"Cannot load OpenCV face detector from {cascade_path}."
            )

        self._threshold = threshold
        self._min_face_size = min_face_size
        self._recognizer = cv2.face.LBPHFaceRecognizer_create(1, 8, 8, 8, threshold)
        reference_faces = self._load_reference_faces(reference_directory)
        if not reference_faces:
            raise FaceAuthenticationSetupError(
                "No usable face was found in "
                f"{reference_directory}. Add clear, front-facing owner photos."
            )

        labels = np.full(len(reference_faces), OWNER_LABEL, dtype=np.int32)
        self._recognizer.train(reference_faces, labels)
        LOGGER.info(
            "Face authentication is ready with %d owner reference image(s).",
            len(reference_faces),
        )

    def authenticate(self, frame_bgr) -> FaceAuthenticationResult:
        """Authorize only one visible face that matches the owner references."""
        gray_frame = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        faces = self._detect_faces(gray_frame)
        if not faces:
            return FaceAuthenticationResult(FaceAuthenticationStatus.NO_FACE)
        if len(faces) != 1:
            return FaceAuthenticationResult(FaceAuthenticationStatus.MULTIPLE_FACES)

        face_box = faces[0]
        face_image = self._crop_and_normalize(gray_frame, face_box)
        label, confidence = self._recognizer.predict(face_image)
        confidence = float(confidence)
        if label == OWNER_LABEL and confidence <= self._threshold:
            return FaceAuthenticationResult(
                FaceAuthenticationStatus.AUTHORIZED,
                confidence,
                face_box,
            )
        return FaceAuthenticationResult(
            FaceAuthenticationStatus.UNKNOWN_FACE,
            confidence,
            face_box,
        )

    def draw_result(self, frame_bgr, result: FaceAuthenticationResult) -> None:
        """Draw the face location in a color that reflects the authorization gate."""
        if result.bounding_box is None:
            return
        x, y, width, height = result.bounding_box
        color = (0, 255, 0) if result.authorized else (0, 0, 255)
        cv2.rectangle(frame_bgr, (x, y), (x + width, y + height), color, 2)

    def _load_reference_faces(self, reference_directory: Path) -> list:
        if not reference_directory.is_dir():
            raise FaceAuthenticationSetupError(
                f"Face reference directory does not exist: {reference_directory}."
            )

        reference_faces = []
        image_paths = sorted(
            path
            for path in reference_directory.iterdir()
            if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
        )
        for image_path in image_paths:
            image = cv2.imread(str(image_path))
            if image is None:
                LOGGER.warning("Ignoring unreadable face reference image: %s", image_path)
                continue
            gray_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            faces = self._detect_faces(gray_image)
            if not faces:
                LOGGER.warning("No face found in reference image: %s", image_path.name)
                continue
            largest_face = max(faces, key=lambda box: box[2] * box[3])
            normalized_face = self._crop_and_normalize(gray_image, largest_face)
            reference_faces.extend((normalized_face, cv2.flip(normalized_face, 1)))
        return reference_faces

    def _detect_faces(self, gray_image) -> list[tuple[int, int, int, int]]:
        detected = self._face_detector.detectMultiScale(
            gray_image,
            scaleFactor=1.1,
            minNeighbors=6,
            minSize=(self._min_face_size, self._min_face_size),
        )
        return [tuple(map(int, face)) for face in detected]

    @staticmethod
    def _crop_and_normalize(gray_image, face_box: tuple[int, int, int, int]):
        x, y, width, height = face_box
        face = gray_image[y:y + height, x:x + width]
        return cv2.resize(face, FACE_SIZE, interpolation=cv2.INTER_AREA)
