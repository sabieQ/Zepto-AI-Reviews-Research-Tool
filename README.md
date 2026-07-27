# Zepto AI Product Research Assistant

Browser-based internal tool that ingests public Zepto customer conversations, indexes them with embeddings, and answers **free-form research questions** with evidence-backed RAG reports.

```text
Browser (Next.js / Vercel)
        │ HTTPS
        ▼
FastAPI (Render free web service)
        │
        ├─► Supabase Postgres + pgvector (conversations, chunks, reports)
        └─► OpenRouter / OpenAI / Groq / Gemini (embeddings + chat)
```

**Architecture lock:** cloud free-tier · no auth in MVP · CSV/JSON import + optional store collectors (Phase 7) · RAG never calls the LLM without retrieved evidence.

## Phase status

| Phase | Status |
|-------|--------|
| 1 Foundation | Complete |
| 2 Datasets | Complete |
| 3 Embeddings | Complete |
| 4 Research engine | Complete |
| 5 UI + export | Complete |
| 6 Harden & ship | Complete (smoke + docs + invariant tests) |
| 7 Collection (feasibility) | 7b Refresh + bulk backfill — see [docs/phase-7-user-guide.md](docs/phase-7-user-guide.md) |

See [docs/phase-architecture.md](docs/phase-architecture.md), [docs/phased-edge-cases.md](docs/phased-edge-cases.md), [docs/manual-ui-checklist.md](docs/manual-ui-checklist.md).

## Repository layout

```text
frontend/   Next.js 15 app
backend/    FastAPI + Alembic
database/   Reference SQL + seeds
prompts/    RAG prompt templates
docs/       Specs and phase plans
docker/     Optional local Postgres (pgvector)
scripts/    Smoke helpers (smoke_e2e.py)
```

## Prerequisites

- Node.js 20+
- Python 3.12+
- Supabase project with the `vector` extension **or** Docker Postgres with pgvector
- OpenRouter (recommended) or another OpenAI-compatible API key

## Environment

### Backend (`backend/.env`)

Copy from `backend/.env.example`:

| Variable | Required | Notes |
|----------|----------|--------|
| `DATABASE_URL` | Yes | Prefer Supabase **pooler** URL: `postgresql+psycopg://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres?sslmode=require` — URL-encode `@` in passwords as `%40` |
| `FRONTEND_URL` | Yes (prod) | Exact browser origin for CORS, e.g. `https://your-app.vercel.app` |
| `LOG_LEVEL` | No | Default `INFO` |
| `AI_PROVIDER` | Phase 3+ | `openrouter` (default), `openai`, `groq`, `gemini`, `openai_compatible` |
| `AI_API_KEY` | Phase 3+ | Never commit; never expose to the frontend |
| `AI_BASE_URL` | If compatible | Required when provider is `openai_compatible` |
| `AI_MODEL` | No | Default `openai/gpt-4o-mini` |
| `EMBEDDING_MODEL` | No | Default `openai/text-embedding-3-small` |
| `EMBEDDING_DIMENSIONS` | No | Default **1536** — must match model; changing requires **re-index** |

### Frontend (`frontend/.env.local`)

| Variable | Required | Notes |
|----------|----------|--------|
| `NEXT_PUBLIC_API_BASE_URL` | Yes | Backend origin only, e.g. `http://localhost:8000` or `https://your-api.onrender.com` (HTTPS in production) |

Only `NEXT_PUBLIC_*` is bundled to the browser. API keys must **not** appear here.

## Hard limits (server-enforced)

| Limit | Value |
|-------|--------|
| Upload size | 10 MB |
| Import rows | 5,000 |
| `top_k` | 1–100 (default 12) |
| Question length | 10–2000 characters |
| History list | Latest 200 reports |

**Re-index:** Idempotent — deletes existing chunks for the dataset and rebuilds embeddings. Changing embedding model/dimensions via Settings resets `ready` datasets to `imported`; research is blocked until you Index again.

## Local run

### 1. Database

**Recommended for this project:** Supabase cloud (no Docker required). Enable **Extensions → vector**, then set `DATABASE_URL` as above.

Optional Docker:

```bash
docker compose -f docker/docker-compose.yml up -d db
```

### 2. Backend

```bash
cd backend
python -m venv .venv
# Windows: .\.venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env   # or cp — then edit DATABASE_URL + AI_API_KEY
# Clear any shell override that points at localhost:
# PowerShell: Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

Health: `GET http://localhost:8000/api/v1/health` → `{ "success": true, ... }`

