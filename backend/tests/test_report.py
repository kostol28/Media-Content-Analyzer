from app.services.analysis import build_batch_report


def test_build_batch_report_counts():
    analyses = [
        {"primary_theme": "innovation", "sentiment": "positive", "narrative_frame": "leadership"},
        {"primary_theme": "innovation", "sentiment": "neutral", "narrative_frame": "launch"},
    ]
    report = build_batch_report(analyses, {"total": 3, "success": 2, "failed": 1})
    assert report["extraction_success_rate"] == 0.667
    assert report["top_primary_themes"][0][0] == "innovation"
