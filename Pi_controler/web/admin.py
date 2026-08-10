"""Django administration for devices and their control history."""

from django.contrib import admin

from .models import ControlEvent, ControlMode, Device, LedState, Scene


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ("name", "serial_port", "serial_baudrate", "is_enabled")
    search_fields = ("name", "serial_port")


@admin.register(LedState)
class LedStateAdmin(admin.ModelAdmin):
    list_display = ("device", "led1", "led2", "led3", "last_source", "updated_at")
    list_filter = ("last_source",)


@admin.register(ControlMode)
class ControlModeAdmin(admin.ModelAdmin):
    list_display = ("device", "mode", "changed_by", "updated_at")
    list_filter = ("mode",)


@admin.register(Scene)
class SceneAdmin(admin.ModelAdmin):
    list_display = ("name", "device", "led1", "led2", "led3")
    list_filter = ("device",)


@admin.register(ControlEvent)
class ControlEventAdmin(admin.ModelAdmin):
    list_display = ("created_at", "device", "event_type", "source", "user")
    list_filter = ("source", "event_type", "device")
    readonly_fields = ("created_at",)
