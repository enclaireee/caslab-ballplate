import type { Metadata } from "next";
import { Barlow, Barlow_Condensed, Martian_Mono } from "next/font/google";
import Link from "next/link";
import Nav from "./components/Nav";
import "./globals.css";

// Barlow for text, Barlow Condensed for titles and labels, Martian Mono for numbers.
const barlow = Barlow({
  variable: "--font-barlow",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
});

const barlowCond = Barlow_Condensed({
  variable: "--font-barlow-cond",
  subsets: ["latin"],
  weight: ["600", "700"],
});

const martian = Martian_Mono({
  variable: "--font-martian",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Ball & Plate dashboard",
  description: "Live data and step responses of the Ball & Plate lab",
};

// Every page: a top bar (name + tabs), the page itself, and one line of facts at the bottom.
// No frame around the page, so phones use their full width.
export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${barlow.variable} ${barlowCond.variable} ${martian.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col">
        <a href="#main" className="btn sr-only bg-bg focus:not-sr-only focus:absolute focus:top-4 focus:left-4 focus:z-10">
          Skip to content
        </a>

        <header className="border-b border-line">
          <div className="mx-auto flex max-w-[1440px] flex-col sm:flex-row sm:items-stretch sm:justify-between sm:px-8">
            <Link href="/" className="flex min-h-14 items-center gap-3 px-4 sm:px-0">
              {/* logo: viewfinder corners around the ball */}
              <svg viewBox="0 0 20 20" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
                <path d="M1 6V1h5M14 1h5v5M19 14v5h-5M6 19H1v-5" />
                <circle cx="10" cy="10" r="3" fill="var(--focus)" stroke="none" />
              </svg>
              <span className="font-cond text-lg font-bold tracking-[0.08em] uppercase">Ball &amp; Plate</span>
            </Link>
            <Nav />
          </div>
        </header>

        <main id="main" className="mx-auto w-full max-w-[1440px] min-w-0 flex-1 px-4 py-8 sm:px-8 sm:py-12">
          {children}
        </main>

        <footer className="border-t border-line">
          <p className="mx-auto max-w-[1440px] px-4 py-4 font-mono text-xs leading-relaxed text-muted sm:px-8">
            Control Lab, task 4 · data from datalog.py on port 8000 · units mm, degrees, seconds
          </p>
        </footer>
      </body>
    </html>
  );
}
