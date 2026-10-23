import { PLATE_HALF_MM, fmt } from "../config";
import type { Sample } from "../config";
import StatusPill from "./StatusPill";

const HALF = PLATE_HALF_MM; // short name for the plate half-size; centre = (0, 0)
const TRAIL = 50; // trail = last 50 samples (about 1 s)
const LOCK_MM = 5; // closer than this to the setpoint = "LOCK"

// Grid lines every 30 mm, ending just inside the plate edge (0 is the centre cross).
const GRID_MM = 30;
const GRID_REACH = Math.floor(PLATE_HALF_MM / GRID_MM);
const GRID = Array.from({ length: 2 * GRID_REACH + 1 }, (_, i) => (i - GRID_REACH) * GRID_MM).filter(
  (mm) => mm !== 0,
);

// Time of a sample as a camera timecode, e.g. 83400 ms -> "01:23.4".
function timecode(ms: number) {
  const s = ms / 1000;
  const min = Math.floor(s / 60);
  return `${String(min).padStart(2, "0")}:${(s % 60).toFixed(1).padStart(4, "0")}`;
}

// The plate as the tracking camera sees it, like a camera viewfinder:
//   corner brackets around the image, REC light and timecode on top
//   light dot with a fading trail = ball, inside an amber focus box
//   amber reticle                  = setpoint
//   amber dashed line + "e"        = error, the distance the PID tries to make 0
//   info bar at the bottom         = the newest numbers
// SVG y goes down, plate y goes up, so every y is flipped (-y).
export default function PlateView({ samples, connected }: { samples: Sample[]; connected: boolean }) {
  const last = samples.length > 0 ? samples[samples.length - 1] : null;
  const trail = samples.slice(-TRAIL);

  // The info bar: label, unit, value. The setpoint is amber like on the plate.
  const info = [
    { label: "X", unit: "mm", value: fmt(last?.x_mm), color: "text-ink" },
    { label: "Y", unit: "mm", value: fmt(last?.y_mm), color: "text-ink" },
    { label: "Setpoint", unit: "mm", value: `${fmt(last?.sp_x_mm)}, ${fmt(last?.sp_y_mm)}`, color: "text-focus" },
    { label: "Tilt", unit: "°", value: `${fmt(last?.u_x_deg)}, ${fmt(last?.u_y_deg)}`, color: "text-ink" },
  ];

  return (
    <figure className="-mx-4 border-y border-line bg-panel sm:mx-0 sm:border">
      {/* the image area, with the 4 corner brackets on top (.brackets).
          The text rows are pushed in (px-7) so they never touch a bracket. */}
      <div className="brackets relative px-3 py-5 sm:px-4">
        <div className="flex items-center justify-between px-7">
          <StatusPill connected={connected} />
          <span className="font-mono text-xs text-muted">
            TC <span className="text-ink">{last ? timecode(last.t_ms) : "--:--.-"}</span>
          </span>
        </div>

        <svg
          viewBox="-160 -160 320 320"
          role="img"
          aria-label="Plate seen from the camera: ball position, its trail, the setpoint and the error between them"
          className="mx-auto my-3 block w-full max-w-[560px]"
        >
          {/* plate outline, 30 mm grid and centre cross */}
          <rect x={-HALF} y={-HALF} width={2 * HALF} height={2 * HALF} fill="none" stroke="var(--muted)" strokeWidth="0.75" opacity="0.5" />
          {GRID.map((g) => (
            <g key={g} stroke="var(--line)" strokeWidth="0.75">
              <line x1={g} y1={-HALF} x2={g} y2={HALF} />
              <line x1={-HALF} y1={g} x2={HALF} y2={g} />
            </g>
          ))}
          <g stroke="var(--muted)" strokeWidth="0.75" opacity="0.5">
            <line x1={-HALF} y1="0" x2={HALF} y2="0" />
            <line x1="0" y1={-HALF} x2="0" y2={HALF} />
          </g>
          <g className="font-mono" fontSize="8" fill="var(--muted)">
            <text x={HALF - 6} y="-5" textAnchor="end">+X</text>
            <text x="5" y={-HALF + 12}>+Y</text>
          </g>

          {!last && (
            <text x="0" y="4" textAnchor="middle" className="font-mono" fontSize="11" letterSpacing="2" fill="var(--muted)">
              NO SIGNAL
            </text>
          )}

          {last && (
            <>
              {/* trail, like a long exposure: older samples are smaller and fainter */}
              {trail.map((s, i) => (
                <circle key={s.t_ms} cx={s.x_mm} cy={-s.y_mm} r={1 + (3 * i) / TRAIL} fill="var(--ink)" opacity={(0.35 * i) / TRAIL} />
              ))}

              <Reticle x={last.sp_x_mm} y={last.sp_y_mm} />
              <ErrorLine sample={last} />
              <FocusBox sample={last} />
            </>
          )}
        </svg>

        <div className="flex justify-between px-7 font-mono text-[11px] text-muted">
          <span>Plate {2 * PLATE_HALF_MM} × {2 * PLATE_HALF_MM} mm</span>
          <span>Grid {GRID_MM} mm</span>
        </div>
      </div>

      {/* info bar: 4 cells in a row, 2 x 2 on phones (gap-px + bg-line draws the lines between them) */}
      <dl className="grid grid-cols-2 gap-px border-t border-line bg-line sm:grid-cols-4">
        {info.map((cell) => (
          <div key={cell.label} className="min-w-0 bg-panel px-4 py-3 sm:px-5">
            <dt className="label">
              {cell.label} <span className="tracking-normal normal-case">{cell.unit}</span>
            </dt>
            <dd className={`mt-1 font-mono text-lg tracking-tight sm:text-2xl ${cell.color}`}>{cell.value}</dd>
          </div>
        ))}
      </dl>
    </figure>
  );
}

