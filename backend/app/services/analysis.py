import json
from collections import Counter
try:
    from openai import OpenAI
except Exception:
    OpenAI = None

from app.core.config import settings

ARTICLE_ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "primary_theme": {"type": "string"},
        "secondary_themes": {"type": "array", "items": {"type": "string"}},
        "sentiment": {"type": "string"},
        "tone": {"type": "string"},
        "article_type": {"type": "string"},
        "audience_type": {"type": "string"},
        "brand_mentions": {"type": "array", "items": {"type": "string"}},
        "spokesperson_mentions": {"type": "array", "items": {"type": "string"}},
        "product_mentions": {"type": "array", "items": {"type": "string"}},
        "competitors_mentioned": {"type": "array", "items": {"type": "string"}},
        "key_messages_detected": {"type": "object", "additionalProperties": {"type": "string"}},
        "narrative_frame": {"type": "string"},
        "prominence_bucket": {"type": "string"},
        "relevance_score": {"type": "number"},
        "notable_quotes_or_passages": {"type": "array", "items": {"type": "string"}},
        "risks_or_negative_angles": {"type": "array", "items": {"type": "string"}},
        "opportunities_or_positive_angles": {"type": "array", "items": {"type": "string"}},
        "reasoning_notes_short": {"type": "string"},
    },
    "required": ["summary", "primary_theme", "secondary_themes", "sentiment", "tone", "article_type", "audience_type", "brand_mentions", "spokesperson_mentions", "product_mentions", "competitors_mentioned", "key_messages_detected", "narrative_frame", "prominence_bucket", "relevance_score", "notable_quotes_or_passages", "risks_or_negative_angles", "opportunities_or_positive_angles", "reasoning_notes_short"],
    "additionalProperties": False,
}


def analyze_article(text: str, title: str | None = None, taxonomy: dict | None = None) -> dict:
    if not settings.openai_api_key or OpenAI is None:
        return {
            "summary": (text[:240] + "...") if len(text) > 240 else text,
            "primary_theme": "general_coverage",
            "secondary_themes": ["brand_visibility"],
            "sentiment": "neutral",
            "tone": "informative",
            "article_type": "news_brief",
            "audience_type": "general",
            "brand_mentions": [],
            "spokesperson_mentions": [],
            "product_mentions": [],
            "competitors_mentioned": [],
            "key_messages_detected": {},
            "narrative_frame": "factual_update",
            "prominence_bucket": "medium",
            "relevance_score": 0.5,
            "notable_quotes_or_passages": [],
            "risks_or_negative_angles": [],
            "opportunities_or_positive_angles": [],
            "reasoning_notes_short": "Fallback mode without OpenAI key.",
        }

    client = OpenAI(api_key=settings.openai_api_key)
    prompt = f"""You are a PR media analyst. Analyze this article for qualitative coverage.
Return strict JSON matching the provided schema. Do not invent facts.
Article title: {title or 'N/A'}
Article text:\n{text[:12000]}"""

    response = client.responses.create(
        model=settings.openai_model,
        input=prompt,
        text={
            "format": {
                "type": "json_schema",
                "name": "article_analysis",
                "schema": ARTICLE_ANALYSIS_SCHEMA,
                "strict": True,
            }
        },
    )
    return json.loads(response.output_text)


def build_batch_report(analyses: list[dict], totals: dict) -> dict:
    theme_counts = Counter([a.get("primary_theme", "unknown") for a in analyses])
    sentiment_counts = Counter([a.get("sentiment", "unknown") for a in analyses])
    return {
        "total_rows_in_date_range": totals["total"],
        "total_successfully_extracted": totals["success"],
        "total_failed": totals["failed"],
        "extraction_success_rate": round((totals["success"] / totals["total"]), 3) if totals["total"] else 0,
        "top_primary_themes": theme_counts.most_common(10),
        "sentiment_distribution": dict(sentiment_counts),
        "narrative_trends": [a.get("narrative_frame") for a in analyses[:20]],
    }


def report_to_markdown(report: dict) -> str:
    return "\n".join([
        "# Batch Qualitative Coverage Report",
        f"- Total rows: {report['total_rows_in_date_range']}",
        f"- Success: {report['total_successfully_extracted']}",
        f"- Failed: {report['total_failed']}",
        f"- Success rate: {report['extraction_success_rate']}",
        "## Top Themes",
        *[f"- {t[0]}: {t[1]}" for t in report.get("top_primary_themes", [])],
    ])
