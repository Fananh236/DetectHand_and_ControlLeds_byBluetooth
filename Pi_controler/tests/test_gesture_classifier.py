"""Unit tests for geometry-based hand gesture recognition."""

from __future__ import annotations

from dataclasses import dataclass
from unittest import TestCase

from src.vision import Gesture, GestureClassifier


@dataclass
class FakeLandmark:
    x: float
    y: float
    z: float = 0.0


class GestureClassifierTests(TestCase):
    def setUp(self) -> None:
        self.classifier = GestureClassifier()

    def test_classifies_all_supported_gestures(self) -> None:
        cases = {
            Gesture.THUMBS_UP: self._landmarks(thumb="up"),
            Gesture.THUMBS_DOWN: self._landmarks(thumb="down"),
            Gesture.VICTORY: self._landmarks(extended={"index", "middle"}),
            Gesture.OK: self._landmarks(
                ok_sign=True, extended={"middle", "ring", "pinky"}
            ),
            Gesture.ROCK: self._landmarks(
                thumb="side", extended={"index", "pinky"}
            ),
            Gesture.THREE_FINGERS: self._landmarks(
                extended={"index", "middle", "ring"}
            ),
            Gesture.OPEN_PALM: self._landmarks(
                thumb="side", extended={"index", "middle", "ring", "pinky"}
            ),
            Gesture.FIST: self._landmarks(),
        }

        for expected, landmarks in cases.items():
            with self.subTest(gesture=expected):
                self.assertEqual(self.classifier.classify(landmarks), expected)

    def test_returns_unknown_for_an_unsupported_shape(self) -> None:
        self.assertEqual(
            self.classifier.classify(self._landmarks(extended={"index"})),
            Gesture.UNKNOWN,
        )

    def test_classifies_rock_horns_with_a_folded_thumb(self) -> None:
        """The common \N{SIGN OF THE HORNS} pose must also turn on LED3."""
        self.assertEqual(
            self.classifier.classify(
                self._landmarks(extended={"index", "pinky"})
            ),
            Gesture.ROCK,
        )

    def test_returns_unknown_for_incomplete_landmarks(self) -> None:
        self.assertEqual(
            self.classifier.classify([FakeLandmark(0.5, 0.5)] * 20),
            Gesture.UNKNOWN,
        )

    @staticmethod
    def _landmarks(
        thumb: str = "closed",
        extended: set[str] | None = None,
        ok_sign: bool = False,
    ) -> list[FakeLandmark]:
        extended = extended or set()
        points = [FakeLandmark(0.5, 0.8) for _ in range(21)]
        points[0] = FakeLandmark(0.5, 0.9)  # Wrist

        # MCP, PIP and extended fingertip y-coordinates for four fingers.
        finger_coordinates = {
            "index": (5, 6, 8, 0.44, 0.66, 0.54, 0.30),
            "middle": (9, 10, 12, 0.50, 0.62, 0.50, 0.24),
            "ring": (13, 14, 16, 0.56, 0.65, 0.54, 0.29),
            "pinky": (17, 18, 20, 0.62, 0.70, 0.58, 0.38),
        }
        for name, (mcp, pip, tip, x, mcp_y, pip_y, tip_y) in finger_coordinates.items():
            points[mcp] = FakeLandmark(x, mcp_y)
            if name in extended:
                points[pip] = FakeLandmark(x, pip_y)
                points[tip] = FakeLandmark(x, tip_y)
            else:
                points[pip] = FakeLandmark(x, mcp_y + 0.03)
                points[tip] = FakeLandmark(x, mcp_y + 0.07)

        points[2] = FakeLandmark(0.38, 0.70)  # Thumb MCP
        if thumb == "up":
            points[3] = FakeLandmark(0.38, 0.55)
            points[4] = FakeLandmark(0.38, 0.25)
        elif thumb == "down":
            points[3] = FakeLandmark(0.38, 0.82)
            points[4] = FakeLandmark(0.38, 1.08)
        elif thumb == "side":
            points[3] = FakeLandmark(0.30, 0.68)
            points[4] = FakeLandmark(0.15, 0.66)
        elif ok_sign:
            points[3] = FakeLandmark(0.40, 0.64)
            points[4] = FakeLandmark(0.42, 0.65)
            # The index fingertip touches the thumb and therefore is folded.
            points[6] = FakeLandmark(0.44, 0.67)
            points[8] = FakeLandmark(0.43, 0.65)
        else:
            points[3] = FakeLandmark(0.42, 0.73)
            points[4] = FakeLandmark(0.45, 0.74)
        return points
