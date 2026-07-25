"""Generate a tiny sample CSV for Phase 2 import testing."""

from pathlib import Path

SAMPLE = """content,author,rating,posted_at,url,external_id,source
Delivery was late by 40 minutes,user1,2,2024-01-15T10:00:00Z,,gp-1,google_play
Love the fast grocery delivery,user2,5,2024-01-16T11:00:00Z,,gp-2,google_play
Cannot find pet care products easily,user3,3,2024-01-17T12:00:00Z,,gp-3,google_play
"""


def main() -> None:
    out = Path(__file__).resolve().parent / "sample_conversations.csv"
    out.write_text(SAMPLE, encoding="utf-8")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
