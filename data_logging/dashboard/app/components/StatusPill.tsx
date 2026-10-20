// Connection status, like a camera's record light:
// blinking red dot + "REC" while data comes in, grey "No signal" when datalog.py is not running.
export default function StatusPill({ connected }: { connected: boolean }) {
  return (
    <span role="status" className="inline-flex items-center gap-2 font-mono text-xs tracking-wider uppercase">
      <span className={`h-2.5 w-2.5 rounded-full ${connected ? "blink bg-rec" : "bg-muted"}`} />
      {connected ? "REC" : "No signal"}
    </span>
  );
}
