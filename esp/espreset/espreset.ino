// espreset.ino - plate level and still, separate from the main sketch (open this
// file on its own).
//
// Upload it to stop whatever the ESP32 was doing (esp.ino or esptest.ino). It
// sends both servos to the centre pulse once and then does nothing. The servos
// stay powered, so they keep holding the plate level. To run again, upload esp/esp.ino.

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

Servo servoX;
Servo servoY;

void setup() {
  Serial.begin(115200);

  // One timer per servo, 50 Hz, 16-bit pulse resolution.
  ESP32PWM::allocateTimer(0);
  ESP32PWM::allocateTimer(1);
  servoX.setPeriodHertz(50);
  servoY.setPeriodHertz(50);
  servoX.attach(SERVO_X_PIN, SERVO_US_MIN, SERVO_US_MAX);
  servoY.attach(SERVO_Y_PIN, SERVO_US_MIN, SERVO_US_MAX);
  // 16-bit = 0.3 us steps. The 10-bit default rounds the centre pulse away.
  // Must come after attach(), because attach() resets the timer width.
  servoX.setTimerWidth(16);
  servoY.setTimerWidth(16);

  // Clamp the centre in case someone edits it beyond the safe window.
  int pulseX = constrain(PULSE_CENTER_X, PULSE_MIN, PULSE_MAX);
  int pulseY = constrain(PULSE_CENTER_Y, PULSE_MIN, PULSE_MAX);
  servoX.writeMicroseconds(pulseX);
  servoY.writeMicroseconds(pulseY);
  Serial.printf("# espreset: center pulse X=%d Y=%d\n", pulseX, pulseY);
}

void loop() {}
