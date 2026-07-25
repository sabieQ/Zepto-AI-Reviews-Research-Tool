# Zepto AI Product Research Assistant — Detailed Implementation Plan

**Status:** Ready for build  
**Architecture:** Cloud free-tier (Option 1)  
**Sources of truth:** [engineering-spec.md](../engineering-spec.md) for how; [problem-statement.md](../problem-statement.md) for why/what  
**Conflict rule:** Eng-spec + cloud free-tier override PRD local-first/offline defaults. Ollama is a future/config extension only.

---

## 1. Product one-liner

Browser-based internal tool that ingests public Zepto customer conversations, indexes them with embeddings, and answers **free-form user research questions** (with optional preset shortcuts) using **RAG evidence-backed reports**.

---

## 2. Locked stack

| Layer | Technology | Host |
|-------|------------|------|
| Frontend | Next.js 15, React 19, TypeScript, Tailwind, shadcn/ui, TanStack Query, React Hook Form, Zod | Vercel free |
| Backend | Python 3.12+, FastAPI, SQLAlchemy, Alembic, Pydantic | Render free |
| Database | Supabase PostgreSQL + pgvector | Supabase free |
| AI | OpenAI-compatible client; env-switched OpenRouter / Groq / Gemini | API keys via env |
| Uploads (MVP) | Local disk on Render (`/tmp` or persistent disk if available) | Later: Supabase Storage |
| Auth | None | URL access only |

---

## 3. Repository layout

Monorepo at project root:

```text
zepto/
├── frontend/                 # Next.js App Router
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx                    # Dashboard
│   │   ├── datasets/
│   │   │   ├── page.tsx
│   │   │   └── [id]/page.tsx
│   │   ├── research/page.tsx
│   │   ├── history/
│   │   │   ├── page.tsx
│   │   │   └── [id]/page.tsx
│   │   └── settings/page.tsx
│   ├── components/
│   │   ├── layout/           # Sidebar, shell
│   │   ├── datasets/
│   │   ├── research/
│   │   ├── reports/
│   │   └── ui/               # shadcn
│   ├── hooks/
│   ├── lib/                  # API client, utils
│   ├── types/
│   ├── package.json
│   └── .env.example
│
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── api/              # Route modules
│   │   │   ├── datasets.py
│   │   │   ├── import_data.py
│   │   │   ├── research.py
│   │   │   ├── reports.py
│   │   │   └── settings.py
│   │   ├── core/             # config, logging, response helpers
│   │   ├── models/           # SQLAlchemy models
│   │   ├── schemas/          # Pydantic request/response
│   │   ├── repositories/
│   │   ├── services/
│   │   │   ├── cleaning.py
│   │   │   ├── embeddings.py
│   │   │   ├── retrieval.py
│   │   │   ├── research.py
│   │   │   ├── ai_provider.py
│   │   │   └── export.py
│   │   ├── workers/          # Optional sync jobs for embed/import
│   │   └── utils/
│   ├── alembic/
│   ├── alembic.ini
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
│
├── database/
│   ├── schema.sql            # Reference DDL + pgvector
│   └── seed_research_questions.sql
│
├── prompts/
│   ├── free_form_research.md      # Primary generic RAG prompt (required)
│   ├── pain_points.md             # Optional preset shortcut
│   ├── feature_requests.md
│   ├── sentiment.md
│   ├── opportunities.md
│   ├── discovery_behaviour.md
│   └── executive_summary.md
│
├── scripts/
│   ├── seed_sample_csv.py
│   └── smoke_test_api.sh
│
├── docker/
│   └── docker-compose.yml    # Local backend + optional Postgres for dev
│
├── docs/
│   └── implementation-plan.md
│
├── problem-statement.md
├── engineering-spec.md
└── README.md
```

---

## 4. Database schema

