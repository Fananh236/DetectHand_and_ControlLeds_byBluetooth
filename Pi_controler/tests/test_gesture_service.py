"""Tests for gesture stability, latching and cooldown."""

from __future__ import annotations

from unittest import TestCase

from src.services import GestureService, LedService, LedStates
from src.vision import Gesture


class GestureServiceTests(TestCase):
    def test_triggers_after_configured_consecutive_frames(self) -> None:
        service = GestureService(
            LedService(),
            confirmation_seconds=10,
            confirmation_frames=3,
            cooldown_seconds=1,
        )

        self.assertFalse(service.observe(Gesture.THUMBS_UP, now=0.0).triggered)
        self.assertFalse(service.observe(Gesture.THUMBS_UP, now=0.1).triggered)
        decision = service.observe(Gesture.THUMBS_UP, now=0.2)

        self.assertTrue(decision.triggered)
        self.assertEqual(decision.states, LedStates(True, False, False))

    def test_triggers_after_confirmation_duration(self) -> None:
        service = GestureService(
            LedService(),
            confirmation_seconds=0.5,
            confirmation_frames=99,
            cooldown_seconds=1,
        )

        self.assertFalse(service.observe(Gesture.VICTORY, now=0.0).triggered)
        self.assertFalse(service.observe(Gesture.VICTORY, now=0.49).triggered)
        decision = service.observe(Gesture.VICTORY, now=0.5)

        self.assertTrue(decision.triggered)
        self.assertEqual(decision.states, LedStates(False, True, False))

    def test_held_gesture_is_latched_and_cooldown_delays_next_gesture(self) -> None:
        service = GestureService(
            LedService(),
            confirmation_seconds=0,
            confirmation_frames=1,
            cooldown_seconds=1,
        )

        self.assertTrue(service.observe(Gesture.THUMBS_UP, now=0.0).triggered)
        self.assertFalse(service.observe(Gesture.THUMBS_UP, now=0.2).triggered)
        self.assertFalse(service.observe(Gesture.UNKNOWN, now=0.3).triggered)
        self.assertFalse(service.observe(Gesture.VICTORY, now=0.4).triggered)
        decision = service.observe(Gesture.VICTORY, now=1.0)

        self.assertTrue(decision.triggered)
        self.assertEqual(decision.states, LedStates(True, True, False))

    def test_reset_allows_a_new_gesture_session_after_mode_change(self) -> None:
        service = GestureService(
            LedService(),
            confirmation_seconds=0,
            confirmation_frames=1,
            cooldown_seconds=10,
        )
        self.assertTrue(service.observe(Gesture.THUMBS_UP, now=0).triggered)

        service.reset()
        decision = service.observe(Gesture.VICTORY, now=0.1)

        self.assertTrue(decision.triggered)
        self.assertEqual(decision.states, LedStates(True, True, False))
