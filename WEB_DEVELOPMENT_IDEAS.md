# Định hướng phát triển Web cho DetectHand and Control LEDs by Bluetooth

Tài liệu này dùng để brainstorm và chọn hướng phát triển web từ hệ thống hiện có: nhận diện cử chỉ tay bằng webcam, xác thực khuôn mặt cục bộ, sau đó điều khiển 3 LED qua HC-05 và Arduino.

## Bản triển khai hiện có

Dashboard all-in-one đã được dựng trong `Pi_controler` bằng Django:

- `web_config/`: cấu hình Django, ASGI và WebSocket routing.
- `web/`: model SQLite, REST API, realtime consumer, dashboard, first-run setup và Django Admin.
- `web/services.py`: một đường điều khiển chung cho web, scene và gesture trước khi gửi Bluetooth.
- `web/vision_runtime.py`: camera worker nền, xác thực khuôn mặt, nhận diện cử chỉ và preview JPEG trong RAM.
- `manage.py migrate` tạo trạng thái thiết bị, scene `All On`/`All Off`; `/setup/` tạo tài khoản quản trị đầu tiên.

Thiết kế các app nhỏ hơn bên dưới vẫn phù hợp nếu project phát triển thành nhiều gateway hoặc nhiều nhóm cùng làm việc. Với một thiết bị, một Django app `web` giữ bản đầu tiên gọn và dễ demo.

## 1. Điểm xuất phát của project

Hiện tại project là một ứng dụng Python chạy trên máy chủ thiết bị (Windows hoặc Raspberry Pi):

```text
Webcam -> nhận diện tay / khuôn mặt -> Python app -> Bluetooth Classic HC-05 -> Arduino -> LED
```

Các phần đã có thể tái sử dụng:

- Nhận diện 8 cử chỉ tay bằng MediaPipe.
- Luật trạng thái LED độc lập (`LedService`).
- Chống gửi lệnh lặp, xác nhận cử chỉ và cooldown (`GestureService`).
- Giao tiếp serial Bluetooth không chặn camera (`BluetoothClient`).
- Xác thực chủ sở hữu bằng LBPH trên ảnh local.
- Firmware Arduino nhận lệnh đơn giản: `LED:xyz\n`.

Điểm quan trọng: HC-05 dùng **Bluetooth Classic SPP/RFCOMM**. Trình duyệt web không thể kết nối trực tiếp tới HC-05 bằng Web Bluetooth (Web Bluetooth dành cho BLE). Vì vậy web phải đi qua một **dịch vụ Python chạy gần thiết bị** để gửi lệnh xuống Arduino.

## 2. Mục tiêu web nên hướng tới

Một web dashboard tốt cho project này không chỉ là nút bật/tắt LED. Nó nên biến project thành một hệ thống IoT có thể demo, giám sát và mở rộng:

- Xem trạng thái 3 LED và kết nối Bluetooth theo thời gian thực.
- Bật/tắt từng LED hoặc chạy cảnh (scene) từ giao diện web.
- Xem cử chỉ được nhận diện, FPS, trạng thái xác thực khuôn mặt và lịch sử lệnh.
- Cho phép chuyển giữa điều khiển bằng cử chỉ và điều khiển thủ công.
- Chạy trên cùng mạng LAN trước; sau đó mới cân nhắc điều khiển từ Internet.
- Có nền tảng để mở rộng từ 3 LED sang relay, servo, quạt, cảm biến hoặc nhiều board Arduino.

## 3. Hướng khuyến nghị: Local gateway + Web dashboard

Đây là hướng phù hợp nhất cho MVP vì tận dụng gần như toàn bộ mã hiện tại và không buộc thay đổi phần cứng.

```text
                 ┌────────────────────────────┐
                 │ Web browser                 │
                 │ Dashboard React/Vue/HTML    │
                 └──────────────┬─────────────┘
                                │ HTTP + WebSocket
                 ┌──────────────▼─────────────┐
                 │ Django trên Pi/PC           │
                 │ REST API + Channels         │
                 ├───────────┬─────────────────┤
                 │           │
        Camera/AI │           │ Bluetooth serial
                 ▼           ▼
       Gesture engine       HC-05 -> Arduino -> LED
```

### Vì sao nên bắt đầu ở LAN

