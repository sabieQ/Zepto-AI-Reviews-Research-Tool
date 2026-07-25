# Phase 7 — Your step-by-step guide (7a spike → 7b collectors)

This guide tells you **exactly what to run**, **what only you can do** (accounts/APIs), and **when we can build 7b**.

Related: [phase-7-collection-feasibility.md](./phase-7-collection-feasibility.md)

---

## Big picture

```text
YOU NOW (7a)
  1. Run spike scripts (Play + App Store)     ← automated samples
  2. Import CSV into the app + try Research   ← prove value
  3. Decide Conditional OK with stakeholders  ← policy
  4. (Optional) chase official APIs           ← longer path

THEN (7b — ask the agent to build)
  Collectors auto-refresh a master dataset
```

**Important:** The spike uses **unofficial** scrapers (`google-play-scraper` + Node `app-store-scraper`). They work for research pilots but are **Conditional** (may conflict with store ToS; can break). Official APIs are better long-term if you have Console access.

---

## Step 1 — Run the 7a spike (local)

### 1.1 Install spike deps

```powershell
cd d:\Zepto

# Python Play scraper (use backend venv)
.\backend\.venv\Scripts\pip.exe install -r .\scripts\spikes\requirements-spikes.txt

# Node App Store scraper
cd .\scripts\spikes
npm install
cd d:\Zepto
```

### 1.2 Run spike (≤100 reviews per store; default 50)

```powershell
cd d:\Zepto
.\backend\.venv\Scripts\python.exe .\scripts\spikes\spike_store_reviews.py --country in --limit 50
```

Useful flags:

```powershell
# Play only
.\backend\.venv\Scripts\python.exe .\scripts\spikes\spike_store_reviews.py --skip-ios --limit 50

# App Store only
.\backend\.venv\Scripts\python.exe .\scripts\spikes\spike_store_reviews.py --skip-play --limit 50
```

Defaults:

| Store | ID |
|-------|-----|
| Google Play | `com.zeptoconsumerapp` |
| App Store | `1575323645` |

### 1.3 Outputs

Written under `docs/spikes/out/`:

| File | Purpose |
|------|---------|
| `google_play_reviews.csv` | Play-only |
| `app_store_reviews.csv` | iOS-only |
| **`combined_import.csv`** | **Import this into the app** |
| `spike_summary.json` | Counts + method notes |

### 1.4 Fill the spike log

Copy template notes into:

- `docs/spikes/2026-07-25-google-play.md`
- `docs/spikes/2026-07-25-app-store.md`

(Templates are created alongside this guide; edit scores after you run.)

---

## Step 2 — Prove the data in your existing app

1. Start backend + frontend (as usual).
2. **Datasets → Create** → name e.g. `Zepto Public Mentions`.
3. **Import** `docs/spikes/out/combined_import.csv`.
4. Wait until status is **`ready`** (Index if needed).
5. **Research** → ask e.g. *“What are the most common delivery pain points?”*
6. Confirm History shows citations with `google_play` / `app_store` sources.

If this click-path works, **7a technical proof is done** for these two stores.

---

## Step 3 — What only you can do (accounts & “APIs”)

### A) Unofficial scrapers (what the spike uses) — no API keys

| Need from you | Status |
|---------------|--------|
| API key | **None** |
| Approval | Internal OK that Conditional scraping is acceptable for **internal research** |
| Legal | Recommended before scaling past spikes |

### B) Official Google Play reviews (best long-term if Zepto owns the app)

1. Get access to **Google Play Console** for the Zepto consumer app (`com.zeptoconsumerapp`).
2. Enable **Google Play Android Developer API** in Google Cloud linked to that Console.
3. Create a service account; grant it Play Console permissions (View app info / reply to reviews as needed).
4. Download JSON key → store only in server env (never frontend).
5. Use **Reply to Reviews / reviews list** endpoints for **your** app only.

Docs starting points:

