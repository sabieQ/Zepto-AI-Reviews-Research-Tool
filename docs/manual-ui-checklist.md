# Manual UI checklist (Phase 6)

Run once against staging or production after deploy. Check each box.

## Preconditions

- [ ] Frontend URL (Vercel) loads over HTTPS
- [ ] Backend health is green on Dashboard (retry if cold start)
- [ ] `FRONTEND_URL` matches the Vercel origin (CORS)
- [ ] `NEXT_PUBLIC_API_BASE_URL` is the Render HTTPS URL
- [ ] Supabase has `vector` extension; migrations applied
- [ ] `AI_API_KEY` set on Render

## Core workflow

- [ ] Create a dataset
- [ ] Import `scripts/sample_conversations.csv`
- [ ] Wait until status is `ready` (Index / Re-index if needed)
- [ ] Research: select dataset, type a free-form question (≥10 chars), Run
- [ ] Land on History detail with summary, findings, evidence, confidence
- [ ] Export Markdown downloads a `.md` file with citations
- [ ] History list shows the question text and status
- [ ] Optional: click a preset chip, edit text, run still works
- [ ] Settings: change chat model, save, next report shows new `model_name`
- [ ] Delete report; dataset remains
- [ ] Delete dataset; conversations/chunks/reports gone

## Failure paths

- [ ] Research with blank question — Run disabled / blocked
- [ ] Failed report shows `error_message`; Export disabled
- [ ] Stop backend — Dashboard shows unreachable + Retry
- [ ] Invalid settings provider — validation error, not fake success

## Smoke (API)

```bash
# from repo root, API running
python scripts/smoke_e2e.py
```

- [ ] Smoke exits 0