- Không cần cloud, domain, NAT, MQTT broker hay tài khoản ngoài.
- Độ trễ thấp, phù hợp thao tác điều khiển thiết bị.
- Ảnh khuôn mặt và stream camera có thể giữ trong mạng nội bộ.
- Dễ demo: mở dashboard bằng điện thoại/laptop cùng Wi-Fi.
- Khi kiến trúc API đã ổn, có thể thêm cloud sau mà không phải viết lại nghiệp vụ LED.

## 4. Kiến trúc phần mềm đề xuất

### 4.1. Tách ứng dụng hiện tại thành các lớp

`main.py` hiện vừa điều khiển camera, vẽ giao diện OpenCV, gọi nhận diện và gửi Bluetooth. Để phục vụ Django, nên đưa phần nghiệp vụ ra các service độc lập, sau đó gọi chúng từ Django views, REST API và background worker.

```text
Pi_controler/
  manage.py
  config/                      # Django settings, URL routing, ASGI/WSGI
  apps/
    devices/                   # Device, LED state, scene và API
    control/                   # ControllerService và các quy tắc mode
    events/                    # Event log, audit và WebSocket consumer
    vision/                    # Camera engine, nhận diện tay/khuôn mặt
    accounts/                  # User, quyền dashboard (khi cần)
  hardware/
    bluetooth_client.py        # HC-05 / serial
    arduino_gateway.py         # API hẹp: apply_led_state()
  core/
    led_service.py             # Giữ luật trạng thái LED
    gesture_service.py         # Giữ xác nhận/cooldown cử chỉ
  templates/                   # Django templates
  static/                      # CSS/JavaScript/ảnh giao diện
```

Nguyên tắc: Django view, DRF viewset và Channels consumer không được tự thao tác cổng Bluetooth. Mọi lệnh web và cử chỉ phải đi qua cùng một `ControllerService`; nhờ vậy trạng thái, nhật ký và luật ưu tiên luôn thống nhất.

### 4.2. Trạng thái trung tâm

Nên duy trì một `DeviceState` duy nhất trong bộ nhớ:

```json
{
  "device_id": "lab-led-01",
  "leds": {"led1": true, "led2": false, "led3": true},
  "bluetooth": {"connected": true, "port": "COM10"},
  "control_mode": "gesture",
  "face_authorized": true,
  "last_gesture": "VICTORY",
  "last_updated_at": "2026-08-10T08:30:00Z"
}
```

Mọi cập nhật phải:

1. Kiểm tra quyền và mode điều khiển.
2. Cập nhật `LedService`.
3. Gửi trạng thái mới qua `BluetoothClient`.
4. Ghi event.
5. Broadcast trạng thái mới qua WebSocket.

## 5. Giao diện dashboard MVP

Một giao diện một trang là đủ cho phiên bản đầu tiên.

### Khu vực chính

| Khu vực | Nội dung | Mục đích |
| --- | --- | --- |
| Header | Tên thiết bị, online/offline, người dùng | Biết nhanh hệ thống có sẵn sàng không |
| LED cards | LED1, LED2, LED3; switch ON/OFF | Điều khiển thủ công trực quan |
| Scene panel | All On, All Off, Demo sequence | Thao tác nhiều LED trong một lần |
| Control mode | Gesture / Manual / Locked | Tránh lệnh web và cử chỉ cạnh tranh nhau |
| Live status | Cử chỉ, số ngón, FPS, Bluetooth, face auth | Phục vụ demo và chẩn đoán |
| Event timeline | Ai/cái gì gửi lệnh, thời gian, kết quả | Dễ truy vết lỗi |
| Camera preview (tuỳ chọn) | Ảnh JPEG định kỳ hoặc video stream | Quan sát nhận diện từ xa trong LAN |

### Luồng UX khuyến nghị

1. Người dùng mở dashboard và thấy ngay LED/Bluetooth đang ở trạng thái nào.
2. Chọn `Manual` để điều khiển bằng switch; hệ thống hiện cảnh báo nếu Bluetooth mất kết nối.
3. Chọn `Gesture` để camera điều khiển. Các switch chuyển thành chỉ đọc hoặc yêu cầu xác nhận override.
4. Khi khuôn mặt chưa được xác thực, dashboard hiển thị `LOCKED` và không chấp nhận lệnh cử chỉ.
5. Lịch sử luôn ghi nguồn lệnh: `web`, `gesture`, `scene`, `system`.

