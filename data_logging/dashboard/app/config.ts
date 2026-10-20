// Address of esp/datalog.py (always 127.0.0.1, not localhost).
export const API = "http://127.0.0.1:8000";

// One row of data = the 7 CSV columns.
export type Sample = {
  t_ms: number;
  x_mm: number;
  y_mm: number;
  sp_x_mm: number;
  sp_y_mm: number;
  u_x_deg: number;
  u_y_deg: number;
};

// Which axis we look at.
export type Axis = "x" | "y";

// Show a number with 1 decimal, or "--" when there is no data yet.
// Tiny values show as 0.0 (not "-0.0").
export function fmt(n: number | undefined) {
  if (n === undefined) return "--";
  return Math.abs(n) < 0.05 ? "0.0" : n.toFixed(1);
}
