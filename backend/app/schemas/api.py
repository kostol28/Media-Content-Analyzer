from datetime import datetime
from pydantic import BaseModel


class DatasetCreateResponse(BaseModel):
    dataset_id: int
    detected_columns: list[str]
    total_rows: int


class ColumnMappingRequest(BaseModel):
    mapping: dict[str, str]


class UrlIntakeRequest(BaseModel):
    name: str = "pasted_urls"
    urls: list[str]


class RunJobRequest(BaseModel):
    start_date: datetime | None = None
    end_date: datetime | None = None


class JobResponse(BaseModel):
    job_id: int
    status: str


class RowReviewUpdate(BaseModel):
    included: bool
    exclusion_reason: str | None = None
    manual_article_text: str | None = None
    review_notes: str | None = None


class AnalysisOutput(BaseModel):
    summary: str
    primary_theme: str
    secondary_themes: list[str]
    sentiment: str
    tone: str
    article_type: str
    audience_type: str
    brand_mentions: list[str]
    spokesperson_mentions: list[str]
    product_mentions: list[str]
    competitors_mentioned: list[str]
    key_messages_detected: dict[str, str]
    narrative_frame: str
    prominence_bucket: str
    relevance_score: float
    notable_quotes_or_passages: list[str]
    risks_or_negative_angles: list[str]
    opportunities_or_positive_angles: list[str]
    reasoning_notes_short: str
