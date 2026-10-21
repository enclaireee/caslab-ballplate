// plate.ino - turn a plate tilt (degrees) into a servo angle (degrees).
//
// The servo is mounted so that one degree of servo movement tilts the plate
// by 1 / SERVO_RATIO degrees. So a 15 degree tilt needs 30 degrees of servo.
//
// Servo angle = SERVO_CENTER + direction * SERVO_RATIO * tilt

// Servo angle that makes the plate level.
const int SERVO_CENTER = 90;

// Servo degrees per degree of plate tilt. Measure yours: tilt the plate 5
// degrees with a phone level app and see how far the servo moved.
const float SERVO_RATIO = 2.0;

// Never drive the servo past these, so it does not hit the mechanical stops.
const int SERVO_MIN = 20;
const int SERVO_MAX = 160;

// Which way each axis pushes is in esp.ino (SERVO_DIR_X, SERVO_DIR_Y).

int tiltToServo(float tilt, int direction) {
  float angle = SERVO_CENTER + direction * SERVO_RATIO * tilt;
  return (int)constrain(angle, SERVO_MIN, SERVO_MAX);
}
