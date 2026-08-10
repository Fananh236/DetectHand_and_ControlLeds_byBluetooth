"""Tests for camera performance settings loaded from the environment."""

from __future__ import annotations

import os
from unittest import TestCase
from unittest.mock import patch

from src.config import Settings


class SettingsTests(TestCase):
    def test_camera_fps_can_be_increased_from_the_environment(self) -> None:
        with patch.dict(os.environ, {"CAMERA_FPS": "60"}):
            settings = Settings.from_environment()

        self.assertEqual(settings.camera_fps, 60)

    def test_camera_fps_must_be_positive(self) -> None:
        with patch.dict(os.environ, {"CAMERA_FPS": "0"}):
            with self.assertRaisesRegex(ValueError, "CAMERA_FPS"):
                Settings.from_environment()
