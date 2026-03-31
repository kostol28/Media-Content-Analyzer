"""Utilities for parsing uploaded CSV files with unknown encodings."""

from __future__ import annotations

import io
from typing import BinaryIO

import pandas as pd


def read_uploaded_csv(file_obj: BinaryIO) -> pd.DataFrame:
    """Read an uploaded CSV file with resilient encoding fallback.

    Meltwater exports are frequently encoded as UTF-16 LE with BOM. If we force
    UTF-8 we can hit a ``UnicodeDecodeError`` where byte ``0xff`` is the first
    byte in the stream. This helper attempts common encodings in order.
    """

    raw_bytes = file_obj.read()
    if hasattr(file_obj, "seek"):
        file_obj.seek(0)

    encodings = ["utf-8-sig", "utf-16", "utf-16-le", "latin-1"]
    last_error: UnicodeDecodeError | None = None

    for encoding in encodings:
        try:
            return pd.read_csv(io.BytesIO(raw_bytes), encoding=encoding)
        except UnicodeDecodeError as exc:
            last_error = exc

    if last_error is not None:
        raise last_error

    return pd.read_csv(io.BytesIO(raw_bytes))
