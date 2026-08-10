#!/usr/bin/env python
"""Django management entry point for the LED controller dashboard."""

import os
import sys


def main() -> None:
    """Run Django administrative commands."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "web_config.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:  # pragma: no cover - environment failure
        raise ImportError(
            "Django is not available. Activate the project virtual environment and "
            "install requirements.txt."
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
