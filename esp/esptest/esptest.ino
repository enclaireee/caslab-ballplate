// esptest.ino - servo test, separate from the main sketch (open this file on its own).
//
// No Serial Monitor needed. After the upload the ESP32:
//   1. puts the plate flat (PULSE_CENTER_X / Y) for 2 seconds,
//   2. fades into a smooth sine wave on each servo over the next 2 seconds,
//   3. keeps moving both servos through PULSE_MIN..PULSE_MAX, forever.
// To stop it, unplug the ESP32 or upload the main sketch (esp/esp.ino).
//
// X and Y use different periods, so together the plate tilts in every direction
// and by every amount, not only along one diagonal. A sine wave slows down
// before each end and turns around gently, so the plate never stops with a jerk.
//
// Nothing ever goes outside PULSE_MIN..PULSE_MAX. If the plate touches the frame
// at either end, narrow them here and in esp.ino.

#include <ESP32Servo.h>

// Same as esp/esp.ino.
const int SERVO_X_PIN = 2;
const int SERVO_Y_PIN = 4;
const int PULSE_CENTER_X = 1400;
const int PULSE_CENTER_Y = 1400;
const int PULSE_MIN = 1150;
const int PULSE_MAX = 1950;

// Seconds for one full back-and-forth. Bigger = slower. Keep X and Y different.
const float PERIOD_X = 4.0;
const float PERIOD_Y = 5.0;

// Middle of the range and how far to go each way: 1550 +- 400 = 1150..1950.
const float PULSE_MID = (PULSE_MIN + PULSE_MAX) / 2.0;
const float PULSE_HALF = (PULSE_MAX - PULSE_MIN) / 2.0;

Servo servoX;
Servo servoY;

unsigned long startMs = 0;

void setup() {
  servoX.attach(SERVO_X_PIN, PULSE_MIN, PULSE_MAX);
  servoY.attach(SERVO_Y_PIN, PULSE_MIN, PULSE_MAX);
  servoX.writeMicroseconds(PULSE_CENTER_X);
  servoY.writeMicroseconds(PULSE_CENTER_Y);
  delay(2000);  // 2 s flat, time to check that the plate is level
  startMs = millis();
}

void loop() {
  float t = (millis() - startMs) / 1000.0;  // seconds since the motion started

  // 0 -> 1 over the first 2 s, so the plate eases out of flat instead of jumping.
  float fade = min(t / 2.0, 1.0);

  float targetX = PULSE_MID + PULSE_HALF * sin(2 * PI * t / PERIOD_X);
  float targetY = PULSE_MID + PULSE_HALF * sin(2 * PI * t / PERIOD_Y);

  moveServo(servoX, PULSE_CENTER_X, targetX, fade);
  moveServo(servoY, PULSE_CENTER_Y, targetY, fade);
}

// Blend from the flat pulse to the target, keep it inside PULSE_MIN..PULSE_MAX.
void moveServo(Servo &servo, int center, float target, float fade) {
  float pulse = center + (target - center) * fade;
  pulse = constrain(pulse, PULSE_MIN, PULSE_MAX);
  servo.writeMicroseconds(round(pulse));
}
