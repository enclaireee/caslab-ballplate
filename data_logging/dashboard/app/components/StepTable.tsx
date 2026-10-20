import type { StepResult } from "../stepResponse";

// A number with 2 decimals, or "--" if it was never reached.
function fmt(n: number | null) {
  return n === null ? "--" : n.toFixed(2);
}

const head = ["Step mm", "Rise s", "Overshoot %", "Settling s", "SS error mm"];
const cell = "border-l border-line px-3"; // every cell except the first

// Data table: one row per setpoint step.
// Overshoot is printed bigger, it is the number people ask about first.
export default function StepTable({ rows }: { rows: StepResult[] }) {
  return (
    <div className="overflow-x-auto" tabIndex={0}>
      <table className="w-full border-collapse text-left font-mono text-sm">
        <thead>
          <tr className="border-y border-muted">
            {head.map((h) => (
              <th key={h} scope="col" className="label border-l border-line px-3 py-2 font-semibold whitespace-nowrap text-ink first:border-l-0 first:pl-0">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className="border-b border-line transition-colors hover:bg-ink/[0.03]">
              <td className="py-3 pr-3 whitespace-nowrap">
                {r.from} <span className="text-focus">→ {r.to}</span>
              </td>
              <td className={cell}>{fmt(r.riseS)}</td>
              <td className={`${cell} text-2xl tracking-tight`}>{fmt(r.overshootPct)}</td>
              <td className={cell}>{fmt(r.settlingS)}</td>
              <td className={cell}>{fmt(r.sseMm)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
