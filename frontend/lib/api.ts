import type {
  ApiEnvelope,
  AppSettings,
  CollectorRun,
  Dataset,
  DatasetDetail,
  HealthData,
  ImportResult,
  Report,
  ResearchQuestion,
} from "@/types/api";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

export class ApiClientError extends Error {
  status: number;
  body: ApiEnvelope<unknown> | null;

  constructor(
    message: string,
    status: number,
    body: ApiEnvelope<unknown> | null = null,
  ) {
    super(message);
    this.name = "ApiClientError";
    this.status = status;
    this.body = body;
  }
}

export function getApiBaseUrl(): string {
  return API_BASE.replace(/\/$/, "");
}

export async function apiFetch<T>(
  path: string,
  init?: RequestInit,
): Promise<ApiEnvelope<T>> {
  const base = getApiBaseUrl();
  if (!base) {
    throw new ApiClientError(
      "NEXT_PUBLIC_API_BASE_URL is not configured",
      0,
      null,
    );
  }

  const url = `${base}${path.startsWith("/") ? path : `/${path}`}`;
  const headers = new Headers(init?.headers);
  if (!headers.has("Accept")) {
    headers.set("Accept", "application/json");
  }

  let response: Response;
  try {
    response = await fetch(url, { ...init, headers });
  } catch {
    throw new ApiClientError(
      "API unreachable (cold start?). Wait a few seconds and retry.",
      0,
      null,
    );
  }

  let body: ApiEnvelope<T> | null = null;
  try {
    body = (await response.json()) as ApiEnvelope<T>;
  } catch {
    body = null;
  }

  if (!response.ok) {
    let message =
      body && "message" in body && body.message
        ? body.message
        : `Request failed (${response.status})`;
    if (response.status === 429) {
      message =
        message ||
        "Rate limited by the AI provider. Wait a minute or change model in Settings.";
    }
    throw new ApiClientError(message, response.status, body);
  }

  if (!body) {
    throw new ApiClientError("Invalid API response", response.status, null);
  }

  return body;
}

export async function getHealth() {
  return apiFetch<HealthData>("/api/v1/health");
}

export async function listDatasets() {
  return apiFetch<Dataset[]>("/api/v1/datasets");
}

export async function getDataset(id: string) {
  return apiFetch<DatasetDetail>(`/api/v1/datasets/${id}`);
}

