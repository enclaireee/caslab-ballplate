// esp.ino - Ball and Plate, ESP32 side.
//
// One "pos x y" line from the laptop = one control step:
//   PID per axis -> plate tilt -> servo pulse -> one data line back.
//
// Commands (115200 baud, one line each):
//   pos 12.5 -3.0    ball position in mm, every camera frame
//   pos none         the ball is not visible
//
// Files: esp.ino (settings + loop), pid.ino (PID maths),
// plate.ino (servo pulse), pid.h (the PID type).
// Needs the ESP32Servo library from Library Manager.

#include <ESP32Servo.h>
#include "pid.h"

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

// ---------- Controller ----------

// PID gains. KP is degrees of tilt per mm of error, KD damps the ball speed.
const float KP = 0.03f;
const float KI = 0.01f;
const float KD = 0.03f;

// Target: the centre of the plate, in mm.
const float SP_X = 0.0f;
const float SP_Y = 0.0f;

// No "pos" line for this long -> the laptop stopped, so level the plate.
const unsigned long SERIAL_TIMEOUT_MS = 500;

Servo servoX;
Servo servoY;
PID pid;

unsigned long lastSerialMs = 0;   // time of the last command from the laptop
unsigned long lastControlMs = 0;  // 0 = no previous control step (after hold)

// Declared here so the reader sees the whole flow before the definitions.
void handleCommand(String line);
void controlStep(float x, float y);
void hold();
void moveServos(float tiltX, float tiltY);
void setTiltLimits();

void setup() {
  Serial.begin(115200);
  Serial.setTimeout(5);  // readStringUntil waits at most 5 ms for a full line

  // Gains first, then clear the state, then let the pulse window set the limits.
  pid.x.kp = KP;
  pid.x.ki = KI;
  pid.x.kd = KD;
  pid.y.kp = KP;
  pid.y.ki = KI;
  pid.y.kd = KD;
  resetPID(pid);
  setTiltLimits();

  // One timer per servo, 50 Hz, 16-bit pulse resolution.
  ESP32PWM::allocateTimer(0);
  ESP32PWM::allocateTimer(1);
  servoX.setPeriodHertz(50);
  servoY.setPeriodHertz(50);
  servoX.attach(SERVO_X_PIN, SERVO_US_MIN, SERVO_US_MAX);
  servoY.attach(SERVO_Y_PIN, SERVO_US_MIN, SERVO_US_MAX);
  // 16-bit = 0.3 us steps. The 10-bit default rounds small PID corrections
  // away. Must come after attach(), because attach() resets the timer width.
  servoX.setTimerWidth(16);
  servoY.setTimerWidth(16);

  hold();
  lastSerialMs = millis();
  Serial.println("# ball and plate ready");
}

void loop() {
  // Safety: the laptop went quiet -> level the plate and forget the old state.
  if (millis() - lastSerialMs > SERIAL_TIMEOUT_MS) {
    hold();
    Serial.println("# timeout: holding flat");
    lastSerialMs = millis();
  }

  if (Serial.available()) {
    handleCommand(Serial.readStringUntil('\n'));
  }
}

// Only two commands exist: a position, or "none" when the camera lost the ball.
void handleCommand(String line) {
  line.trim();
  lastSerialMs = millis();  // any line means the laptop is alive

  if (line == "pos none") {
    hold();
    Serial.println("# no ball");
    return;
  }

  float x, y;
  if (sscanf(line.c_str(), "pos %f %f", &x, &y) == 2) {
    controlStep(x, y);
  }
}

// One control step: new ball position in, one CSV line out.
void controlStep(float x, float y) {
  unsigned long now = millis();

  // dt is seconds since the previous accepted frame. After hold() it is 0, so
  // the first frame back uses P only: no fake speed and no integral jump.
  float dt = 0.0f;
  if (lastControlMs != 0) {
    dt = (now - lastControlMs) / 1000.0f;
  }
  lastControlMs = now;

  float ux = axisStep(pid.x, SP_X, x, dt);  // plate tilt in degrees
  float uy = axisStep(pid.y, SP_Y, y, dt);
  moveServos(ux, uy);

  // t_ms,x_mm,y_mm,sp_x_mm,sp_y_mm,u_x_deg,u_y_deg
  Serial.printf("%lu,%.1f,%.1f,%.1f,%.1f,%.2f,%.2f\n", now, x, y, SP_X, SP_Y, ux, uy);
}

// Plate flat and controller state cleared. Used at boot, on "pos none" and on
// the serial timeout, so a dropout can never leak old speed or integral into
// the first frame after the ball comes back.
void hold() {
  moveServos(0.0f, 0.0f);
  resetPID(pid);
  lastControlMs = 0;
}
