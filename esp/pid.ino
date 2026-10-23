// pid.ino - the PID maths for one axis. Same code for X and Y.
//
//   error    = setpoint - position          (mm)
//   speed    = how fast the ball moved      (mm/s)
//   tilt (u) = kp*error + ki*integral - kd*speed   (degrees)
//
// The result is a plate tilt, limited to the range the servo pulse window
// allows (tiltMin..tiltMax, set by setTiltLimits() in plate.ino).

#include "pid.h"

// Clear both axes. Called at boot and whenever the ball is lost, so a dropout
// never leaves old speed or integral behind.
void resetPID(PID &p) {
  p.x.integral = 0.0f;
  p.x.prevPos = NAN;
  p.y.integral = 0.0f;
  p.y.prevPos = NAN;
}

// One PID step for one axis. pos and setpoint are mm, dt is seconds, and the
// returned tilt is degrees.
float axisStep(Axis &a, float setpoint, float pos, float dt) {
  float error = setpoint - pos;  // mm

  // Trust dt only for a normal camera frame (<= 200 ms). After a dropout the
  // gap is long, so skip the speed and the integral for that one frame.
  bool fresh = !isnan(a.prevPos) && dt > 0.0f && dt <= 0.2f;
  float speed = fresh ? (pos - a.prevPos) / dt : 0.0f;  // mm/s
  a.prevPos = pos;

  // No integral action when KI is zero, so the sum cannot creep.
  float nextIntegral = a.integral;
  if (a.ki == 0.0f) {
    a.integral = 0.0f;
  } else if (fresh) {
    nextIntegral = a.integral + error * dt;
  }

  float u = a.kp * error + a.ki * nextIntegral - a.kd * speed;  // degrees

  // Anti-windup: keep the integral only while the output is inside its window.
  if (a.ki != 0.0f && fresh && u >= a.tiltMin && u <= a.tiltMax) {
    a.integral = nextIntegral;
  }

  return constrain(u, a.tiltMin, a.tiltMax);
}
