"use client";

import { useEffect, useState } from "react";
import { API } from "./config";
import type { Sample } from "./config";

const KEEP = 500; // 10 s at 50 samples per second

// Opens the live stream and returns the last 500 samples + connection state.
export default function useLiveData() {
  const [samples, setSamples] = useState<Sample[]>([]);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    const source = new EventSource(`${API}/stream`);
    source.onopen = () => setConnected(true);
    source.onerror = () => setConnected(false); // browser retries by itself
    source.onmessage = (event) => {
      const sample: Sample = JSON.parse(event.data);
      setConnected(true);
      setSamples((old) => [...old, sample].slice(-KEEP));
    };
    // Close the stream when the page is left.
    return () => source.close();
  }, []);

  return { samples, connected };
}