- [Play Developer API](https://developers.google.com/android-publisher)
- Reviews are for apps **you publish**, not arbitrary competitors.

**You do:** obtain Console + Cloud credentials.  
**Agent does (7b):** wire official connector if you provide credentials + say “use official Play API”.

### C) Official App Store reviews (App Store Connect)

1. Join / access **Apple Developer** team that owns Zepto (`id1575323645`).
2. In **App Store Connect → Users and Access → Integrations → App Store Connect API**, create an API key (Issuer ID, Key ID, `.p8` private key).
3. Store Issuer ID / Key ID / `.p8` in backend secrets only.
4. Use App Store Connect API customer reviews for **your** apps.

Docs: [App Store Connect API](https://developer.apple.com/app-store-connect/api/)

**Note (2026 spike finding):** Apple’s old public customer-reviews **RSS** returned **0** entries for Zepto; Python `app-store-scraper` also failed. Node `app-store-scraper` still returned reviews in testing — fragile. Prefer Connect API when you have access.

### D) Reddit (optional later)

1. Read [Reddit Data API Terms](https://redditinc.com/policies/data-api-terms) + Responsible Builder Policy.
2. Request developer / data access for **internal research ingest** (not model training).
3. Expect approval delays and possible fees for commercial use.
4. **Do not** HTML-scrape Reddit as a workaround if denied.

### E) YouTube (optional later)

1. Create a Google Cloud project → enable **YouTube Data API v3**.
2. Create an API key (restrict by IP/API).
3. Quotas are limited on free tier — fine for small comment pulls.

---

## Step 4 — Decision gate before 7b

Check these boxes:

- [ ] Spike produced `combined_import.csv` with Play and/or iOS rows  
- [ ] Import → Index → Research worked on that CSV  
- [ ] Stakeholder accepts **Conditional** scrapers for pilot **or** you have official Console credentials ready  
- [ ] You want a **master dataset** auto-refreshed (not one-off CSV)

Then tell the agent: **“Build Phase 7b collectors”** and specify:

1. Scrapers pilot (Play Python + iOS Node), and/or  
2. Official Play / App Store Connect connectors  

---

## Step 5 — Phase 7b collectors (built)

### 5.1 Incremental Refresh (UI / API)

On **Datasets**, click **Refresh from stores** (≤100 reviews/store → `Zepto Public Mentions`, auto-index).

Or:

```powershell
# API must be running
curl.exe -X POST http://127.0.0.1:8000/api/v1/collectors/run -H "Content-Type: application/json" -d "{\"limit\":100,\"auto_index\":true}"
```

### 5.2 One-shot bulk backfill (Play-first, target 100k)

This is the path for your hard volume requirement. Prefer the **CLI** (can run for a long time):

```powershell
cd d:\Zepto
Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue
.\backend\.venv\Scripts\python.exe .\scripts\bulk_backfill_reviews.py --target 100000 --play-countries in,us
```

- Play tries sorts `newest` → `most_relevant` → `rating` per country, ingesting in chunks  
- Stop condition is **dataset conversation_count ≥ target** (restarts continue toward the goal)  
- App Store is best-effort afterward  
- **Does not auto-index by default** (indexing tens of thousands needs AI quota/time). When counts look good:

```powershell
# Index via UI on Zepto Public Mentions, or:
# POST /api/v1/datasets/{id}/reindex
```

Report written to `docs/spikes/out/bulk_backfill_report.json`.

**Expectation:** We measure what Google/Apple actually allow. 100k is ambitious on unofficial scrapers; if the ceiling is below that, the measured max is the outcome — App Store scrapers cannot fill the gap to millions.

### 5.3 APIs

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/v1/collectors/run` | Small refresh (≤100/store) |
| POST | `/api/v1/collectors/bulk` | One-shot bulk (long; prefer CLI) |
| GET | `/api/v1/collectors/runs` | Recent run history |

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `google-play-scraper` missing | `pip install -r scripts/spikes/requirements-spikes.txt` |
| `Node app-store-scraper not installed` | `cd scripts/spikes && npm install` |
| App Store returns 0 / UnicodeDecodeError on Windows | Re-pull latest script (UTF-8 fix); App Store is often empty/flaky — **Play-only CSV is enough** for Step 2. Prefer App Store Connect API later. |
| Play blocked / empty | Wait, lower `--limit`, check network; Google may throttle |
| Import rejects CSV | Ensure `content` column exists (spike CSV already has it) |
| Research weak | Need more rows / reindex / ask delivery-related questions |

---

## Checklist — your actions this week

1. [ ] Run Step 1 spike (or skip if already imported)  
2. [ ] Use **Refresh from stores** for incremental updates  
3. [ ] Run **bulk backfill** CLI toward 100k and check `docs/spikes/out/bulk_backfill_report.json`  
4. [ ] **Index** `Zepto Public Mentions` after bulk (bulk does not auto-index)  
5. [ ] Ask internally: OK to keep unofficial scrapers for pilot?  
6. [ ] Ask internally: Who has Play Console / App Store Connect for official scale?
