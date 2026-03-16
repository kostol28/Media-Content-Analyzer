# Media Content Analyzer (v1)

Production-oriented local-first internal web app for PR/media coverage ingestion, auditable extraction, and qualitative AI analysis.

## Architecture

- **Frontend:** Next.js + TypeScript single-page analyst workflow UI (`frontend/`).
- **Backend API:** FastAPI + SQLAlchemy (`backend/`).
- **Worker model:** DB-backed jobs processed in background threads (upgrade path to Celery/RQ).
- **Database:** SQLite by default via `DATABASE_URL`, abstracted for PostgreSQL migration.
- **Extraction pipeline:** requests + trafilatura with BeautifulSoup fallback, retries/backoff, per-domain throttling.
- **AI analysis:** OpenAI Responses API with strict JSON schema; safe local fallback when key missing.

## Features implemented

- CSV dataset upload with detected columns.
- Column mapping UI and normalization to canonical fields.
- Date range filtering and asynchronous ingestion job.
- URL validation, redirects, HTTP status capture, extraction status, failure classification.
- Audit-friendly storage of fetch and extraction metadata.
- Structured article-level analysis JSON (theme/sentiment/narrative/messaging fields).
- Batch-level aggregate report with theme/sentiment trend summaries.
- Analyst workflow UI: preview, mapping, run job, progress dashboard, results/failures, article detail.
- Export endpoints for enriched CSV, failures CSV, aggregate JSON, markdown report.
- Sample fixture CSV and unit tests for parsing/report helpers.

## Quickstart (local)

### 1) Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### 2) Frontend

```bash
cd frontend
npm install
npm run dev
```

### 3) Open app

- Frontend: http://localhost:3000
- API docs: http://localhost:8000/docs

Copy `.env.example` to `.env` and set `OPENAI_API_KEY` to enable real LLM analysis.

## Testing

```bash
cd backend
PYTHONPATH=. pytest
```

## Notes / tradeoffs in v1

- Worker uses in-process background thread (simple local-first). For production scale, move to dedicated queue workers.
- JS-heavy page fallback (Playwright) is not wired yet; failures can be labeled `js_required` in a future pass.
- Aggregate report is concise but extensible; schema hooks exist for custom client taxonomies.
- Current frontend is a single-page flow for speed; can be split into route-based screens later.
