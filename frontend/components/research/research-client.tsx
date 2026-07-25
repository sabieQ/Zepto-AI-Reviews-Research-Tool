"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  extractFailedReport,
  formatApiError,
  listDatasets,
  listResearchQuestions,
  runResearch,
} from "@/lib/api";

const MIN_Q = 10;
const MAX_Q = 2000;

export function ResearchClient() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [datasetId, setDatasetId] = useState("");
  const [question, setQuestion] = useState("");
  const [presetId, setPresetId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const datasets = useQuery({
    queryKey: ["datasets"],
    queryFn: async () => {
      const res = await listDatasets();
      if (!res.success) throw new Error(res.message);
      return res.data;
    },
  });

  const presets = useQuery({
    queryKey: ["research-questions"],
    queryFn: async () => {
      const res = await listResearchQuestions();
      if (!res.success) throw new Error(res.message);
      return res.data;
    },
  });

  const readyDatasets = useMemo(
    () => (datasets.data ?? []).filter((d) => d.status === "ready"),
    [datasets.data],
  );

  const trimmed = question.trim();
  const questionValid = trimmed.length >= MIN_Q && trimmed.length <= MAX_Q;

  const run = useMutation({
    mutationFn: async () => {
      const res = await runResearch({
        dataset_id: datasetId,
        question: trimmed,
        research_question_id: presetId,
      });
      return res.data;
    },
    onSuccess: async (report) => {
      setError(null);
      await queryClient.invalidateQueries({ queryKey: ["reports"] });
      router.push(`/history/${report.id}`);
    },
    onError: async (err) => {
      const failed = extractFailedReport(err);
      await queryClient.invalidateQueries({ queryKey: ["reports"] });
      if (failed?.id) {
        setError(formatApiError(err));
        router.push(`/history/${failed.id}`);
        return;
      }
      setError(formatApiError(err));
    },
  });

  const canRun = Boolean(datasetId) && questionValid && !run.isPending;

  return (
    <div className="space-y-6">
      <header>
        <h2 className="text-2xl font-semibold tracking-tight">Research</h2>
        <p className="mt-1 text-sm text-zinc-600">
          Ask a free-form question over a ready dataset. Optional presets only
          pre-fill the question — you can edit before running.
        </p>
      </header>

      {datasets.isError ? (
        <p className="text-sm text-red-600">{formatApiError(datasets.error)}</p>
      ) : null}

      <section className="space-y-4 rounded-lg border border-zinc-200 bg-white p-4">
        <div>
          <label className="text-xs font-medium uppercase tracking-wide text-zinc-500">
            Dataset
          </label>
          <select
            className="mt-1 w-full rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm"
            value={datasetId}
            onChange={(e) => setDatasetId(e.target.value)}
            disabled={datasets.isLoading}
          >
            <option value="">
              {readyDatasets.length === 0
                ? "No ready datasets — import & index first"
                : "Select a ready dataset"}
            </option>
            {readyDatasets.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name} ({d.conversation_count} conversations)
              </option>
            ))}
          </select>
          {readyDatasets.length === 0 && datasets.isSuccess ? (
            <p className="mt-2 text-sm text-zinc-500">
              Go to{" "}
              <Link href="/datasets" className="text-violet-700 hover:underline">
                Datasets
              </Link>
              , import conversations, then click Index until status is{" "}
              <code>ready</code>.
            </p>
          ) : null}
        </div>

        <div>
          <label className="text-xs font-medium uppercase tracking-wide text-zinc-500">
            Optional preset shortcuts
          </label>
          <div className="mt-2 flex flex-wrap gap-2">
            {(presets.data ?? []).map((p) => (
              <button
                key={p.id}
                type="button"
                onClick={() => {
                  setQuestion(p.title);
                  setPresetId(p.id);
                }}
                className={`rounded-md border px-3 py-1.5 text-left text-xs transition-colors ${
                  presetId === p.id
                    ? "border-violet-400 bg-violet-50 text-violet-900"
                    : "border-zinc-200 bg-zinc-50 text-zinc-700 hover:border-zinc-300"
                }`}
                title={p.description ?? p.title}
              >
                {p.title}
              </button>
            ))}
            {presets.isSuccess && (presets.data?.length ?? 0) === 0 ? (
              <p className="text-sm text-zinc-500">No presets seeded — free-form still works.</p>
            ) : null}
          </div>
        </div>

        <div>
          <div className="flex items-baseline justify-between gap-2">
            <label className="text-xs font-medium uppercase tracking-wide text-zinc-500">
              Research question
            </label>
            <span className="text-[11px] text-zinc-400">
              {trimmed.length}/{MAX_Q} (min {MIN_Q})
            </span>
          </div>
          <textarea
            className="mt-1 min-h-28 w-full rounded-md border border-zinc-300 px-3 py-2 text-sm"
            value={question}
            onChange={(e) => {
              setQuestion(e.target.value);
              // Editing clears preset link unless text still matches
              if (presetId) setPresetId(null);
            }}
            placeholder="e.g. What are the most common delivery pain points?"
            maxLength={MAX_Q}
          />
        </div>

        {error ? <p className="text-sm text-red-600">{error}</p> : null}

        <div className="flex flex-wrap items-center gap-3">
          <Button
            type="button"
            disabled={!canRun}
            onClick={() => {
              setError(null);
              run.mutate();
            }}
          >
            {run.isPending ? "Running analysis…" : "Run analysis"}
          </Button>
          {run.isPending ? (
            <p className="text-sm text-zinc-500">
              This can take up to a couple of minutes on cold start.
            </p>
          ) : null}
        </div>
      </section>
    </div>
  );
}
