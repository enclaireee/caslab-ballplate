// pid.ino - the PID maths for one axis. Same idea for X and Y.
//
//   error      = setpoint - position        (mm)
//   speed      = how fast the ball moved    (mm/s)
//   tilt (u)   = kp*error + ki*integral - kd*speed
//
// The result is a plate tilt in degrees, limited to +-15.

#include "pid.h"

// Start (or restart) one axis. Clears the integral and the speed history.
void pidBegin(Pid &p, float kp, float ki, float kd) {
  p.kp = kp;
  p.ki = ki;
  p.kd = kd;
  p.integral = 0;
  p.lastPos = 0;
  p.haveLast = false;
}

void resetIntegral(Pid &p) {
  p.integral = 0;
}

// One control step. Returns the tilt angle in degrees for this axis.
float pidStep(Pid &p, float setpoint, float pos, float dt) {
  float error = setpoint - pos;

  // The derivative works on the CHANGE IN POSITION, not the change in error.
  // If it used the error, a new setpoint would look like a huge ball speed
  // and kick the plate. This way a setpoint jump only moves the kp part.
  float speed = p.haveLast ? (pos - p.lastPos) / dt : 0;
  p.lastPos = pos;
  p.haveLast = true;

  float nextIntegral = p.integral + error * dt;
  float u = p.kp * error + p.ki * nextIntegral - p.kd * speed;

  // Anti-windup: once the plate is already at its limit, the integral would
  // keep growing while the ball cannot catch up. Freeze it instead.
  if (u <= TILT_LIMIT && u >= -TILT_LIMIT) {
    p.integral = nextIntegral;
  }

  return constrain(u, -TILT_LIMIT, TILT_LIMIT);
}
