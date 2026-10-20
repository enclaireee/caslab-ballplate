"use client";

import LineChart from "./components/LineChart";
import PageTitle from "./components/PageTitle";
import PlateView from "./components/PlateView";
import Section from "./components/Section";
import useLiveData from "./useLiveData";

// Live page: the camera's view of the plate on the left (with the newest numbers
// in its info bar), and the X and Y position over the last 10 seconds on the right.
export default function LivePage() {
  const { samples, connected } = useLiveData();

  return (
    <div className="flex flex-col gap-8 sm:gap-12">
      <PageTitle title="Live">
        What the tracking camera sees right now. The amber box locks onto the ball; the amber ring is where the PID
        wants it.
      </PageTitle>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12 lg:gap-8">
        <div className="min-w-0 lg:col-span-8">
          <PlateView samples={samples} connected={connected} />
        </div>

        <div className="flex min-w-0 flex-col gap-6 lg:col-span-4 lg:gap-8">
          <Section title="X position · last 10 s">
            <LineChart samples={samples} yKey="x_mm" spKey="sp_x_mm" />
          </Section>
          <Section title="Y position · last 10 s">
            <LineChart samples={samples} yKey="y_mm" spKey="sp_y_mm" />
          </Section>
        </div>
      </div>
    </div>
  );
}
