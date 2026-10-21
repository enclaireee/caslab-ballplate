import type { Metadata } from "next";
import PageTitle from "../components/PageTitle";
import Terminal from "../components/Terminal";

export const metadata: Metadata = {
  title: "How to run · Ball & Plate dashboard",
};

// What runs where, from the hardware to your screen.
const flow = [
  { name: "ESP32", detail: "PID + servos, USB serial at 115200 baud" },
  { name: "datalog.py", detail: "Terminal 1, saves CSV, port 8000" },
  { name: "dashboard", detail: "Terminal 2, port 3000" },
  { name: "browser", detail: "localhost:3000, this page" },
];

// When something doesn't work.
const problems = [
  {
    problem: "Waiting for datalog.py",
    fix: <>Terminal 1 is not running. Start step 2 again.</>,
  },
  {
    problem: "Address already in use",
    fix: (
      <>
        An old datalog.py still holds port 8000. Find its PID with <Code>lsof -i :8000</Code>, then stop it with{" "}
        <Code>kill PID</Code>.
      </>
    ),
  },
  {
    problem: "No ESP32 found",
    fix: (
      <>
        The board is not plugged in, or another program holds the port. Close the Arduino Serial Monitor, then try
        again. If it still fails, pass the port: <Code>--port /dev/cu.usbserial-0001</Code>.
      </>
    ),
  },
  {
    problem: "No runs in the list",
    fix: <>Nothing saved yet. Let datalog.py run for a few seconds, then press Refresh.</>,
  },
];

// Small helpers so the text below stays readable.
function Code({ children }: { children: React.ReactNode }) {
  return <code className="font-mono text-[0.9em] text-ink">{children}</code>;
}
function Key({ children }: { children: React.ReactNode }) {
  return (
    <kbd className="border border-muted/50 bg-panel px-1.5 py-0.5 font-mono text-[0.85em] text-ink">
      {children}
    </kbd>
  );
}

// One step of the timeline: a numbered dot on the left, a line down to the next step.
function Step({
  n,
  title,
  when,
  last = false,
  children,
}: {
  n: string;
  title: string;
  when: string;
  last?: boolean;
  children: React.ReactNode;
}) {
  return (
    <li className="grid grid-cols-[2.5rem_minmax(0,1fr)] gap-x-4 sm:gap-x-6">
      <div className="flex flex-col items-center">
        <span className="flex h-10 w-10 shrink-0 items-center justify-center border border-focus font-mono text-sm text-focus">
          {n}
        </span>
        {!last && <span className="w-px flex-1 bg-line" aria-hidden="true" />}
      </div>
      <div className={`min-w-0 pt-1.5 ${last ? "" : "pb-14"}`}>
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <h2 className="text-xl font-medium tracking-tight">{title}</h2>
          <span className="label">{when}</span>
        </div>
        <div className="mt-2 flex flex-col gap-4">{children}</div>
      </div>
    </li>
  );
}