## 6. Cách tổ chức Django và API đề xuất cho MVP

### Django stack khuyến nghị

- **Django**: web server, template, admin site, xác thực user, ORM và migration.
- **Django REST Framework (DRF)**: các endpoint JSON cho dashboard hoặc mobile app sau này.
- **Django Channels**: WebSocket để cập nhật LED, Bluetooth và gesture theo thời gian thực.
- **Redis**: channel layer của Channels ở production; môi trường local có thể bắt đầu bằng in-memory layer.
- **Django Templates + HTMX**: khuyến nghị cho MVP vì giao diện động nhưng không phải dựng một frontend React riêng.
- **SQLite**: database đầu tiên cho device, event và scene. Chuyển PostgreSQL khi triển khai nhiều người dùng/thiết bị.

`apps/devices` sở hữu model và API thiết bị. `apps/control` chỉ sở hữu nghiệp vụ điều khiển; view hoặc consumer không được gửi serial command trực tiếp. `apps/vision` chạy camera engine nền và phát event qua Channels.

### Model dữ liệu khởi đầu

| Model | Trường quan trọng | Vai trò |
| --- | --- | --- |
| `Device` | `name`, `serial_port`, `is_enabled` | Một gateway/Arduino có thể điều khiển |
| `LedState` | `device`, `led1`, `led2`, `led3`, `updated_at` | Trạng thái LED mới nhất |
| `ControlMode` | `device`, `mode`, `changed_by` | `gesture`, `manual`, `locked` |
| `Scene` | `name`, `led1`, `led2`, `led3` | Lệnh trạng thái tái sử dụng |
| `ControlEvent` | `device`, `source`, `event_type`, `payload`, `created_at` | Audit trail và timeline |

Đặt `unique=True` hoặc `OneToOneField` cho `LedState` và `ControlMode` theo mỗi `Device`, để một thiết bị luôn chỉ có một trạng thái hiện hành.

### REST API qua Django REST Framework

| Method | Endpoint | Mục đích |
| --- | --- | --- |
| `GET` | `/api/v1/devices/{id}/` | Đọc trạng thái đầy đủ của thiết bị |
| `GET` | `/api/v1/health/` | Kiểm tra Django, camera, Bluetooth |
| `PUT` | `/api/v1/devices/{id}/leds/` | Cập nhật đồng thời 3 LED |
| `PATCH` | `/api/v1/devices/{id}/leds/{led_id}/` | Bật/tắt một LED |
| `POST` | `/api/v1/devices/{id}/scenes/all-on/` | Bật toàn bộ LED |
| `POST` | `/api/v1/devices/{id}/scenes/all-off/` | Tắt toàn bộ LED |
| `PUT` | `/api/v1/devices/{id}/control-mode/` | Chuyển `manual`, `gesture`, `locked` |
| `GET` | `/api/v1/devices/{id}/events/` | Lấy lịch sử lệnh gần đây |
| `POST` | `/api/v1/devices/{id}/camera/start/` | Bắt đầu camera nếu chạy theo yêu cầu |
| `POST` | `/api/v1/devices/{id}/camera/stop/` | Dừng camera an toàn |

Ví dụ gửi lệnh toàn bộ LED:

```http
PUT /api/v1/leds
Content-Type: application/json

{
  "led1": true,
  "led2": false,
  "led3": true,
  "source": "web"
}
```

Phản hồi nên trả trạng thái thực tế đã được chấp nhận, không chỉ trả lại request:

```json
{
  "accepted": true,
  "command": "LED:101",
  "state": {
    "led1": true,
    "led2": false,
    "led3": true
  },
  "bluetooth_connected": true
}
```

### WebSocket realtime qua Django Channels

Endpoint: `/ws/devices/{id}/`

Server broadcast các event kiểu:

```json
{
  "type": "device.state_changed",
  "occurred_at": "2026-08-10T08:30:00Z",
  "source": "gesture",
  "payload": {
    "gesture": "OPEN_PALM",
    "leds": [true, true, true],
    "bluetooth_connected": true
  }
}
```

Các loại event nên có:

- `device.state_changed`
- `gesture.detected`
- `gesture.confirmed`
- `face.authentication_changed`
- `bluetooth.connected`
- `bluetooth.disconnected`
- `command.failed`
- `camera.status_changed`

