from datetime import datetime
from sqlalchemy import String, Integer, DateTime, Text, ForeignKey, JSON, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Dataset(Base):
    __tablename__ = "datasets"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    original_filename: Mapped[str] = mapped_column(String(255))
    detected_columns: Mapped[dict] = mapped_column(JSON, default=list)
    column_mapping: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    rows = relationship("DatasetRow", back_populates="dataset", cascade="all, delete-orphan")


class DatasetRow(Base):
    __tablename__ = "dataset_rows"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id"))
    row_index: Mapped[int] = mapped_column(Integer)
    metadata_json: Mapped[dict] = mapped_column(JSON)
    normalized_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    normalized_title: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    normalized_source: Mapped[str | None] = mapped_column(String(255), nullable=True)
    normalized_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    dataset = relationship("Dataset", back_populates="rows")
    fetch = relationship("ArticleFetch", back_populates="dataset_row", uselist=False)


class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id"))
    status: Mapped[str] = mapped_column(String(50), default="queued")
    start_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    end_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    total_rows: Mapped[int] = mapped_column(Integer, default=0)
    processed_rows: Mapped[int] = mapped_column(Integer, default=0)
    success_count: Mapped[int] = mapped_column(Integer, default=0)
    failure_count: Mapped[int] = mapped_column(Integer, default=0)
    logs: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ArticleFetch(Base):
    __tablename__ = "article_fetches"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("ingestion_jobs.id"))
    dataset_row_id: Mapped[int] = mapped_column(ForeignKey("dataset_rows.id"))
    original_url: Mapped[str] = mapped_column(String(1024))
    final_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    fetch_status: Mapped[str] = mapped_column(String(50), default="pending")
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    extraction_status: Mapped[str] = mapped_column(String(50), default="pending")
    failure_reason: Mapped[str | None] = mapped_column(String(100), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    dataset_row = relationship("DatasetRow", back_populates="fetch")
    article = relationship("ExtractedArticle", back_populates="fetch", uselist=False)


class ExtractedArticle(Base):
    __tablename__ = "extracted_articles"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    fetch_id: Mapped[int] = mapped_column(ForeignKey("article_fetches.id"))
    extracted_title: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    extracted_publish_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    raw_text_length: Mapped[int] = mapped_column(Integer, default=0)
    article_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    fetch = relationship("ArticleFetch", back_populates="article")
    analysis = relationship("ArticleAnalysis", back_populates="article", uselist=False)


class ArticleAnalysis(Base):
    __tablename__ = "article_analyses"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    article_id: Mapped[int] = mapped_column(ForeignKey("extracted_articles.id"))
    model_name: Mapped[str] = mapped_column(String(100))
    analysis_json: Mapped[dict] = mapped_column(JSON)
    relevance_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    article = relationship("ExtractedArticle", back_populates="analysis")


class BatchReport(Base):
    __tablename__ = "batch_reports"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("ingestion_jobs.id"), unique=True)
    report_json: Mapped[dict] = mapped_column(JSON)
    markdown_report: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