### 3. Frontend

```bash
cd frontend
copy .env.example .env.local
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

### 4. Unit test (RAG invariant)

```bash
cd backend
# DATABASE_URL must be set (same as .env) so app imports resolve
.\.venv\Scripts\python.exe -m unittest tests.test_rag_invariant -v
```

### 5. Full API smoke (Phase 6)

With the API running and `AI_API_KEY` configured:

```bash
# PowerShell
$env:API_BASE_URL="http://127.0.0.1:8000"
.\backend\.venv\Scripts\python.exe .\scripts\smoke_e2e.py
```

Spine: health → create → import → index → research → get report → export Markdown → delete (+ negatives: bad CSV, empty question, missing dataset, invalid settings).

## Product workflow (UI)

1. **Datasets** — create → import CSV/JSON → Index until `ready`
2. **Research** — pick ready dataset → free-form question (or preset chip) → Run analysis
3. **History** — view report / export Markdown / delete
4. **Settings** — provider, chat model, embedding model, top_k (API key stays in `.env`)

Sample file: [`scripts/sample_conversations.csv`](scripts/sample_conversations.csv)

## Deploy

Full production runbook (GitHub → Supabase → Render → Vercel): **[docs/deployment.md](docs/deployment.md)**

### Quick summary

1. **Supabase** — enable `vector`; set pooler `DATABASE_URL` (`postgresql+psycopg://…?sslmode=require`)
2. **Render** — Blueprint (`render.yaml`) or Docker web service; context = **repo root**, Dockerfile = `backend/Dockerfile`; set `DATABASE_URL`, `FRONTEND_URL`, `AI_API_KEY`; health = `/api/v1/health`
3. **Vercel** — Root Directory = `frontend`; `NEXT_PUBLIC_API_BASE_URL` = Render HTTPS URL
4. Update Render `FRONTEND_URL` to the exact Vercel origin (CORS), then smoke the UI

Migrations run on container start via `backend/docker-entrypoint.sh`. Free Render sleeps when idle — first request may take 30–60s (UI shows Retry).

### Production checklist

- [ ] HTTPS on both Vercel and Render (no mixed content)
- [ ] `FRONTEND_URL` exactly matches the Vercel origin
- [ ] Health green from Dashboard
- [ ] Run [`docs/manual-ui-checklist.md`](docs/manual-ui-checklist.md)
- [ ] `API_BASE_URL=https://your-api.onrender.com python scripts/smoke_e2e.py` exits 0

## Free-tier limits (expect these)

| Service | Limitation |
|---------|------------|
| Render | Spins down when idle; cold starts; request timeouts on very long jobs |
| Supabase | Row/storage quotas; prefer pooler; rotate DB password if leaked |
| OpenRouter / AI | Rate limits (429) and daily credits — switch model in Settings or wait |

Stale research rows left `running` are marked `failed` on API startup after 30 minutes.

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Missing `DATABASE_URL` | App fails at startup — set `backend/.env` |
| Shell `DATABASE_URL` overrides `.env` | `Remove-Item Env:DATABASE_URL` (PowerShell) then restart uvicorn |
| Health 503 / connection timeout | Wrong host, password, or IPv6-only direct host — use **pooler** + `sslmode=require` |
| CORS errors | Align `FRONTEND_URL` with browser origin (no trailing slash) |
| API unreachable / cold start | Wait and Retry; check Render is awake |
| Embedding dimension mismatch | Set `EMBEDDING_DIMENSIONS=1536` for `text-embedding-3-small`; re-index |
| Research “index first” | Dataset must be `ready` |
| Insufficient evidence | No/weak retrieval — LLM is **not** called; report `failed` |
| Rate limit 429 | Wait or change provider/model in Settings |
| PowerShell curl JSON errors | Use single-quoted `-d '{...}'` or `Invoke-RestMethod` |
| Alembic `%` in password | `env.py` escapes `%` as `%%` for ConfigParser |

## Security (MVP)

- Secrets only in server env / Supabase — not in the Next.js bundle
- Settings API returns `ai_api_key_set` boolean only
- Mutating routes validated with Pydantic; upload size and row caps enforced server-side
- Evidence links open with `rel="noopener noreferrer"`

## License

Internal / proprietary — Zepto product research use.
