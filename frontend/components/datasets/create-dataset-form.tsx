"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { createDataset, formatApiError } from "@/lib/api";
import { DATASET_SOURCES } from "@/types/api";
import { Button } from "@/components/ui/button";
import { useState } from "react";

const schema = z.object({
  name: z.string().trim().min(1, "Name is required").max(200),
  source: z.enum(DATASET_SOURCES),
  description: z.string().max(2000).optional(),
});

type FormValues = z.infer<typeof schema>;

export function CreateDatasetForm({ onCreated }: { onCreated?: () => void }) {
  const queryClient = useQueryClient();
  const [apiError, setApiError] = useState<string | null>(null);
  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { name: "", source: "csv", description: "" },
  });

  const mutation = useMutation({
    mutationFn: async (values: FormValues) => {
      const res = await createDataset({
        name: values.name,
        source: values.source,
        description: values.description || undefined,
      });
      if (!res.success) throw new Error(res.message);
      return res.data;
    },
    onSuccess: async () => {
      setApiError(null);
      form.reset({ name: "", source: "csv", description: "" });
      await queryClient.invalidateQueries({ queryKey: ["datasets"] });
      onCreated?.();
    },
    onError: (err) => setApiError(formatApiError(err)),
  });

  return (
    <form
      className="space-y-3 rounded-lg border border-zinc-200 bg-zinc-50 p-4"
      onSubmit={form.handleSubmit((values) => mutation.mutate(values))}
    >
      <h3 className="text-sm font-semibold text-zinc-900">Create dataset</h3>
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="block text-sm">
          <span className="mb-1 block text-zinc-600">Name</span>
          <input
            className="w-full rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm"
            {...form.register("name")}
          />
          {form.formState.errors.name ? (
            <span className="mt-1 block text-xs text-red-600">
              {form.formState.errors.name.message}
            </span>
          ) : null}
        </label>
        <label className="block text-sm">
          <span className="mb-1 block text-zinc-600">Source</span>
          <select
            className="w-full rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm"
            {...form.register("source")}
          >
            {DATASET_SOURCES.map((source) => (
              <option key={source} value={source}>
                {source}
              </option>
            ))}
          </select>
          {form.formState.errors.source ? (
            <span className="mt-1 block text-xs text-red-600">
              {form.formState.errors.source.message}
            </span>
          ) : null}
        </label>
      </div>
      <label className="block text-sm">
        <span className="mb-1 block text-zinc-600">Description (optional)</span>
        <textarea
          className="w-full rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm"
          rows={2}
          {...form.register("description")}
        />
      </label>
      {apiError ? <p className="text-sm text-red-600">{apiError}</p> : null}
      <Button type="submit" disabled={mutation.isPending}>
        {mutation.isPending ? "Creating…" : "Create dataset"}
      </Button>
    </form>
  );
}
