"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import {
  ConfidenceBadge,
  ReportStatusBadge,
} from "@/components/research/report-badges";
import { Button } from "@/components/ui/button";
import {
  downloadReportMarkdown,
  formatApiError,
  getReport,
  listDatasets,
} from "@/lib/api";

function Section({
  title,
  items,
}: {
  title: string;
  items: string[] | null | undefined;
}) {
  const list = Array.isArray(items) ? items : [];
  return (
    <section className="space-y-2">
      <h3 className="text-sm font-semibold text-zinc-900">{title}</h3>
      {list.length === 0 ? (
        <p className="text-sm text-zinc-400">None</p>
      ) : (
        <ul className="list-disc space-y-1 pl-5 text-sm text-zinc-700">
          {list.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      )}
    </section>
  );
}

export function HistoryDetailClient({ reportId }: { reportId: string }) {
  const [exportError, setExportError] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);

  const report = useQuery({
    queryKey: ["report", reportId],
    queryFn: async () => {
      const res = await getReport(reportId);
      if (!res.success) throw new Error(res.message);
      return res.data;
    },
    refetchInterval: (q) =>
      q.state.data?.status === "running" || q.state.data?.status === "pending"
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

  const datasetName = datasets.data?.find(
    (d) => d.id === report.data?.dataset_id,
  )?.name;

  if (report.isLoading) {
    return <p className="text-sm text-zinc-500">Loading report…</p>;
  }

  if (report.isError) {
    return (
      <div className="space-y-3">
        <p className="text-sm text-red-600">{formatApiError(report.error)}</p>
        <Link href="/history" className="text-sm text-violet-700 hover:underline">
          ← Back to history
        </Link>
      </div>
    );
  }

  const r = report.data!;
  const canExport = r.status === "completed";

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <Link
            href="/history"
            className="text-xs text-violet-700 hover:underline"
          >
            ← History
          </Link>
          <h2 className="mt-2 text-2xl font-semibold tracking-tight">
            {r.title || "Research report"}
          </h2>
          <div className="mt-2 flex flex-wrap items-center gap-3">
            <ReportStatusBadge status={r.status} />
            <ConfidenceBadge value={r.confidence} />
            <span className="text-xs text-zinc-500">
              {datasetName ?? r.dataset_id.slice(0, 8)}
            </span>
          </div>
        </div>
        <Button
          type="button"
          variant="outline"
          disabled={!canExport || exporting}
          onClick={async () => {
            setExportError(null);
            setExporting(true);
            try {
              await downloadReportMarkdown(r.id);
            } catch (err) {
              setExportError(formatApiError(err));
            } finally {
              setExporting(false);
            }
          }}
        >
          {exporting ? "Exporting…" : "Export Markdown"}
        </Button>
      </div>

      {exportError ? <p className="text-sm text-red-600">{exportError}</p> : null}

      <section className="rounded-lg border border-zinc-200 bg-zinc-50 px-4 py-3">
        <p className="text-xs font-medium uppercase tracking-wide text-zinc-500">
          Question asked
        </p>
        <p className="mt-1 whitespace-pre-wrap text-sm text-zinc-800">
          {r.question_text}
        </p>
      </section>

      {r.status === "failed" ? (
        <section className="rounded-lg border border-red-200 bg-red-50 px-4 py-3">
          <p className="text-sm font-medium text-red-800">Research failed</p>
          <p className="mt-1 text-sm text-red-700">
            {r.error_message || "Unknown error"}
          </p>
        </section>
      ) : null}

      {r.status === "running" || r.status === "pending" ? (
        <p className="text-sm text-amber-700">
          Analysis still in progress — this page refreshes automatically.
        </p>
      ) : null}

      {r.status === "completed" ? (
        <>
          <section className="space-y-2">
            <h3 className="text-sm font-semibold text-zinc-900">
              Executive summary
            </h3>
            <p className="whitespace-pre-wrap text-sm leading-relaxed text-zinc-700">
              {r.executive_summary || "—"}
            </p>
            {r.confidence_rationale ? (
              <p className="text-xs text-zinc-500">
                Confidence: {r.confidence_rationale}
              </p>
            ) : null}
          </section>

          <Section title="Key findings" items={r.key_findings} />
          <Section title="Root causes" items={r.root_causes} />
          <Section title="Themes" items={r.themes} />
          <Section title="Opportunities" items={r.opportunities} />

          <section className="space-y-3">
            <h3 className="text-sm font-semibold text-zinc-900">Evidence</h3>
            {(r.evidence ?? []).length === 0 ? (
              <p className="text-sm text-zinc-400">No citations</p>
            ) : (
              <ul className="space-y-3">
                {(r.evidence ?? []).map((ev, i) => (
                  <li
                    key={`${ev.conversation_id}-${i}`}
                    className="rounded-lg border border-zinc-200 px-4 py-3"
                  >
                    <blockquote className="text-sm text-zinc-800">
                      “{ev.quote}”
                    </blockquote>
                    <p className="mt-2 text-xs text-zinc-500">
                      {ev.source ? `${ev.source} · ` : ""}
                      {ev.conversation_id
                        ? `conversation ${ev.conversation_id.slice(0, 8)}…`
                        : null}
                      {ev.url ? (
                        <>
                          {" · "}
                          <a
                            href={ev.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-violet-700 hover:underline"
                          >
                            source link
                          </a>
                        </>
                      ) : null}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <p className="text-xs text-zinc-400">
            Model: {r.model_provider ?? "—"} / {r.model_name ?? "—"}
          </p>
        </>
      ) : null}
    </div>
  );
}
