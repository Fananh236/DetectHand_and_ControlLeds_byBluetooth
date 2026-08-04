"""Translate detected fingers into LED states."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Final


BLINK: Final = "BLINK"
ALL_OFF: Final = "ALL_OFF"
FINGER_CONTROL: Final = "FINGER_CONTROL"


@dataclass(frozen=True)
class GestureUpdate:
    """The current recognized gesture and LED state it produces."""

    gesture: str
    fingers: tuple[bool, bool, bool, bool, bool]
    led_states: tuple[bool, bool, bool]


class GestureLedService:
    """Maintain LED behaviour for hand gestures across camera frames."""

    def __init__(self, blink_interval_seconds: float) -> None:
        self._blink_interval_seconds = blink_interval_seconds
        self._led_states: tuple[bool, bool, bool] = (False, False, False)
        self._previous_gesture: str | None = None
        self._last_blink_time = 0.0

    @property
    def led_states(self) -> tuple[bool, bool, bool]:
        return self._led_states

    def update(self, fingers: tuple[bool, bool, bool, bool, bool]) -> GestureUpdate:
        """Update the LED state for a newly detected hand."""
        finger_count = sum(fingers)
        if finger_count == 4:
            gesture = BLINK
        elif finger_count == 5:
            gesture = ALL_OFF
        else:
            gesture = FINGER_CONTROL

        if gesture == BLINK:
            now = time.monotonic()
            if self._previous_gesture != BLINK:
                self._led_states = (True, True, True)
                self._last_blink_time = now
            elif now - self._last_blink_time >= self._blink_interval_seconds:
                next_state = not self._led_states[0]
                self._led_states = (next_state, next_state, next_state)
                self._last_blink_time = now
        elif gesture == ALL_OFF:
            self._led_states = (False, False, False)
        else:
            # Index 0 is thumb; index 1..3 map to Arduino pins 8, 9 and 10.
            self._led_states = (fingers[1], fingers[2], fingers[3])

        self._previous_gesture = gesture
        return GestureUpdate(gesture, fingers, self._led_states)
