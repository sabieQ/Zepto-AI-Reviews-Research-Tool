"use client";

import { cn } from "@/lib/utils";

const STYLES: Record<string, string> = {
  completed: "bg-emerald-50 text-emerald-800 border-emerald-200",
  failed: "bg-red-50 text-red-800 border-red-200",
  running: "bg-amber-50 text-amber-900 border-amber-200",
  pending: "bg-zinc-100 text-zinc-700 border-zinc-200",
};

export function ReportStatusBadge({ status }: { status: string }) {
  return (
    <span
      className={cn(
        "inline-flex rounded-full border px-2 py-0.5 text-xs font-medium capitalize",
        STYLES[status] ?? "bg-zinc-100 text-zinc-700 border-zinc-200",
      )}
    >
      {status}
    </span>
  );
}

export function ConfidenceBadge({ value }: { value: string | null }) {
  if (!value) return <span className="text-xs text-zinc-400">—</span>;
  const tone =
    value === "high"
      ? "text-emerald-700"
      : value === "medium"
        ? "text-amber-700"
        : "text-zinc-600";
  return <span className={cn("text-xs font-medium capitalize", tone)}>{value}</span>;
}
