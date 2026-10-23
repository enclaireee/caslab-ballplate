"use client";

import { useEffect, useState } from "react";
import { API, parseCsv } from "../config";
import type { Axis, Sample } from "../config";
import { findSteps, stepMetrics } from "../stepResponse";
import LineChart from "../components/LineChart";
import Section from "../components/Section";
import PageTitle from "../components/PageTitle";
import StepTable from "../components/StepTable";

// Runs page ("playback"): a list of saved CSVs (the clips) on the left,
// the whole run and the step metrics of the one you click on the right.
export default function RunsPage() {
  const [runs, setRuns] = useState<string[]>([]);
  const [selected, setSelected] = useState("");
  const [axis, setAxis] = useState<Axis>("x");
  const [samples, setSamples] = useState<Sample[]>([]);
  const [error, setError] = useState(false);
  const [reload, setReload] = useState(0); // change it to re-fetch the list

  // Load the list of runs (again whenever Refresh is pressed).
  useEffect(() => {
    fetch(`${API}/runs`)
      .then((res) => res.json())
      .then((names: string[]) => {
        setRuns(names);
        setError(false);
        setSelected((old) => (names.includes(old) ? old : (names[0] ?? "")));
      })
      .catch(() => setError(true));
  }, [reload]);

  // Load the CSV of the selected run.
  useEffect(() => {
    if (selected === "") return;
    fetch(`${API}/runs/${selected}`)
      .then((res) => res.text())
      .then((text) => setSamples(parseCsv(text)))
      .catch(() => setError(true));
  }, [selected, reload]);

  const steps = findSteps(samples, axis);
  const rows = steps.map((step) => stepMetrics(samples, step, axis));

  return (
    <div className="flex flex-col gap-8 sm:gap-12">
      <PageTitle title="Runs">
        Every run datalog.py saved. Pick one to see the whole run; the step table fills in when the setpoint changes
        during a run.
      </PageTitle>

      {error && (
        <p role="alert" className="border-l-[3px] border-rec pl-3 text-rec">
          Cannot reach datalog.py. Start it in Terminal 1, then press Refresh.
        </p>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12 lg:gap-8">
        {/* the run index: one row per saved CSV */}
        <nav aria-label="Saved runs" className="lg:col-span-3">
          <div className="flex items-center justify-between border-b border-muted pb-2">
            <h2 className="label text-ink">Clips · {runs.length} runs</h2>
            <button className="btn min-h-9 border-0 px-2" onClick={() => setReload(reload + 1)}>
              Refresh
            </button>
          </div>
          <ol className="max-h-72 overflow-y-auto lg:max-h-[32rem]">
            {runs.map((name, i) => (
              <li key={name}>
                <button
                  onClick={() => setSelected(name)}
                  aria-current={name === selected ? "true" : undefined}
                  className={`flex min-h-11 w-full items-center gap-3 border-b border-line px-2 text-left font-mono text-sm transition-colors ${
                    name === selected ? "bg-focus/10 text-focus" : "hover:bg-ink/[0.03]"
                  }`}
                >
                  {/* the selected clip gets a play mark instead of its number */}
                  <span className={`w-5 ${name === selected ? "" : "text-muted"}`}>{name === selected ? "▶" : String(i + 1).padStart(2, "0")}</span>
                  <span className="min-w-0 truncate">{name}</span>
                </button>
              </li>
            ))}
          </ol>
          {runs.length === 0 && !error && (
            <p className="py-4 text-sm text-muted">
              No runs yet. Start <code className="font-mono text-ink">.venv\Scripts\python esp\datalog.py run1</code> and
              let it run for a few seconds.
            </p>
          )}
        </nav>

        <div className="flex min-w-0 flex-col gap-6 lg:col-span-9 lg:gap-8">
          {/* toolbar: X/Y switch and download */}
          <div className="flex flex-wrap items-center gap-3">
            <div className="inline-flex border border-muted" role="group" aria-label="Axis">
              {(["x", "y"] as Axis[]).map((a) => (
                <button
                  key={a}
                  aria-pressed={axis === a}
                  onClick={() => setAxis(a)}
                  className={`min-h-11 min-w-14 font-mono text-sm transition-colors ${
                    axis === a ? "bg-focus text-bg" : "text-muted hover:text-ink"
                  }`}
                >
                  {a.toUpperCase()}
                </button>
              ))}
            </div>
            {selected !== "" && (
              <a href={`${API}/runs/${selected}`} download className="btn sm:ml-auto">
                Download CSV
              </a>
            )}
          </div>

          <Section title={`${axis.toUpperCase()} position · whole run`}>
            <LineChart samples={samples} yKey={axis === "x" ? "x_mm" : "y_mm"} spKey={axis === "x" ? "sp_x_mm" : "sp_y_mm"} />
          </Section>
          <Section title={`Step response · ${axis.toUpperCase()}`}>
            {rows.length === 0 ? (
              <p className="text-sm text-muted">This run has no setpoint change on {axis.toUpperCase()}.</p>
            ) : (
              <StepTable rows={rows} />
            )}
          </Section>
        </div>
      </div>
    </div>
  );
}
