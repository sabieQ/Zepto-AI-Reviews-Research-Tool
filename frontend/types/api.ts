export type ApiSuccess<T> = {
  success: true;
  message: string;
  data: T;
};

export type ApiError = {
  success: false;
  message: string;
  errors: unknown[];
};

export type ApiEnvelope<T> = ApiSuccess<T> | ApiError;

export type HealthData = {
  status: string;
  database: string;
  service: string;
};

export type Dataset = {
  id: string;
  name: string;
  source: string;
  description: string | null;
  conversation_count: number;
  status: string;
  error_message: string | null;
  created_at: string | null;
  updated_at: string | null;
};

export type Conversation = {
  id: string;
  external_id: string | null;
  source: string | null;
  author: string | null;
  content: string;
  rating: number | null;
  posted_at: string | null;
  url: string | null;
  created_at: string | null;
};

export type DatasetDetail = Dataset & {
  conversations: Conversation[];
};

export type ImportResult = {
  dataset: Dataset;
  inserted: number;
  skipped: number;
  truncated_rows: number;
  message: string;
};

export type EvidenceItem = {
  quote: string;
  conversation_id: string | null;
  chunk_id?: string | null;
  source?: string | null;
  url?: string | null;
};

export type Report = {
  id: string;
  dataset_id: string;
  research_question_id: string | null;
  question_text: string;
  title: string | null;
  status: string;
  executive_summary: string | null;
  key_findings: string[] | null;
  root_causes: string[] | null;
  themes: string[] | null;
  opportunities: string[] | null;
  confidence: string | null;
  confidence_rationale: string | null;
  evidence: EvidenceItem[] | null;
  model_provider: string | null;
  model_name: string | null;
  error_message: string | null;
  created_at: string | null;
  completed_at: string | null;
};

export type ResearchQuestion = {
  id: string;
  slug: string;
  category: string | null;
  title: string;
  description: string | null;
  prompt_file: string | null;
  is_active: boolean;
  sort_order: number;
};

export type AppSettings = {
  ai_provider: string;
  ai_model: string;
  embedding_model: string;
  embedding_dimensions: number;
  top_k: number;
  ai_api_key_set: boolean;
  reindex_required?: boolean;
  warning?: string;
  datasets_reset?: number;
};

export const DATASET_SOURCES = [
  "google_play",
  "app_store",
  "reddit",
  "youtube",
  "csv",
  "other",
] as const;

export const AI_PROVIDERS = [
  "openrouter",
  "openai",
  "openai_compatible",
  "groq",
  "gemini",
] as const;

export type CollectorRun = {
  id: string;
  dataset_id: string;
  status: string;
  sources: string[] | unknown;
  inserted: number;
  skipped: number;
  error_message: string | null;
  context: Record<string, unknown> | null;
  created_at: string | null;
  completed_at: string | null;
  dataset?: {
    id: string;
    name: string;
    status: string;
    conversation_count: number;
  } | null;
};
