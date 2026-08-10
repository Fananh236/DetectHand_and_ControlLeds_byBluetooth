# Điều khiển 3 LED bằng nhận diện cử chỉ tay và HC-05

Ứng dụng Python nhận diện cử chỉ tay từ webcam bằng OpenCV và MediaPipe Hand Landmarker. Mỗi cử chỉ được xác nhận ổn định trước khi gửi trạng thái LED qua Bluetooth Classic HC-05 đến Arduino Uno.

> HC-05 dùng Bluetooth Classic Serial Port Profile (SPP/RFCOMM), không phải BLE.

## Trạng thái dự án

Đã hoàn thành kiểm thử chức năng: camera nhận diện cử chỉ, kết nối HC-05 qua cổng Bluetooth, và điều khiển ba LED trên Arduino. Bộ kiểm thử tự động hiện có **13 test đều đạt**.

```text
Ran 13 tests
OK
```

## Chức năng

- Nhận diện 8 cử chỉ tay từ 21 MediaPipe landmarks.
- Duy trì trạng thái riêng của LED1, LED2 và LED3.
- Xác nhận cử chỉ trong tối thiểu 0.5 giây **hoặc** 10 frame liên tiếp.
- Chống gửi lệnh lặp: cử chỉ đã kích hoạt được khóa đến khi tay đổi cử chỉ; cooldown mặc định là 1 giây.
- Bluetooth không làm chậm camera; khi mất kết nối, ứng dụng thử lại sau mỗi 5 giây.
- Chỉ mở điều khiển cử chỉ sau khi khuôn mặt khớp với ảnh chủ sở hữu trong `Pi_controler/data`.
- UI camera hiển thị cử chỉ, trạng thái LED, Bluetooth, số ngón tay, FPS và hướng dẫn thoát.
- Chạy trên Windows hoặc Raspberry Pi 4 với Python 3.10+.

## Kiến trúc

```text
Webcam
  │
  ▼
HandDetector ──► GestureClassifier ──► GestureService ──► LedService
                                                                  │
                                                                  ▼
                                                    BluetoothClient (HC-05)
                                                                  │
                                                                  ▼
                                                            Arduino Uno
                                                                  │
                                                                  ▼
                                                              3 LED
```

- `HandDetector`: chạy MediaPipe Hand Landmarker và vẽ skeleton bàn tay.
- `GestureClassifier`: biến landmarks thành enum cử chỉ.
- `GestureService`: xác nhận độ ổn định, cooldown và chống kích hoạt lặp.
- `LedService`: lưu trạng thái LED, chỉ thay đổi LED được cử chỉ yêu cầu.
- `BluetoothClient`: gửi `LED:xyz\n` không đồng bộ và tự kết nối lại HC-05.

## Cấu trúc thư mục

```text
DetectHand_and_ControlLeds_byBle/
├── arduino/
│   ├── led_controller/led_controller.ino
│   └── hc05_config/hc05_config.ino
├── Pi_controler/
│   ├── model/hand_landmarker.task
│   ├── src/
│   │   ├── main.py
│   │   ├── config/settings.py
│   │   ├── communication/bluetooth_client.py
│   │   ├── services/gesture_service.py
│   │   ├── services/led_service.py
│   │   └── vision/
│   │       ├── hand_detector.py
│   │       └── gesture_classifier.py
│   └── tests/
├── requirements.txt
└── README.md
```

## Cử chỉ và trạng thái LED

| Cử chỉ          | Ý nghĩa                      | Kết quả                                |
| ----------------- | ------------------------------ | ---------------------------------------- |
| `THUMBS_UP`     | 👍                             | Bật LED1, giữ LED2 và LED3.           |
| `THUMBS_DOWN`   | 👎                             | Tắt LED1, giữ LED2 và LED3.           |
| `VICTORY`       | ✌️                           | Bật LED2, giữ LED1 và LED3.           |
| `OK`            | 👌                             | Tắt LED2, giữ LED1 và LED3.           |
| `ROCK`          | 🤘 hoặc 🤟                    | Bật LED3, giữ LED1 và LED2.           |
| `THREE_FINGERS` | Mở ngón trỏ, giữa, áp út | Tắt LED3, giữ LED1 và LED2.           |
| `OPEN_PALM`     | 🖐                             | Bật cả ba LED:`LED:111`.<br /><br /> |
| `FIST`          | ✊                             | Tắt cả ba LED:`LED:000`.             |

