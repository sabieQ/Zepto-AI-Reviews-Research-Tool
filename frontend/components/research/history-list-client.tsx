"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import {
  ConfidenceBadge,
  ReportStatusBadge,
} from "@/components/research/report-badges";
import { Button } from "@/components/ui/button";
import { deleteReport, formatApiError, listDatasets, listReports } from "@/lib/api";
import { useMemo, useState } from "react";

function truncate(text: string, n = 100) {
  const t = text.trim();
  return t.length <= n ? t : `${t.slice(0, n)}…`;
}

export function HistoryListClient() {
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);

  const reports = useQuery({
    queryKey: ["reports"],
    queryFn: async () => {
      const res = await listReports();
      if (!res.success) throw new Error(res.message);
      return res.data;
    },
    refetchInterval: (q) =>
      q.state.data?.some((r) => r.status === "running" || r.status === "pending")
        ? 4000
        : false,
  });

  const datasets = useQuery({
    queryKey: ["datasets"],
    queryFn: async () => {
      const res = await listDatasets();
      if (!res.success) throw new Error(res.message);
      return res.data;
    },
  });

  const nameById = useMemo(() => {
    const map = new Map<string, string>();
    for (const d of datasets.data ?? []) map.set(d.id, d.name);
    return map;
  }, [datasets.data]);

  const remove = useMutation({
    mutationFn: async (id: string) => {
      const res = await deleteReport(id);
      if (!res.success) throw new Error(res.message);
      return res.data;
    },
    onSuccess: async () => {
      setError(null);
      await queryClient.invalidateQueries({ queryKey: ["reports"] });
    },
    onError: (err) => setError(formatApiError(err)),
  });

  return (
    <div className="space-y-6">
      <header>
        <h2 className="text-2xl font-semibold tracking-tight">History</h2>
        <p className="mt-1 text-sm text-zinc-600">
          Past research runs — including failed attempts with error details.
        </p>
      </header>

      {error ? <p className="text-sm text-red-600">{error}</p> : null}
      {reports.isError ? (
        <p className="text-sm text-red-600">{formatApiError(reports.error)}</p>
      ) : null}
      {reports.isLoading ? (
        <p className="text-sm text-zinc-500">Loading reports…</p>
      ) : null}

      {reports.isSuccess && reports.data.length === 0 ? (
        <div className="rounded-lg border border-dashed border-zinc-300 bg-zinc-50 px-4 py-10 text-center">
          <p className="text-sm font-medium text-zinc-800">No reports yet</p>
          <p className="mt-1 text-sm text-zinc-500">
            Run a question from{" "}
            <Link href="/research" className="text-violet-700 hover:underline">
              Research
            </Link>
            .
          </p>
        </div>
      ) : null}

      {reports.isSuccess && reports.data.length > 0 ? (
        <div className="overflow-x-auto rounded-lg border border-zinc-200">
          <table className="min-w-full text-left text-sm">
            <thead className="border-b border-zinc-200 bg-zinc-50 text-xs uppercase text-zinc-500">
              <tr>
                <th className="px-3 py-2 font-medium">Question</th>
                <th className="px-3 py-2 font-medium">Dataset</th>
                <th className="px-3 py-2 font-medium">Status</th>
                <th className="px-3 py-2 font-medium">Confidence</th>
                <th className="px-3 py-2 font-medium">Created</th>
                <th className="px-3 py-2 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {reports.data.map((r) => (
                <tr key={r.id} className="border-b border-zinc-100">
                  <td className="max-w-xs px-3 py-2">
                    <Link
                      href={`/history/${r.id}`}
                      className="font-medium text-violet-700 hover:underline"
                      title={r.question_text}
                    >
                      {truncate(r.question_text)}
                    </Link>
                  </td>
                  <td className="px-3 py-2 text-zinc-600">
                    {nameById.get(r.dataset_id) ?? r.dataset_id.slice(0, 8)}
                  </td>
                  <td className="px-3 py-2">
                    <ReportStatusBadge status={r.status} />
                  </td>
                  <td className="px-3 py-2">
                    <ConfidenceBadge value={r.confidence} />
                  </td>
                  <td className="px-3 py-2 text-zinc-500">
                    {r.created_at
                      ? new Date(r.created_at).toLocaleString()
                      : "—"}
                  </td>
                  <td className="px-3 py-2">
                    <Button
                      type="button"
                      variant="ghost"
                      className="text-red-600"
                      disabled={remove.isPending}
                      onClick={() => {
                        if (confirm("Delete this report?")) remove.mutate(r.id);
                      }}
                    >
                      Delete
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  );
}
