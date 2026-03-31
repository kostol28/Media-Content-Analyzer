from app.services.parsing import validate_url, parse_date, normalize_title


def test_validate_url():
    assert validate_url("https://example.com/a")
    assert not validate_url("ftp://example.com")
    assert not validate_url("nope")


def test_parse_date_and_title():
    assert parse_date("2025-01-02") is not None
    assert parse_date("not-a-date") is None
    assert normalize_title("  Hello   World  ") == "hello world"
