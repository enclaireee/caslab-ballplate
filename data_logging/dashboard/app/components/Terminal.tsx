import Command from "./Command";

// A terminal window: a title bar, one line per command, and an optional note under it.
// "running" adds a blinking red dot (like REC) for terminals that stay open while you work.
export default function Terminal({
  title,
  commands,
  note,
  running = false,
}: {
  title: string;
  commands: string[];
  note?: React.ReactNode;
  running?: boolean;
}) {
  return (
    <figure className="min-w-0 overflow-hidden border border-line bg-panel">
      <figcaption className="flex items-center justify-between gap-3 border-b border-line px-4 py-2.5">
        <span className="flex items-center gap-2 text-sm">
          {running && <span className="blink h-2 w-2 rounded-full bg-rec" aria-hidden="true" />}
          {title}
        </span>
        <span className="hidden font-mono text-xs text-muted sm:inline">caslab-ballplate/</span>
      </figcaption>
      <div className="py-1.5">
        {commands.map((command) => (
          <Command key={command} text={command} />
        ))}
      </div>
      {note && <p className="border-t border-line px-4 py-3 text-sm text-muted [&_code]:text-ink">{note}</p>}
    </figure>
  );
}