// The setpoint: an amber ring with 4 ticks pointing at its centre.
function Reticle({ x, y }: { x: number; y: number }) {
  return (
    <g stroke="var(--focus)" strokeWidth="1.5" fill="none" transform={`translate(${x} ${-y})`}>
      <circle r="10" />
      <line x1="-18" y1="0" x2="-6" y2="0" />
      <line x1="6" y1="0" x2="18" y2="0" />
      <line x1="0" y1="-18" x2="0" y2="-6" />
      <line x1="0" y1="6" x2="0" y2="18" />
    </g>
  );
}

// The error e = distance from ball to setpoint: a dashed amber line with its length
// written in the middle. Hidden when the ball is close (the boxes would overlap).
function ErrorLine({ sample }: { sample: Sample }) {
  const ex = sample.sp_x_mm - sample.x_mm;
  const ey = sample.sp_y_mm - sample.y_mm;
  const e = Math.hypot(ex, ey);
  if (e < 30) return null;

  // Start at the edge of the focus box and stop at the edge of the reticle, not in the centres.
  const startX = sample.x_mm + (ex / e) * 14;
  const startY = sample.y_mm + (ey / e) * 14;
  const endX = sample.sp_x_mm - (ex / e) * 12;
  const endY = sample.sp_y_mm - (ey / e) * 12;
  const midX = (sample.x_mm + sample.sp_x_mm) / 2;
  const midY = (sample.y_mm + sample.sp_y_mm) / 2;

  return (
    <g>
      <line x1={startX} y1={-startY} x2={endX} y2={-endY} stroke="var(--focus)" strokeWidth="1" strokeDasharray="3 3" />
      {/* the dark outline (paint-order stroke) keeps the text readable on top of the line */}
      <text x={midX} y={-midY + 3} textAnchor="middle" className="font-mono" fontSize="9" fill="var(--focus)" stroke="var(--panel)" strokeWidth="4" paintOrder="stroke">
        e {e.toFixed(1)}
      </text>
    </g>
  );
}

// The ball inside an amber focus box. The box and its label move together in one group.
// When the ball is on the setpoint the box closes in and says LOCK.
// ponytail: no CSS transition here. Samples arrive faster than the screen redraws, so a
// transition restarts before it moves and the ball gets stuck behind its real position.
// The label sits on the side away from the plate edge, so it never leaves the image.
function FocusBox({ sample }: { sample: Sample }) {
  const locked = Math.hypot(sample.sp_x_mm - sample.x_mm, sample.sp_y_mm - sample.y_mm) < LOCK_MM;
  const sx = sample.x_mm > 40 ? -1 : 1; // near the right edge: label on the left
  const sy = sample.y_mm > 110 ? 1 : -1; // near the top edge: label below

  return (
    <g transform={`translate(${sample.x_mm} ${-sample.y_mm})`}>
      {/* 4 corners of the box; scale() pulls them in when locked */}
      <g transform={`scale(${locked ? 0.75 : 1})`} stroke="var(--focus)" strokeWidth="1.5" fill="none">
        <path d="M-14 -8V-14H-8 M8 -14H14V-8 M14 8V14H8 M-8 14H-14V8" />
      </g>
      <text
        x={sx * 18}
        y={sy > 0 ? 26 : -18}
        textAnchor={sx > 0 ? "start" : "end"}
        className="font-mono"
        fontSize="8.5"
        fill={locked ? "var(--focus)" : "var(--ink)"}
        stroke="var(--panel)"
        strokeWidth="3"
        paintOrder="stroke"
      >
        {locked ? "LOCK  " : ""}x {fmt(sample.x_mm)}
        <tspan dx="8">y {fmt(sample.y_mm)}</tspan>
      </text>
      <circle r="6.5" fill="var(--ink)" className="glow" />
    </g>
  );
}
