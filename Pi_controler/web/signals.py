"""Create the initial device state once database migrations are complete."""

from django.apps import apps
from django.db.models.signals import post_migrate
from django.dispatch import receiver


@receiver(post_migrate)
def create_default_device(sender, **_kwargs) -> None:
    """Seed one local device without overwriting a user's existing settings."""
    if sender.name != "web":
        return
    device_model = apps.get_model("web", "Device")
    led_state_model = apps.get_model("web", "LedState")
    control_mode_model = apps.get_model("web", "ControlMode")
    scene_model = apps.get_model("web", "Scene")

    device, _ = device_model.objects.get_or_create(name="Lab LED 01")
    led_state_model.objects.get_or_create(device=device)
    control_mode_model.objects.get_or_create(device=device)
    for name, states in {"All On": (True, True, True), "All Off": (False, False, False)}.items():
        scene_model.objects.get_or_create(
            device=device,
            name=name,
            defaults={"led1": states[0], "led2": states[1], "led3": states[2]},
        )