// How to run page: everything runs on this laptop from the terminal, nothing is deployed.
export default function HowToRunPage() {
  return (
    <div className="flex flex-col gap-8 sm:gap-12">
      <PageTitle title="Setup">
        Nothing is deployed. It all runs on this laptop: two terminals and one browser tab. Open every terminal in
        the project folder <Code>caslab-ballplate</Code>.
      </PageTitle>

      <div className="grid gap-12 lg:grid-cols-[minmax(0,1fr)_16rem] lg:gap-16">
        {/* Side panel: what runs where. On phones it sits above the steps. */}
        <aside className="lg:sticky lg:top-8 lg:order-last lg:self-start">
          <h2 className="label text-ink">What runs where</h2>
          <div className="relative mt-5">
            {/* the line between the dots: 3 gaps of 4rem (each item is h-16) */}
            <span className="absolute top-[7px] left-[5px] h-48 w-px bg-line" aria-hidden="true" />
            {/* a ball rolls down the line, like the data going from the ESP32 to the browser */}
            <span className="flow absolute top-[3px] left-[1px] h-48" aria-hidden="true">
              <span className="block h-[9px] w-[9px] rounded-full bg-ink" />
            </span>
            <ol>
              {flow.map((node) => (
                <li key={node.name} className="relative h-16 pl-7">
                  <span className="absolute top-[2px] left-0 h-[11px] w-[11px] rounded-full border border-ink bg-bg" />
                  <p className="font-mono text-sm leading-4">{node.name}</p>
                  <p className="mt-1 text-xs text-muted">{node.detail}</p>
                </li>
              ))}
            </ol>
          </div>
          <p className="mt-2 border-t border-line pt-4 text-sm text-muted">
            To stop everything, press <Key>Ctrl</Key> + <Key>C</Key> in both terminals.
          </p>
        </aside>

        <ol>
          <Step n="01" title="Set up" when="only once">
            <p className="text-muted">Makes a Python environment in .venv and installs the Python and dashboard packages.</p>
            <Terminal
              title="Terminal"
              commands={[
                "python3 -m venv .venv",
                ".venv/bin/pip install -r requirements.txt",
                "cd data_logging/dashboard && npm install && cd ../..",
              ]}
              note={
                <>
                  From now on use <Code>.venv/bin/python</Code> instead of <Code>python3</Code>, so the installed
                  packages are found.
                </>
              }
            />
          </Step>

          <Step n="02" title="Start the logger and the dashboard" when="every time">
            <p className="text-muted">Two terminals. Keep both open while you work.</p>
            <Terminal
              title="Terminal 1 · logger"
              running
              commands={[".venv/bin/python esp/datalog.py run1"]}
              note={
                <>
                  Saves every sample to <Code>data_logging/runs/run1.csv</Code>. Leave out the name and it uses the
                  date and time. No hardware yet? Add <Code>--mock</Code> after the name: the fake ESP32 runs the same
                  PID on a simulated ball.
                </>
              }
            />
            <Terminal
              title="Terminal 2 · dashboard"
              running
              commands={["cd data_logging/dashboard", "npm run dev"]}
              note={
                <>
                  Then open <Code>http://localhost:3000</Code>. The Live page turns green when data arrives.
                </>
              }
            />
          </Step>

          <Step n="03" title="Set up the camera" when="optional">
            <p className="text-muted">
              Shows what the camera sees. Press <Key>p</Key> and drag a box over the plate, slide the threshold until
              only the ball is white, then press <Key>q</Key> to save.
            </p>
            <Terminal
              title="Terminal"
              commands={[".venv/bin/python vision/vision.py"]}
              note="Mac: if no camera window opens, allow your terminal in System Settings → Privacy & Security → Camera."
            />
          </Step>

          <Step n="04" title="Flash the ESP32" when="once per board" last>
            <p className="text-muted">
              Arduino IDE: board <Code>ESP32 Dev Module</Code>, install the <Code>ESP32Servo</Code> library (Library
              Manager), then open <Code>esp/esp.ino</Code>. The other three files (<Code>pid.ino</Code>,{" "}
              <Code>plate.ino</Code>, <Code>pid.h</Code>) open as tabs next to it, so keep them in the same folder.
              Press Upload.
            </p>
            <Terminal
              title="Terminal 1 · real rig"
              commands={[".venv/bin/python esp/datalog.py run1"]}
              note={
                <>
                  Without <Code>--mock</Code> the logger opens the camera and sends <Code>pos x y</Code> to the board
                  once per frame. The USB port is found automatically; add <Code>--port /dev/cu.usbserial-0001</Code>{" "}
                  if it picks the wrong one. Type <Code>sp 50 0</Code> in this terminal to move the setpoint.
                </>
              }
            />
          </Step>
        </ol>
      </div>

      <section>
        <h2 className="label text-ink">If something doesn&apos;t work</h2>
        <dl className="mt-3 divide-y divide-line border-y border-muted">
          {problems.map((p) => (
            <div key={p.problem} className="grid gap-1 py-4 sm:grid-cols-[16rem_minmax(0,1fr)] sm:gap-8">
              <dt className="font-mono text-sm text-focus">{p.problem}</dt>
              <dd className="text-muted">{p.fix}</dd>
            </div>
          ))}
        </dl>
      </section>
    </div>
  );
}
