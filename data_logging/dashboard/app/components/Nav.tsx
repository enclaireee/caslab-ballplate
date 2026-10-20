"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const links = [
  { href: "/", label: "Live" },
  { href: "/runs", label: "Runs" },
  { href: "/how-to-run", label: "Setup" },
];

// The tabs; the one that matches the current URL gets an amber line under it.
// On phones the tabs share the full width; on bigger screens they sit on the right.
export default function Nav() {
  const pathname = usePathname();

  return (
    <nav aria-label="Main" className="flex border-t border-line sm:border-t-0">
      {links.map((link) => {
        const active = pathname === link.href;
        return (
          <Link
            key={link.href}
            href={link.href}
            aria-current={active ? "page" : undefined}
            className={`flex min-h-12 flex-1 items-center justify-center border-b-2 px-5 font-cond text-sm font-semibold tracking-[0.14em] uppercase transition-colors sm:flex-none ${
              active ? "border-focus text-ink" : "border-transparent text-muted hover:text-ink"
            }`}
          >
            {link.label}
          </Link>
        );
      })}
    </nav>
  );
}