Enable extension once:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
```

### 4.1 `datasets`

| Column | Type | Notes |
|--------|------|--------|
| id | UUID PK | default uuid_generate_v4() |
| name | TEXT NOT NULL | |
| source | TEXT NOT NULL | `google_play` \| `app_store` \| `reddit` \| `youtube` \| `csv` \| `other` |
| description | TEXT | nullable |
| conversation_count | INT | default 0 |
| status | TEXT | `pending` \| `processing` \| `ready` \| `failed` |
| error_message | TEXT | nullable |
| created_at | TIMESTAMPTZ | |
| updated_at | TIMESTAMPTZ | |

### 4.2 `conversations`

| Column | Type | Notes |
|--------|------|--------|
| id | UUID PK | |
| dataset_id | UUID FK → datasets ON DELETE CASCADE | |
| external_id | TEXT | source-native id for dedupe |
| source | TEXT | denormalized source |
| author | TEXT | nullable |
| content | TEXT NOT NULL | cleaned body |
| raw_content | TEXT | original |
| rating | INT | nullable (app reviews) |
| posted_at | TIMESTAMPTZ | nullable |
| url | TEXT | nullable |
| metadata | JSONB | default `{}` |
| created_at | TIMESTAMPTZ | |

Unique: `(dataset_id, external_id)` where external_id IS NOT NULL.

### 4.3 `conversation_chunks`

| Column | Type | Notes |
|--------|------|--------|
| id | UUID PK | |
| conversation_id | UUID FK → conversations ON DELETE CASCADE | |
| dataset_id | UUID FK → datasets ON DELETE CASCADE | |
| chunk_index | INT | |
| content | TEXT NOT NULL | |
| token_count | INT | nullable |
| embedding | vector(1536) | dimension must match `EMBEDDING_MODEL`; document chosen dim in README |
| created_at | TIMESTAMPTZ | |

Index: IVFFlat or HNSW on `embedding` (cosine). For MVP volume, HNSW preferred if Supabase plan allows; else IVFFlat.

### 4.4 `research_questions`

Optional **preset shortcuts** only. Free-form questions do not require a row here.

| Column | Type | Notes |
|--------|------|--------|
| id | UUID PK | |
| slug | TEXT UNIQUE | e.g. `pain_points` |
| category | TEXT | discovery, behaviour, experience, category, competitive |
| title | TEXT | shown as preset chip / shortcut |
| description | TEXT | pre-fills or clarifies the preset |
| prompt_file | TEXT | optional specialized prompt; else use `free_form_research.md` |
| is_active | BOOLEAN | default true |
| sort_order | INT | |

### 4.5 `reports`

| Column | Type | Notes |
|--------|------|--------|
| id | UUID PK | |
| dataset_id | UUID FK → datasets | |
| research_question_id | UUID FK → research_questions | nullable; set only when a preset was used |
| question_text | TEXT NOT NULL | exact free-form question the user asked (always stored) |
| title | TEXT | derived from question_text (truncated) or preset title |
| status | TEXT | `pending` \| `running` \| `completed` \| `failed` |
| executive_summary | TEXT | |
| key_findings | JSONB | array of strings/objects |
| root_causes | JSONB | |
| themes | JSONB | |
| opportunities | JSONB | |
| confidence | TEXT | `high` \| `medium` \| `low` |
| confidence_rationale | TEXT | |
| evidence | JSONB | quotes + conversation_id + source + url |
| model_provider | TEXT | |
| model_name | TEXT | |
| error_message | TEXT | |
| created_at | TIMESTAMPTZ | |
| completed_at | TIMESTAMPTZ | |

### 4.6 `settings`

Single-row or key-value store.

| Column | Type | Notes |
|--------|------|--------|
| id | UUID PK | |
| key | TEXT UNIQUE | |
| value | JSONB | |
| updated_at | TIMESTAMPTZ | |

Keys: `ai_provider`, `ai_model`, `embedding_model`, `embedding_dimensions`, `top_k`.

Env vars remain source of defaults; DB settings override at runtime when present.

### 4.7 `logs`

| Column | Type | Notes |
|--------|------|--------|
| id | UUID PK | |
| level | TEXT | info/warn/error |
| event | TEXT | import, embed, research, api_error |
| message | TEXT | |
| context | JSONB | |
| created_at | TIMESTAMPTZ | |

---

## 5. API contract

Base URL: `https://<render-service>/api/v1`  
Envelope:

```json
{ "success": true, "message": "", "data": {} }
```

```json
{ "success": false, "message": "", "errors": [] }
```

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Liveness |
| GET | `/datasets` | List datasets |
| POST | `/datasets` | Create dataset `{ name, source, description? }` |
| GET | `/datasets/{id}` | Detail + counts |
| DELETE | `/datasets/{id}` | Cascade delete |
| POST | `/import` | Multipart: `dataset_id` + file (CSV/JSON) |
| GET | `/research-questions` | Optional preset catalog (shortcuts) |
| POST | `/research` | `{ dataset_id, question: string, research_question_id?, top_k? }` — `question` required (free-form); preset id optional |
| GET | `/reports` | List (optional `dataset_id`) |
| GET | `/reports/{id}` | Full report + evidence |
| DELETE | `/reports/{id}` | Delete |
| GET | `/reports/{id}/export?format=md\|pdf\|docx` | Export |
| GET | `/settings` | Effective settings |
| PUT | `/settings` | Update provider/model/embedding |

