# Phase 7 — Public mentions collection (feasibility → connectors → master corpus)

**Status:** 7b shipped — **Refresh** (≤100/store) + **bulk backfill** CLI/API (Play-first, target 100k). See [phase-7-user-guide.md](./phase-7-user-guide.md) §5.  
**Depends on:** Phases 1–6 (import → embed → research pipeline stable)  
**Related:** [phase-architecture.md](./phase-architecture.md), [implementation-plan.md](./implementation-plan.md), [phased-edge-cases.md](./phased-edge-cases.md)

---

## 1. Objective

Find which public platforms can supply Zepto-related reviews, comments, and mentions in a way that is:

1. **Technically workable** (stable access, parseable fields)  
2. **Policy-aware** (ToS / API terms / robots — not “scrape everything”)  
3. **Operable on free-tier** (or cheap paid APIs with clear caps)  
4. **Compatible with the existing schema** (`conversations` + `source` + `external_id` + `url`)

Then, only for **Go / Conditional** sources, build collectors that feed a **single master research dataset** (“Zepto Public Mentions”) while preserving per-row source metadata.

**This document is not legal advice.** Before enabling any Conditional connector in production, have Zepto legal/compliance review the target platform terms for your use case (internal product research).

---

## 2. Guiding principles

| Principle | Meaning |
|-----------|---------|
| Research before code | No collector ships until its row in the matrix is filled with evidence |
| Collectors ≠ scrapers | Prefer official APIs → licensed providers → export tools → scraping last |
| One corpus, many sources | One dataset for Research; every row keeps `source`, `url`, `external_id`, `posted_at` |
| Idempotent ingest | Re-runs upsert/dedupe; never explode duplicates |
| Fail closed | Blocked / ToS-no-go sources stay manual CSV import only |
| Don’t break Phase 1–6 | Collection is an **ingress** into existing clean → embed → RAG |

```text
[Platforms]
    ↓  Phase 7a: feasibility matrix + spikes
[Approved collectors]
    ↓  normalize → conversation rows
[Master dataset: Zepto Public Mentions]
    ↓  existing Phase 2–4 path
[Index → Research → History]
```

---

## 3. Phase 7 sub-phases

| Sub-phase | Goal | Deliverable | Code? |
|-----------|------|-------------|-------|
| **7a Feasibility** | Score platforms | This matrix filled + spike notes | Spike scripts only (throwaway OK) |
| **7b Pilot connectors** | 1–3 Go sources live | Collector jobs → upsert into master dataset | Yes |
| **7c Master corpus UX** | PM can refresh / see source mix | UI: “Refresh sources”, source breakdown, last sync | Yes |
| **7d Harden** | Quotas, retries, audit | Smoke for collectors; docs | Yes |

**Gate:** Do not start **7b** until **7a** exit criteria pass for at least two **Go** (or one Go + one Conditional with legal OK).

---

## 4. Feasibility matrix (initial — to be confirmed in 7a)

**Verdict legend**

| Verdict | Meaning |
|---------|---------|
| **Go** | Viable path exists that is primarily API/export/licensed; fit for pilot |
| **Conditional** | Possible via third-party API or careful collection; needs legal + cost approval |
| **No-go (auto)** | Do not build automated collectors for MVP+; manual export only if ever |
| **TBD** | Spike required before verdict |

**Method preference order:** Official API → Licensed data API → Manual/tool export → HTML scrape (last resort).

| Platform category | Example targets (Zepto / quick-commerce) | Official / supported access | Unofficial scrape | Initial verdict | Notes for 7a spike |
|-------------------|------------------------------------------|----------------------------|-------------------|-----------------|-------------------|
| **Google Play Store** | Zepto Android app reviews | **Own-app only** via Play Developer API | Python `google-play-scraper` | **Conditional** (spike OK: 50 reviews 2026-07-25) | Prefer official API if Console access; else pilot scraper with stakeholder OK |
| **Apple App Store** | Zepto iOS reviews | **Own-app only** via App Store Connect | Node `app-store-scraper` (Python lib broken; RSS empty) | **Conditional / fragile** | Get Connect API keys; scraper intermittent |
| **Reddit** | r/india, city subs, q-commerce threads mentioning Zepto | Data API under Reddit terms; **approval required**; commercial/AI use restricted; scraping discouraged | Against policy / fragile | **Conditional** (API + approval) | Spike: register developer intent for *internal research ingest* (not model training). Measure rate limits. Prefer search + subreddit listing over bulk dump |
| **Community forums** | Team-BHP-style, local city forums, MouthShut threads, etc. | Rarely consistent APIs; often HTML + login walls | Case-by-case robots/ToS | **TBD** per forum → usually **Conditional** or **No-go** | Spike: pick ≤3 India-relevant forums; check robots.txt + ToS; sample 20 threads manually first |
| **Social — YouTube** | Review videos / comments mentioning Zepto | YouTube Data API (quota, key, ToS) | Comment scrape brittle | **Conditional** (official API) | Spike: search `Zepto` + comment threads; quota cost for 1k comments |
| **Social — X / Twitter** | Mentions of Zepto | Paid API tiers; free access very limited | Against ToS / blocked | **No-go (auto)** for free-tier MVP | Document manual export only if needed later |
| **Social — Instagram / Facebook** | Reels comments, pages | Meta Graph API for owned assets only | Hard anti-bot | **No-go (auto)** for public scrape; **Conditional** if Zepto owns pages | Spike only if marketing gives page tokens |
| **Product review sites** | MouthShut, Mouthshut-like, Trustpilot-style (if Zepto listed) | Occasional partner APIs; mostly HTML | ToS often prohibit bots | **TBD / Conditional** | Spike: is Zepto listed? robots + sample. Prefer licensed review aggregators |
| **Quick-commerce discussion** | Dedicated Discords, Telegram, WhatsApp groups, Reddit AMAs | Usually private / consent-heavy | Do not scrape private groups | **No-go (auto)** for private chats | Public web forums only if 7a finds open ones |
| **News / blogs** | Articles mentioning Zepto delivery UX | RSS / publisher APIs | Full-site scrape often blocked | **Conditional** (RSS / search API) | Lower priority than reviews; optional enrichment |
| **Manual / partner CSV** | Exports from AppFollow, Sensor Tower, internal CX tools | N/A — already supported | N/A | **Go** (baseline) | Keep as fallback for every Conditional source |