Không nên gửi 30 frame/giây qua WebSocket cho MVP. Chỉ gửi sự kiện và trạng thái; camera preview cần một endpoint/stream riêng với tốc độ hạn chế.

## 7. Quy tắc điều khiển khi có cả web và gesture

Đây là quyết định sản phẩm quan trọng nhất. Nếu không có quy tắc, web có thể bật LED trong khi gesture vừa tắt LED.

### Phương án khuyến nghị

| Mode | Web dashboard | Gesture | Dùng khi |
| --- | --- | --- | --- |
| `gesture` | Chỉ xem hoặc yêu cầu takeover | Có hiệu lực sau face auth | Demo nhận diện cử chỉ |
| `manual` | Có hiệu lực | Không gửi lệnh | Điều khiển từ dashboard |
| `locked` | Không điều khiển | Không điều khiển | Bảo trì, lỗi hoặc an toàn |

Khi chuyển mode, hãy ghi event. Nếu web muốn takeover ở mode `gesture`, cần nút xác nhận và thông báo rõ rằng cử chỉ bị tạm dừng.

## 8. Lựa chọn frontend với Django

### Lựa chọn A — Django Templates + HTMX (khuyến nghị cho MVP)

Phù hợp nhất để hoàn thành dashboard nhanh với một codebase Django duy nhất.

- Django render trang chính, quản lý URL, đăng nhập và CSRF sẵn có.
- HTMX gọi các endpoint nhỏ để cập nhật LED cards, event timeline hoặc mode mà không phải viết SPA lớn.
- JavaScript thuần chỉ cần dùng cho WebSocket và biểu đồ/hiệu ứng đặc biệt.
- Ít cấu hình build, dễ chạy trên Raspberry Pi hơn một hệ frontend/backend tách rời.

### Lựa chọn B — React + Vite + TypeScript

Phù hợp nếu mục tiêu là portfolio, đồ án hoặc muốn tiếp tục mở rộng.

- Component hoá LED card, scene, biểu đồ event.
- Quản lý WebSocket và state dễ hơn.
- Có thể thêm xác thực, đa ngôn ngữ, dashboard nhiều thiết bị.
- Dùng Tailwind CSS hoặc Material UI để làm nhanh.

### Lựa chọn C — HTML/CSS/JavaScript thuần trong Django templates

Phù hợp cho demo học phần cần hoàn thành nhanh.

- Ít công cụ build.
- Django có thể phục vụ trực tiếp static files trong môi trường phát triển.
- Dễ hiểu, nhưng sẽ khó bảo trì khi tăng số màn hình/tính năng.

### Lựa chọn D — Streamlit

Phù hợp bảng giám sát nội bộ, không phải web sản phẩm.

- Rất nhanh để dựng dashboard Python.
- Không phải lựa chọn tốt nếu cần UI chuyên nghiệp, realtime phức tạp hoặc mobile-first.

Khuyến nghị thực tế: bắt đầu bằng **Django Templates + HTMX + Channels**. Khi dashboard đã có nhiều màn hình độc lập hoặc cần mobile app/frontend team riêng, giữ DRF và thay UI bằng React mà không cần đổi service điều khiển.

## 9. Lựa chọn backend và lưu trữ

### Backend

Django phù hợp vì:

- Cùng Python với engine nhận diện hiện có.
- Có ORM, migration, Django Admin và xác thực user sẵn có.
- DRF tạo API có validation, permission và browsable API rõ ràng.
- Django Channels bổ sung WebSocket; ASGI phù hợp cho dashboard realtime.
- Dễ bắt đầu với SQLite, sau đó đổi PostgreSQL mà ít ảnh hưởng code nghiệp vụ.

### Lưu trữ theo giai đoạn

| Giai đoạn | Lưu trữ | Dữ liệu |
| --- | --- | --- |
| MVP | Bộ nhớ + JSON log xoay vòng | Trạng thái hiện tại, 100 event gần nhất |
| V1 | SQLite | Event, scene, thiết bị, người dùng local |
| Cloud | PostgreSQL | Nhiều user/thiết bị, audit và báo cáo |

Không nên lưu ảnh khuôn mặt hay video mặc định. Nếu thật sự cần lưu để debug, phải có consent, thời gian xoá rõ ràng và quyền truy cập chặt chẽ.

## 10. Camera trên web: ba mức độ triển khai

### Mức 1 — Không stream camera (khuyến nghị cho MVP)

