# Spike: Google Play (Zepto)

Date: 2026-07-25  
Reviewer: eng spike script  
Official docs / ToS links:

- Play listing: https://play.google.com/store/apps/details?id=com.zeptoconsumerapp  
- Unofficial lib: https://pypi.org/project/google-play-scraper/  
- Official (own app only): https://developers.google.com/android-publisher  

Access obtained? **n/a** (unofficial public scrape — no API key)  
Method tested: Python `google-play-scraper`  
Sample size: **50** (cap 100)  
Country/lang: `in` / `en`

## Schema mapping

| Our field | Lib field |
|-----------|-----------|
| content | `content` |
| author | `userName` |
| rating | `score` |
| posted_at | `at` |
| url | Play listing URL |
| external_id | `gp-{reviewId}` |
| source | `google_play` |

## Results

- Success: yes  
- Avg rating in sample: ~3.6  
- Output: `docs/spikes/out/google_play_reviews.csv`

## Failures / blocks

None in this run. Expect intermittent throttling at higher volume.

## Scores

| L | T | S | C | V | P |
|---|---|---|---|---|---|
| 2 | 5 | 3 | 5 | 4 | 3 |

- **L=2:** Unofficial; ToS risk — Conditional, needs stakeholder OK  
- **T=5:** Clean structured fields  
- **S=3:** Can break if Google changes endpoints  
- **C=5:** Free, no key  
- **V=4:** Real Zepto delivery/app feedback  
- **P=3:** Display names only in sample  

## Verdict

**Conditional (pilot OK with stakeholder approval)**

Legal review required? **Recommended before 7b scale**

## Recommendation for 7b

Ship Play collector using this lib **or** switch to official Play Developer API if Console access is available (preferred).
