(() => {
  const root = document.getElementById("dashboard");
  if (!root) return;
  const deviceId = root.dataset.deviceId;
  const apiBase = `/api/v1/devices/${deviceId}`;
  const toast = document.getElementById("toast");
  const state = { status: null, camera: null, socket: null };

  const csrfToken = () => document.cookie.split("; ").find((row) => row.startsWith("csrftoken="))?.split("=")[1] || "";
  const notify = (message, isError = false) => {
    toast.textContent = message; toast.hidden = false; toast.classList.toggle("is-error", isError);
    window.clearTimeout(notify.timeout); notify.timeout = window.setTimeout(() => { toast.hidden = true; }, 3600);
  };
  const request = async (url, options = {}) => {
    const response = await fetch(url, { ...options, headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken(), ...(options.headers || {}) } });
    const body = response.status === 204 ? null : await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(body.detail || "Không thể hoàn tất yêu cầu.");
    return body;
  };
  const modeHint = { manual: "Manual cho phép dashboard gửi lệnh trực tiếp.", gesture: "Gesture nhận lệnh từ camera sau khi xác thực khuôn mặt.", locked: "Locked chặn mọi lệnh điều khiển cho tới khi mở khoá." };
  const renderStatus = (status) => {
    if (!status) return; state.status = status;
    ["led1", "led2", "led3"].forEach((led) => {
      const isOn = Boolean(status.leds[led]); const card = document.querySelector(`[data-led-card="${led}"]`); const label = document.querySelector(`[data-led-label="${led}"]`); const button = document.querySelector(`[data-led="${led}"]`);
      card.classList.toggle("is-on", isOn); label.textContent = isOn ? "ON" : "OFF"; button.setAttribute("aria-pressed", String(isOn)); button.disabled = status.control_mode !== "manual";
    });
    document.getElementById("command-value").textContent = status.leds.command;
    document.getElementById("source-value").textContent = status.leds.last_source;
    document.getElementById("mode-title").textContent = status.control_mode[0].toUpperCase() + status.control_mode.slice(1);
    document.getElementById("mode-badge").textContent = status.control_mode;
    document.getElementById("mode-hint").textContent = modeHint[status.control_mode] || "";
    document.querySelectorAll("[data-mode]").forEach((button) => button.classList.toggle("is-active", button.dataset.mode === status.control_mode));
    const online = Boolean(status.bluetooth.connected); document.querySelector(".status-dot").classList.toggle("is-online", online); document.getElementById("connection-label").textContent = online ? "Bluetooth connected" : "Bluetooth reconnecting";
  };
  const renderVision = (vision) => {
    if (!vision) return; state.camera = vision;
    document.getElementById("camera-running").textContent = vision.running ? "Camera live" : "Camera idle";
    const faceConfidence = vision.face_confidence == null ? "" : ` · ${Number(vision.face_confidence).toFixed(1)}`;
    document.getElementById("face-status").textContent = `${vision.face_status || "Waiting"}${faceConfidence}`;
    document.getElementById("gesture-status").textContent = vision.gesture || "UNKNOWN";
    document.getElementById("finger-count").textContent = vision.finger_count ?? 0;
    document.getElementById("fps-value").textContent = Number(vision.fps || 0).toFixed(1);
    const preview = document.getElementById("camera-preview"); const placeholder = document.getElementById("camera-placeholder");
    if (vision.error) notify(vision.error, true);
    if (vision.running && preview.dataset.streaming !== "true") {
      preview.dataset.streaming = "true";
      preview.src = `${apiBase}/camera/stream/?at=${Date.now()}`;
      preview.hidden = false;
      placeholder.hidden = true;
    }
    if (!vision.running && preview.dataset.streaming === "true") {
      preview.removeAttribute("src");
      preview.dataset.streaming = "false";
      preview.hidden = true;
      placeholder.hidden = false;
    }
  };
  const renderEvents = (events) => {
    const list = document.getElementById("event-list"); list.innerHTML = "";
    events.forEach((event) => { const item = document.createElement("li"); const time = new Date(event.created_at).toLocaleString("vi-VN"); item.innerHTML = `<span class="event-time">${time}</span><strong>${event.event_type.replaceAll(".", " · ")}</strong><span class="event-source">${event.source}</span>`; list.append(item); });
    document.getElementById("event-count").textContent = `${events.length} event gần nhất`;
  };
  const load = async () => { try { const [status, events, health] = await Promise.all([request(`${apiBase}/`), request(`${apiBase}/events/`), request("/api/v1/health/")]); renderStatus(status); renderEvents(events); renderVision(health.camera); } catch (error) { notify(error.message, true); } };
  document.querySelectorAll("[data-led]").forEach((button) => button.addEventListener("click", async () => { const led = button.dataset.led; try { const payload = await request(`${apiBase}/leds/`, { method: "PATCH", body: JSON.stringify({ [led]: !state.status.leds[led] }) }); renderStatus(payload); } catch (error) { notify(error.message, true); } }));
  document.querySelectorAll("[data-mode]").forEach((button) => button.addEventListener("click", async () => { try { const payload = await request(`${apiBase}/control-mode/`, { method: "PUT", body: JSON.stringify({ mode: button.dataset.mode }) }); renderStatus(payload); } catch (error) { notify(error.message, true); } }));
  document.querySelectorAll("[data-scene-id]").forEach((button) => button.addEventListener("click", async () => { try { const payload = await request(`${apiBase}/scenes/${button.dataset.sceneId}/apply/`, { method: "POST", body: "{}" }); renderStatus(payload); } catch (error) { notify(error.message, true); } }));
  document.querySelectorAll("[data-camera-action]").forEach((button) => button.addEventListener("click", async () => { try { const vision = await request(`${apiBase}/camera/${button.dataset.cameraAction}/`, { method: "POST", body: "{}" }); renderVision(vision); } catch (error) { notify(error.message, true); } }));
  document.getElementById("refresh-button").addEventListener("click", load);
  const connectSocket = () => { const protocol = location.protocol === "https:" ? "wss" : "ws"; const socket = new WebSocket(`${protocol}://${location.host}/ws/devices/${deviceId}/`); state.socket = socket; socket.onmessage = ({ data }) => { const event = JSON.parse(data); if (event.type === "device.state_changed") renderStatus(event.payload); if (event.type === "vision.update") renderVision(event.payload); }; socket.onclose = () => window.setTimeout(connectSocket, 2200); };
  load(); connectSocket();
})();
