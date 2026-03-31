from io import StringIO
from threading import Thread
import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.entities import Dataset, DatasetRow, IngestionJob, ArticleFetch, ExtractedArticle, ArticleAnalysis, BatchReport
from app.schemas.api import DatasetCreateResponse, ColumnMappingRequest, UrlIntakeRequest, RunJobRequest, JobResponse, RowReviewUpdate
from app.services.parsing import normalize_col, parse_date, normalize_title, validate_url
from app.services.analysis import analyze_article, build_batch_report, report_to_markdown
from app.workers.jobs import run_job
from .csv_utils import read_uploaded_csv

router = APIRouter()

CANONICAL_COLUMNS = {
    "url": ["url", "link", "articleurl"],
    "title": ["title", "headline"],
    "source": ["mediaoutlet", "source", "outlet", "publication"],
    "date": ["date", "publisheddate", "coveragedate"],
    "author": ["author", "writer"],
    "brand": ["brand"],
    "tags": ["tags", "keywords"],
}


def auto_map(cols: list[str]) -> dict[str, str]:
    normalized = {c: normalize_col(c) for c in cols}
    mapped = {}
    for canonical, aliases in CANONICAL_COLUMNS.items():
        for raw, norm in normalized.items():
            if norm in aliases:
                mapped[canonical] = raw
                break
    return mapped


def row_text_and_source(row: DatasetRow) -> tuple[str | None, str]:
    if row.manual_article_text and row.manual_article_text.strip():
        return row.manual_article_text.strip(), "manual"
    if row.fetch and row.fetch.article and row.fetch.article.article_text:
        return row.fetch.article.article_text, "extracted"
    return None, "missing"


