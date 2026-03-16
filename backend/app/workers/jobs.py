from datetime import datetime
import time
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.entities import IngestionJob, DatasetRow, ArticleFetch, ExtractedArticle
from app.services.extraction import extract_article, classify_failure
from app.services.parsing import validate_url


def append_log(job: IngestionJob, message: str):
    logs = job.logs or []
    logs.append({"ts": datetime.utcnow().isoformat(), "message": message})
    job.logs = logs[-500:]
    job.updated_at = datetime.utcnow()


def run_job(job_id: int):
    db: Session = SessionLocal()
    job = db.get(IngestionJob, job_id)
    if not job:
        return

    job.status = "running"
    append_log(job, "Extraction job started")
    db.commit()

    rows = db.query(DatasetRow).filter(DatasetRow.dataset_id == job.dataset_id).all()
    if job.start_date and job.end_date:
        selected = [r for r in rows if r.normalized_date and job.start_date <= r.normalized_date <= job.end_date]
    else:
        selected = rows

    job.total_rows = len(selected)
    db.commit()

    for row in selected:
        url = row.normalized_url
        if not validate_url(url):
            fetch = ArticleFetch(job_id=job.id, dataset_row_id=row.id, original_url=url or "", fetch_status="failed", extraction_status="failed", failure_reason="invalid_url")
            db.merge(fetch)
            job.failure_count += 1
            job.processed_rows += 1
            db.commit()
            continue

        fetch = db.query(ArticleFetch).filter(ArticleFetch.dataset_row_id == row.id).first()
        if not fetch:
            fetch = ArticleFetch(job_id=job.id, dataset_row_id=row.id, original_url=url, fetch_status="pending")
            db.add(fetch)
            db.commit()

        success = False
        for attempt in range(3):
            try:
                result = extract_article(url)
                fetch.final_url = result["final_url"]
                fetch.http_status = result["http_status"]
                fetch.fetch_status = "success"
                if not result["text"]:
                    fetch.extraction_status = "failed"
                    fetch.failure_reason = "extraction_empty"
                    break
                fetch.extraction_status = "success"

                existing_article = db.query(ExtractedArticle).filter(ExtractedArticle.fetch_id == fetch.id).first()
                if existing_article:
                    existing_article.extracted_title = result["title"] or row.normalized_title
                    existing_article.raw_text_length = len(result["text"])
                    existing_article.article_text = result["text"]
                else:
                    db.add(ExtractedArticle(
                        fetch_id=fetch.id,
                        extracted_title=result["title"] or row.normalized_title,
                        raw_text_length=len(result["text"]),
                        article_text=result["text"],
                    ))
                db.commit()
                success = True
                break
            except Exception as exc:
                fetch.retry_count = attempt + 1
                fetch.fetch_status = "failed"
                fetch.extraction_status = "failed"
                fetch.failure_reason = classify_failure(exc=exc)
                db.commit()
                time.sleep(1.5 * (attempt + 1))

        job.processed_rows += 1
        if success:
            job.success_count += 1
        else:
            job.failure_count += 1
        append_log(job, f"Processed row {row.id}: {'success' if success else 'failed'}")
        db.commit()

    job.status = "completed"
    append_log(job, "Extraction job completed")
    db.commit()
    db.close()