Ví dụ: LED1 đang ON, sau đó nhận `VICTORY`, trạng thái trở thành LED1=ON, LED2=ON, LED3=OFF và lệnh gửi đi là `LED:110`.

## Phần cứng

- Arduino Uno hoặc board tương thích 5 V.
- HC-05 dạng breakout.
- Ba LED và điện trở 220–330 Ω.
- Điện trở 1 kΩ và 2 kΩ cho mạch giảm áp logic.
- Webcam.

### Kết nối LED

| LED                    | Arduino |
| ---------------------- | ------- |
| LED1 (qua điện trở) | D8      |
| LED2 (qua điện trở) | D9      |
| LED3 (qua điện trở) | D10     |
| Cực âm LED           | GND     |

### Kết nối HC-05

| HC-05   | Arduino                    | Ghi chú                                        |
| ------- | -------------------------- | ----------------------------------------------- |
| `VCC` | `5V`                     | Chỉ dùng 5 V nếu HC-05 breakout có ổn áp. |
| `GND` | `GND`                    | Bắt buộc nối chung mass.                     |
| `TXD` | `D2`                     | Arduino RX của`SoftwareSerial`.              |
| `RXD` | `D3` qua mạch giảm áp | RXD HC-05 chỉ nhận mức logic 3.3 V.          |

```text
HC-05 TXD  -----------------> Arduino D2

Arduino D3 -- 1kΩ --+-------> HC-05 RXD
                    |
                   2kΩ
                    |
Arduino GND --------+
```

## Cấu hình HC-05 lần đầu

Bỏ qua mục này nếu HC-05 đã chạy data mode 9600 baud và đã ghép đôi được.

1. Nạp `arduino/hc05_config/hc05_config.ino` vào Arduino.
2. Ngắt nguồn HC-05, giữ nút nhỏ của module hoặc nối `KEY/EN` lên 3.3 V, rồi cấp nguồn lại.
3. Đèn HC-05 phải nháy chậm (khoảng hai giây một lần): full AT mode.
4. Mở Serial Monitor bằng **cổng USB Arduino** (ví dụ `COM3`), không dùng Bluetooth `COM10`.
5. Chọn Serial Monitor: `9600 baud`, `CRLF` hoặc `Both NL & CR`.
6. Gửi từng lệnh và đợi `OK`:

```text
AT
AT+UART=9600,0,0
AT+UART?
AT+ROLE=0
AT+NAME=DetectHand
AT+PSWD=1234
AT+RESET
```

`AT+UART?` phải trả về `+UART:9600,0,0`.

7. Tắt nguồn, bỏ nút/KEY, cấp nguồn lại. Đèn phải nháy nhanh: data mode.
8. Nạp **`arduino/led_controller/led_controller.ino`** vào Arduino. Không để `hc05_config.ino` trên Arduino khi chạy ứng dụng chính.

Trong AT mode, sketch bridge nói với HC-05 ở 38400 baud. Trong data mode, firmware LED và HC-05 đều dùng 9600 baud.

## Cài đặt

### Windows

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Để chạy lint, coverage và toàn bộ kiểm thử khi phát triển, thay lệnh cuối bằng:

```powershell
python -m pip install -r requirements-dev.txt
```

> Xác thực khuôn mặt dùng `opencv-contrib-python`. Nếu trước đây đã cài `opencv-python`, hãy gỡ nó trước để tránh hai gói cùng cung cấp module `cv2`:

```powershell
python -m pip uninstall opencv-python
python -m pip install -r requirements.txt
```

### Raspberry Pi 4 / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Ghép đôi Bluetooth

### Windows

1. Ghép đôi `DetectHand` bằng PIN `1234`.
2. Xác định cổng Bluetooth **Outgoing** trong Bluetooth Settings, ví dụ `COM10`.
3. Đặt cổng trước khi chạy nếu không dùng giá trị mặc định:

```powershell
$env:BLUETOOTH_SERIAL_PORT = "COM10"
$env:BLUETOOTH_SERIAL_BAUDRATE = "9600"
```

`COM10` là cổng Bluetooth khi chạy ứng dụng; `COM3` là cổng USB Arduino chỉ dùng để cấu hình AT.

### Raspberry Pi

Ghép đôi HC-05 qua `bluetoothctl`, sau đó tạo RFCOMM (kênh SPP mặc định là 1):

```bash
sudo rfcomm bind 0 AA:BB:CC:DD:EE:FF 1
```

Thay địa chỉ MAC bằng HC-05 của bạn. Ứng dụng dùng `/dev/rfcomm0` mặc định.

