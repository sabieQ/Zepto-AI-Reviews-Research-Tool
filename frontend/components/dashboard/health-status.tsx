"use client";

import { useQuery } from "@tanstack/react-query";
import { RefreshCw } from "lucide-react";
import { ApiClientError, getApiBaseUrl, getHealth } from "@/lib/api";
import type { HealthData } from "@/types/api";

async function fetchHealth(): Promise<{
  online: boolean;
  degraded: boolean;
  data: HealthData | null;
  message: string;
}> {
  try {
    const res = await getHealth();
    if (!res.success) {
      return {
        online: true,
        degraded: true,
        data: null,
        message: res.message,
      };
    }
    return {
      online: true,
      degraded: res.data.status !== "ok",
      data: res.data,
      message: res.data.database,
    };
  } catch (err) {
    if (err instanceof ApiClientError && err.body && typeof err.body === "object") {
      const body = err.body as {
        success?: boolean;
        message?: string;
        errors?: Array<{ status?: string; database?: string }>;
      };
      const detail = body.errors?.[0];
      if (err.status === 503 && detail) {
        return {
          online: true,
          degraded: true,
          data: {
            status: detail.status ?? "degraded",
            database: detail.database ?? body.message ?? "unreachable",
            service: "zepto-research-api",
          },
          message: body.message ?? "Database unreachable",
        };
      }
      return {
        online: false,
        degraded: false,
        data: null,
        message: err.message,
      };
    }
    return {
      online: false,
      degraded: false,
      data: null,
      message:
        err instanceof Error
          ? err.message
          : "Could not reach the backend. Retry after the service wakes up.",
    };
  }
}

export function HealthStatus() {
  const query = useQuery({
    queryKey: ["health"],
    queryFn: fetchHealth,
    refetchInterval: 30_000,
  });

  const base = getApiBaseUrl();

  let statusLabel = "Checking…";
  let detail = "Contacting API (cold start may take a moment on free tiers).";
  let tone = "border-amber-200 bg-amber-50 text-amber-900";

  if (!base) {
    statusLabel = "Misconfigured";
    detail = "Set NEXT_PUBLIC_API_BASE_URL in frontend/.env.local";
    tone = "border-red-200 bg-red-50 text-red-900";
  } else if (query.isError) {
    statusLabel = "API unreachable";
    detail = "Could not reach the backend.";
    tone = "border-red-200 bg-red-50 text-red-900";
  } else if (query.isSuccess) {
    const result = query.data;
    if (!result.online) {
      statusLabel = "API unreachable";
      detail = result.message;
      tone = "border-red-200 bg-red-50 text-red-900";
    } else if (result.degraded) {
      statusLabel = "Degraded";
      detail = result.data
        ? `Database: ${result.data.database}`
        : result.message;
      tone = "border-amber-200 bg-amber-50 text-amber-900";
    } else {
      statusLabel = "Online";
      detail = result.data
        ? `Database: ${result.data.database}`
        : result.message;
      tone = "border-emerald-200 bg-emerald-50 text-emerald-900";
    }
  }

  return (
    <div className={`rounded-lg border p-4 ${tone}`}>
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide opacity-70">
            Backend health
          </p>
          <p className="mt-1 text-lg font-semibold">{statusLabel}</p>
          <p className="mt-1 text-sm opacity-90">{detail}</p>
          {base ? (
            <p className="mt-2 font-mono text-xs opacity-60">{base}</p>
          ) : null}
        </div>
        <button
          type="button"
          onClick={() => query.refetch()}
          className="inline-flex items-center gap-1 rounded-md border border-current/20 bg-white/60 px-2.5 py-1.5 text-xs font-medium hover:bg-white"
          disabled={query.isFetching}
        >
          <RefreshCw
            className={`h-3.5 w-3.5 ${query.isFetching ? "animate-spin" : ""}`}
          />
          Retry
        </button>
      </div>
    </div>
  );
}
