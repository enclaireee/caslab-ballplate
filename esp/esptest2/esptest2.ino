// esptest2.ino - servo test you drive from the Serial Monitor (open this file on its own).
//
// Serial Monitor: 115200 baud, line ending "Newline". Type a command, press Enter:
//   test X+      ball rolls to +x (right)    test X+Y+   right+up
//   test X-      ball rolls to -x (left)     test X+Y-   right+down
//   test Y+      ball rolls to +y (up)       test X-Y+   left+up
//   test Y-      ball rolls to -y (down)     test X-Y-   left+down
//   stop         stay where it is now
//   flat         go slowly back to level
// Upper or lower case both work. An axis you do not name goes back to flat.
//
// After a "test" the plate creeps slowly (SPEED_US_PER_S) towards the pulse
// limit of that direction and stops there. It prints the pulse and tilt while
// it moves. If the plate touches the frame or a servo buzzes, type "stop":
// the pulse printed last is the real limit for that side. Use it for
// PULSE_MIN / PULSE_MAX.
//
// The directions mean the same as in esptest.ino: where the BALL rolls, seen
// from the camera. Nothing ever goes outside PULSE_MIN..PULSE_MAX.

#include <ESP32Servo.h>

// ---------- Servo hardware (same block in esp.ino, esptest.ino, esptest2.ino, espreset.ino) ----------

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

// ---------- Test speed ----------

const float SPEED_US_PER_S = 50.0f;  // slow: centre to 1950 us takes 11 s
const int FRAME_MS = 20;             // one servo frame (50 Hz)
const int PRINT_MS = 250;            // how often to print while moving
const float STEP_US = SPEED_US_PER_S * FRAME_MS / 1000.0f;  // pulse change per frame

Servo servoX;
Servo servoY;

// Where the servos are now and where they are going, in microseconds.
float nowX = PULSE_CENTER_X;
float nowY = PULSE_CENTER_Y;
float targetX = PULSE_CENTER_X;
float targetY = PULSE_CENTER_Y;
bool moving = false;

unsigned long lastFrameMs = 0;
unsigned long lastPrintMs = 0;
String line = "";  // the command being typed

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
  printPosition("flat");
  Serial.println("commands: test X+ | test X-Y+ | ... | stop | flat");
}

void loop() {
  readSerial();
  // One small step per servo frame, so the move is slow and smooth.
  if (millis() - lastFrameMs >= FRAME_MS) {
    lastFrameMs = millis();
    stepServos();
  }
}

// Collect typed characters and run the command when Enter arrives.
// Not readStringUntil(): that waits, and the servos would stop moving.
void readSerial() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n' || c == '\r') {
      if (line.length() > 0) handleCommand(line);
      line = "";
    } else {
      line += c;
    }
  }
}

void handleCommand(String cmd) {
  cmd.trim();
  cmd.toUpperCase();
  if (cmd == "STOP") {
    targetX = nowX;
    targetY = nowY;
    moving = false;
    printPosition("stopped");
  } else if (cmd == "FLAT") {
    startMove("flat", PULSE_CENTER_X, PULSE_CENTER_Y);
  } else if (cmd.startsWith("TEST ")) {
    String dir = cmd.substring(5);
    dir.replace(" ", "");
    int rollX = axisSign(dir, 'X');
    int rollY = axisSign(dir, 'Y');
    if (rollX == 0 && rollY == 0) {
      Serial.println("# say which way, e.g. test X+ or test X+Y-");
      return;
    }
    startMove(dir.c_str(), rollPulse(rollX, PULSE_CENTER_X, SERVO_DIR_X),
              rollPulse(rollY, PULSE_CENTER_Y, SERVO_DIR_Y));
  } else {
    Serial.println("# unknown command: " + cmd);
  }
}

// +1 / -1 from the sign right after the axis letter ("X+" -> +1), 0 if the
// letter is not there.
int axisSign(String dir, char axis) {
  int i = dir.indexOf(axis);
  if (i < 0 || i + 1 >= (int)dir.length()) return 0;
  if (dir[i + 1] == '+') return +1;
  if (dir[i + 1] == '-') return -1;
  return 0;
}

// The pulse that rolls the ball as far as allowed towards `roll` (+1 / -1),
// or the centre for 0. Same as esptest.ino.
int rollPulse(int roll, int center, int servoDir) {
  int side = roll * servoDir;
  if (side > 0) return PULSE_MAX;
  if (side < 0) return PULSE_MIN;
  return center;
}

void startMove(const char *name, int x, int y) {
  targetX = x;
  targetY = y;
  moving = true;
  Serial.printf("%s -> X %d us (%+.1f deg)  Y %d us (%+.1f deg)\n", name,
                x, pulseToTilt(x, PULSE_CENTER_X, SERVO_DIR_X),
                y, pulseToTilt(y, PULSE_CENTER_Y, SERVO_DIR_Y));
}

// Move both servos one STEP_US closer to the target, print now and then,
// and say when the target is reached.
void stepServos() {
  if (!moving) return;
  nowX = stepTowards(nowX, targetX);
  nowY = stepTowards(nowY, targetY);
  servoX.writeMicroseconds(round(constrain(nowX, PULSE_MIN, PULSE_MAX)));
  servoY.writeMicroseconds(round(constrain(nowY, PULSE_MIN, PULSE_MAX)));

  if (nowX == targetX && nowY == targetY) {
    moving = false;
    printPosition("reached");
  } else if (millis() - lastPrintMs >= PRINT_MS) {
    lastPrintMs = millis();
    printPosition("at");
  }
}

// One step from `now` towards `target`, without going past it.
float stepTowards(float now, float target) {
  if (now < target) return min(now + STEP_US, target);
  return max(now - STEP_US, target);
}

// Plate tilt in degrees for a pulse, the inverse of the formula above.
float pulseToTilt(float pulse, int center, int servoDir) {
  return (pulse - center) / (servoDir * PULSE_PER_DEG);
}

void printPosition(const char *label) {
  Serial.printf("%-8s X %4.0f us (%+.2f deg)  Y %4.0f us (%+.2f deg)\n", label,
                nowX, pulseToTilt(nowX, PULSE_CENTER_X, SERVO_DIR_X),
                nowY, pulseToTilt(nowY, PULSE_CENTER_Y, SERVO_DIR_Y));
}