## Chạy ứng dụng

```powershell
cd Pi_controler
python -m src.main
```

Trên cửa sổ camera sẽ có:

```text
Gesture: VICTORY
Finger Count: 2
L1: ON
L2: ON
L3: OFF
Bluetooth: CONNECTED
FPS: 28.4
Press Q to exit
```

Nhấn `Q` để thoát.

## Cấu hình bằng biến môi trường

| Biến                                    | Mặc định                  | Mô tả                                                      |
| ---------------------------------------- | ---------------------------- | ------------------------------------------------------------ |
| `CAMERA_INDEX`                         | `0`                        | Chỉ số webcam.                                             |
| `CAMERA_WIDTH`, `CAMERA_HEIGHT`      | `640`, `480`             | Độ phân giải camera mong muốn.                          |
| `CAMERA_FPS`                          | `30`                     | FPS webcam yêu cầu; đặt `60` nếu camera hỗ trợ.        |
| `BLUETOOTH_SERIAL_PORT`                | `COM10` / `/dev/rfcomm0` | Cổng HC-05. Đặt rỗng để chạy camera không Bluetooth. |
| `BLUETOOTH_SERIAL_BAUDRATE`            | `9600`                     | Baud data mode.                                              |
| `SERIAL_TIMEOUT_SECONDS`               | `0.5`                      | Timeout đọc/ghi serial.                                    |
| `BLUETOOTH_RECONNECT_INTERVAL_SECONDS` | `5.0`                      | Chu kỳ thử kết nối lại HC-05.                           |
| `GESTURE_CONFIRMATION_SECONDS`         | `0.5`                      | Thời gian xác nhận cử chỉ.                              |
| `GESTURE_CONFIRMATION_FRAMES`          | `10`                       | Số frame liên tiếp để xác nhận cử chỉ.              |
| `GESTURE_COOLDOWN_SECONDS`             | `1.0`                      | Thời gian khóa sau một lệnh.                             |
| `FACE_AUTH_ENABLED`                    | `true`                     | Bật xác thực khuôn mặt trước khi nhận diện tay. Chỉ tắt khi phát triển/debug. |
| `FACE_AUTH_THRESHOLD`                  | `75.0`                     | Ngưỡng LBPH; nhỏ hơn nghiêm ngặt hơn. Tăng dần nếu chính chủ bị từ chối. |
| `FACE_AUTH_CHECK_INTERVAL_FRAMES`      | `5`                        | Số frame giữa hai lần so khớp khuôn mặt để giảm tải CPU. |
| `LOG_LEVEL`                            | `INFO`                     | Mức log, ví dụ`DEBUG`.                                  |

Ví dụ dùng camera số 1:

```powershell
$env:CAMERA_INDEX = "1"
python -m src.main
```

## Ví dụ log

```text
2026-08-04 16:10:20,005 - INFO - src.communication.bluetooth_client - Connected to Arduino HC-05 on RFCOMM port COM10.
2026-08-04 16:10:21,018 - INFO - src.main - Confirmed gesture THUMBS_UP; scheduling LED:100.
2026-08-04 16:10:21,019 - INFO - src.communication.bluetooth_client - Arduino <- LED:100
2026-08-04 16:10:22,612 - INFO - src.main - Confirmed gesture VICTORY; scheduling LED:110.
```

## Kiểm thử tự động

Từ thư mục `Pi_controler`:

```powershell
python -m unittest discover -s tests -v
```

Các test dùng landmarks giả và serial mock, không cần webcam, Arduino hay HC-05:

- `test_gesture_classifier.py`: toàn bộ cử chỉ hỗ trợ và trường hợp không hợp lệ.
- `test_led_service.py`: trạng thái LED bền vững và giao thức `LED:xyz`.
- `test_gesture_service.py`: xác nhận theo frame/thời gian, latch và cooldown.
- `test_arduino_controller.py`: tương thích với driver serial cũ.

## Kiểm thử phần cứng đã thực hiện

Checklist trước khi bàn giao:

- [X] HC-05 được cấu hình data mode `9600,0,0`.
- [X] HC-05 ghép đôi Bluetooth và chạy qua cổng RFCOMM Windows, ví dụ `COM10`.
- [X] Arduino nhận lệnh `LED:xyz` và điều khiển ba LED.
- [X] Cửa sổ camera hiển thị landmark, cử chỉ, trạng thái LED, Bluetooth, số ngón và FPS.
- [X] Nhấn `Q` đóng ứng dụng và giải phóng camera/cổng Bluetooth.

