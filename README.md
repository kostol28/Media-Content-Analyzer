# Media Content Analyzer (Post-Curation v1)

Internal local-first app for PR/media analysts who already curate relevant coverage upstream and now need automated text extraction, review controls, and final-corpus qualitative analysis.

## Post-curation workflow

1. Intake cleaned coverage via **CSV upload** or **paste URLs**.
2. Create article records.
3. Run extraction pipeline across all records (optional date filter for CSVs).
4. Review extraction results in a table with status + text source visibility.
5. Add manual text only where extraction is missing/incomplete.
6. Exclude/remove articles and restore later.
7. Run AI analysis only on final included rows with usable text.

## Architecture

- **Frontend:** Next.js TypeScript (`frontend/`) single-page analyst workflow.
- **Backend:** FastAPI + SQLAlchemy (`backend/`).
- **Jobs:** DB-backed extraction jobs via background thread.
- **Database:** SQLite default (easy local setup), swappable to PostgreSQL by `DATABASE_URL`.
- **Extraction:** `requests` + `trafilatura` first, BeautifulSoup fallback, retries/backoff, per-domain throttling.
- **Analysis:** OpenAI Responses API strict JSON schema; fallback mode without key.

## Key features

- Intake from CSVs or pasted URLs.
- Column detection/mapping for CSV inputs.
- Auditable fetch/extraction metadata (`original_url`, `final_url`, HTTP status, failures).
- Review-table controls for include/exclude/restore and manual text override.
- Text source label per row: `extracted`, `manual`, or `missing`.
- Corpus readiness counters before analysis (included/excluded/usable/missing).
- Final-corpus-only analysis + aggregate reporting.
- Exports: enriched CSV, failures CSV, aggregate JSON, markdown report.

## Local setup

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open:
- UI: http://localhost:3000
- API docs: http://localhost:8000/docs

Set envs from `.env.example`.

## Tests

```bash
PYTHONPATH=backend python -m pytest backend/tests
python -m compileall backend/app
```

## Tradeoffs in this v1

- In-process background worker (simple local-first), intended to migrate to queue workers later.
- No Playwright JS-page fallback yet.
- Single-page frontend for speed; can be split into route-based pages later.
