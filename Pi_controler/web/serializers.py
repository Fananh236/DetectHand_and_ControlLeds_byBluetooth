"""Validation and response serializers for the dashboard REST API."""

from rest_framework import serializers

from .models import ControlEvent, Scene


class LedWriteSerializer(serializers.Serializer):
    """Accept one or more boolean LED values for a manual command."""

    led1 = serializers.BooleanField(required=False)
    led2 = serializers.BooleanField(required=False)
    led3 = serializers.BooleanField(required=False)

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError("Provide at least one LED value.")
        return attrs


class ModeWriteSerializer(serializers.Serializer):
    """Validate the chosen control source."""

    mode = serializers.ChoiceField(choices=("manual", "gesture", "locked"))


class SceneSerializer(serializers.ModelSerializer):
    """Render user-defined and built-in scenes."""

    class Meta:
        model = Scene
        fields = ("id", "name", "led1", "led2", "led3")


class EventSerializer(serializers.ModelSerializer):
    """Render a safe subset of the device audit history."""

    username = serializers.SerializerMethodField()

    class Meta:
        model = ControlEvent
        fields = ("id", "source", "event_type", "payload", "username", "created_at")

    @staticmethod
    def get_username(event: ControlEvent) -> str | None:
        return event.user.get_username() if event.user else None
