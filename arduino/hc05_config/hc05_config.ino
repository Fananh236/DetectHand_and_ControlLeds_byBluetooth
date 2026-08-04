// USB-to-HC-05 AT-command bridge for configuring the Bluetooth module.
//
// Wiring is identical to the LED controller:
//   Arduino D2  <- HC-05 TXD
//   Arduino D3  -> 1k resistor -> HC-05 RXD, with 2k from RXD to GND
//   Arduino GND <-> HC-05 GND
//   Arduino 5V  -> HC-05 VCC (only for a breakout board with a regulator)
//
// Before reset/power-on, hold the HC-05 button or connect KEY/EN to 3.3V.
// A slow blink (roughly once every two seconds) indicates full AT mode.
// Open the Arduino Serial Monitor at 9600 baud, with "Both NL & CR" enabled.

#include <SoftwareSerial.h>

const byte HC05_RX_PIN = 2;
const byte HC05_TX_PIN = 3;
const long USB_SERIAL_BAUDRATE = 9600;
const long HC05_AT_BAUDRATE = 38400;

SoftwareSerial hc05Serial(HC05_RX_PIN, HC05_TX_PIN);

void setup() {
  Serial.begin(USB_SERIAL_BAUDRATE);
  hc05Serial.begin(HC05_AT_BAUDRATE);

  Serial.println("HC-05 AT bridge ready.");
  Serial.println("Send AT. Expected reply: OK");
}

void loop() {
  while (Serial.available() > 0) {
    hc05Serial.write(static_cast<byte>(Serial.read()));
  }

  while (hc05Serial.available() > 0) {
    Serial.write(static_cast<byte>(hc05Serial.read()));
  }
}
