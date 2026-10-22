// plate.ino - turn a plate tilt (degrees) into a servo pulse (microseconds).
//
// Pulse = center + direction * PULSE_PER_DEG * tilt
//
// The servo is driven by pulse width directly, not by whole degrees, so one
// microsecond is the smallest step (about 0.05 degree of plate) and the plate
// moves almost smoothly.
//
// All the numbers are in esp.ino: PULSE_CENTER_X/Y, PULSE_MIN, PULSE_MAX,
// PULSE_PER_DEG and SERVO_DIR_X/Y.

int tiltToPulse(float tilt, int center, int direction) {
  float pulse = center + direction * PULSE_PER_DEG * tilt;
  pulse = constrain(pulse, PULSE_MIN, PULSE_MAX);
  return round(pulse);  // to the nearest microsecond
}
