"""Example route snippet for CSV upload handling."""

from __future__ import annotations

from .csv_utils import read_uploaded_csv


def upload_dataset(file):
    """Parse an uploaded dataset file-like object into a DataFrame."""
    return read_uploaded_csv(file.file)
