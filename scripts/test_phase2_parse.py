"""Quick Phase 2 parser/cleaner checks (no database)."""

from app.services.cleaning import clean_content, parse_rating
from app.services.import_service import ImportError, parse_upload


def main() -> None:
    assert clean_content("  <b>late</b> delivery  ") == "late delivery"
    assert clean_content("   ") is None
    assert parse_rating("99") is None and parse_rating("4") == 4

    rows = parse_upload(
        "t.csv",
        b"content,author,external_id\nHello,a,1\nHello,b,1\n",
    )
    assert len(rows) == 2

    try:
        parse_upload("t.csv", b"author\nx")
        raise AssertionError("expected missing content error")
    except ImportError as exc:
        assert "content" in exc.message.lower()

    try:
        parse_upload("t.json", b'{"content":"x"}')
        raise AssertionError("expected array error")
    except ImportError:
        pass

    bom_rows = parse_upload("t.csv", b"\xef\xbb\xbfcontent\nHi")
    assert bom_rows[0]["content"] == "Hi"
    print("phase2_parse_ok")


if __name__ == "__main__":
    main()
