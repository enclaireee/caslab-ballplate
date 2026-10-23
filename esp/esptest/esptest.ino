// esptest.ino - servo test, separate from the main sketch (open this file on its own).
//
// After the upload the ESP32 tilts the plate to the extreme of each of the 8
// directions, going back to flat in between:
//   flat -> right -> flat -> right+up -> flat -> up -> flat -> ... -> right+down -> flat
// and then starts again, forever. To stop it, unplug the ESP32 or upload esp/esp.ino.
//
// Every move is smooth (slow at the start and end), and it holds each position
// for a moment so you can look at it or measure it.
//
// Nothing ever goes outside PULSE_MIN..PULSE_MAX. If the plate touches the frame
// at an extreme, narrow them here and in esp.ino.

#include <ESP32Servo.h>

// ---------- Servo hardware (same block in esp.ino, esptest.ino, espreset.ino) ----------

const int SERVO_X_PIN = 2;
const int SERVO_Y_PIN = 4;

// The servo's own pulse scale (its full travel). Only for attach(); the limits
// below are ours and narrower.
const int SERVO_US_MIN = 500;
const int SERVO_US_MAX = 2500;

// Pulse width (microseconds) that makes the plate level on this rig, per axis.
const int PULSE_CENTER_X = 1400;
const int PULSE_CENTER_Y = 1400;

// Never send a pulse outside these, so the plate does not hit its stops.
const int PULSE_MIN = 1150;
const int PULSE_MAX = 1950;

// Microseconds of pulse per degree of plate tilt. With PULSE_CENTER = 1400,
// PULSE_MIN = 1150, PULSE_MAX = 1950 and PULSE_PER_DEG = 100.0, the physical
// tilt range is -5.5 deg (1950 us) to +2.5 deg (1150 us):
//
//   pulse_us = constrain(round(PULSE_CENTER + SERVO_DIR * tilt_deg * PULSE_PER_DEG),
//                        PULSE_MIN, PULSE_MAX)
const float PULSE_PER_DEG = 100.0f;

// +1 = positive tilt pushes the ball towards +x / +y. -1 flips the direction.
const int SERVO_DIR_X = -1;
const int SERVO_DIR_Y = -1;

// ---------- Test pattern ----------

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

  // One timer per servo, 50 Hz, 16-bit pulse resolution.
  ESP32PWM::allocateTimer(0);
  ESP32PWM::allocateTimer(1);
  servoX.setPeriodHertz(50);
  servoY.setPeriodHertz(50);
  servoX.attach(SERVO_X_PIN, SERVO_US_MIN, SERVO_US_MAX);
  servoY.attach(SERVO_Y_PIN, SERVO_US_MIN, SERVO_US_MAX);
  // 16-bit = 0.3 us steps. The 10-bit default rounds small moves away.
  // Must come after attach(), because attach() resets the timer width.
  servoX.setTimerWidth(16);
  servoY.setTimerWidth(16);

  servoX.writeMicroseconds(PULSE_CENTER_X);
  servoY.writeMicroseconds(PULSE_CENTER_Y);
  Serial.printf("flat  X %d  Y %d  (2 s)\n", PULSE_CENTER_X, PULSE_CENTER_Y);
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
