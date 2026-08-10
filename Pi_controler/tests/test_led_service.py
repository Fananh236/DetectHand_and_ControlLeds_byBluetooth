"""Tests for persistent LED-state changes."""

from __future__ import annotations

from unittest import TestCase

from src.services import LedService, LedStates
from src.vision import Gesture


class LedServiceTests(TestCase):
    def test_individual_gestures_preserve_unrelated_leds(self) -> None:
        service = LedService(LedStates(led1=True, led2=True, led3=False))

        self.assertEqual(
            service.apply(Gesture.THUMBS_DOWN).states,
            LedStates(False, True, False),
        )
        self.assertEqual(
            service.apply(Gesture.ROCK).states,
            LedStates(False, True, True),
        )
        self.assertEqual(
            service.apply(Gesture.OK).states,
            LedStates(False, False, True),
        )
        self.assertEqual(
            service.apply(Gesture.VICTORY).states,
            LedStates(False, True, True),
        )
        self.assertEqual(
            service.apply(Gesture.THREE_FINGERS).states,
            LedStates(False, True, False),
        )

    def test_open_palm_and_fist_change_all_leds(self) -> None:
        service = LedService(LedStates(True, False, True))

        self.assertEqual(
            service.apply(Gesture.OPEN_PALM).states,
            LedStates(True, True, True),
        )
        update = service.apply(Gesture.FIST)
        self.assertEqual(update.states, LedStates(False, False, False))
        self.assertTrue(update.changed)

    def test_unknown_does_not_change_state(self) -> None:
        states = LedStates(True, False, True)
        update = LedService(states).apply(Gesture.UNKNOWN)
        self.assertEqual(update.states, states)
        self.assertFalse(update.changed)

    def test_command_uses_arduino_protocol_order(self) -> None:
        self.assertEqual(LedStates(True, False, True).command, "LED:101")

    def test_manual_replacement_updates_all_leds_at_once(self) -> None:
        service = LedService(LedStates(False, False, False))

        update = service.set_states(LedStates(True, False, True))

        self.assertTrue(update.changed)
        self.assertEqual(update.states.command, "LED:101")
