import type { Metadata } from "next";
import Link from "next/link";
import PageTitle from "./components/PageTitle";

export const metadata: Metadata = {
  title: "No signal · Ball & Plate dashboard",
};

// 404 page: an empty viewfinder, like a camera with nothing plugged in.
export default function NotFound() {
  return (
    <div className="flex flex-col gap-8 sm:gap-12">
      <PageTitle title="No signal">This address shows nothing. The dashboard has three pages; pick one below.</PageTitle>
      <div className="brackets relative -mx-4 flex aspect-video items-center justify-center border-y border-line bg-panel sm:mx-0 sm:border">
        <p className="font-mono text-sm tracking-[0.3em] text-muted">NO SIGNAL · 404</p>
      </div>
      <div className="flex flex-wrap gap-3">
        <Link href="/" className="btn">Live</Link>
        <Link href="/runs" className="btn">Runs</Link>
        <Link href="/how-to-run" className="btn">Setup</Link>
      </div>
    </div>
  );
}