Dashboard chỉ hiển thị trạng thái nhận diện: gesture, face auth, FPS. Đây là cách đơn giản, riêng tư và ít tải CPU nhất.

### Mức 2 — Ảnh snapshot định kỳ

API trả JPEG mới nhất, frontend cập nhật 1–3 ảnh/giây. Đủ để demo, dễ hơn video streaming.

### Mức 3 — Video stream/WebRTC

Chỉ nên làm khi thật sự cần giám sát từ xa.

- MJPEG dễ triển khai nhưng tốn băng thông.
- WebRTC có độ trễ tốt hơn nhưng cần signalling và phức tạp hơn nhiều.
- Cần xem xét kỹ riêng tư vì camera và xác thực khuôn mặt đang hoạt động.

## 11. Bảo mật và quyền riêng tư

### Tối thiểu cho dashboard LAN

- Chỉ bind server vào mạng tin cậy; không expose cổng trực tiếp ra Internet.
- Có mật khẩu quản trị hoặc API key qua biến môi trường.
- Dùng CORS allowlist, không để `*` trong môi trường thật.
- Validate mọi LED request; không cho client gửi raw serial command.
- Giới hạn tốc độ API để tránh spam Bluetooth.
- Ghi log nguồn lệnh, không ghi thông tin nhạy cảm.

### Dữ liệu khuôn mặt

- Ảnh tham chiếu ở `Pi_controler/data` là dữ liệu nhạy cảm.
- `.gitignore` hiện không bao phủ đúng thư mục này; cần đổi thành `Pi_controler/data/*` và giữ lại `Pi_controler/data/.gitkeep` nếu cần.
- Không đưa ảnh vào thư mục frontend/public hoặc API static.
- Nếu tạo tính năng đăng nhập web, không nên dùng lại LBPH của camera như một cơ chế password. Web login nên dùng tài khoản/password được hash hoặc giải pháp SSO riêng.

### Khi đưa lên Internet

Không mở port Django trực tiếp ra Internet. Cần reverse proxy HTTPS, xác thực mạnh, quản lý secret, audit log và tốt nhất là VPN/Tailscale hoặc một gateway cloud được thiết kế riêng.

## 12. Các hướng phát triển sản phẩm

### Hướng 1 — Smart-room / IoT dashboard

Mở rộng 3 LED thành đèn, relay, quạt, rèm, servo hoặc ổ cắm thông minh. Cử chỉ là một cách điều khiển; web là control center.

Tính năng tiếp theo:

- Scene: `Study`, `Night`, `Presentation`, `All Off`.
- Lịch bật/tắt.
- Sensor nhiệt độ/độ ẩm/chuyển động.
- Biểu đồ trạng thái và mức sử dụng.

### Hướng 2 — Dashboard demo AI/Computer Vision

Tập trung vào trực quan hoá cử chỉ:

- Bảng thống kê mỗi cử chỉ theo ngày.
- Độ tin cậy, FPS, lỗi camera.
- Giao diện so sánh gesture thô và gesture đã xác nhận.
- Chế độ ghi lại event phục vụ báo cáo đồ án.

### Hướng 3 — Nhiều thiết bị / phòng lab

Mỗi Raspberry Pi là một gateway và được đăng ký như một thiết bị.

```text
Web dashboard -> API/Message broker -> Gateway Pi A -> Arduino A
                               └────> Gateway Pi B -> Arduino B
```

Khi đó nên dùng MQTT hoặc WebSocket gateway và định danh rõ `device_id`.

### Hướng 4 — Accessibility / touchless control

Tập trung vào giao diện không chạm cho người dùng có nhu cầu hỗ trợ vận động.

- Profile cử chỉ cá nhân.
- Cỡ chữ lớn, màu tương phản cao.
- Feedback âm thanh.
- Emergency stop cố định trên web và phần cứng.

Hướng này có ý nghĩa cao nhưng yêu cầu kiểm thử UX và an toàn kỹ hơn.

## 13. Lộ trình triển khai đề xuất

### Phase 0 — Chuẩn bị codebase (1–2 ngày)

- Chọn một implementation Bluetooth duy nhất; app hiện dùng `BluetoothClient`.
- Xoá hoặc đánh dấu legacy cho `arduino_controller.py` và `config.py` nếu không còn dùng.
- Bổ sung test cho `BluetoothClient`, `Settings` và `ControllerService` mới.
- Sửa README: 18 test thay vì 13; cập nhật hướng dẫn lint.
- Sửa `.gitignore` cho dữ liệu khuôn mặt.

