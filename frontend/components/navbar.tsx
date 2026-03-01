"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const navItems = [
  { href: "/", label: "Home" },
  { href: "/builder", label: "Create" },
  { href: "/agents", label: "My Agents" },
];

export function Navbar() {
  const pathname = usePathname();

  return (
    <nav className="relative z-10 mb-10 flex items-center text-lg text-zinc-900 sm:text-xl">
      {navItems.map((item, idx) => {
        const active =
          item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
        return (
          <Link
            key={item.href}
            href={item.href}
            className={`mr-6 font-medium transition ${
              active
                ? "text-zinc-900 underline decoration-[var(--color-primary)] decoration-2 underline-offset-4"
                : "text-zinc-600 hover:text-zinc-900"
            } ${idx === navItems.length - 1 ? "mr-0" : ""}`}
          >
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}
