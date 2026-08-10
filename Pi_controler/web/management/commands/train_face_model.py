"""Train and save the local owner's LBPH face-recognition model."""

from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from src.config import Settings
from src.vision import FaceAuthenticationSetupError, FaceAuthenticator


class Command(BaseCommand):
    help = "Train the local owner face model from images in Pi_controler/data."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--output",
            type=Path,
            help="Optional output .yml path; defaults to model/face_authenticator.yml.",
        )
        parser.add_argument(
            "--threshold",
            type=float,
            help="LBPH distance threshold; defaults to FACE_AUTH_THRESHOLD.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Replace an existing generated model.",
        )

    def handle(self, *args, **options) -> None:
        settings = Settings.from_environment()
        output_path = options["output"] or settings.face_auth_model_path
        if not output_path.is_absolute():
            output_path = settings.project_root / output_path
        threshold = options["threshold"] or settings.face_auth_threshold

        if output_path.exists() and not options["force"]:
            raise CommandError(
                f"Model already exists at {output_path}. Use --force to retrain it."
            )

        try:
            authenticator = FaceAuthenticator(
                settings.face_auth_reference_directory,
                threshold=threshold,
                model_path=None,
            )
            authenticator.save_model(output_path)
        except (FaceAuthenticationSetupError, ValueError) as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(
            self.style.SUCCESS(
                "Face model trained successfully with "
                f"{authenticator.reference_face_count} normalized sample(s): "
                f"{output_path}"
            )
        )