@router.post("/datasets/upload", response_model=DatasetCreateResponse)
def upload_dataset(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV supported")
    df = read_uploaded_csv(file.file)
    cols = [str(c) for c in df.columns]
    dataset = Dataset(name=file.filename, original_filename=file.filename, intake_type="csv", detected_columns=cols, column_mapping=auto_map(cols))
    db.add(dataset)
    db.commit()
    db.refresh(dataset)

    mapping = dataset.column_mapping or {}
    for idx, row in df.iterrows():
        meta = {k: (None if pd.isna(v) else str(v)) for k, v in row.to_dict().items()}
        db.add(DatasetRow(
            dataset_id=dataset.id,
            row_index=int(idx),
            metadata_json=meta,
            normalized_url=meta.get(mapping.get("url", "")),
            normalized_title=normalize_title(meta.get(mapping.get("title", ""))),
            normalized_source=meta.get(mapping.get("source", "")),
            normalized_date=parse_date(meta.get(mapping.get("date", ""))),
            included=True,
        ))
    db.commit()
    return DatasetCreateResponse(dataset_id=dataset.id, detected_columns=cols, total_rows=len(df))


@router.post("/datasets/intake-urls", response_model=DatasetCreateResponse)
def intake_urls(payload: UrlIntakeRequest, db: Session = Depends(get_db)):
    cols = ["URL"]
    dataset = Dataset(name=payload.name, original_filename="pasted_urls", intake_type="pasted_urls", detected_columns=cols, column_mapping={"url": "URL"})
    db.add(dataset)
    db.commit()
    db.refresh(dataset)

    for idx, url in enumerate(payload.urls):
        clean = (url or "").strip()
        if not clean:
            continue
        db.add(DatasetRow(
            dataset_id=dataset.id,
            row_index=idx,
            metadata_json={"URL": clean},
            normalized_url=clean,
            normalized_title=None,
            normalized_source=None,
            normalized_date=None,
            included=True,
        ))
    db.commit()
    total = db.query(DatasetRow).filter(DatasetRow.dataset_id == dataset.id).count()
    return DatasetCreateResponse(dataset_id=dataset.id, detected_columns=cols, total_rows=total)


@router.get("/datasets/{dataset_id}")
def dataset_preview(dataset_id: int, db: Session = Depends(get_db)):
    dataset = db.get(Dataset, dataset_id)
    if not dataset:
        raise HTTPException(404, "Dataset not found")
    rows = db.query(DatasetRow).filter(DatasetRow.dataset_id == dataset_id).limit(100).all()
    return {
        "dataset": {"id": dataset.id, "columns": dataset.detected_columns, "mapping": dataset.column_mapping, "intake_type": dataset.intake_type},
        "rows": [{"id": r.id, **r.metadata_json, "included": r.included} for r in rows],
    }


@router.put("/datasets/{dataset_id}/mapping")
def update_mapping(dataset_id: int, payload: ColumnMappingRequest, db: Session = Depends(get_db)):
    dataset = db.get(Dataset, dataset_id)
    if not dataset:
        raise HTTPException(404, "Dataset not found")
    dataset.column_mapping = payload.mapping
    rows = db.query(DatasetRow).filter(DatasetRow.dataset_id == dataset_id).all()
    for row in rows:
        m = row.metadata_json
        row.normalized_url = m.get(payload.mapping.get("url", ""))
        row.normalized_title = normalize_title(m.get(payload.mapping.get("title", "")))
        row.normalized_source = m.get(payload.mapping.get("source", ""))
        row.normalized_date = parse_date(m.get(payload.mapping.get("date", "")))
    db.commit()
    return {"ok": True}


@router.post("/datasets/{dataset_id}/jobs", response_model=JobResponse)
def start_extraction_job(dataset_id: int, payload: RunJobRequest, db: Session = Depends(get_db)):
    job = IngestionJob(dataset_id=dataset_id, start_date=payload.start_date, end_date=payload.end_date)
    db.add(job)
    db.commit()
    db.refresh(job)
    Thread(target=run_job, args=(job.id,), daemon=True).start()
    return JobResponse(job_id=job.id, status=job.status)


@router.get("/jobs/{job_id}")
def get_job(job_id: int, db: Session = Depends(get_db)):
    job = db.get(IngestionJob, job_id)
    if not job:
        raise HTTPException(404, "Job not found")

    rows = db.query(DatasetRow).filter(DatasetRow.dataset_id == job.dataset_id).all()
    included_rows = [r for r in rows if r.included]
    usable_text_rows = 0
    for row in included_rows:
        text, _ = row_text_and_source(row)
        if text:
            usable_text_rows += 1

    report = db.query(BatchReport).filter(BatchReport.job_id == job_id).first()
    return {
        "job": {
            "id": job.id,
            "dataset_id": job.dataset_id,
            "status": job.status,
            "total_rows": job.total_rows,
            "processed_rows": job.processed_rows,
            "success_count": job.success_count,
            "failure_count": job.failure_count,
            "logs": job.logs,
        },
        "corpus_counts": {
            "total_rows": len(rows),
            "included_rows": len(included_rows),
            "excluded_rows": len(rows) - len(included_rows),
            "included_with_usable_text": usable_text_rows,
            "included_missing_text": len(included_rows) - usable_text_rows,
        },
        "report": report.report_json if report else None,
    }


@router.get("/jobs/{job_id}/articles")
def list_articles(job_id: int, db: Session = Depends(get_db)):
    job = db.get(IngestionJob, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    rows = db.query(DatasetRow).filter(DatasetRow.dataset_id == job.dataset_id).all()
    output = []
    for row in rows:
        fetch = row.fetch
        text, source = row_text_and_source(row)
        output.append({
            "row_id": row.id,
            "original_url": row.normalized_url,
            "final_url": fetch.final_url if fetch else None,
            "included": row.included,
            "exclusion_reason": row.exclusion_reason,
            "extraction_status": fetch.extraction_status if fetch else "pending",
            "failure_reason": fetch.failure_reason if fetch else None,
            "title": (fetch.article.extracted_title if fetch and fetch.article else row.normalized_title),
            "text_length": len(text) if text else 0,
            "text_source": source,
            "review_notes": row.review_notes,
        })
    return output


@router.put("/rows/{row_id}/review")
def update_row_review(row_id: int, payload: RowReviewUpdate, db: Session = Depends(get_db)):
    row = db.get(DatasetRow, row_id)
    if not row:
        raise HTTPException(404, "Row not found")
    row.included = payload.included
    row.exclusion_reason = payload.exclusion_reason
    row.review_notes = payload.review_notes
    if payload.manual_article_text is not None:
        row.manual_article_text = payload.manual_article_text.strip() or None
    db.commit()
    return {"ok": True}


@router.get("/rows/{row_id}")
def row_detail(row_id: int, db: Session = Depends(get_db)):
    row = db.get(DatasetRow, row_id)
    if not row:
        raise HTTPException(404, "Row not found")
    fetch = row.fetch
    text, source = row_text_and_source(row)
    analysis = fetch.article.analysis.analysis_json if fetch and fetch.article and fetch.article.analysis else None
    return {
        "metadata": row.metadata_json,
        "included": row.included,
        "exclusion_reason": row.exclusion_reason,
        "review_notes": row.review_notes,
        "manual_article_text": row.manual_article_text,
        "url_info": {
            "original_url": row.normalized_url,
            "final_url": fetch.final_url if fetch else None,
            "http_status": fetch.http_status if fetch else None,
            "fetch_status": fetch.fetch_status if fetch else "pending",
            "extraction_status": fetch.extraction_status if fetch else "pending",
            "failure_reason": fetch.failure_reason if fetch else None,
            "url_valid": validate_url(row.normalized_url),
            "text_source": source,
        },
        "article_text": text,
        "analysis": analysis,
    }


@router.post("/jobs/{job_id}/analyze")
def run_corpus_analysis(job_id: int, db: Session = Depends(get_db)):
    job = db.get(IngestionJob, job_id)
    if not job:
        raise HTTPException(404, "Job not found")

    rows = db.query(DatasetRow).filter(DatasetRow.dataset_id == job.dataset_id, DatasetRow.included == True).all()
    analyses = []
    for row in rows:
        fetch = row.fetch
        if not fetch or not fetch.article:
            continue
        text, _ = row_text_and_source(row)
        if not text:
            continue
        analysis_json = analyze_article(text, title=fetch.article.extracted_title or row.normalized_title)
        if fetch.article.analysis:
            fetch.article.analysis.analysis_json = analysis_json
            fetch.article.analysis.relevance_score = analysis_json.get("relevance_score")
        else:
            db.add(ArticleAnalysis(article_id=fetch.article.id, model_name="responses-api", analysis_json=analysis_json, relevance_score=analysis_json.get("relevance_score")))
        analyses.append(analysis_json)
    report_json = build_batch_report(analyses, {
        "total": len(rows),
        "success": len(analyses),
        "failed": len(rows) - len(analyses),
    })
    markdown = report_to_markdown(report_json)
    existing = db.query(BatchReport).filter(BatchReport.job_id == job.id).first()
    if existing:
        existing.report_json = report_json
        existing.markdown_report = markdown
    else:
        db.add(BatchReport(job_id=job.id, report_json=report_json, markdown_report=markdown))
    db.commit()
    return {"ok": True, "analyzed_articles": len(analyses), "included_rows": len(rows)}


@router.get("/jobs/{job_id}/export/enriched.csv")
def export_enriched(job_id: int, db: Session = Depends(get_db)):
    job = db.get(IngestionJob, job_id)
    rows = db.query(DatasetRow).filter(DatasetRow.dataset_id == job.dataset_id).all()
    out = []
    for row in rows:
        fetch = row.fetch
        text, source = row_text_and_source(row)
        out_row = dict(row.metadata_json)
        out_row.update({
            "included": row.included,
            "exclusion_reason": row.exclusion_reason,
            "review_notes": row.review_notes,
            "original_url": row.normalized_url,
            "final_url": fetch.final_url if fetch else None,
            "fetch_status": fetch.fetch_status if fetch else None,
            "extraction_status": fetch.extraction_status if fetch else None,
            "failure_reason": fetch.failure_reason if fetch else None,
            "text_source": source,
            "article_text": text,
            "analysis_json": fetch.article.analysis.analysis_json if fetch and fetch.article and fetch.article.analysis else None,
        })
        out.append(out_row)
    return StreamingResponse(StringIO(pd.DataFrame(out).to_csv(index=False)), media_type="text/csv")


@router.get("/jobs/{job_id}/export/failures.csv")
def export_failures(job_id: int, db: Session = Depends(get_db)):
    job = db.get(IngestionJob, job_id)
    rows = db.query(DatasetRow).filter(DatasetRow.dataset_id == job.dataset_id).all()
    failures = []
    for row in rows:
        fetch = row.fetch
        text, source = row_text_and_source(row)
        if source == "missing":
            failures.append({"url": row.normalized_url, "extraction_status": fetch.extraction_status if fetch else "pending", "failure_reason": fetch.failure_reason if fetch else "missing_fetch"})
    return StreamingResponse(StringIO(pd.DataFrame(failures).to_csv(index=False)), media_type="text/csv")


@router.get("/jobs/{job_id}/export/aggregate.json")
def export_aggregate(job_id: int, db: Session = Depends(get_db)):
    report = db.query(BatchReport).filter(BatchReport.job_id == job_id).first()
    return JSONResponse(report.report_json if report else {})


@router.get("/jobs/{job_id}/export/report.md")
def export_md(job_id: int, db: Session = Depends(get_db)):
    report = db.query(BatchReport).filter(BatchReport.job_id == job_id).first()
    return StreamingResponse(StringIO(report.markdown_report if report else ""), media_type="text/markdown")
