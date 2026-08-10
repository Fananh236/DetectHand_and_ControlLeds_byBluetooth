"""HTML dashboard and authenticated REST endpoints."""

from __future__ import annotations

from asgiref.sync import sync_to_async
from django.conf import settings
from django.contrib.auth import get_user_model, login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404, HttpResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import FormView, TemplateView
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ControlEvent, Device, Scene
from .forms import InitialSetupForm
from .serializers import EventSerializer, LedWriteSerializer, ModeWriteSerializer, SceneSerializer
from .services import ControlRejected, get_controller, get_default_device
from .vision_runtime import get_camera_runtime


class DashboardView(LoginRequiredMixin, TemplateView):
    """Render the primary single-device dashboard."""

    template_name = "web/dashboard.html"

    def dispatch(self, request, *args, **kwargs):
        if not get_user_model().objects.exists():
            return redirect("initial-setup")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        device = get_default_device()
        context["device"] = device
        context["status"] = get_controller().get_status(device)
        context["scenes"] = device.scenes.all()
        return context


class InitialSetupView(FormView):
    """Let the first local operator create credentials without a CLI command."""

    template_name = "registration/initial_setup.html"
    form_class = InitialSetupForm
    success_url = reverse_lazy("dashboard")

    def dispatch(self, request, *args, **kwargs):
        if get_user_model().objects.exists():
            return redirect("login")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        user = form.save()
        login(self.request, user)
        return super().form_valid(form)


class DeviceStatusAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, device_id: int):
        device = get_object_or_404(Device, pk=device_id)
        return Response(get_controller().get_status(device))


class HealthAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        device = get_default_device()
        return Response(
            {
                "status": "ok",
                "device": get_controller().get_status(device),
                "camera": get_camera_runtime().status,
            }
        )


class LedStateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request, device_id: int):
        return self._update(request, device_id, partial=False)

    def patch(self, request, device_id: int):
        return self._update(request, device_id, partial=True)

    @staticmethod
    def _update(request, device_id: int, *, partial: bool):
        device = get_object_or_404(Device, pk=device_id)
        serializer = LedWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        current = get_controller().get_status(device)["leds"]
        values = serializer.validated_data
        states = (
            values.get("led1", current["led1"]),
            values.get("led2", current["led2"]),
            values.get("led3", current["led3"]),
        )
        if not partial and set(values) != {"led1", "led2", "led3"}:
            return Response(
                {"detail": "PUT requires led1, led2 and led3."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            payload = get_controller().set_leds(
                device,
                states,
                source=ControlEvent.Source.WEB,
                user=request.user,
            )
        except ControlRejected as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response(payload)


class ControlModeAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request, device_id: int):
        device = get_object_or_404(Device, pk=device_id)
        serializer = ModeWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(
            get_controller().set_mode(
                device,
                serializer.validated_data["mode"],
                user=request.user,
            )
        )


class SceneAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, device_id: int):
        scenes = Scene.objects.filter(device_id=device_id)
        return Response(SceneSerializer(scenes, many=True).data)

    def post(self, request, device_id: int, scene_id: int):
        device = get_object_or_404(Device, pk=device_id)
        scene = get_object_or_404(Scene, pk=scene_id, device=device)
        try:
            payload = get_controller().apply_scene(device, scene, user=request.user)
        except ControlRejected as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response(payload)


class EventListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, device_id: int):
        get_object_or_404(Device, pk=device_id)
        limit = min(max(int(request.query_params.get("limit", 30)), 1), settings.CONTROL_EVENT_LIMIT)
        events = ControlEvent.objects.filter(device_id=device_id)[:limit]
        return Response(EventSerializer(events, many=True).data)


class CameraControlAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, device_id: int, action: str):
        device = get_object_or_404(Device, pk=device_id)
        runtime = get_camera_runtime()
        if action == "start":
            try:
                return Response(runtime.start(device), status=status.HTTP_202_ACCEPTED)
            except RuntimeError as exc:
                return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        if action == "stop":
            return Response(runtime.stop())
        raise Http404("Unknown camera action.")


class CameraSnapshotAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, device_id: int):
        get_object_or_404(Device, pk=device_id)
        snapshot = get_camera_runtime().snapshot()
        if snapshot is None:
            raise Http404("No camera preview is available.")
        return HttpResponse(snapshot, content_type="image/jpeg")


class CameraStreamView(LoginRequiredMixin, View):
    """Stream the latest in-memory JPEG frames as low-latency MJPEG."""

    def get(self, request, device_id: int):
        get_object_or_404(Device, pk=device_id)
        runtime = get_camera_runtime()

        async def generate_frames():
            last_version = -1
            while True:
                version, snapshot, running = await sync_to_async(
                    runtime.wait_for_snapshot,
                    thread_sensitive=False,
                )(
                    last_version,
                    1.0,
                )
                if snapshot is not None and version > last_version:
                    last_version = version
                    yield (
                        b"--frame\r\n"
                        b"Content-Type: image/jpeg\r\n"
                        + f"Content-Length: {len(snapshot)}\r\n\r\n".encode("ascii")
                        + snapshot
                        + b"\r\n"
                    )
                if not running:
                    break

        response = StreamingHttpResponse(
            generate_frames(),
            content_type="multipart/x-mixed-replace; boundary=frame",
        )
        response["Cache-Control"] = "no-store, no-cache, must-revalidate"
        response["X-Accel-Buffering"] = "no"
        return response
