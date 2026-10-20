"use client";

import { useState } from "react";

// One command line inside a Terminal, with a Copy button on the right.
export default function Command({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);

  function copy() {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500); // show "Copied" for 1.5 s
  }

  return (
    <div className="flex items-center gap-3 pr-1.5 pl-4 transition-colors hover:bg-ink/[0.03]">
      <code className="min-w-0 flex-1 py-2.5 font-mono text-sm break-words whitespace-pre-wrap">
        <span className="text-focus select-none">$ </span>
        {text}
      </code>
      <button
        onClick={copy}
        className={`flex min-h-11 shrink-0 items-center gap-1.5 px-3 font-mono text-xs transition-colors hover:text-ink ${
          copied ? "text-focus" : "text-muted"
        }`}
      >
        {/* two overlapping squares = "copy" */}
        <svg viewBox="0 0 16 16" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
          <rect x="5.5" y="5.5" width="8" height="8" rx="1.5" />
          <path d="M10.5 3.5v-1a1 1 0 0 0-1-1h-6a1 1 0 0 0-1 1v6a1 1 0 0 0 1 1h1" />
        </svg>
        {copied ? "Copied" : "Copy"}
      </button>
    </div>
  );
}
