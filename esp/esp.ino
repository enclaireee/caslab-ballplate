// esp.ino - Ball and Plate, ESP32 side.
//
// One "pos x y" line from the laptop = one control step:
//   PID per axis -> plate tilt -> servo pulse -> one data line back.
//
// Commands (115200 baud, one line each):
//   pos 12.5 -3.0    ball position in mm, every camera frame
//   pos none         the ball is not visible
//   sp 50 0          set the setpoint in mm
//   pid 0.4 0 0.15   set kp ki kd for both axes
//
// Files: esp.ino (settings + loop), pid.ino (PID maths), plate.ino (servo pulse),
// pid.h (the Pid type). Needs the ESP32Servo library from Library Manager.

#include <ESP32Servo.h>
#include "pid.h"

// ---------- Settings ----------

const int SERVO_X_PIN = 18;
const int SERVO_Y_PIN = 19;

// Pulse width (microseconds) for 0 and 180 degrees of servo. These are the
// ESP32Servo defaults, so 90 degrees gives the same pulse servo.write(90) did.
const int PULSE_0_DEG = 544;
const int PULSE_180_DEG = 2400;

// Servo angle that makes the plate level, per axis. Decimals are fine, e.g. 91.5.
const float SERVO_CENTER_X = 90.0;
const float SERVO_CENTER_Y = 90.0;

// +1 = positive tilt pushes the ball towards +x / +y. Use -1 if it goes the wrong way.
const int SERVO_DIR_X = 1;
const int SERVO_DIR_Y = 1;

float KP = 0.074;  // degrees of tilt per mm of error
float KI = 0.0;    // degrees per (mm * second)
float KD = 0.025;  // degrees per (mm/s) of ball speed

const unsigned long POS_TIMEOUT_MS = 200;  // no pos for this long -> plate flat

Servo servoX;
Servo servoY;
Pid pidX;
Pid pidY;

float spX = 0.0;
float spY = 0.0;

bool havePos = false;
unsigned long lastPosMs = 0;

void setup() {
  Serial.begin(115200);
  Serial.setTimeout(5);  // readStringUntil waits at most 5 ms for the rest of a line

  pidBegin(pidX, KP, KI, KD);
  pidBegin(pidY, KP, KI, KD);

  servoX.attach(SERVO_X_PIN, PULSE_0_DEG, PULSE_180_DEG);
  servoY.attach(SERVO_Y_PIN, PULSE_0_DEG, PULSE_180_DEG);
  hold();

  Serial.println("# ball and plate ready");
}

void loop() {
  // Safety: the laptop stopped sending positions -> plate flat.
  if (havePos && millis() - lastPosMs > POS_TIMEOUT_MS) {
    havePos = false;
    hold();
    Serial.println("# timeout: plate flat");
  }

  if (Serial.available()) {
    handleCommand(Serial.readStringUntil('\n'));
  }
}

void handleCommand(String line) {
  float a, b, c;
  if (sscanf(line.c_str(), "pos %f %f", &a, &b) == 2) {
    controlStep(a, b);
  } else if (line.startsWith("pos none")) {
    havePos = false;
    hold();
    Serial.println("# no ball");
  } else if (sscanf(line.c_str(), "sp %f %f", &a, &b) == 2) {
    spX = a;
    spY = b;
  } else if (sscanf(line.c_str(), "pid %f %f %f", &a, &b, &c) == 3) {
    KP = a;
    KI = b;
    KD = c;
    pidBegin(pidX, KP, KI, KD);
    pidBegin(pidY, KP, KI, KD);
  }
}

// One control step: new ball position in, one CSV line out.
void controlStep(float x, float y) {
  unsigned long now = millis();

  // dt = time since the last pos line. The first line uses one camera frame.
  float dt = havePos ? (now - lastPosMs) / 1000.0 : 0.02;
  if (dt <= 0) dt = 0.02;  // two lines in the same millisecond

  havePos = true;
  lastPosMs = now;

  float ux = pidStep(pidX, spX, x, dt);
  float uy = pidStep(pidY, spY, y, dt);

  servoX.writeMicroseconds(tiltToPulse(ux, SERVO_CENTER_X, SERVO_DIR_X));
  servoY.writeMicroseconds(tiltToPulse(uy, SERVO_CENTER_Y, SERVO_DIR_Y));

  // t_ms,x_mm,y_mm,sp_x_mm,sp_y_mm,u_x_deg,u_y_deg
  Serial.printf("%lu,%.1f,%.1f,%.1f,%.1f,%.2f,%.2f\n", now, x, y, spX, spY, ux, uy);
}

// Plate flat and integrators cleared. Used at boot, on "pos none" and on timeout.
void hold() {
  servoX.writeMicroseconds(tiltToPulse(0, SERVO_CENTER_X, SERVO_DIR_X));
  servoY.writeMicroseconds(tiltToPulse(0, SERVO_CENTER_Y, SERVO_DIR_Y));
  resetIntegral(pidX);
  resetIntegral(pidY);
}