### 4.1 Likely pilot shortlist (hypothesis — confirm in 7a)

1. **Google Play reviews for Zepto’s own app** (official API) — if Console access exists  
2. **App Store reviews for Zepto’s own app** (Connect / approved method) — if access exists  
3. **Reddit** (approved Data API) **or** skip until approval  
4. **YouTube Data API** comments on high-signal videos (quota-limited)  
5. Always-on: **CSV/JSON import** from any tool export  

Everything else waits behind Conditional + legal.

---

## 5. Research & testing plan (Phase 7a)

### 5.1 Scorecard dimensions (fill per platform)

Score each 1–5 (5 = best). Weighted recommendation = average unless Legal = 1 (hard stop).

| Dimension | Question |
|-----------|----------|
| **L — Legal / ToS** | Is automated collection permitted for *internal product research*? |
| **T — Technical** | Can we get structured text + id + date + url reliably? |
| **S — Stability** | Will this break monthly? Anti-bot? |
| **C — Cost** | Free tier / approval / paid API within budget? |
| **V — Volume & value** | Enough Zepto-specific signal for RAG? |
| **P — PII risk** | Authors, phones, addresses in clear text? |

**Decision rule**

- Any **L = 1** → **No-go (auto)**  
- **L ≥ 4** and **T ≥ 4** and **C ≥ 3** → **Go**  
- Else if **L ≥ 3** and stakeholder accepts risk/cost → **Conditional**  
- Else → **No-go** or stay on manual import  

### 5.2 Spike protocol (per candidate)

For each platform in the matrix:

1. **Desk research (½ day)**  
   - Find official docs + ToS / Developer / Data API terms  
   - Note: rate limits, approval gates, “no scraping”, AI/training clauses  
   - Record links + date reviewed in spike log  

2. **Access check (½–1 day)**  
   - Can we obtain keys / Console access / API approval?  
   - If no within 1 week → demote to Conditional/No-go  

3. **Technical spike (½–1 day)**  
   - Pull **≤ 100** sample items (hard cap)  
   - Map to conversation schema:  
     `content, author, rating, posted_at, url, external_id, source, metadata`  
   - Measure: success rate, fields missing, duplicates, language mix  

4. **Policy checkpoint**  
   - Write 5-line summary: method, risk, go/conditional/no-go  
   - Escalate Conditional to legal before 7b  

5. **Stop rule**  
   - Do not scale beyond 100 items in 7a  
   - Do not commit scraper credentials to git  
   - Do not store more PII than needed (prefer handles over emails/phones)

### 5.3 Spike log template

Save under `docs/spikes/YYYY-MM-DD-<platform>.md`:

```markdown
# Spike: <platform>
Date:
Reviewer:
Official docs / ToS links:
Access obtained? (yes/no/pending):
Method tested: (API / vendor / export / HTML)
Sample size:
Schema mapping notes:
Failures / blocks:
Scores: L=_ T=_ S=_ C=_ V=_ P=_
Verdict: Go | Conditional | No-go
Legal review required? (yes/no)
Recommendation for 7b:
```

### 5.4 7a schedule (suggested ~1–2 weeks)

| Day | Activity |
|-----|----------|
| 1–2 | Desk research: Play, App Store, Reddit, YouTube, 2 forums, 1 review site |
| 3–5 | Access + technical spikes for top 4 candidates |
| 6 | Fill matrix verdicts; legal pass on Conditionals |
| 7 | Write 7a exit report; pick pilot connectors for 7b |

### 5.5 7a exit criteria

