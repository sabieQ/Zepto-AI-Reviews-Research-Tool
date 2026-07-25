"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { HealthStatus } from "@/components/dashboard/health-status";
import {
  ConfidenceBadge,
  ReportStatusBadge,
} from "@/components/research/report-badges";
import { formatApiError, listDatasets, listReports } from "@/lib/api";

function truncate(text: string, n = 80) {
  const t = text.trim();
  return t.length <= n ? t : `${t.slice(0, n)}…`;
}

export function DashboardClient() {
  const datasets = useQuery({
    queryKey: ["datasets"],
    queryFn: async () => {
      const res = await listDatasets();
      if (!res.success) throw new Error(res.message);
      return res.data;
    },
  });

  const reports = useQuery({
    queryKey: ["reports"],
    queryFn: async () => {
      const res = await listReports();
      if (!res.success) throw new Error(res.message);
      return res.data;
    },
  });

  const totalDatasets = datasets.data?.length ?? 0;
  const readyCount =
    datasets.data?.filter((d) => d.status === "ready").length ?? 0;
  const conversations =
    datasets.data?.reduce((sum, d) => sum + (d.conversation_count || 0), 0) ??
    0;
  const recent = (reports.data ?? []).slice(0, 5);

  return (
    <div className="space-y-6">
      <header>
        <h2 className="text-2xl font-semibold tracking-tight">Dashboard</h2>
        <p className="mt-1 text-sm text-zinc-600">
          Overview of datasets and recent research.
        </p>
      </header>

      <HealthStatus />

      {(datasets.isError || reports.isError) && (
        <p className="text-sm text-red-600">
          {formatApiError(datasets.error ?? reports.error)}
        </p>
      )}

      <section className="grid gap-4 sm:grid-cols-4">
        {[
          { label: "Datasets", value: datasets.isLoading ? "…" : totalDatasets },
          {
            label: "Ready",
            value: datasets.isLoading ? "…" : readyCount,
          },
          {
            label: "Conversations",
            value: datasets.isLoading ? "…" : conversations,
          },
          {
            label: "Reports",
            value: reports.isLoading ? "…" : (reports.data?.length ?? 0),
          },
        ].map((card) => (
          <div
            key={card.label}
            className="rounded-lg border border-zinc-200 bg-zinc-50 px-4 py-5"
          >
            <p className="text-xs font-medium uppercase tracking-wide text-zinc-500">
              {card.label}
            </p>
            <p className="mt-2 text-2xl font-semibold text-zinc-900">
              {card.value}
            </p>
          </div>
        ))}
      </section>

      <div className="flex flex-wrap gap-3 text-sm">
        <Link
          href="/datasets"
          className="rounded-md bg-violet-600 px-3 py-2 font-medium text-white hover:bg-violet-700"
        >
          Manage datasets
        </Link>
        <Link
          href="/research"
          className="rounded-md border border-zinc-300 px-3 py-2 font-medium text-zinc-800 hover:bg-zinc-50"
        >
          Run research
        </Link>
      </div>

      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-zinc-900">Recent reports</h3>
          <Link href="/history" className="text-xs text-violet-700 hover:underline">
            View all
          </Link>
        </div>
        {reports.isSuccess && recent.length === 0 ? (
          <div className="rounded-lg border border-dashed border-zinc-300 bg-zinc-50 px-4 py-8 text-center text-sm text-zinc-500">
            No reports yet. Ask a free-form question on Research.
          </div>
        ) : null}
        {recent.length > 0 ? (
          <ul className="divide-y divide-zinc-100 rounded-lg border border-zinc-200">
            {recent.map((r) => (
              <li key={r.id} className="flex items-start justify-between gap-3 px-4 py-3">
                <div className="min-w-0">
                  <Link
                    href={`/history/${r.id}`}
                    className="text-sm font-medium text-violet-700 hover:underline"
                    title={r.question_text}
                  >
                    {truncate(r.question_text)}
                  </Link>
                  <p className="mt-1 text-xs text-zinc-500">
                    {r.created_at
                      ? new Date(r.created_at).toLocaleString()
                      : ""}
                  </p>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  <ConfidenceBadge value={r.confidence} />
                  <ReportStatusBadge status={r.status} />
                </div>
              </li>
            ))}
          </ul>
        ) : null}
      </section>
    </div>
  );
}
