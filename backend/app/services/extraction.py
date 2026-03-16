import time
from urllib.parse import urlparse
import requests
import trafilatura
from bs4 import BeautifulSoup

from app.core.config import settings

DOMAIN_LAST_SEEN: dict[str, float] = {}


def _rate_limit(domain: str, min_interval: float = 1.0):
    now = time.time()
    last = DOMAIN_LAST_SEEN.get(domain, 0)
    wait = min_interval - (now - last)
    if wait > 0:
        time.sleep(wait)
    DOMAIN_LAST_SEEN[domain] = time.time()


def classify_failure(exc: Exception | None = None, status_code: int | None = None, empty: bool = False) -> str:
    if empty:
        return "extraction_empty"
    if status_code in {401, 403}:
        return "blocked"
    if status_code == 402:
        return "paywalled"
    if exc and "Invalid URL" in str(exc):
        return "invalid_url"
    if isinstance(exc, requests.Timeout):
        return "timeout"
    return "unknown_error"


def extract_article(url: str) -> dict:
    domain = urlparse(url).netloc
    _rate_limit(domain)
    headers = {"User-Agent": "Mozilla/5.0 (MediaAnalyzerBot/1.0)"}
    response = requests.get(url, headers=headers, timeout=settings.request_timeout_seconds, allow_redirects=True)
    downloaded = response.text
    text = trafilatura.extract(downloaded, include_comments=False, include_tables=False)
    if not text:
        soup = BeautifulSoup(downloaded, "html.parser")
        text = "\n".join([p.get_text(" ", strip=True) for p in soup.select("article p, main p, p")])
    text = (text or "").strip()
    return {
        "final_url": response.url,
        "http_status": response.status_code,
        "text": text,
        "title": trafilatura.extract_metadata(downloaded).title if downloaded else None,
        "published": trafilatura.extract_metadata(downloaded).date if downloaded else None,
    }
