"""Rule-based gesture recognition using MediaPipe's 21 hand landmarks."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import hypot
from typing import Protocol, Sequence


class Landmark(Protocol):
    """The coordinate interface shared by MediaPipe normalized landmarks."""

    x: float
    y: float
    z: float


class Gesture(str, Enum):
    """Gestures that can change the persistent LED state."""

    THUMBS_UP = "THUMBS_UP"
    THUMBS_DOWN = "THUMBS_DOWN"
    VICTORY = "VICTORY"
    OK = "OK"
    ROCK = "ROCK"
    THREE_FINGERS = "THREE_FINGERS"
    OPEN_PALM = "OPEN_PALM"
    FIST = "FIST"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class FingerStates:
    """Whether thumb through pinky are visibly extended."""

    thumb: bool
    index: bool
    middle: bool
    ring: bool
    pinky: bool

    @property
    def count(self) -> int:
        return sum((self.thumb, self.index, self.middle, self.ring, self.pinky))


class GestureClassifier:
    """Classify upright hand shapes from normalized MediaPipe landmarks.

    The rules use ratios relative to palm size rather than fixed pixels, so
    they work with different camera resolutions and hand distances. They are
    intentionally conservative: ambiguous or partially occluded poses return
    :class:`Gesture.UNKNOWN` instead of issuing a hardware command.
    """

    WRIST = 0
    THUMB_MCP = 2
    THUMB_IP = 3
    THUMB_TIP = 4
    INDEX_MCP = 5
    INDEX_PIP = 6
    INDEX_TIP = 8
    MIDDLE_MCP = 9
    MIDDLE_PIP = 10
    MIDDLE_TIP = 12
    RING_MCP = 13
    RING_PIP = 14
    RING_TIP = 16
    PINKY_MCP = 17
    PINKY_PIP = 18
    PINKY_TIP = 20
    LANDMARK_COUNT = 21

    def classify(
        self,
        landmarks: Sequence[Landmark],
        handedness: str | None = None,
    ) -> Gesture:
        """Return the recognised gesture or ``UNKNOWN`` for an ambiguous pose.

        ``handedness`` is accepted to keep the classifier compatible with the
        MediaPipe result, although these geometry rules do not depend on it.
        """
        del handedness
        if len(landmarks) < self.LANDMARK_COUNT:
            return Gesture.UNKNOWN

        scale = self._palm_scale(landmarks)
        fingers = self.finger_states(landmarks, scale)

        if all(
            (fingers.thumb, fingers.index, fingers.middle, fingers.ring, fingers.pinky)
        ):
            return Gesture.OPEN_PALM
        if not any(
            (fingers.thumb, fingers.index, fingers.middle, fingers.ring, fingers.pinky)
        ):
            return Gesture.FIST
        if self._is_ok(landmarks, fingers, scale):
            return Gesture.OK

        folded = (not fingers.index, not fingers.middle, not fingers.ring, not fingers.pinky)
        if fingers.thumb and folded:
            if self._thumb_points_up(landmarks, scale):
                return Gesture.THUMBS_UP
            if self._thumb_points_down(landmarks, scale):
                return Gesture.THUMBS_DOWN

        if (
            not fingers.thumb
            and fingers.index
            and fingers.middle
            and not fingers.ring
            and not fingers.pinky
        ):
            return Gesture.VICTORY
        # "Rock" is commonly made as either horns (\N{SIGN OF THE HORNS},
        # thumb folded) or the I-love-you sign (\N{SIGN LANGUAGE I LOVE YOU
        # GESTURE}, thumb extended).  The raised index and pinky identify both
        # variants; requiring the thumb to be extended rejected the usual
        # horns pose.
        if (
            fingers.index
            and not fingers.middle
            and not fingers.ring
            and fingers.pinky
        ):
            return Gesture.ROCK
        if (
            not fingers.thumb
            and fingers.index
            and fingers.middle
            and fingers.ring
            and not fingers.pinky
        ):
            return Gesture.THREE_FINGERS
        return Gesture.UNKNOWN

    def finger_states(
        self,
        landmarks: Sequence[Landmark],
        palm_scale: float | None = None,
    ) -> FingerStates:
        """Calculate extended-finger flags that can also drive the camera UI."""
        if len(landmarks) < self.LANDMARK_COUNT:
            return FingerStates(False, False, False, False, False)
        scale = palm_scale if palm_scale is not None else self._palm_scale(landmarks)
        return FingerStates(
            thumb=self._thumb_extended(landmarks, scale),
            index=self._finger_extended(
                landmarks, self.INDEX_MCP, self.INDEX_PIP, self.INDEX_TIP, scale
            ),
            middle=self._finger_extended(
                landmarks, self.MIDDLE_MCP, self.MIDDLE_PIP, self.MIDDLE_TIP, scale
            ),
            ring=self._finger_extended(
                landmarks, self.RING_MCP, self.RING_PIP, self.RING_TIP, scale
            ),
            pinky=self._finger_extended(
                landmarks, self.PINKY_MCP, self.PINKY_PIP, self.PINKY_TIP, scale
            ),
        )

    def _palm_scale(self, landmarks: Sequence[Landmark]) -> float:
        return max(
            self._distance(landmarks[self.WRIST], landmarks[self.MIDDLE_MCP]),
            0.05,
        )

    def _finger_extended(
        self,
        landmarks: Sequence[Landmark],
        mcp_index: int,
        pip_index: int,
        tip_index: int,
        palm_scale: float,
    ) -> bool:
        # With an upright palm, a raised fingertip is noticeably above its PIP.
        return (
            landmarks[tip_index].y < landmarks[pip_index].y - (0.18 * palm_scale)
            and landmarks[pip_index].y <= landmarks[mcp_index].y + (0.25 * palm_scale)
        )

    def _thumb_extended(
        self, landmarks: Sequence[Landmark], palm_scale: float
    ) -> bool:
        thumb_tip = landmarks[self.THUMB_TIP]
        thumb_ip = landmarks[self.THUMB_IP]
        thumb_mcp = landmarks[self.THUMB_MCP]
        index_mcp = landmarks[self.INDEX_MCP]
        long_enough = self._distance(thumb_tip, thumb_mcp) > (0.75 * palm_scale)
        vertical_extension = abs(thumb_tip.y - thumb_ip.y) > (0.35 * palm_scale)
        side_extension = abs(thumb_tip.x - index_mcp.x) > (0.55 * palm_scale)
        return long_enough and (vertical_extension or side_extension)

    def _thumb_points_up(self, landmarks: Sequence[Landmark], palm_scale: float) -> bool:
        return (
            landmarks[self.THUMB_TIP].y
            < landmarks[self.THUMB_IP].y - (0.35 * palm_scale)
            < landmarks[self.THUMB_MCP].y
        )

    def _thumb_points_down(
        self, landmarks: Sequence[Landmark], palm_scale: float
    ) -> bool:
        return (
            landmarks[self.THUMB_TIP].y
            > landmarks[self.THUMB_IP].y + (0.35 * palm_scale)
            > landmarks[self.THUMB_MCP].y
        )

    def _is_ok(
        self,
        landmarks: Sequence[Landmark],
        fingers: FingerStates,
        palm_scale: float,
    ) -> bool:
        thumb_index_touching = self._distance(
            landmarks[self.THUMB_TIP], landmarks[self.INDEX_TIP]
        ) <= (0.55 * palm_scale)
        return (
            thumb_index_touching
            and fingers.middle
            and fingers.ring
            and fingers.pinky
            and not fingers.index
        )

    @staticmethod
    def _distance(first: Landmark, second: Landmark) -> float:
        return hypot(first.x - second.x, first.y - second.y)
