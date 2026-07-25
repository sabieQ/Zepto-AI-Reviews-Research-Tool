-- Reference DDL for Zepto AI Product Research Assistant
-- Source of truth for migrations: backend/alembic/versions/
-- Embedding dimensions: 1536 (must match EMBEDDING_DIMENSIONS)

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS datasets (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    source TEXT NOT NULL,
    description TEXT,
    conversation_count INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'pending',
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS research_questions (
    id UUID PRIMARY KEY,
    slug TEXT NOT NULL UNIQUE,
    category TEXT,
    title TEXT NOT NULL,
    description TEXT,
    prompt_file TEXT,
    is_active BOOLEAN NOT NULL DEFAULT true,
    sort_order INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS conversations (
    id UUID PRIMARY KEY,
    dataset_id UUID NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    external_id TEXT,
    source TEXT,
    author TEXT,
    content TEXT NOT NULL,
    raw_content TEXT,
    rating INTEGER,
    posted_at TIMESTAMPTZ,
    url TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_conversations_dataset_external UNIQUE (dataset_id, external_id)
);

CREATE TABLE IF NOT EXISTS conversation_chunks (
    id UUID PRIMARY KEY,
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    dataset_id UUID NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    token_count INTEGER,
    embedding vector(1536),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_conversation_chunks_dataset_id ON conversation_chunks (dataset_id);

-- After embeddings exist (Phase 3):
-- CREATE INDEX ix_conversation_chunks_embedding
--   ON conversation_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

CREATE TABLE IF NOT EXISTS reports (
    id UUID PRIMARY KEY,
    dataset_id UUID NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    research_question_id UUID REFERENCES research_questions(id) ON DELETE SET NULL,
    question_text TEXT NOT NULL,
    title TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    executive_summary TEXT,
    key_findings JSONB,
    root_causes JSONB,
    themes JSONB,
    opportunities JSONB,
    confidence TEXT,
    confidence_rationale TEXT,
    evidence JSONB,
    model_provider TEXT,
    model_name TEXT,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS settings (
    id UUID PRIMARY KEY,
    key TEXT NOT NULL UNIQUE,
    value JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS logs (
    id UUID PRIMARY KEY,
    level TEXT NOT NULL,
    event TEXT NOT NULL,
    message TEXT NOT NULL,
    context JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
