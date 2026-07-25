"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ImportDialog } from "@/components/datasets/import-dialog";
import { StatusBadge } from "@/components/datasets/status-badge";
import { Button } from "@/components/ui/button";
import { deleteDataset, formatApiError, getDataset, reindexDataset } from "@/lib/api";

export function DatasetDetailClient({ id }: { id: string }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [showImport, setShowImport] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const query = useQuery({
    queryKey: ["dataset", id],
    queryFn: async () => {
      const res = await getDataset(id);
      if (!res.success) throw new Error(res.message);
      return res.data;
    },
    refetchInterval: (q) =>
      q.state.data?.status === "indexing" || q.state.data?.status === "processing"
        ? 3000
        : false,
  });

  const remove = useMutation({
    mutationFn: async () => {
      const res = await deleteDataset(id);
      if (!res.success) throw new Error(res.message);
      return res.data;
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["datasets"] });
      router.push("/datasets");
    },
    onError: (err) => setActionError(formatApiError(err)),
  });

  const reindex = useMutation({
    mutationFn: async () => {
      const res = await reindexDataset(id);
      if (!res.success) throw new Error(res.message);
      return res.data;
    },
    onSuccess: async () => {
      setActionError(null);
      await queryClient.invalidateQueries({ queryKey: ["dataset", id] });
      await queryClient.invalidateQueries({ queryKey: ["datasets"] });
    },
    onError: (err) => setActionError(formatApiError(err)),
  });

  if (query.isLoading) {
    return <p className="text-sm text-zinc-500">Loading dataset…</p>;
  }

  if (query.isError) {
    return (
      <div className="space-y-3">
        <p className="text-sm text-red-600">{formatApiError(query.error)}</p>
        <Link href="/datasets" className="text-sm text-violet-700 hover:underline">
          Back to datasets
        </Link>
      </div>
    );
  }

  const ds = query.data!;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <Link
            href="/datasets"
            className="text-xs font-medium text-violet-700 hover:underline"
          >
            ← Datasets
          </Link>
          <h2 className="mt-2 text-2xl font-semibold tracking-tight">{ds.name}</h2>
          <p className="mt-1 text-sm text-zinc-600">
            {ds.description || "No description"}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            type="button"
            variant="outline"
            onClick={() => setShowImport(true)}
            disabled={ds.status === "processing" || ds.status === "indexing"}
          >
            Import
          </Button>
          <Button
            type="button"
            variant="outline"
            onClick={() => reindex.mutate()}
            disabled={
              ds.conversation_count < 1 ||
              ds.status === "processing" ||
              ds.status === "indexing" ||
              reindex.isPending
            }
          >
            {ds.status === "indexing"
              ? "Indexing…"
              : ds.status === "ready"
                ? "Re-index"
                : "Index"}
          </Button>
          <Button
            type="button"
            variant="ghost"
            onClick={() => {
              if (
                window.confirm(
                  `Delete dataset “${ds.name}”? This cannot be undone.`,
                )
              ) {
                remove.mutate();
              }
            }}
          >
            Delete
          </Button>
        </div>
      </div>

      {actionError ? <p className="text-sm text-red-600">{actionError}</p> : null}

      <dl className="grid gap-3 rounded-lg border border-zinc-200 bg-zinc-50 p-4 sm:grid-cols-2">
        <div>
          <dt className="text-xs uppercase text-zinc-500">Source</dt>
          <dd className="text-sm font-medium">{ds.source}</dd>
        </div>
        <div>
          <dt className="text-xs uppercase text-zinc-500">Status</dt>
          <dd className="mt-0.5">
            <StatusBadge status={ds.status} />
          </dd>
        </div>
        <div>
          <dt className="text-xs uppercase text-zinc-500">Conversations</dt>
          <dd className="text-sm font-medium">{ds.conversation_count}</dd>
        </div>
        <div>
          <dt className="text-xs uppercase text-zinc-500">Created</dt>
          <dd className="text-sm">
            {ds.created_at ? new Date(ds.created_at).toLocaleString() : "—"}
          </dd>
        </div>
        {ds.error_message ? (
          <div className="sm:col-span-2">
            <dt className="text-xs uppercase text-red-500">Error</dt>
            <dd className="text-sm text-red-700">{ds.error_message}</dd>
          </div>
        ) : null}
      </dl>

      <section>
        <h3 className="text-sm font-semibold text-zinc-900">
          Recent conversations
        </h3>
        {ds.conversations.length === 0 ? (
          <p className="mt-3 text-sm text-zinc-500">
            No conversations yet. Import a CSV/JSON file to populate this
            dataset.
          </p>
        ) : (
          <ul className="mt-3 space-y-3">
            {ds.conversations.map((c) => (
              <li
                key={c.id}
                className="rounded-lg border border-zinc-200 bg-white px-4 py-3"
              >
                <p className="text-sm text-zinc-900 whitespace-pre-wrap">
                  {c.content}
                </p>
                <p className="mt-2 text-xs text-zinc-500">
                  {[c.author, c.source, c.rating != null ? `★ ${c.rating}` : null]
                    .filter(Boolean)
                    .join(" · ")}
                </p>
              </li>
            ))}
          </ul>
        )}
      </section>

      {showImport ? (
        <ImportDialog
          datasetId={ds.id}
          datasetName={ds.name}
          onClose={() => setShowImport(false)}
        />
      ) : null}
    </div>
  );
}
