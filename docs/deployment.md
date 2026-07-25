# Deploy Zepto live (GitHub → Render + Vercel + Supabase)

This guide gets a **working production app**: Next.js on **Vercel**, FastAPI on **Render**, Postgres + pgvector on **Supabase**, source on **GitHub**.

Architecture:

```text
Browser → Vercel (frontend) → Render (API) → Supabase (DB)
                └─ AI keys stay only on Render (never in Next.js)
```

---

## Prerequisites

| Account | Why |
|---------|-----|
| [GitHub](https://github.com) | Host the monorepo |
| [Supabase](https://supabase.com) | Postgres + `vector` |
| [Render](https://render.com) | Backend Docker web service |
| [Vercel](https://vercel.com) | Frontend |
| [OpenRouter](https://openrouter.ai/keys) (or other AI) | Index + Research |

Local tools: Git, and optionally the GitHub CLI (`gh`).

---

## Step 0 — Secrets checklist (gather before clicking Deploy)

Copy these somewhere private (password manager). You will paste them into dashboards — **never commit them**.

| Secret | Where it goes | Notes |
|--------|---------------|--------|
| Supabase DB password + pooler URL | Render `DATABASE_URL` | Use **session pooler port 5432**. Prefix driver: `postgresql+psycopg://…`. Encode `@` in password as `%40`. Append `?sslmode=require` if missing. |
| OpenRouter (or provider) API key | Render `AI_API_KEY` | |
| Vercel site URL | Render `FRONTEND_URL` | Exact origin, e.g. `https://zepto-xxx.vercel.app` — **no trailing slash** |
| Render API URL | Vercel `NEXT_PUBLIC_API_BASE_URL` | e.g. `https://zepto-api.onrender.com` — **HTTPS**, no trailing slash |

Chicken-and-egg: deploy API first with a temporary `FRONTEND_URL=http://localhost:3000`, deploy Vercel, then **update** Render `FRONTEND_URL` to the real Vercel URL and redeploy (or restart) the API.

---

## Step 1 — Put the repo on GitHub

From the project root (`d:\Zepto`):

```powershell
cd d:\Zepto
git status
```

If there is no git repo yet:

```powershell
git init
git add .
git commit -m "Initial commit: Zepto AI Product Research Assistant"
gh repo create zepto --private --source=. --remote=origin --push
```

Or create an empty repo on github.com, then:

```powershell
git remote add origin https://github.com/<you>/<repo>.git
git branch -M main
git push -u origin main
```

Confirm `.env` / `.env.local` are **not** in the commit (they are gitignored).

---

## Step 2 — Supabase database

1. Create a project at [supabase.com](https://supabase.com).
2. **Database → Extensions** → enable **`vector`**.
3. **Project Settings → Database → Connection string**:
   - Prefer **Session pooler** (host like `aws-0-<region>.pooler.supabase.com`, port **5432**).
   - Avoid transaction pooler (**6543**) for this app’s SQLAlchemy sessions.
4. Build `DATABASE_URL`:

```text
postgresql+psycopg://postgres.<project-ref>:<PASSWORD>@aws-0-<region>.pooler.supabase.com:5432/postgres?sslmode=require
```

5. Migrations run automatically when the Render container starts (`docker-entrypoint.sh` → `alembic upgrade head`). You can also run once from your laptop:

```powershell
cd d:\Zepto\backend
Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue
# Put DATABASE_URL in backend/.env, then:
.\.venv\Scripts\alembic.exe upgrade head
```

---

## Step 3 — Backend on Render

### Option A — Blueprint (recommended)

1. Push `render.yaml` with the repo (already in the monorepo root).
2. Render Dashboard → **New → Blueprint** → select the GitHub repo.
3. When prompted, set:

| Key | Value |
|-----|--------|
| `DATABASE_URL` | Pooler URL from Step 2 |
| `FRONTEND_URL` | Temporary `http://localhost:3000`, then update after Vercel |
| `AI_API_KEY` | Your provider key |

4. Confirm service settings:
   - **Dockerfile path:** `./backend/Dockerfile`
   - **Docker context:** repo root (`.`)
   - **Health check:** `/api/v1/health`
5. Deploy and wait until health is green.
6. Copy the service URL, e.g. `https://zepto-api.onrender.com`.

### Option B — Manual Web Service

1. **New → Web Service** → connect GitHub repo.
2. Runtime: **Docker**
3. Dockerfile path: `backend/Dockerfile`
4. Docker build context directory: `/` (repo root)
5. Health check path: `/api/v1/health`
6. Same env vars as Option A.

### Verify API

```powershell
curl.exe https://YOUR-API.onrender.com/api/v1/health
```

Expect `"success": true`. First hit on the **free** plan may take 30–60s (cold start).

---

## Step 4 — Frontend on Vercel

1. [vercel.com/new](https://vercel.com/new) → Import the same GitHub repo.
2. **Root Directory:** `frontend` (important — monorepo).
3. Framework: Next.js (auto).
4. Environment variable:

| Name | Value |
|------|--------|
| `NEXT_PUBLIC_API_BASE_URL` | `https://YOUR-API.onrender.com` |

5. Deploy.
6. Copy the production URL, e.g. `https://zepto-xxx.vercel.app`.

---

## Step 5 — Wire CORS (required for a working UI)

1. Render → zepto-api → **Environment**
2. Set `FRONTEND_URL` = your Vercel origin exactly (no trailing slash).  
   Optional preview: `https://zepto-xxx.vercel.app,https://zepto-xxx-git-main-you.vercel.app`
3. **Manual Deploy** / restart so CORS reloads.
4. Open the Vercel site → Dashboard should show API healthy (Retry if cold).

---

## Step 6 — Smoke the live app

In the browser:

1. **Datasets** → create → import [`scripts/sample_conversations.csv`](../scripts/sample_conversations.csv) (or a small CSV) → **Index** until `ready`.
2. **Research** → ask a question → report succeeds.
3. **History** → open / export Markdown.
4. Optional: **Refresh from stores** (small incremental collect). Do **not** rely on HTTP **bulk 100k** on free Render — timeouts; run bulk from a laptop with production `DATABASE_URL` if needed.

From your machine (with backend venv):

```powershell
$env:API_BASE_URL="https://YOUR-API.onrender.com"
cd d:\Zepto
.\backend\.venv\Scripts\python.exe .\scripts\smoke_e2e.py
```

---

## Step 7 — Optional hardening

| Item | Suggestion |
|------|------------|
| Custom domains | Add domain on Vercel + Render; update `FRONTEND_URL` / `NEXT_PUBLIC_API_BASE_URL` |
| Keep Render awake | Cron ping `/api/v1/health` every 10–14 min, or upgrade plan |
| AI spend | Cap OpenRouter credits; use cheaper embedding/chat models in Settings |
| Auth | MVP has no login — treat URLs as semi-public; add auth before sharing widely |
| Bulk collectors | Prefer local CLI against prod DB; App Store remains best-effort |
| Secrets rotation | If a DB password leaked in chat/logs, rotate in Supabase and update Render |

---

## Env reference (production)

### Render

| Variable | Required |
|----------|----------|
| `DATABASE_URL` | Yes |
| `FRONTEND_URL` | Yes (Vercel origin) |
| `AI_API_KEY` | Yes for Index/Research |
| `AI_PROVIDER` | Default `openrouter` |
| `AI_MODEL` / `EMBEDDING_*` | Optional |
| `PROMPTS_DIR` | `/prompts` (set in Blueprint) |

### Vercel

| Variable | Required |
|----------|----------|
| `NEXT_PUBLIC_API_BASE_URL` | Yes (Render HTTPS origin) |

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| CORS / blocked fetch | `FRONTEND_URL` must match the browser origin exactly |
| Mixed content | Frontend HTTPS must call HTTPS API |
| Health 503 | Bad `DATABASE_URL`, wrong password encoding, or vector extension off |
| Research “prompt not found” | Image must include `/prompts` (repo-root Docker context) |
| Build fails on Render | Context must be **repo root**, Dockerfile `backend/Dockerfile` |
| Vercel build wrong app | Root Directory must be `frontend` |
| Cold start / timeouts | Wait + Retry; long Index/Research may need a paid Render plan |
| Empty schema | Check container logs for `alembic upgrade head` on boot |

---

## What we aligned in the repo for this plan

- `backend/Dockerfile` — repo-root context, Node for App Store helper, `$PORT`, copies `prompts/`
- `backend/docker-entrypoint.sh` — runs migrations on start
- `render.yaml` — Blueprint for Render
- `frontend/vercel.json` + `.nvmrc` (Node 20+)
- Prompt path + SSL connect args safe for local vs hosted DB
- `.dockerignore` so `.env` is not baked into images