CORS: allow Vercel frontend origin via `FRONTEND_URL`.

---

## 6. Core workflows

### 6.1 Import → index

```text
Upload CSV/JSON
  → validate columns (content required; optional: author, rating, date, url, external_id)
  → clean (trim, normalize whitespace, strip HTML, drop empties)
  → dedupe by (dataset_id, external_id) or content hash
  → insert conversations
  → chunk (simple: ~500–800 chars with overlap; one chunk if short)
  → embed via provider abstraction
  → store vectors in conversation_chunks
  → dataset.status = ready
```

MVP import format (CSV headers):

`content,author,rating,posted_at,url,external_id,source`

### 6.2 Research (RAG — mandatory)

```text
Accept free-form question_text (required)
  → optionally resolve preset → may override/specialize prompt file
  → load prompts/free_form_research.md (or preset prompt_file)
  → embed query text = user question (plus preset description if used)
  → pgvector similarity search filtered by dataset_id (top_k, default 12)
  → build context with citations (conversation_id, snippet, source)
  → LLM with system: answer ONLY from context; refuse if insufficient
  → parse structured sections into report JSON fields
  → compute confidence from evidence count/diversity
  → persist report with question_text always stored
```

Never call the LLM without retrieval results. If zero chunks: fail report with clear message.

Free-form validation (server + client):

- Reject empty / whitespace-only questions
- Min length ~10 chars; max length ~2000 chars (configurable)
- Not a chatbot thread: each Run is one-shot research → one report
- Still evidence-first: off-topic or unanswered questions fail with insufficient evidence, not world-knowledge answers

### 6.3 AI provider abstraction

Single interface in `services/ai_provider.py`:

- `embed(texts: list[str]) -> list[list[float]]`
- `chat(messages: list[dict], temperature: float) -> str`

Implementations share OpenAI-compatible HTTP where possible (`AI_BASE_URL` + `AI_API_KEY` + `AI_MODEL`). Gemini via compatible endpoint or thin adapter; no provider-specific branching in research/import services.

---

## 7. Frontend pages (MVP only)

| Route | UI |
|-------|-----|
| `/` | Counts: datasets, conversations, indexed; recent reports; CTAs |
| `/datasets` | Table + create + import + delete |
| `/datasets/[id]` | Metadata, status, sample conversations, re-embed optional later |
| `/research` | Dataset select, **free-form question textarea** (required), optional preset chips that pre-fill the textarea, Run Analysis, results pane |
| `/history` | Past reports list (shows `question_text`) |
| `/history/[id]` | Full structured report + question asked + evidence list + export buttons |
| `/settings` | Provider, model, embedding model (writes API settings) |

Shell: persistent sidebar (Dashboard, Datasets, Research, History, Settings). No auth screens.

---

## 8. Free-form questions and optional presets (MVP)

**Primary input:** users type any research question about the selected dataset.

**Optional presets:** seeded shortcuts that pre-fill the question box (and may select a specialized prompt). They do **not** replace free-form input.

| Slug | Preset title (pre-fills question) | Prompt file |
|------|-----------------------------------|-------------|
| *(default)* | — | `prompts/free_form_research.md` |
| pain_points | What are the most common customer pain points? | `prompts/pain_points.md` |
| feature_requests | What features do customers request most often? | `prompts/feature_requests.md` |
| sentiment | What is overall customer sentiment and why? | `prompts/sentiment.md` |
| discovery_behaviour | Why do customers stick to familiar categories / fail to discover new ones? | `prompts/discovery_behaviour.md` |
| opportunities | What product opportunities emerge from customer evidence? | `prompts/opportunities.md` |
| executive_summary | Produce an executive research summary for leadership | `prompts/executive_summary.md` |

`free_form_research.md` and every preset prompt must instruct: evidence-only, quote customers, separate observation vs opportunity, assign confidence, refuse when evidence is insufficient.

This is **not** a multi-turn chatbot. Each submission produces one structured research report.

---

## 9. Environment variables

```text
# Backend
DATABASE_URL=
SUPABASE_URL=
SUPABASE_KEY=
AI_PROVIDER=openrouter          # openrouter | groq | gemini | openai_compatible
AI_API_KEY=
AI_BASE_URL=                    # optional override
AI_MODEL=
EMBEDDING_MODEL=
EMBEDDING_DIMENSIONS=1536
FRONTEND_URL=
UPLOAD_DIR=/tmp/zepto-uploads
LOG_LEVEL=INFO

# Frontend
NEXT_PUBLIC_API_BASE_URL=
```

