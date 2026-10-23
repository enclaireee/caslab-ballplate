// esptest.ino - servo test, separate from the main sketch (open this file on its own).
//
// After the upload the ESP32 tilts the plate as far as it can in each of the 8
// directions, going back to flat in between:
//   flat -> right -> flat -> right+up -> flat -> up -> flat -> ... -> right+down -> flat
// and then starts again, forever. To stop it, unplug the ESP32 or upload esp/esp.ino.
//
// The names say where the BALL rolls, seen from the camera: right = +x,
// up = +y (the same axes as esp.ino). SERVO_DIR_X/Y turn that into the right
// pulse, so if "right" rolls the ball left, that SERVO_DIR is wrong.
//
// Each side goes to its own pulse limit, so the tilt is not the same both ways:
// with the numbers below, right/up reach +2.5 deg (1150 us) and left/down
// reach -5.5 deg (1950 us). The Serial Monitor (115200 baud) prints both.
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

// The 8 directions the ball should roll: +1 = towards +x / +y, -1 = towards
// -x / -y, 0 = that axis stays flat. Read as {x, y}.
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
    int pulseX = rollPulse(DIRECTIONS[i][0], PULSE_CENTER_X, SERVO_DIR_X);
    int pulseY = rollPulse(DIRECTIONS[i][1], PULSE_CENTER_Y, SERVO_DIR_Y);
    moveTo(NAMES[i], pulseX, pulseY);
    moveTo("flat", PULSE_CENTER_X, PULSE_CENTER_Y);  // back to flat
  }
}

// The pulse that rolls the ball as far as allowed towards `roll` (+1 / -1),
// or the centre for 0. A positive tilt moves the pulse by +servoDir, so the
// side to use is the sign of roll * servoDir.
int rollPulse(int roll, int center, int servoDir) {
  int side = roll * servoDir;
  if (side > 0) return PULSE_MAX;
  if (side < 0) return PULSE_MIN;
  return center;
}

// Plate tilt in degrees for a pulse, the inverse of the formula above.
float pulseToTilt(int pulse, int center, int servoDir) {
  return (pulse - center) / (servoDir * PULSE_PER_DEG);
}

// Glide both servos from where they are to (targetX, targetY), then hold there.
// name is only for the Serial Monitor.
void moveTo(const char *name, int targetX, int targetY) {
  Serial.printf("%-10s  X %d us (%+.1f deg)  Y %d us (%+.1f deg)\n", name,
                targetX, pulseToTilt(targetX, PULSE_CENTER_X, SERVO_DIR_X),
                targetY, pulseToTilt(targetY, PULSE_CENTER_Y, SERVO_DIR_Y));
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
