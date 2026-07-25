"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Database,
  History,
  LayoutDashboard,
  Search,
  Settings,
} from "lucide-react";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/datasets", label: "Datasets", icon: Database },
  { href: "/research", label: "Research", icon: Search },
  { href: "/history", label: "History", icon: History },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="flex w-56 shrink-0 flex-col border-r border-zinc-200 bg-zinc-50">
      <div className="border-b border-zinc-200 px-4 py-5">
        <p className="text-xs font-semibold uppercase tracking-wider text-violet-700">
          Zepto
        </p>
        <h1 className="mt-1 text-sm font-semibold text-zinc-900 leading-snug">
          AI Product Research
        </h1>
      </div>
      <nav className="flex flex-1 flex-col gap-1 p-3">
        {NAV.map(({ href, label, icon: Icon }) => {
          const active =
            href === "/" ? pathname === "/" : pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors",
                active
                  ? "bg-violet-100 text-violet-900 font-medium"
                  : "text-zinc-600 hover:bg-zinc-100 hover:text-zinc-900",
              )}
            >
              <Icon className="h-4 w-4 shrink-0" />
              {label}
            </Link>
          );
        })}
      </nav>
      <p className="px-4 py-3 text-[11px] text-zinc-400">Phase 6 · Ship</p>
    </aside>
  );
}
