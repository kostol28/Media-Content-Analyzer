from datetime import datetime
import re
from urllib.parse import urlparse


def normalize_col(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    raw = str(value).strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def validate_url(url: str | None) -> bool:
    if not url:
        return False
    try:
        parsed = urlparse(url)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
    except Exception:
        return False


def normalize_title(title: str | None) -> str | None:
    if not title:
        return None
    return re.sub(r"\s+", " ", title.strip().lower())
