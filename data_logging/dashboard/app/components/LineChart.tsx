import type { Sample } from "../config";

const W = 600;
const H = 220;
const RULER = 14; // height of the time ruler at the bottom

// Keep a label's y between the top and the ruler of the chart.
function clamp(y: number) {
  return Math.min(Math.max(y, 12), H - RULER - 12);
}

// Plain SVG line chart, like a waveform monitor: light line = ball ("yKey"), amber dashed line = setpoint ("spKey").
// The lines are labelled at their right end (no legend), and a ruler at the
// bottom has one tick per second (or per 5 / 30 s for long runs).
export default function LineChart({
  samples,
  yKey,
  spKey,
}: {
  samples: Sample[];
  yKey: keyof Sample;
  spKey: keyof Sample;
}) {
  if (samples.length < 2) {
    return <p className="py-16 text-center text-sm text-muted">No data yet.</p>;
  }

  // Find the ranges of time and value.
  const t0 = samples[0].t_ms;
  const t1 = samples[samples.length - 1].t_ms;
  let min = Infinity;
  let max = -Infinity;
  for (const s of samples) {
    min = Math.min(min, s[yKey], s[spKey]);
    max = Math.max(max, s[yKey], s[spKey]);
  }
  // Show at least 20 mm, so +-0.5 mm of camera noise doesn't fill the whole chart.
  if (max - min < 20) {
    const mid = (max + min) / 2;
    max = mid + 10;
    min = mid - 10;
  }
  // Leave a little room above and below the lines.
  const pad = (max - min) * 0.08;
  max += pad;
  min -= pad;

  // Sample -> position inside the SVG.
  function toX(t: number) {
    return ((t - t0) / (t1 - t0 || 1)) * W;
  }
  function toY(value: number) {
    return (H - RULER) * (1 - (value - min) / (max - min));
  }

  // Turn one column into the "points" text of a polyline.
  function toPoints(key: keyof Sample) {
    return samples.map((s) => `${toX(s.t_ms).toFixed(1)},${toY(s[key]).toFixed(1)}`).join(" ");
  }

  // Ruler ticks: every 1 s, or every 5 s / 30 s when the run is long. Every 5th tick is long.
  const spanS = (t1 - t0) / 1000;
  const stepS = spanS <= 20 ? 1 : spanS <= 100 ? 5 : 30;
  const ticks = [];
  for (let k = 0; k * stepS <= spanS; k++) ticks.push(k);

  const last = samples[samples.length - 1];
  const ballY = toY(last[yKey]);
  const spY = toY(last[spKey]);
  // Put the "ball" label on the far side from the "setpoint" label so they don't overlap,
  // and keep both labels inside the plot (not on the ruler).
  const ballBelow = ballY >= spY;
  const ballLabelY = clamp(ballY + (ballBelow ? 20 : -20));
  const spLabelY = clamp(spY + (ballBelow ? -20 : 20));

  return (
    <div>
      <div className="flex justify-between font-mono text-xs text-muted">
        <span>{max.toFixed(1)} mm</span>
        <span>
          {spanS.toFixed(1)} s{stepS > 1 ? `, ticks ${stepS} s` : ""}
        </span>
      </div>
      {/* the labels are HTML on top of the SVG so they stay readable when the chart gets small */}
      <div className="relative my-1">
        <svg
          viewBox={`0 0 ${W} ${H}`}
          role="img"
          aria-label={`${yKey} (light line) and setpoint ${spKey} (amber dashed) over ${spanS.toFixed(1)} s, ${min.toFixed(1)} to ${max.toFixed(1)} mm`}
          className="block w-full overflow-visible"
        >
          {/* faint guide lines at 25%, 50% and 75% height, plus a stronger line at 0 mm */}
          {[0.25, 0.5, 0.75].map((f) => (
            <line key={f} x1="0" x2={W} y1={(H - RULER) * f} y2={(H - RULER) * f} stroke="var(--line)" vectorEffect="non-scaling-stroke" />
          ))}
          {min < 0 && max > 0 && (
            <line x1="0" x2={W} y1={toY(0)} y2={toY(0)} stroke="var(--muted)" strokeDasharray="2 3" vectorEffect="non-scaling-stroke" />
          )}

          {/* time ruler */}
          <line x1="0" x2={W} y1={H - RULER} y2={H - RULER} stroke="var(--muted)" vectorEffect="non-scaling-stroke" />
          {ticks.map((k) => {
            const x = toX(t0 + k * stepS * 1000);
            return <line key={k} x1={x} x2={x} y1={H - RULER} y2={H - RULER + (k % 5 === 0 ? RULER : RULER / 2)} stroke="var(--muted)" vectorEffect="non-scaling-stroke" />;
          })}

          <polyline points={toPoints(spKey)} fill="none" stroke="var(--focus)" strokeWidth="1.5" strokeDasharray="6 5" vectorEffect="non-scaling-stroke" />
          <polyline points={toPoints(yKey)} fill="none" stroke="var(--ink)" strokeWidth="1.75" strokeLinejoin="round" vectorEffect="non-scaling-stroke" className="glow" />
          {/* dot on the newest sample */}
          <circle cx={W} cy={ballY} r="4" fill="var(--ink)" />
        </svg>

        <span
          className="label absolute right-3 -translate-y-1/2 bg-panel px-1 text-ink"
          style={{ top: `${(ballLabelY / H) * 100}%` }}
        >
          ball
        </span>
        <span
          className="label absolute right-3 -translate-y-1/2 bg-panel px-1 text-focus"
          style={{ top: `${(spLabelY / H) * 100}%` }}
        >
          setpoint
        </span>
      </div>
      <p className="font-mono text-xs text-muted">{min.toFixed(1)} mm</p>
    </div>
  );
}
