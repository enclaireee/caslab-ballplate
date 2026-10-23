"use client";

import { useEffect, useState } from "react";
import { API, STALE_MS, parseCsv } from "./config";
import type { Sample } from "./config";

const POLL_MS = 500; // read the newest CSV twice a second
const KEEP = 500; // 10 s at 50 samples per second

// Polls datalog.py: the newest CSV is the run being written right now.
// Returns its last 500 samples and whether new data is still arriving.
export default function useLiveData() {
  const [samples, setSamples] = useState<Sample[]>([]);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    let alive = true;
    let busy = false; // never let two polls overlap
    let run = ""; // newest CSV we are following
    let lastBody = ""; // its text at the previous poll
    let lastChange = Date.now();

    async function poll() {
      if (busy) return;
      busy = true;
      try {
        const listRes = await fetch(`${API}/runs`, { cache: "no-store" });
        const names: string[] = await listRes.json();
        if (!Array.isArray(names) || names.length === 0) throw new Error("no runs");
        const newest = names[names.length - 1];

        // A different file = a new run, so drop the previous run's points.
        if (newest !== run) {
          run = newest;
          lastBody = "";
          lastChange = Date.now();
          if (alive) setSamples([]);
        }

        const bodyRes = await fetch(`${API}/runs/${newest}`, { cache: "no-store" });
        if (!bodyRes.ok) throw new Error("cannot read the newest CSV");
        const body = await bodyRes.text();
        if (!alive) return;

        // A changed body means the logger just wrote a new line.
        if (body !== lastBody) {
          lastBody = body;
          lastChange = Date.now();
          setSamples(parseCsv(body).slice(-KEEP));
          setConnected(true);
        } else if (Date.now() - lastChange > STALE_MS) {
          setConnected(false);
        }
      } catch {
        // datalog.py is not running (or has no runs yet).
        if (alive) setConnected(false);
      } finally {
        busy = false;
      }
    }

    poll();
    const timer = setInterval(poll, POLL_MS);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, []);

  return { samples, connected };
}