export async function createDataset(payload: {
  name: string;
  source: string;
  description?: string;
}) {
  return apiFetch<Dataset>("/api/v1/datasets", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function deleteDataset(id: string) {
  return apiFetch<{ id: string }>(`/api/v1/datasets/${id}`, {
    method: "DELETE",
  });
}

export async function importConversations(datasetId: string, file: File) {
  const form = new FormData();
  form.append("dataset_id", datasetId);
  form.append("file", file);
  form.append("auto_index", "true");
  return apiFetch<ImportResult>("/api/v1/import", {
    method: "POST",
    body: form,
  });
}

export async function reindexDataset(id: string) {
  return apiFetch<{
    dataset_id: string;
    status: string;
    conversation_count: number;
    message: string;
    dataset: Dataset;
  }>(`/api/v1/datasets/${id}/reindex`, {
    method: "POST",
  });
}

export async function searchChunks(payload: {
  dataset_id: string;
  query: string;
  top_k?: number;
}) {
  return apiFetch<{ results: unknown[]; count: number }>("/api/v1/search", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function listResearchQuestions() {
  return apiFetch<ResearchQuestion[]>("/api/v1/research-questions");
}

export async function listReports(datasetId?: string) {
  const qs = datasetId ? `?dataset_id=${encodeURIComponent(datasetId)}` : "";
  return apiFetch<Report[]>(`/api/v1/reports${qs}`);
}

export async function getReport(id: string) {
  return apiFetch<Report>(`/api/v1/reports/${id}`);
}

export async function deleteReport(id: string) {
  return apiFetch<{ id: string }>(`/api/v1/reports/${id}`, {
    method: "DELETE",
  });
}

/** Extract failed report embedded in research 400 errors (for History). */
export function extractFailedReport(err: unknown): Report | null {
  if (!(err instanceof ApiClientError) || !err.body || err.body.success) {
    return null;
  }
  const errors = err.body.errors;
  if (!Array.isArray(errors)) return null;
  for (const item of errors) {
    if (
      item &&
      typeof item === "object" &&
      "report" in item &&
      item.report &&
      typeof item.report === "object" &&
      "id" in (item.report as object)
    ) {
      return item.report as Report;
    }
  }
  return null;
}

/**
 * Run research. On failure-with-report (insufficient evidence etc.), still
 * throws ApiClientError but callers can use extractFailedReport().
 */
export async function runResearch(payload: {
  dataset_id: string;
  question: string;
  research_question_id?: string | null;
  top_k?: number;
}) {
  const base = getApiBaseUrl();
  if (!base) {
    throw new ApiClientError(
      "NEXT_PUBLIC_API_BASE_URL is not configured",
      0,
      null,
    );
  }

  let response: Response;
  try {
    response = await fetch(`${base}/api/v1/research`, {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
      signal: AbortSignal.timeout(180_000),
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === "TimeoutError") {
      throw new ApiClientError(
        "Research timed out. Check History — a failed/running report may still exist.",
        0,
        null,
      );
    }
    throw new ApiClientError("API unreachable (cold start?). Retry in a moment.", 0, null);
  }

  let body: ApiEnvelope<Report> | null = null;
  try {
    body = (await response.json()) as ApiEnvelope<Report>;
  } catch {
    body = null;
  }

  if (!response.ok || !body?.success) {
    const message =
      body && "message" in body && body.message
        ? body.message
        : `Request failed (${response.status})`;
    throw new ApiClientError(message, response.status, body);
  }

  return body;
}

export async function getSettings() {
  return apiFetch<AppSettings>("/api/v1/settings");
}

export async function updateSettings(payload: Partial<{
  ai_provider: string;
  ai_model: string;
  embedding_model: string;
  embedding_dimensions: number;
  top_k: number;
}>) {
  return apiFetch<AppSettings>("/api/v1/settings", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function runCollectorsRefresh(payload?: {
  dataset_id?: string;
  sources?: ("google_play" | "app_store")[];
  limit?: number;
  country?: string;
  lang?: string;
  auto_index?: boolean;
}) {
  return apiFetch<CollectorRun>("/api/v1/collectors/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload ?? {}),
  });
}

export async function listCollectorRuns(limit = 10) {
  return apiFetch<CollectorRun[]>(
    `/api/v1/collectors/runs?limit=${encodeURIComponent(String(limit))}`,
  );
}

export async function downloadReportMarkdown(reportId: string): Promise<void> {
  const base = getApiBaseUrl();
  if (!base) {
    throw new ApiClientError(
      "NEXT_PUBLIC_API_BASE_URL is not configured",
      0,
      null,
    );
  }
  const response = await fetch(
    `${base}/api/v1/reports/${reportId}/export?format=md`,
  );
  if (!response.ok) {
    let message = `Export failed (${response.status})`;
    try {
      const body = (await response.json()) as ApiEnvelope<unknown>;
      if (body.message) message = body.message;
    } catch {
      /* ignore */
    }
    throw new ApiClientError(message, response.status, null);
  }
  const blob = await response.blob();
  const disposition = response.headers.get("Content-Disposition") || "";
  const match = /filename="?([^"]+)"?/i.exec(disposition);
  const filename = match?.[1] || `report-${reportId.slice(0, 8)}.md`;
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export function formatApiError(err: unknown): string {
  if (err instanceof ApiClientError) {
    if (err.status === 429) {
      return (
        err.message ||
        "AI provider rate limit reached. Wait a minute or switch model in Settings."
      );
    }
    return err.message;
  }
  if (err instanceof Error) return err.message;
  return "Something went wrong";
}
