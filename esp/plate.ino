// plate.ino - turn a plate tilt (degrees) into a servo pulse (microseconds).
//
// The servo is mounted so that one degree of servo movement tilts the plate
// by 1 / SERVO_RATIO degrees. So a 15 degree tilt needs 30 degrees of servo.
//
// Servo angle = center + direction * SERVO_RATIO * tilt
//
// The angle is sent as a pulse width, not as whole degrees. servo.write() only
// takes whole degrees, and 1 servo degree = 0.5 plate degree is a big jump for
// the ball. One microsecond of pulse is about 0.1 servo degree, so the plate
// moves almost smoothly.

// Servo degrees per degree of plate tilt. Measure yours: tilt the plate 5
// degrees with a phone level app and see how far the servo moved.
const float SERVO_RATIO = 2.0;

// Never drive the servo past these, so it does not hit the mechanical stops.
const float SERVO_MIN = 20;
const float SERVO_MAX = 170;

// The level angle and push direction of each axis are in esp.ino
// (SERVO_CENTER_X/Y, SERVO_DIR_X/Y), and so is the pulse for 0 and 180 degrees
// (PULSE_0_DEG, PULSE_180_DEG).

int tiltToPulse(float tilt, float center, int direction) {
  float angle = center + direction * SERVO_RATIO * tilt;
  angle = constrain(angle, SERVO_MIN, SERVO_MAX);
  // 0..180 degrees -> PULSE_0_DEG..PULSE_180_DEG microseconds, to the nearest one
  return round(PULSE_0_DEG + angle * (PULSE_180_DEG - PULSE_0_DEG) / 180.0);
}