Khi triển khai trên máy khác, chỉ cần kiểm tra lại số cổng Bluetooth Outgoing và đặt `BLUETOOTH_SERIAL_PORT` tương ứng.

## Khắc phục sự cố

### Không nhận được `OK` khi gửi `AT`

- Dùng `COM3` (USB Arduino), không phải `COM10` (Bluetooth).
- HC-05 phải nháy chậm; nếu nháy nhanh, nó đang ở data mode.
- Serial Monitor đặt 9600 và CRLF.
- Kiểm tra D2/D3 đấu chéo, điện trở giảm áp và GND chung.

### Bluetooth hiển thị `DISCONNECTED`

- Kiểm tra HC-05 nháy nhanh và đã ghép đôi.
- Kiểm tra đúng cổng Outgoing `COMx`.
- Đóng Serial Monitor hoặc ứng dụng khác đang giữ cổng Bluetooth.
- Ứng dụng sẽ tự thử lại sau 5 giây; có thể thay đổi bằng biến môi trường.

### Cử chỉ bị nhận nhầm

- Để toàn bộ bàn tay trong khung hình, lòng bàn tay hướng tương đối về camera.
- Giữ cử chỉ ổn định ít nhất 0.5 giây hoặc 10 frame.
- Tránh ngược sáng; thử tăng độ sáng và đặt tay tách khỏi nền.
- Các cử chỉ phức tạp như `OK` và `ROCK` cần đầu ngón rõ ràng, không bị che

## Web dashboard Django (all-in-one)

Project có sẵn dashboard Django chạy cùng máy/Raspberry Pi đang nối webcam,
HC-05 và Arduino. Browser không kết nối trực tiếp với HC-05; Django là gateway
an toàn nhận lệnh web rồi gửi trạng thái `LED:xyz` qua Python Bluetooth client.

Dashboard bao gồm:

- Đăng nhập và màn hình tạo tài khoản quản trị ở lần chạy đầu tiên.
- Điều khiển 3 LED, scene `All On`/`All Off` và Django Admin.
- Ba mode `manual`, `gesture`, `locked` để tránh xung đột lệnh.
- REST API, WebSocket realtime, trạng thái Bluetooth/camera và event timeline.
- Camera preview chỉ giữ trong RAM thiết bị, không lưu ảnh/video.

### Huấn luyện model khuôn mặt

Đặt ảnh chính diện của cùng một chủ sở hữu trong `Pi_controler/data`, sau đó
chạy lệnh sau từ thư mục `Pi_controler`:

```powershell
python manage.py train_face_model --force
```

Model LBPH được lưu tại `Pi_controler/model/face_authenticator.yml` và được ứng
dụng tải trực tiếp khi bấm **Start camera**. File model được giữ local và không
đưa vào Git vì là dữ liệu sinh trắc học dẫn xuất. Ảnh không phát hiện được
khuôn mặt sẽ bị bỏ qua kèm cảnh báo; nên dùng ảnh chính diện, đủ sáng và không
bị che khuất.

### Chạy dashboard

Từ thư mục gốc project sau khi cài dependencies:

```powershell
.\.venv\Scripts\Activate.ps1
cd Pi_controler
python manage.py migrate
python manage.py runserver
```

Mở `http://127.0.0.1:8000`. Lần đầu hệ thống chuyển tới `/setup/` để tạo tài
khoản quản trị; không có mật khẩu mặc định. Sau khi đăng nhập, dùng nút
**Start camera** khi muốn kích hoạt nhận diện cử chỉ.

Để mở dashboard cho điện thoại/laptop cùng Wi-Fi, đặt IP LAN của máy gateway
vào allowlist rồi chạy server trên mọi network interface:

```powershell
$env:DJANGO_ALLOWED_HOSTS = "localhost,127.0.0.1,192.168.1.20"
$env:DJANGO_SECRET_KEY = "thay-bang-mot-chuoi-bi-mat-dai-va-ngau-nhien"
cd Pi_controler
python manage.py runserver 0.0.0.0:8000
```

Thay `192.168.1.20` bằng IP của máy đang chạy Django. Không mở cổng này trực
tiếp ra Internet; dùng VPN hoặc reverse proxy HTTPS cùng xác thực phù hợp nếu
cần truy cập từ xa.

### Kiểm thử dashboard

```powershell
cd Pi_controler
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test web
python -m unittest discover -s tests -v
```
