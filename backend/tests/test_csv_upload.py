from io import BytesIO
from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("starlette")
from app.api.routes import read_uploaded_csv


def test_read_uploaded_csv_supports_utf16_and_tab_separator():
    data = "URL\tTitle\nhttps://example.com\tHello\n"
    encoded = data.encode("utf-16")
    upload = SimpleNamespace(filename="meltwater.csv", file=BytesIO(encoded))

    df = read_uploaded_csv(upload)

    assert list(df.columns) == ["URL", "Title"]
    assert df.iloc[0]["URL"] == "https://example.com"
    assert df.iloc[0]["Title"] == "Hello"


def test_read_uploaded_csv_raises_for_empty_upload():
    upload = SimpleNamespace(filename="empty.csv", file=BytesIO(b""))

    with pytest.raises(Exception) as exc:
        read_uploaded_csv(upload)
    assert getattr(exc.value, "status_code", None) == 400
    assert "empty" in getattr(exc.value, "detail", "").lower()
