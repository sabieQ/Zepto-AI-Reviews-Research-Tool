# Spike logs (Phase 7a)

Guide: [phase-7-user-guide.md](../phase-7-user-guide.md)

## Completed

| File | Verdict |
|------|---------|
| [2026-07-25-google-play.md](./2026-07-25-google-play.md) | Conditional — spike OK (50 reviews) |
| [2026-07-25-app-store.md](./2026-07-25-app-store.md) | Conditional / fragile — prefer Connect API |

## Outputs

Generated CSVs (gitignored): `docs/spikes/out/combined_import.csv` after you run:

```powershell
.\backend\.venv\Scripts\python.exe .\scripts\spikes\spike_store_reviews.py --country in --limit 50
```
