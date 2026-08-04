# Smart Detect — Điều khiển LED Arduino bằng cử chỉ tay qua HC-05

Ứng dụng dùng webcam và MediaPipe để nhận diện bàn tay, sau đó điều khiển ba LED trên Arduino qua module Bluetooth Classic HC-05.

> HC-05 dùng Bluetooth Classic Serial Port Profile (SPP/RFCOMM), không phải BLE.

## Chức năng

- Nhận diện bàn tay từ webcam.
- Điều khiển ba LED theo ngón trỏ, giữa và áp út.
- Chớp đồng thời ba LED khi mở bốn ngón.
- Tắt cả ba LED khi mở năm ngón.
- Hiển thị trực tiếp trên camera: trạng thái LED, số ngón tay, cử chỉ và hướng dẫn thoát.
- Tự kết nối lại Bluetooth trong nền nếu đường truyền bị ngắt.

## Cấu trúc dự án

```text
.
├── arduino/
│   ├── led_controller/led_controller.ino   # Firmware chạy điều khiển LED
│   └── hc05_config/hc05_config.ino         # Firmware tạm để cấu hình AT cho HC-05
├── Pi_controler/
│   ├── src/
│   │   ├── main.py                          # Camera, nhận diện và giao tiếp Arduino
│   │   ├── vision/                          # MediaPipe Hand Landmarker
│   │   ├── services/                        # Chuyển cử chỉ thành trạng thái LED
│   │   └── communication/                   # Bluetooth RFCOMM
│   └── model/hand_landmarker.task
└── requirements.txt
```

## Phần cứng cần có

- Arduino Uno hoặc board tương thích 5 V.
- Module HC-05 dạng breakout.
- Ba LED và ba điện trở hạn dòng 220–330 Ω.
- Webcam.
- Máy tính Windows hoặc Raspberry Pi có Bluetooth Classic.

## Đấu nối phần cứng

### LED

| LED                     | Arduino |
| ----------------------- | ------- |
| LED 1 (qua điện trở) | D8      |
| LED 2 (qua điện trở) | D9      |
| LED 3 (qua điện trở) | D10     |
| Cực âm các LED       | GND     |

### HC-05 và Arduino

| HC-05   | Arduino  | Ghi chú                                                                                                     |
| ------- | -------- | ------------------------------------------------------------------------------------------------------------ |
| `VCC` | `5V`   | Chỉ áp dụng với board HC-05 có sẵn ổn áp. Module trần phải dùng đúng điện áp theo datasheet. |
| `GND` | `GND`  | Bắt buộc nối mass chung.                                                                                  |
| `TXD` | `D2`   | D2 là chân RX của`SoftwareSerial`.                                                                      |
| `RXD` | `D3`  | nối trực tiếp D3 vào RXD của HC-05.                                                                     |


Tóm lại, đường dữ liệu luôn đấu chéo:

```text
HC-05 TXD  ─────────────> Arduino D2 (RX)
Arduino D3 (TX) ────────> HC-05 RXD
Arduino GND ────────────> HC-05 GND
```

## 1. Cấu hình HC-05

Chỉ thực hiện phần này khi cấu hình lần đầu hoặc khi cần thay đổi tên, PIN, hay tốc độ UART.

### Đưa HC-05 vào AT mode

1. Nạp `arduino/hc05_config/hc05_config.ino` vào Arduino.
2. Ngắt nguồn HC-05.
3. Giữ nút nhỏ trên HC-05, hoặc nối `KEY/EN` lên 3.3 V.
4. Cấp nguồn lại khi vẫn giữ nút/KEY.
5. Đèn HC-05 phải nháy chậm, khoảng hai giây một lần. Đây là full AT mode.

### Gửi lệnh AT

Mở Serial Monitor bằng **cổng USB của Arduino** (ví dụ `COM3`), không dùng cổng Bluetooth như `COM10`.

Thiết lập Serial Monitor:

- Baud rate: `9600`
- Line ending: `CRLF` hoặc `Both NL & CR`

> Sketch `hc05_config.ino` giao tiếp USB với máy tính ở 9600 baud, nhưng giao tiếp từ Arduino sang HC-05 trong AT mode ở 38400 baud. Đây là đúng thiết kế.

Gửi từng lệnh và đợi `OK` sau mỗi lệnh:

```text
AT
AT+UART=9600,0,0
AT+UART?
AT+ROLE=0
AT+NAME=DetectHand
AT+PSWD=1234
AT+RESET
```

Kết quả của `AT+UART?` phải bao gồm:

```text
+UART:9600,0,0
```

Sau đó tắt nguồn HC-05, bỏ nút/KEY và cấp nguồn lại. Đèn phải nháy nhanh, cho biết module đã trở lại data mode.

## 2. Nạp firmware điều khiển LED

Sau khi cấu hình HC-05 xong, nạp `arduino/led_controller/led_controller.ino` vào Arduino.

Firmware này nhận lệnh dạng sau từ HC-05:

```text
LED:101
```

Trong đó `1` là bật và `0` là tắt. Arduino phản hồi bằng:

```text
OK:101
```

> Không để `hc05_config.ino` trên Arduino khi chạy ứng dụng chính; sketch đó chỉ là cầu nối phục vụ AT mode và không xử lý lệnh LED.

