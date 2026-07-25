"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { CreateDatasetForm } from "@/components/datasets/create-dataset-form";
import { ImportDialog } from "@/components/datasets/import-dialog";
import { StatusBadge } from "@/components/datasets/status-badge";
import { Button } from "@/components/ui/button";
import {
  deleteDataset,
  formatApiError,
  listCollectorRuns,
  listDatasets,
  reindexDataset,
  runCollectorsRefresh,
} from "@/lib/api";

export function DatasetsClient() {
  const queryClient = useQueryClient();
  const [importTarget, setImportTarget] = useState<{
    id: string;
    name: string;
  } | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [collectMsg, setCollectMsg] = useState<string | null>(null);

  const query = useQuery({
    queryKey: ["datasets"],
    queryFn: async () => {
      const res = await listDatasets();
      if (!res.success) throw new Error(res.message);
      return res.data;
    },
    refetchInterval: (q) =>
      q.state.data?.some((d) => d.status === "indexing" || d.status === "processing")
        ? 3000
        : false,
  });

  const runs = useQuery({
    queryKey: ["collector-runs"],
    queryFn: async () => {
      const res = await listCollectorRuns(5);
      if (!res.success) throw new Error(res.message);
      return res.data;
    },
  });

  const remove = useMutation({
    mutationFn: async (id: string) => {
      const res = await deleteDataset(id);
      if (!res.success) throw new Error(res.message);
      return res.data;
    },
    onSuccess: async () => {
      setActionError(null);
      await queryClient.invalidateQueries({ queryKey: ["datasets"] });
    },
    onError: (err) => setActionError(formatApiError(err)),
  });

  const reindex = useMutation({
    mutationFn: async (id: string) => {
      const res = await reindexDataset(id);
      if (!res.success) throw new Error(res.message);
      return res.data;
    },
    onSuccess: async () => {
      setActionError(null);
      await queryClient.invalidateQueries({ queryKey: ["datasets"] });
    },
    onError: (err) => setActionError(formatApiError(err)),
  });

  const refreshStores = useMutation({
    mutationFn: async () => {
      const res = await runCollectorsRefresh({
        limit: 100,
        auto_index: true,
      });
      if (!res.success) throw new Error(res.message);
      return res.data;
    },
    onSuccess: async (data) => {
      setActionError(null);
      setCollectMsg(
        `Refresh done: +${data.inserted} inserted, ${data.skipped} skipped` +
          (data.dataset
            ? ` → ${data.dataset.name} (${data.dataset.conversation_count} total, ${data.dataset.status})`
            : ""),
      );
      await queryClient.invalidateQueries({ queryKey: ["datasets"] });
      await queryClient.invalidateQueries({ queryKey: ["collector-runs"] });
    },
    onError: (err) => {
      setCollectMsg(null);
      setActionError(formatApiError(err));
    },
  });

  return (
    <div className="space-y-6">
      <header>
        <h2 className="text-2xl font-semibold tracking-tight">Datasets</h2>
        <p className="mt-1 text-sm text-zinc-600">
          Create datasets, import conversations, then index them for semantic
          search. Status <code>ready</code> means embeddings are built.
        </p>
      </header>

      <section className="rounded-lg border border-zinc-200 bg-zinc-50 px-4 py-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold text-zinc-900">
              Store collectors
            </h3>
            <p className="mt-1 text-sm text-zinc-600">
              <strong>Refresh</strong> pulls up to 100 newest reviews per store
              into <code>Zepto Public Mentions</code>. For a one-time ~100k
              backfill, run the CLI (see phase-7 user guide) — not this button.
            </p>
          </div>
          <Button
            type="button"
            disabled={refreshStores.isPending}
            onClick={() => refreshStores.mutate()}
          >
            {refreshStores.isPending
              ? "Refreshing from stores…"
              : "Refresh from stores"}
          </Button>
        </div>
        {collectMsg ? (
          <p className="mt-2 text-sm text-emerald-700">{collectMsg}</p>
        ) : null}
        {runs.isSuccess && runs.data.length > 0 ? (
          <ul className="mt-3 space-y-1 text-xs text-zinc-600">
            {runs.data.map((r) => (
              <li key={r.id}>
                {r.created_at
                  ? new Date(r.created_at).toLocaleString()
                  : "—"}{" "}
                · {r.status} · +{r.inserted} / skip {r.skipped}
                {r.context &&
                typeof r.context === "object" &&
                "mode" in r.context
                  ? ` · ${String((r.context as { mode?: string }).mode ?? "refresh")}`
                  : ""}
                {r.error_message ? ` · ${r.error_message.slice(0, 80)}` : ""}
              </li>
            ))}
          </ul>
        ) : null}
      </section>

      <CreateDatasetForm />

      {actionError ? (
        <p className="text-sm text-red-600">{actionError}</p>
      ) : null}
      {query.isError ? (
        <p className="text-sm text-red-600">{formatApiError(query.error)}</p>
      ) : null}

      {query.isLoading ? (
        <p className="text-sm text-zinc-500">Loading datasets…</p>
      ) : null}

      {query.isSuccess && query.data.length === 0 ? (
        <div className="rounded-lg border border-dashed border-zinc-300 bg-zinc-50 px-4 py-10 text-center">
          <p className="text-sm font-medium text-zinc-800">No datasets yet</p>
          <p className="mt-1 text-sm text-zinc-500">
            Create a dataset above, import a CSV, or click{" "}
            <strong>Refresh from stores</strong>.
          </p>
        </div>
      ) : null}

      {query.isSuccess && query.data.length > 0 ? (
        <div className="overflow-x-auto rounded-lg border border-zinc-200">
          <table className="min-w-full text-left text-sm">
            <thead className="border-b border-zinc-200 bg-zinc-50 text-xs uppercase text-zinc-500">
              <tr>
                <th className="px-3 py-2 font-medium">Name</th>
                <th className="px-3 py-2 font-medium">Source</th>
                <th className="px-3 py-2 font-medium">Count</th>
                <th className="px-3 py-2 font-medium">Status</th>
                <th className="px-3 py-2 font-medium">Created</th>
                <th className="px-3 py-2 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {query.data.map((ds) => (
                <tr key={ds.id} className="border-b border-zinc-100">
                  <td className="px-3 py-2">
                    <Link
                      href={`/datasets/${ds.id}`}
                      className="font-medium text-violet-700 hover:underline"
                    >
                      {ds.name}
                    </Link>
                    {ds.error_message ? (
                      <p className="mt-0.5 text-xs text-red-600">
                        {ds.error_message}
                      </p>
                    ) : null}
                  </td>
                  <td className="px-3 py-2 text-zinc-600">{ds.source}</td>
                  <td className="px-3 py-2">{ds.conversation_count}</td>
                  <td className="px-3 py-2">
                    <StatusBadge status={ds.status} />
                  </td>
                  <td className="px-3 py-2 text-zinc-500">
                    {ds.created_at
                      ? new Date(ds.created_at).toLocaleString()
                      : "—"}
                  </td>
                  <td className="px-3 py-2">
                    <div className="flex flex-wrap gap-2">
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        onClick={() =>
                          setImportTarget({ id: ds.id, name: ds.name })
                        }
                        disabled={
                          ds.status === "processing" || ds.status === "indexing"
                        }
                      >
                        Import
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        onClick={() => reindex.mutate(ds.id)}
                        disabled={
                          ds.conversation_count < 1 ||
                          ds.status === "processing" ||
                          ds.status === "indexing" ||
                          reindex.isPending
                        }
                      >
                        {ds.status === "indexing" ? "Indexing…" : "Index"}
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        onClick={() => {
                          if (
                            window.confirm(
                              `Delete dataset “${ds.name}”? This cannot be undone.`,
                            )
                          ) {
                            remove.mutate(ds.id);
                          }
                        }}
                      >
                        Delete
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      {importTarget ? (
        <ImportDialog
          datasetId={importTarget.id}
          datasetName={importTarget.name}
          onClose={() => setImportTarget(null)}
        />
      ) : null}
    </div>
  );
}
