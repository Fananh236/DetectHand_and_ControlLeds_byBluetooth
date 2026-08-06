"""Tests for the owner-only face-authentication gate."""

from __future__ import annotations

from unittest import TestCase

import numpy as np

from src.vision.face_authenticator import (
    FaceAuthenticationStatus,
    FaceAuthenticator,
)


class _FaceDetector:
    def __init__(self, faces) -> None:
        self._faces = faces

    def detectMultiScale(self, *_args, **_kwargs):
        return self._faces


class _Recognizer:
    def __init__(self, label: int, confidence: float) -> None:
        self._prediction = (label, confidence)
        self.was_called = False

    def predict(self, _face):
        self.was_called = True
        return self._prediction


class FaceAuthenticatorTests(TestCase):
    def _authenticator(self, faces, label=0, confidence=40.0) -> FaceAuthenticator:
        authenticator = FaceAuthenticator.__new__(FaceAuthenticator)
        authenticator._face_detector = _FaceDetector(faces)
        authenticator._recognizer = _Recognizer(label, confidence)
        authenticator._threshold = 55.0
        authenticator._min_face_size = 20
        return authenticator

    @staticmethod
    def _frame():
        return np.zeros((200, 200, 3), dtype=np.uint8)

    def test_matching_single_face_authorizes_hand_control(self) -> None:
        authenticator = self._authenticator(np.array([[20, 20, 100, 100]]))

        result = authenticator.authenticate(self._frame())

        self.assertTrue(result.authorized)
        self.assertEqual(result.status, FaceAuthenticationStatus.AUTHORIZED)
        self.assertEqual(result.bounding_box, (20, 20, 100, 100))

    def test_unknown_face_locks_hand_control(self) -> None:
        authenticator = self._authenticator(
            np.array([[20, 20, 100, 100]]), label=-1, confidence=80.0
        )

        result = authenticator.authenticate(self._frame())

        self.assertFalse(result.authorized)
        self.assertEqual(result.status, FaceAuthenticationStatus.UNKNOWN_FACE)

    def test_owner_label_above_threshold_is_still_rejected(self) -> None:
        authenticator = self._authenticator(
            np.array([[20, 20, 100, 100]]), label=0, confidence=55.1
        )

        result = authenticator.authenticate(self._frame())

        self.assertFalse(result.authorized)
        self.assertEqual(result.status, FaceAuthenticationStatus.UNKNOWN_FACE)

    def test_multiple_faces_lock_hand_control_without_prediction(self) -> None:
        authenticator = self._authenticator(
            np.array([[20, 20, 100, 100], [50, 50, 80, 80]])
        )

        result = authenticator.authenticate(self._frame())

        self.assertFalse(result.authorized)
        self.assertEqual(result.status, FaceAuthenticationStatus.MULTIPLE_FACES)
        self.assertFalse(authenticator._recognizer.was_called)