## 3. Cài đặt Python

Từ thư mục gốc của dự án:

### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### Raspberry Pi / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## 4. Ghép đôi Bluetooth và chọn cổng

### Windows

1. Ghép đôi với thiết bị `DetectHand` bằng PIN `1234`.
2. Tạo hoặc xác định cổng Bluetooth **Outgoing** trong Windows Bluetooth Settings.
3. Ví dụ cổng Bluetooth là `COM10`:

```powershell
$env:BLUETOOTH_SERIAL_PORT = "COM10"
$env:BLUETOOTH_SERIAL_BAUDRATE = "9600"
```

`COM10` là cổng Bluetooth dùng khi chạy ứng dụng, khác với `COM3` (cổng USB Arduino) dùng để cấu hình AT.

### Raspberry Pi

Ghép đôi bằng `bluetoothctl`, sau đó tạo cổng RFCOMM:

```bash
sudo rfcomm bind 0 AA:BB:CC:DD:EE:FF 1
```

Thay địa chỉ MAC bằng địa chỉ của HC-05. Ứng dụng sẽ dùng `/dev/rfcomm0` mặc định.

## 5. Chạy ứng dụng

```powershell
cd Pi_controler
python -m src.main
```

Khi chạy thành công, cửa sổ camera có tiêu đề `Hand Gesture LED Controller` sẽ hiển thị:

- `LED Status`: LED1, LED2 và LED3 đang ON/OFF.
- `Finger Count`: tổng số ngón được nhận diện.
- `Gesture`: cử chỉ hiện tại.
- `Press q to quit`: nhấn `q` để thoát.

Ví dụ log kết nối đúng:

```text
Connected to Arduino HC-05 on RFCOMM port COM10.
Arduino <- LED:000
```

## Quy tắc cử chỉ

| Cử chỉ                 | Kết quả                                                         |
| ------------------------ | ----------------------------------------------------------------- |
| Mở 4 ngón              | Cả ba LED chớp cùng lúc.                                      |
| Mở 5 ngón              | Tắt cả ba LED.                                                  |
| Các trường hợp khác | Ngón trỏ, giữa, áp út điều khiển lần lượt LED 1, 2, 3. |
| Không thấy tay         | Giữ trạng thái LED gần nhất.                                 |

## Biến môi trường

| Biến                         | Mặc định                                           | Ý nghĩa                                    |
| ----------------------------- | ----------------------------------------------------- | -------------------------------------------- |
| `CAMERA_INDEX`              | `0`                                                 | Chỉ số webcam.                             |
| `CAMERA_WIDTH`              | `640`                                               | Chiều rộng camera mong muốn.              |
| `CAMERA_HEIGHT`             | `480`                                               | Chiều cao camera mong muốn.                |
| `BLUETOOTH_SERIAL_PORT`     | `COM10` trên Windows, `/dev/rfcomm0` trên Linux | Cổng RFCOMM của HC-05.                     |
| `BLUETOOTH_SERIAL_BAUDRATE` | `9600`                                              | Tốc độ cổng serial khi chạy ứng dụng. |
| `SERIAL_TIMEOUT_SECONDS`    | `0.5`                                               | Thời gian chờ serial.                      |
| `BLINK_INTERVAL_SECONDS`    | `0.2`                                               | Chu kỳ chớp LED khi mở bốn ngón.        |
| `LOG_LEVEL`                 | `INFO`                                              | Mức log, ví dụ`DEBUG`.                  |

Ví dụ thay đổi camera:

```powershell
$env:CAMERA_INDEX = "1"
python -m src.main
```

## Khắc phục sự cố

### Gửi `AT` nhưng không nhận `OK`

Kiểm tra lần lượt:

1. Đang dùng cổng USB Arduino (`COM3` chẳng hạn), không phải Bluetooth `COM10`.
2. HC-05 nháy chậm, nghĩa là đang ở AT mode.
3. Serial Monitor dùng 9600 baud và `CRLF`.
4. Dây D2/D3 được nối chéo, GND chung và D3 có mạch giảm áp.

### Ứng dụng kết nối nhưng LED không thay đổi

1. HC-05 phải nháy nhanh, tức data mode.
2. Arduino phải chạy `led_controller.ino`.
3. HC-05 và firmware LED đều phải dùng 9600 baud.
4. Đóng Serial Monitor hoặc chương trình khác đang chiếm `COM10`.
5. Kiểm tra LED, điện trở và các chân D8, D9, D10.

### Có ký tự lạ trong phản hồi Bluetooth

Kiểm tra lại data-mode baud 9600 của HC-05, nguồn cấp ổn định, mạch giảm áp ở D3 và GND chung. Nếu LED vẫn phản hồi đúng cử chỉ, phần điều khiển vẫn đang hoạt động.

### Không mở được camera

Kiểm tra webcam không bị ứng dụng khác sử dụng. Thử đổi `CAMERA_INDEX`, ví dụ từ `0` sang `1`.

## Kiểm thử

Từ thư mục `Pi_controler`:

```powershell
python -m unittest discover -s tests -v
```

Các kiểm thử này mô phỏng cổng serial; không cần kết nối Arduino hoặc HC-05.
"# DetectHand_and_ControlLeds_byBluetooth" 
