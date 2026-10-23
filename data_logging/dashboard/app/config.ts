// Address of esp/datalog.py (always 127.0.0.1, not localhost).
export const API = "http://127.0.0.1:8000";

// Real plate size in mm. (0, 0) is the centre, so each edge is 125 mm away.
export const PLATE_HALF_MM = 125;

// The tilt gauge stops at this many degrees, so the few degrees the PID uses stay readable.
export const TILT_DISPLAY_MAX_DEG = 6;

// No new data for this long = datalog.py stopped writing.
export const STALE_MS = 2000;

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

// Turn CSV text into samples. Header lines, `#` messages, NUL bytes from a USB
// dropout and anything that is not 7 finite numbers are skipped.
export function parseCsv(text: string): Sample[] {
  const samples: Sample[] = [];

  for (const line of text.replace(/\0/g, "").split(/\r?\n/)) {
    const cells = line.split(",");
    if (cells.length !== 7) continue;

    const values = cells.map(Number);
    if (!values.every(Number.isFinite)) continue;

    samples.push({
      t_ms: values[0],
      x_mm: values[1],
      y_mm: values[2],
      sp_x_mm: values[3],
      sp_y_mm: values[4],
      u_x_deg: values[5],
      u_y_deg: values[6],
    });
  }

  return samples;
}

// Show a number with 1 decimal, or "--" when there is no data yet.
// Tiny values show as 0.0 (not "-0.0").
export function fmt(n: number | undefined) {
  if (n === undefined) return "--";
  return Math.abs(n) < 0.05 ? "0.0" : n.toFixed(1);
}