- [ ] Matrix has a final verdict for every row in §4 (no blank TBD left without a date+owner)  
- [ ] ≥1 **Go** source with successful ≤100-item spike **or** documented blocker (e.g. no Console access)  
- [ ] Spike logs checked into `docs/spikes/`  
- [ ] Explicit list: **Pilot connectors for 7b** vs **parked**  
- [ ] Legal sign-off recorded for any Conditional chosen for pilot  
- [ ] No production scrapers merged  

---

## 6. Target architecture (after 7a — for 7b+)

### 6.1 Master corpus

| Concept | Design |
|---------|--------|
| Master dataset | One dataset, e.g. name `Zepto Public Mentions`, `source=other` or dedicated `aggregated` |
| Per-row provenance | `conversations.source` = `google_play` \| `app_store` \| `reddit` \| … |
| Dedupe | `(dataset_id, external_id)` when platform id exists; else content hash |
| Refresh | Collector job appends/upserts; then **reindex** (or incremental embed later) |
| Research | Unchanged Phase 4/5 UX; optional later filter by source |

Extend `ALLOWED_SOURCES` only when a connector is approved (e.g. keep `youtube`, add `forum` if needed).

### 6.2 Collector shape (do not build in 7a)

```text
POST /api/v1/collectors/{name}/run   # or cron worker
  → fetch page/batch from approved method
  → normalize rows
  → reuse import_service upsert path (or shared ingest service)
  → update collector_runs (status, counts, errors)
  → optional auto-reindex
```

Suggested tables (7b):

- `collector_configs` — enabled sources, query params, secrets ref  
- `collector_runs` — started_at, finished_at, inserted, skipped, error_message  

### 6.3 What Phase 7 must not do

- Replace CSV import (keep as universal fallback)  
- Call LLM during collection  
- Scrape logged-in private groups / WhatsApp / Discord DMs  
- Train foundation models on collected text (out of scope; may violate Reddit/other terms)  
- Bypass CAPTCHAs or rotate residential proxies to evade blocks (hard No-go for this product)

---

## 7. Edge cases (Phase 7-specific)

| ID | Scenario | Expected handling |
|----|----------|-------------------|
| P7-FEAS-001 | Platform ToS forbids scraping | Verdict No-go; document manual export path |
| P7-FEAS-002 | Official API only for “own app” and no Console access | Verdict blocked; ask PM for access or use vendor Conditional |
| P7-FEAS-003 | Reddit denies API approval | Park Reddit; do not HTML-scrape as workaround |
| P7-FEAS-004 | Spike triggers IP ban / CAPTCHA | Stop immediately; mark Stability low; prefer vendor/API |
| P7-FEAS-005 | Sample has heavy PII | Strip phones/emails in normalizer; log P score |
| P7-FEAS-006 | Duplicate across Play + CSV export | Dedupe by external_id / hash inside master dataset |
| P7-FEAS-007 | Source mix skews RAG (90% one angry thread) | Track source counts; optional per-source caps in 7b |
| P7-COLL-001 | Collector mid-failure | Partial upsert OK; run marked failed; no corrupt status machine |
| P7-COLL-002 | Re-run same day | Idempotent; skipped count rises |
| P7-COLL-003 | Embedding settings changed | Same as Phase 4: reindex required before research |
| P7-SEC-001 | API keys in frontend | Forbidden — server env only |
| P7-SEC-002 | Storing full HTML pages | Prefer normalized text only |

---

## 8. Verification

### 7a verify

1. Matrix table complete with scores + verdicts.  
2. Each Go/Conditional has a spike log with sample schema mapping.  
3. Zero collector code merged to main without 7a gate.  

### 7b verify (later)

1. Collector dry-run inserts into master dataset with correct `source`.  
2. Reindex → Research free-form question cites multi-source evidence.  
3. Smoke extension: `collect → import path → research`.  

---

## 9. Success metrics

| Metric | Target (pilot) |
|--------|----------------|
| Approved automated sources | ≥ 2 Go (ideally Play + App Store own-app, or Play + YouTube) |
| Master corpus size | ≥ 500 conversations (quality > vanity volume) |
| Source coverage | ≥ 2 distinct `source` values in master dataset |
| Duplicate rate on re-run | &lt; 5% new inserts on identical pull |
| Research usefulness | PM can answer 3 free-form questions with citations |

---

## 10. Open decisions (for stakeholders)

1. Does Zepto internal team have **Play Console** and **App Store Connect** access for the consumer apps?  
2. Is budget available for **Reddit commercial API** and/or **review-data vendors**?  
3. Is collection limited to **India** storefronts / languages (EN/HI)?  
4. Retention: how long to keep raw mentions (30/90/365 days)?  
5. Who signs Conditional legal approvals?

---

## 11. Immediate next actions

1. Assign owner for 7a (eng + PM).  
2. Answer open decision #1 (Console access).  
3. Create `docs/spikes/` and run Play + App Store + Reddit + YouTube desk research.  
4. Re-open this doc and replace **Initial verdict** column with **Confirmed verdict** + dates.  
5. Only then schedule 7b implementation.

---

## Document control

| Version | Date | Change |
|---------|------|--------|
| 0.1 | 2026-07-24 | Initial draft: principles, matrix, 7a test plan, 7b architecture sketch |
