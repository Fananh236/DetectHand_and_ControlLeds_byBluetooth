// Receives LED:xyz commands through an HC-05 Bluetooth Classic module.
// x, y and z are 0 (OFF) or 1 (ON), mapped to pins 8, 9 and 10.

#include <SoftwareSerial.h>
#include <string.h>

const byte LED_PINS[] = {8, 9, 10};
const byte LED_COUNT = sizeof(LED_PINS) / sizeof(LED_PINS[0]);

// Arduino RX <- HC-05 TX, Arduino TX -> (level shifter) -> HC-05 RX.
const byte HC05_RX_PIN = 2;
const byte HC05_TX_PIN = 3;
const long HC05_UART_BAUDRATE = 9600;

SoftwareSerial bluetoothSerial(HC05_RX_PIN, HC05_TX_PIN);

char commandBuffer[16];
byte commandLength = 0;

void setLedStates(const char* states) {
  for (byte index = 0; index < LED_COUNT; index++) {
    digitalWrite(LED_PINS[index], states[index] == '1' ? HIGH : LOW);
  }
}

void processCommand(const char* command, Stream& reply) {
  // The complete expected command is LED:xyz, for example LED:101.
  if (strlen(command) != 7 || strncmp(command, "LED:", 4) != 0) {
    reply.println("ERR:FORMAT");
    return;
  }

  for (byte index = 4; index < 7; index++) {
    if (command[index] != '0' && command[index] != '1') {
      reply.println("ERR:VALUE");
      return;
    }
  }

  setLedStates(command + 4);
  reply.print("OK:");
  reply.println(command + 4);
}

void setup() {
  for (byte index = 0; index < LED_COUNT; index++) {
    pinMode(LED_PINS[index], OUTPUT);
    digitalWrite(LED_PINS[index], LOW);
  }

  bluetoothSerial.begin(HC05_UART_BAUDRATE);
}

void loop() {
  while (bluetoothSerial.available() > 0) {
    char incoming = static_cast<char>(bluetoothSerial.read());

    if (incoming == '\r') {
      continue;
    }

    if (incoming == '\n') {
      commandBuffer[commandLength] = '\0';
      processCommand(commandBuffer, bluetoothSerial);
      commandLength = 0;
    } else if (commandLength < sizeof(commandBuffer) - 1) {
      commandBuffer[commandLength++] = incoming;
    } else {
      commandLength = 0;
      bluetoothSerial.println("ERR:TOO_LONG");
    }
  }
}
