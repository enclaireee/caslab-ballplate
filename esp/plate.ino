// plate.ino - turn a plate tilt (degrees) into a servo pulse (microseconds).
//
//   pulse_us = constrain(round(PULSE_CENTER + SERVO_DIR * tilt_deg * PULSE_PER_DEG),
//                        PULSE_MIN, PULSE_MAX)
//
// PULSE_PER_DEG = 100 us/deg, so one microsecond is 0.01 degree of plate.
// All the numbers live in esp.ino.

// Pulse for one axis: centre + direction * pulse-per-degree * tilt.
int tiltToPulse(float tilt, int center, int direction) {
  float pulse = center + direction * PULSE_PER_DEG * tilt;
  return round(constrain(pulse, PULSE_MIN, PULSE_MAX));
}

// Move both servos to a plate tilt in degrees (0, 0 = level).
void moveServos(float tiltX, float tiltY) {
  servoX.writeMicroseconds(tiltToPulse(tiltX, PULSE_CENTER_X, SERVO_DIR_X));
  servoY.writeMicroseconds(tiltToPulse(tiltY, PULSE_CENTER_Y, SERVO_DIR_Y));
}

// The tilt range that stays inside PULSE_MIN..PULSE_MAX. The centre is not in
// the middle of that window, so the range is asymmetric: with centre 1400 us,
// window 1150..1950 us, PULSE_PER_DEG = 100 and direction -1, it is
// -5.5 deg (1950 us) to +2.5 deg (1150 us).
void setTiltLimits() {
  float ax = (PULSE_MIN - PULSE_CENTER_X) / (SERVO_DIR_X * PULSE_PER_DEG);
  float bx = (PULSE_MAX - PULSE_CENTER_X) / (SERVO_DIR_X * PULSE_PER_DEG);
  pid.x.tiltMin = min(ax, bx);
  pid.x.tiltMax = max(ax, bx);

  float ay = (PULSE_MIN - PULSE_CENTER_Y) / (SERVO_DIR_Y * PULSE_PER_DEG);
  float by = (PULSE_MAX - PULSE_CENTER_Y) / (SERVO_DIR_Y * PULSE_PER_DEG);
  pid.y.tiltMin = min(ay, by);
  pid.y.tiltMax = max(ay, by);
}
