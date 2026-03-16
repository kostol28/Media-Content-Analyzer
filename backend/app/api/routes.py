from io import StringIO
from threading import Thread
import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.entities import Dataset, DatasetRow, IngestionJob, ArticleFetch, ExtractedArticle, ArticleAnalysis, BatchReport
from app.schemas.api import DatasetCreateResponse, ColumnMappingRequest, RunJobRequest, JobResponse
from app.services.parsing import normalize_col, parse_date, normalize_title
from app.workers.jobs import run_job

router = APIRouter()

CANONICAL_COLUMNS = {
    "url": ["url", "link", "articleurl"],
    "title": ["title", "headline"],
    "source": ["mediaoutlet", "source", "outlet", "publication"],
    "date": ["date", "publisheddate", "coverage_date"],
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


@router.post("/datasets/upload", response_model=DatasetCreateResponse)
def upload_dataset(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV supported")
    df = pd.read_csv(file.file)
    cols = [str(c) for c in df.columns]
    dataset = Dataset(name=file.filename, original_filename=file.filename, detected_columns=cols, column_mapping=auto_map(cols))
    db.add(dataset)
    db.commit()
    db.refresh(dataset)

    for idx, row in df.iterrows():
        meta = {k: (None if pd.isna(v) else str(v)) for k, v in row.to_dict().items()}
        mapping = dataset.column_mapping or {}
        db.add(DatasetRow(
            dataset_id=dataset.id,
            row_index=int(idx),
            metadata_json=meta,
            normalized_url=meta.get(mapping.get("url", "")),
            normalized_title=normalize_title(meta.get(mapping.get("title", ""))),
            normalized_source=meta.get(mapping.get("source", "")),
            normalized_date=parse_date(meta.get(mapping.get("date", ""))),
        ))
    db.commit()
    return DatasetCreateResponse(dataset_id=dataset.id, detected_columns=cols, total_rows=len(df))


@router.get("/datasets/{dataset_id}")
def dataset_preview(dataset_id: int, db: Session = Depends(get_db)):
    dataset = db.get(Dataset, dataset_id)
    rows = db.query(DatasetRow).filter(DatasetRow.dataset_id == dataset_id).limit(50).all()
    return {
        "dataset": {
            "id": dataset.id,
            "columns": dataset.detected_columns,
            "mapping": dataset.column_mapping,
        },
        "rows": [{"id": r.id, **r.metadata_json} for r in rows],
    }


@router.put("/datasets/{dataset_id}/mapping")
def update_mapping(dataset_id: int, payload: ColumnMappingRequest, db: Session = Depends(get_db)):
    dataset = db.get(Dataset, dataset_id)
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
def start_job(dataset_id: int, payload: RunJobRequest, db: Session = Depends(get_db)):
    job = IngestionJob(dataset_id=dataset_id, start_date=payload.start_date, end_date=payload.end_date)
    db.add(job)
    db.commit()
    db.refresh(job)
    Thread(target=run_job, args=(job.id,), daemon=True).start()
    return JobResponse(job_id=job.id, status=job.status)


@router.get("/jobs/{job_id}")
def get_job(job_id: int, db: Session = Depends(get_db)):
    job = db.get(IngestionJob, job_id)
    report = db.query(BatchReport).filter(BatchReport.job_id == job_id).first()
    return {
        "job": {
            "id": job.id,
            "status": job.status,
            "total_rows": job.total_rows,
            "processed_rows": job.processed_rows,
            "success_count": job.success_count,
            "failure_count": job.failure_count,
            "logs": job.logs,
        },
        "report": report.report_json if report else None,
    }


@router.get("/jobs/{job_id}/articles")
def list_articles(job_id: int, db: Session = Depends(get_db)):
    fetches = db.query(ArticleFetch).filter(ArticleFetch.job_id == job_id).all()
    output = []
    for f in fetches:
        a = f.article
        analysis = a.analysis.analysis_json if a and a.analysis else None
        output.append({
            "fetch_id": f.id,
            "row_id": f.dataset_row_id,
            "original_url": f.original_url,
            "final_url": f.final_url,
            "status": f.extraction_status,
            "failure_reason": f.failure_reason,
            "title": a.extracted_title if a else None,
            "text_length": a.raw_text_length if a else 0,
            "primary_theme": analysis.get("primary_theme") if analysis else None,
            "sentiment": analysis.get("sentiment") if analysis else None,
        })
    return output


@router.get("/articles/{fetch_id}")
def article_detail(fetch_id: int, db: Session = Depends(get_db)):
    fetch = db.get(ArticleFetch, fetch_id)
    if not fetch:
        raise HTTPException(404, "Not found")
    row = fetch.dataset_row
    article = fetch.article
    analysis = article.analysis.analysis_json if article and article.analysis else None
    return {
        "metadata": row.metadata_json,
        "url_info": {
            "original_url": fetch.original_url,
            "final_url": fetch.final_url,
            "http_status": fetch.http_status,
            "fetch_status": fetch.fetch_status,
            "extraction_status": fetch.extraction_status,
            "failure_reason": fetch.failure_reason,
        },
        "article_text": article.article_text if article else None,
        "analysis": analysis,
    }


@router.get("/jobs/{job_id}/export/enriched.csv")
def export_enriched(job_id: int, db: Session = Depends(get_db)):
    fetches = db.query(ArticleFetch).filter(ArticleFetch.job_id == job_id).all()
    rows = []
    for f in fetches:
        base = dict(f.dataset_row.metadata_json)
        base.update({
            "original_url": f.original_url,
            "final_url": f.final_url,
            "fetch_status": f.fetch_status,
            "extraction_status": f.extraction_status,
            "failure_reason": f.failure_reason,
            "article_text": f.article.article_text if f.article else None,
            "analysis_json": f.article.analysis.analysis_json if f.article and f.article.analysis else None,
        })
        rows.append(base)
    content = pd.DataFrame(rows).to_csv(index=False)
    return StreamingResponse(StringIO(content), media_type="text/csv")


@router.get("/jobs/{job_id}/export/failures.csv")
def export_failures(job_id: int, db: Session = Depends(get_db)):
    rows = db.query(ArticleFetch).filter(ArticleFetch.job_id == job_id, ArticleFetch.extraction_status == "failed").all()
    content = pd.DataFrame([{"url": r.original_url, "failure_reason": r.failure_reason} for r in rows]).to_csv(index=False)
    return StreamingResponse(StringIO(content), media_type="text/csv")


@router.get("/jobs/{job_id}/export/aggregate.json")
def export_aggregate(job_id: int, db: Session = Depends(get_db)):
    report = db.query(BatchReport).filter(BatchReport.job_id == job_id).first()
    return JSONResponse(report.report_json if report else {})


@router.get("/jobs/{job_id}/export/report.md")
def export_md(job_id: int, db: Session = Depends(get_db)):
    report = db.query(BatchReport).filter(BatchReport.job_id == job_id).first()
    return StreamingResponse(StringIO(report.markdown_report if report else ""), media_type="text/markdown")
