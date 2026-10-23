import { TILT_DISPLAY_MAX_DEG, fmt } from "../config";
import type { Sample } from "../config";

// Marks on the track at half and full scale in both directions.
const TICKS = [-1, -0.5, 0, 0.5, 1].map((fraction) => fraction * TILT_DISPLAY_MAX_DEG);

// The commanded plate tilt, one bar per servo. The gauge stops at the display
// limit, so the few degrees the PID actually uses are easy to read.
export default function TiltMeter({ samples }: { samples: Sample[] }) {
  const last = samples.length > 0 ? samples[samples.length - 1] : null;
  const axes = [
    { name: "X", deg: last?.u_x_deg, color: "var(--ink)" },
    { name: "Y", deg: last?.u_y_deg, color: "var(--focus)" },
  ];

  return (
    <div className="flex flex-col gap-5">
      {axes.map((axis) => {
        const deg = axis.deg ?? 0;
        // Half the track is one limit, so a bar can never leave the track.
        const share = Math.min(Math.abs(deg) / TILT_DISPLAY_MAX_DEG, 1) * 50;

        return (
          <div key={axis.name}>
            <div className="flex items-baseline justify-between font-mono text-sm">
              <span className="text-muted">{axis.name}</span>
              <span className="text-ink">{fmt(axis.deg)}°</span>
            </div>
            <div
              role="img"
              aria-label={`${axis.name} tilt: ${fmt(axis.deg)} degrees`}
              className="relative mt-2 h-2 bg-line"
            >
              <span
                className="absolute top-0 h-full"
                style={{
                  left: `${deg >= 0 ? 50 : 50 - share}%`,
                  width: `${share}%`,
                  background: axis.color,
                }}
              />
              <span className="absolute top-0 left-1/2 h-full w-px bg-muted" />
            </div>
          </div>
        );
      })}

      <div className="flex justify-between font-mono text-[10px] text-muted">
        {TICKS.map((tick) => (
          <span key={tick}>{tick > 0 ? `+${tick}` : tick}°</span>
        ))}
      </div>
    </div>
  );
}
