import type { Axis, Sample } from "./config";

// One setpoint change: samples start..end-1 belong to this step.
export type Step = { start: number; end: number; from: number; to: number };

// Numbers for one step. null = never reached ("—" in the table).
export type StepResult = {
  from: number;
  to: number;
  riseS: number | null;
  overshootPct: number | null;
  settlingS: number | null;
  sseMm: number | null;
};

// Position and setpoint of one sample on the chosen axis.
function pos(s: Sample, axis: Axis) {
  return axis === "x" ? s.x_mm : s.y_mm;
}
function target(s: Sample, axis: Axis) {
  return axis === "x" ? s.sp_x_mm : s.sp_y_mm;
}

// Find every place where the setpoint changes. A step lasts until the next change (or the end).
export function findSteps(samples: Sample[], axis: Axis): Step[] {
  const starts: number[] = [];
  for (let i = 1; i < samples.length; i++) {
    if (Math.abs(target(samples[i], axis) - target(samples[i - 1], axis)) > 1e-9) {
      starts.push(i);
    }
  }
  return starts.map((start, k) => ({
    start,
    end: k + 1 < starts.length ? starts[k + 1] : samples.length,
    from: target(samples[start - 1], axis),
    to: target(samples[start], axis),
  }));
}

// Compute the 4 metrics of one step.
export function stepMetrics(samples: Sample[], step: Step, axis: Axis): StepResult {
  const jump = step.to - step.from;
  const t0 = samples[step.start].t_ms;
  const win = samples.slice(step.start, step.end);
  // progress: 0 = still at "from", 1 = at the target
  const progress = win.map((s) => (pos(s, axis) - step.from) / jump);

  // Rise time: first time at 10% of the jump until first time at 90%.
  const i10 = progress.findIndex((p) => p >= 0.1);
  const i90 = progress.findIndex((p) => p >= 0.9);
  const riseS = i10 >= 0 && i90 >= 0 ? (win[i90].t_ms - win[i10].t_ms) / 1000 : null;

  // Overshoot: biggest excursion past the target, as % of the jump.
  const overshootPct = Math.max(0, (Math.max(...progress) - 1) * 100);

  // Settling time: first time after which the ball stays within ±5% of the jump.
  let lastOut = -1;
  progress.forEach((p, i) => {
    if (Math.abs(p - 1) > 0.05) lastOut = i;
  });
  const settlingS =
    lastOut === win.length - 1 ? null : (win[lastOut + 1].t_ms - t0) / 1000;

  // Steady-state error: target minus mean position over the last 1 s of the step.
  const tEnd = win[win.length - 1].t_ms;
  const tail = win.filter((s) => s.t_ms > tEnd - 1000);
  const mean = tail.reduce((sum, s) => sum + pos(s, axis), 0) / tail.length;

  return { from: step.from, to: step.to, riseS, overshootPct, settlingS, sseMm: step.to - mean };
}
