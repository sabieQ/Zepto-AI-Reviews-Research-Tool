"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { formatApiError, getSettings, updateSettings } from "@/lib/api";
import { AI_PROVIDERS } from "@/types/api";

const schema = z.object({
  ai_provider: z.enum(AI_PROVIDERS),
  ai_model: z.string().trim().min(1, "Model is required"),
  embedding_model: z.string().trim().min(1, "Embedding model is required"),
  embedding_dimensions: z.number().int().min(8).max(4096),
  top_k: z.number().int().min(1).max(50),
});

type FormValues = z.infer<typeof schema>;

export function SettingsClient() {
  const queryClient = useQueryClient();
  const [banner, setBanner] = useState<string | null>(null);
  const [warning, setWarning] = useState<string | null>(null);

  const settings = useQuery({
    queryKey: ["settings"],
    queryFn: async () => {
      const res = await getSettings();
      if (!res.success) throw new Error(res.message);
      return res.data;
    },
  });

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      ai_provider: "openrouter",
      ai_model: "",
      embedding_model: "",
      embedding_dimensions: 1536,
      top_k: 12,
    },
  });

  useEffect(() => {
    if (!settings.data) return;
    form.reset({
      ai_provider: (AI_PROVIDERS.includes(
        settings.data.ai_provider as (typeof AI_PROVIDERS)[number],
      )
        ? settings.data.ai_provider
        : "openrouter") as FormValues["ai_provider"],
      ai_model: settings.data.ai_model,
      embedding_model: settings.data.embedding_model,
      embedding_dimensions: settings.data.embedding_dimensions,
      top_k: settings.data.top_k,
    });
  }, [settings.data, form]);

  const save = useMutation({
    mutationFn: async (values: FormValues) => {
      const res = await updateSettings(values);
      if (!res.success) throw new Error(res.message);
      return res.data;
    },
    onSuccess: async (data) => {
      setBanner("Settings saved");
      setWarning(data.warning ?? null);
      await queryClient.invalidateQueries({ queryKey: ["settings"] });
      await queryClient.invalidateQueries({ queryKey: ["datasets"] });
    },
    onError: (err) => {
      setBanner(null);
      setWarning(null);
      form.setError("root", { message: formatApiError(err) });
    },
  });

  return (
    <div className="space-y-6">
      <header>
        <h2 className="text-2xl font-semibold tracking-tight">Settings</h2>
        <p className="mt-1 text-sm text-zinc-600">
          Effective AI config (DB overrides env). API keys stay in{" "}
          <code>backend/.env</code> only — never shown here.
        </p>
      </header>

      {settings.isLoading ? (
        <p className="text-sm text-zinc-500">Loading settings…</p>
      ) : null}
      {settings.isError ? (
        <p className="text-sm text-red-600">{formatApiError(settings.error)}</p>
      ) : null}

      {settings.data ? (
        <p className="text-xs text-zinc-500">
          API key configured: {settings.data.ai_api_key_set ? "yes" : "no"}
          {settings.data.reindex_required
            ? " · Re-index required after embedding change"
            : ""}
        </p>
      ) : null}

      <form
        className="max-w-xl space-y-4 rounded-lg border border-zinc-200 p-4"
        onSubmit={form.handleSubmit((values) => save.mutate(values))}
      >
        <div>
          <label className="text-xs font-medium uppercase text-zinc-500">
            Provider
          </label>
          <select
            className="mt-1 w-full rounded-md border border-zinc-300 px-3 py-2 text-sm"
            {...form.register("ai_provider")}
          >
            {AI_PROVIDERS.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="text-xs font-medium uppercase text-zinc-500">
            Chat model
          </label>
          <input
            className="mt-1 w-full rounded-md border border-zinc-300 px-3 py-2 text-sm"
            {...form.register("ai_model")}
          />
          {form.formState.errors.ai_model ? (
            <p className="mt-1 text-xs text-red-600">
              {form.formState.errors.ai_model.message}
            </p>
          ) : null}
        </div>

        <div>
          <label className="text-xs font-medium uppercase text-zinc-500">
            Embedding model
          </label>
          <input
            className="mt-1 w-full rounded-md border border-zinc-300 px-3 py-2 text-sm"
            {...form.register("embedding_model")}
          />
          <p className="mt-1 text-[11px] text-zinc-400">
            Changing embedding model/dimensions resets ready datasets — re-index
            required.
          </p>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className="text-xs font-medium uppercase text-zinc-500">
              Embedding dimensions
            </label>
            <input
              type="number"
              className="mt-1 w-full rounded-md border border-zinc-300 px-3 py-2 text-sm"
              {...form.register("embedding_dimensions", { valueAsNumber: true })}
            />
          </div>
          <div>
            <label className="text-xs font-medium uppercase text-zinc-500">
              Default top_k
            </label>
            <input
              type="number"
              className="mt-1 w-full rounded-md border border-zinc-300 px-3 py-2 text-sm"
              {...form.register("top_k", { valueAsNumber: true })}
            />
          </div>
        </div>

        {form.formState.errors.root ? (
          <p className="text-sm text-red-600">
            {form.formState.errors.root.message}
          </p>
        ) : null}
        {banner ? <p className="text-sm text-emerald-700">{banner}</p> : null}
        {warning ? <p className="text-sm text-amber-700">{warning}</p> : null}

        <Button type="submit" disabled={save.isPending || settings.isLoading}>
          {save.isPending ? "Saving…" : "Save settings"}
        </Button>
      </form>
    </div>
  );
}