### Phase 1 — Django foundation và API local (2–3 ngày)

- Khởi tạo Django project, các app `devices`, `control`, `events`, `vision`.
- Thêm Django REST Framework và Django Channels.
- Tạo migration cho `Device`, `LedState`, `ControlMode`, `ControlEvent`.
- Tạo `ControllerService` dùng chung cho web và gesture.
- Làm `GET /device`, `PUT /leds`, `POST /all-on`, `POST /all-off`.
- Thêm WebSocket group theo từng device.
- Test API bằng DRF browsable API, Postman hoặc curl trước.

Tiêu chí hoàn thành: lệnh HTTP điều khiển Arduino thật và dashboard client nhận trạng thái Bluetooth realtime.

### Phase 2 — Dashboard MVP (3–5 ngày)

- Làm Django templates, LED cards, scene, control mode, connection status.
- Dùng HTMX cho thao tác nhanh và Channels cho trạng thái realtime.
- Xử lý WebSocket reconnect ở JavaScript client.
- Có event timeline.
- Làm responsive cho điện thoại.

Tiêu chí hoàn thành: người dùng cùng Wi-Fi có thể điều khiển hệ thống ổn định từ điện thoại.

### Phase 3 — Tích hợp gesture/camera (3–5 ngày)

- Chạy camera engine nền cùng API.
- Broadcast status gesture, face auth và FPS.
- Thêm quy tắc chuyển `manual`/`gesture`/`locked`.
- Có snapshot camera nếu cần demo.

Tiêu chí hoàn thành: dashboard phản ánh lệnh cử chỉ trong dưới một giây và không có xung đột với điều khiển manual.

### Phase 4 — Hoàn thiện và mở rộng

- Đăng nhập dashboard.
- SQLite và lịch sử event.
- Scene tự tạo, schedule.
- Docker Compose / deployment Raspberry Pi.
- MQTT/multi-device hoặc remote access an toàn.

## 14. Bộ test nên thêm khi có web

| Nhóm | Ví dụ kiểm thử |
| --- | --- |
| API | Request LED không hợp lệ trả 422; LED hợp lệ gọi gateway đúng một lần |
| Quyền | Không có token không thể gửi lệnh |
| Mode | Ở `gesture`, manual command bị từ chối hoặc yêu cầu takeover |
| Realtime | WebSocket nhận `state_changed` sau command |
| Bluetooth | Lệnh khi mất kết nối được giữ và gửi lại khi kết nối lại |
| Concurrency | Lệnh web và cử chỉ cùng lúc vẫn cho trạng thái xác định |
| Privacy | Không endpoint nào trả ảnh tham chiếu khuôn mặt |
| E2E | Bấm switch web -> Arduino nhận `LED:xyz` -> status đổi lại |

## 15. Các quyết định cần chốt trước khi code

1. Dashboard chỉ dùng trong LAN hay sẽ truy cập từ Internet?
2. Có cần video camera trên web, hay chỉ cần trạng thái recognition?
3. Khi web và gesture cùng hoạt động, mode ưu tiên nào là mong muốn?
4. Web cần một người quản trị hay nhiều user/role?
5. Project hướng đến demo đồ án, smart home hay hệ thống nhiều thiết bị?
6. Có giữ HC-05 hay chuyển phần cứng về ESP32 Wi-Fi/BLE ở giai đoạn sau?
7. Cần chạy gateway trên Windows hiện tại hay Raspberry Pi độc lập?

## 16. Khuyến nghị chốt cho bản đầu tiên

Nên bắt đầu bằng **Django + Django REST Framework + Django Channels + Django Templates/HTMX trên LAN**, không stream camera, không cloud và chỉ một gateway Raspberry Pi/PC. Giữ cử chỉ làm mode điều khiển riêng, thêm `manual` mode cho dashboard, và để mọi lệnh đi qua cùng `ControllerService`.

Đây là phạm vi vừa đủ để tạo một sản phẩm web có giá trị demo rõ ràng, an toàn hơn việc điều khiển HC-05 trực tiếp, đồng thời vẫn mở rộng được sang IoT dashboard hoặc multi-device sau này.
