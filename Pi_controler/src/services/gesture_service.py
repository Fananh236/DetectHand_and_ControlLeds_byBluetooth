"""Gesture confirmation, cooldown and LED-command orchestration."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

from ..vision.gesture_classifier import Gesture
from .led_service import LedService, LedStates


@dataclass(frozen=True)
class GestureDecision:
    """The result of processing one camera frame."""

    detected_gesture: Gesture
    stable_gesture: Gesture
    states: LedStates
    triggered: bool


class GestureService:
    """Confirm stable gestures and apply each held gesture at most once.

    A pose is actionable once it has been present for the configured duration
    *or* the configured number of consecutive frames. Once triggered, that
    pose is latched until the camera observes a different pose. The latch and
    cooldown together prevent repeated Bluetooth commands while a user holds a
    hand gesture in front of the camera.
    """

    def __init__(
        self,
        led_service: LedService,
        confirmation_seconds: float = 0.5,
        confirmation_frames: int = 10,
        cooldown_seconds: float = 1.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if confirmation_seconds < 0:
            raise ValueError("confirmation_seconds cannot be negative.")
        if confirmation_frames <= 0:
            raise ValueError("confirmation_frames must be greater than zero.")
        if cooldown_seconds < 0:
            raise ValueError("cooldown_seconds cannot be negative.")

        self._led_service = led_service
        self._confirmation_seconds = confirmation_seconds
        self._confirmation_frames = confirmation_frames
        self._cooldown_seconds = cooldown_seconds
        self._clock = clock
        self._candidate = Gesture.UNKNOWN
        self._candidate_started_at = 0.0
        self._candidate_frames = 0
        self._latched_gesture: Gesture | None = None
        self._last_triggered_at = float("-inf")

    @property
    def states(self) -> LedStates:
        return self._led_service.states

    def observe(self, gesture: Gesture, now: float | None = None) -> GestureDecision:
        """Process a raw gesture classification from one video frame."""
        timestamp = self._clock() if now is None else now

        if gesture is not self._latched_gesture:
            self._latched_gesture = None

        if gesture is Gesture.UNKNOWN:
            self._reset_candidate()
            return GestureDecision(gesture, Gesture.UNKNOWN, self.states, False)

        if gesture is not self._candidate:
            self._candidate = gesture
            self._candidate_started_at = timestamp
            self._candidate_frames = 1
        else:
            self._candidate_frames += 1

        confirmed = (
            self._candidate_frames >= self._confirmation_frames
            or timestamp - self._candidate_started_at >= self._confirmation_seconds
        )
        outside_cooldown = timestamp - self._last_triggered_at >= self._cooldown_seconds
        can_trigger = (
            confirmed
            and outside_cooldown
            and self._latched_gesture is None
            and gesture is self._candidate
        )
        if not can_trigger:
            stable_gesture = self._candidate if confirmed else Gesture.UNKNOWN
            return GestureDecision(gesture, stable_gesture, self.states, False)

        self._latched_gesture = gesture
        self._last_triggered_at = timestamp
        update = self._led_service.apply(gesture)
        return GestureDecision(gesture, gesture, update.states, True)

    def _reset_candidate(self) -> None:
        self._candidate = Gesture.UNKNOWN
        self._candidate_started_at = 0.0
        self._candidate_frames = 0
