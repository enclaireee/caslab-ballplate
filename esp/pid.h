// pid.h - the Pid type, shared by esp.ino and pid.ino.
//
// It lives in a header because esp.ino creates the two Pid objects at the top
// of the file, so the type has to be known before pid.ino is reached.

#pragma once

// The plate never tilts more than this, in degrees.
const float TILT_LIMIT = 15.0;

// All the memory one axis's PID needs.
struct Pid {
  float kp;
  float ki;
  float kd;
  float integral;   // running sum of error * dt
  float lastPos;    // previous position, to measure how fast the ball moves
  bool haveLast;    // false until the first position arrives
};

void pidBegin(Pid &p, float kp, float ki, float kd);
float pidStep(Pid &p, float setpoint, float pos, float dt);
void resetIntegral(Pid &p);
