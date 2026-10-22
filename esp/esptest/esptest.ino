// esptest.ino - servo test, separate from the main sketch (open this file on its own).
//
// No Serial Monitor needed, but if you open one (115200 baud) it prints every
// move, e.g. "right+up  X 1950  Y 1950". After the upload the ESP32 tilts the plate to the
// extreme of each of the 8 directions, going back to flat in between:
//   flat -> right -> flat -> right+up -> flat -> up -> flat -> ... -> right+down -> flat
// and then starts again, forever. To stop it, unplug the ESP32 or upload esp/esp.ino.
//
// Every move is smooth (slow at the start and end), and it holds each position
// for a moment so you can look at it or measure it.
//
// Nothing ever goes outside PULSE_MIN..PULSE_MAX. If the plate touches the frame
// at an extreme, narrow them here and in esp.ino.

#include <ESP32Servo.h>

// Same as esp/esp.ino.
const int SERVO_X_PIN = 2;
const int SERVO_Y_PIN = 4;
const int PULSE_CENTER_X = 1400;
const int PULSE_CENTER_Y = 1400;
const int PULSE_MIN = 1150;
const int PULSE_MAX = 1950;

const int MOVE_MS = 1000;  // time for one move
const int HOLD_MS = 1000;  // time to stay at each position

// The 8 directions: -1 = PULSE_MIN, 0 = centre, +1 = PULSE_MAX, for X and Y.
const int DIRECTIONS[8][2] = {
  {+1, 0}, {+1, +1}, {0, +1}, {-1, +1},
  {-1, 0}, {-1, -1}, {0, -1}, {+1, -1},
};
const char *NAMES[8] = {
  "right", "right+up", "up", "left+up",
  "left", "left+down", "down", "right+down",
};

Servo servoX;
Servo servoY;

// Where the servos are now, in microseconds.
float nowX = PULSE_CENTER_X;
float nowY = PULSE_CENTER_Y;

void setup() {
  Serial.begin(115200);
  servoX.attach(SERVO_X_PIN, PULSE_MIN, PULSE_MAX);
  servoY.attach(SERVO_Y_PIN, PULSE_MIN, PULSE_MAX);
  servoX.writeMicroseconds(PULSE_CENTER_X);
  servoY.writeMicroseconds(PULSE_CENTER_Y);
  Serial.println("flat  X 1400  Y 1400  (2 s)");
  delay(2000);  // 2 s flat, time to check that the plate is level
}

void loop() {
  for (int i = 0; i < 8; i++) {
    moveTo(NAMES[i], toPulse(DIRECTIONS[i][0], PULSE_CENTER_X), toPulse(DIRECTIONS[i][1], PULSE_CENTER_Y));
    moveTo("flat", PULSE_CENTER_X, PULSE_CENTER_Y);  // back to flat
  }
}

// -1 / 0 / +1 -> PULSE_MIN / centre / PULSE_MAX
int toPulse(int direction, int center) {
  if (direction < 0) return PULSE_MIN;
  if (direction > 0) return PULSE_MAX;
  return center;
}

// Glide both servos from where they are to (targetX, targetY), then hold there.
// name is only for the Serial Monitor.
void moveTo(const char *name, int targetX, int targetY) {
  Serial.printf("%-10s  X %d  Y %d\n", name, targetX, targetY);
  float startX = nowX;
  float startY = nowY;
  unsigned long startMs = millis();
  float t = 0;
  while (t < 1) {
    t = min((millis() - startMs) / (float)MOVE_MS, 1.0f);
    // Cosine ease: 0 -> 1, slow at both ends, so the plate never jerks.
    float s = (1 - cos(PI * t)) / 2;
    nowX = startX + (targetX - startX) * s;
    nowY = startY + (targetY - startY) * s;
    servoX.writeMicroseconds(round(constrain(nowX, PULSE_MIN, PULSE_MAX)));
    servoY.writeMicroseconds(round(constrain(nowY, PULSE_MIN, PULSE_MAX)));
    delay(20);  // one servo frame
  }
  delay(HOLD_MS);
}
