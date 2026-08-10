"""Persistent LED-state business rules."""

from __future__ import annotations

from dataclasses import dataclass

from ..vision.gesture_classifier import Gesture


@dataclass(frozen=True)
class LedStates:
    """The state of the three physical LEDs in Arduino command order."""

    led1: bool = False
    led2: bool = False
    led3: bool = False

    def as_tuple(self) -> tuple[bool, bool, bool]:
        return (self.led1, self.led2, self.led3)

    @property
    def command(self) -> str:
        return "LED:" + "".join("1" if state else "0" for state in self.as_tuple())


@dataclass(frozen=True)
class LedUpdate:
    """Result of applying one confirmed gesture to the LED state."""

    gesture: Gesture
    previous_states: LedStates
    states: LedStates

    @property
    def changed(self) -> bool:
        return self.previous_states != self.states


class LedService:
    """Apply gestures without overwriting unrelated LED states."""

    def __init__(self, initial_states: LedStates | None = None) -> None:
        self._states = initial_states or LedStates()

    @property
    def states(self) -> LedStates:
        return self._states

    def apply(self, gesture: Gesture) -> LedUpdate:
        """Apply a confirmed gesture and retain the resulting state."""
        previous_states = self._states
        led1, led2, led3 = previous_states.as_tuple()

        if gesture is Gesture.THUMBS_UP:
            led1 = True
        elif gesture is Gesture.THUMBS_DOWN:
            led1 = False
        elif gesture is Gesture.VICTORY:
            led2 = True
        elif gesture is Gesture.OK:
            led2 = False
        elif gesture is Gesture.ROCK:
            led3 = True
        elif gesture is Gesture.THREE_FINGERS:
            led3 = False
        elif gesture is Gesture.OPEN_PALM:
            led1 = led2 = led3 = True
        elif gesture is Gesture.FIST:
            led1 = led2 = led3 = False

        self._states = LedStates(led1, led2, led3)
        return LedUpdate(gesture, previous_states, self._states)

    def set_states(self, states: LedStates) -> LedUpdate:
        """Replace all LED states for a trusted manual or scene command."""
        previous_states = self._states
        self._states = states
        return LedUpdate(Gesture.UNKNOWN, previous_states, self._states)
