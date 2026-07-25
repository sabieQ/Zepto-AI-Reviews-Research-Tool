import { cn } from "@/lib/utils";

const STATUS_STYLES: Record<string, string> = {
  pending: "bg-zinc-100 text-zinc-700",
  processing: "bg-amber-100 text-amber-900",
  imported: "bg-sky-100 text-sky-900",
  indexing: "bg-violet-100 text-violet-900",
  ready: "bg-emerald-100 text-emerald-900",
  failed: "bg-red-100 text-red-900",
};

export function StatusBadge({ status }: { status: string }) {
  return (
    <span
      className={cn(
        "inline-flex rounded-full px-2 py-0.5 text-xs font-medium capitalize",
        STATUS_STYLES[status] ?? "bg-zinc-100 text-zinc-700",
      )}
    >
      {status}
    </span>
  );
}