Never commit secrets. Ship `.env.example` only.

---

## 10. Phased build (execution order)

### Phase 1 — Project foundation

- Scaffold `frontend/` (Next.js 15 + Tailwind + shadcn) and `backend/` (FastAPI)
- Connect Supabase; Alembic migration for schema + pgvector
- Health endpoint; CORS; standard response helpers; structured logging
- Deploy empty shells to Vercel + Render; document env setup in README

**Exit:** Browser hits frontend; frontend can call `/health`.

### Phase 2 — Dataset management

- Dataset CRUD APIs + UI
- CSV/JSON import, cleaning, dedupe, conversation storage
- Dataset status transitions

**Exit:** User can create a dataset, import a sample CSV, see conversation count.

### Phase 3 — Embeddings

- Chunking service
- Embedding provider
- Write `conversation_chunks.embedding`; similarity query helper
- Mark dataset `ready` when indexing completes

**Exit:** Semantic search returns relevant chunks for a smoke query.

### Phase 4 — Research engine

- Generic `prompts/free_form_research.md` + optional preset prompts/seeds
- Accept free-form `question` on `POST /research`; store `question_text` on reports
- Retrieval → context builder → LLM → structured report persistence
- Confidence heuristic (e.g. high ≥8 diverse chunks, medium 4–7, low <4)

**Exit:** `POST /research` with a custom question returns a completed report with evidence citations.

### Phase 5 — Frontend research UX + export

- Research workspace with free-form textarea + optional preset chips
- History detail shows question asked; Dashboard wiring
- Export Markdown (required); PDF/DOCX best-effort (markdown→PDF/DOCX libs)
- Settings page wired to API

**Exit:** Full click-path: import → type question → research → view → export.

### Phase 6 — Harden & ship

- Full E2E smoke (`scripts/smoke_e2e.py`) + RAG no-LLM unit tests
- Production README: deploy, free-tier limits, troubleshooting
- Manual UI checklist (`docs/manual-ui-checklist.md`)
- Caps documented (upload 10MB, 5k rows, top_k 1–50); history limited to latest 200

**Exit:** Smoke green locally; DoD cloud boxes still require your Vercel/Render deploy.

### Phase 7 — Public mentions collection (post-MVP)

- **7a:** Feasibility matrix + spikes (ToS/API first) — [phase-7-collection-feasibility.md](./phase-7-collection-feasibility.md)
- **7b+:** Approved collectors → master “Zepto Public Mentions” dataset → existing RAG
- Do not scrape No-go sources; keep CSV import as fallback

---

## 11. Definition of Done (MVP)

- [ ] App reachable in browser on Vercel
- [ ] Backend on Render connected to Supabase
- [ ] Create/import/delete datasets
- [ ] Conversations cleaned, stored, embedded in pgvector
- [ ] Free-form research questions runnable (optional presets as shortcuts)
- [ ] Reports store `question_text` and include summary, findings, evidence quotes + sources, confidence
- [ ] Reports listed in History and exportable (at least Markdown)
- [ ] AI provider/model switchable via Settings/env
- [ ] No auth; no live scrapers required (file import is enough)
- [ ] README documents setup, env, sample CSV, deploy steps

---

## 12. Explicit non-goals (do not build in MVP)

Live social listening, streaming scrapers, auth/multi-tenant, background queue workers beyond sync processing, predictive analytics, CRM integrations, fine-tuning, agentic workflows, internal Zepto private data, multi-turn chatbot / conversational thread UI.

---

## 13. Risks & mitigations

| Risk | Mitigation |
|------|------------|
| Render free cold starts | Frontend shows loading; health retry; document warm-up |
| Embedding dimension mismatch | Single `EMBEDDING_DIMENSIONS`; migrate if model changes |
| Hallucinations | Enforce RAG; prompt refuse-if-empty; cite conversation IDs |
| Off-topic free-form questions | Insufficient evidence → fail report; never answer from world knowledge |
| Large CSV timeouts | Cap rows per import (e.g. 5k) in MVP; chunked insert |
| Free-tier AI rate limits | Surface errors; allow provider switch in Settings |

---

## 14. Next action after this plan

Begin **Phase 1**: scaffold monorepo (`frontend/`, `backend/`, `database/`, `prompts/`), migrations, and deploy skeleton.
