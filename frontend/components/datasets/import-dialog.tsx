"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { formatApiError, importConversations } from "@/lib/api";
import { Button } from "@/components/ui/button";

export function ImportDialog({
  datasetId,
  datasetName,
  onClose,
}: {
  datasetId: string;
  datasetName: string;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const [apiError, setApiError] = useState<string | null>(null);
  const [resultMsg, setResultMsg] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: async () => {
      if (!file) throw new Error("Choose a CSV or JSON file");
      const res = await importConversations(datasetId, file);
      if (!res.success) throw new Error(res.message);
      return res.data;
    },
    onSuccess: async (data) => {
      setApiError(null);
      setResultMsg(data.message);
      await queryClient.invalidateQueries({ queryKey: ["datasets"] });
      await queryClient.invalidateQueries({ queryKey: ["dataset", datasetId] });
    },
    onError: (err) => {
      setResultMsg(null);
      setApiError(formatApiError(err));
    },
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-md rounded-lg bg-white p-5 shadow-lg">
        <h3 className="text-lg font-semibold">Import conversations</h3>
        <p className="mt-1 text-sm text-zinc-600">
          Dataset: <span className="font-medium">{datasetName}</span>
        </p>
        <p className="mt-2 text-xs text-zinc-500">
          CSV/JSON with required <code>content</code> column. Max 5,000 rows /
          10 MB. UTF-8 only.
        </p>
        <input
          type="file"
          accept=".csv,.json,text/csv,application/json"
          className="mt-4 block w-full text-sm"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
        />
        {apiError ? <p className="mt-3 text-sm text-red-600">{apiError}</p> : null}
        {resultMsg ? (
          <p className="mt-3 text-sm text-emerald-700">{resultMsg}</p>
        ) : null}
        <div className="mt-5 flex justify-end gap-2">
          <Button type="button" variant="outline" onClick={onClose}>
            Close
          </Button>
          <Button
            type="button"
            disabled={!file || mutation.isPending}
            onClick={() => mutation.mutate()}
          >
            {mutation.isPending ? "Importing…" : "Import"}
          </Button>
        </div>
      </div>
    </div>
  );
}
