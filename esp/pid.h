// pid.h - the two-axis PID type, shared by esp.ino, pid.ino and plate.ino.
//
// It lives in a header because esp.ino creates the PID object at the top of
// the file, so the type has to be known before pid.ino is reached.

#pragma once

// All the memory one axis's PID needs.
struct Axis {
  float kp;        // degrees of tilt per mm of error
  float ki;        // degrees per (mm * second)
  float kd;        // degrees per (mm / second) of ball speed
  float integral;  // running sum of error * dt, in mm * second
  float prevPos;   // previous ball position in mm (NAN = no previous frame)
  float tiltMin;   // lowest tilt the pulse window allows, in degrees
  float tiltMax;   // highest tilt the pulse window allows, in degrees
};

// Both axes of the plate.
struct PID {
  Axis x;
  Axis y;
};

void resetPID(PID &p);
float axisStep(Axis &a, float setpoint, float pos, float dt);
