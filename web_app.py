"""Small Flask UI/API for viewing generated HPO review reports."""

from __future__ import annotations

import csv
from pathlib import Path

from flask import Flask, jsonify, render_template, request

from src.logging_config import configure_logging
from src.review_pipeline import OUTPUT_COLUMNS

app = Flask(__name__)
DEFAULT_REPORT = Path("output/hpo_review_openai.csv")


def load_review_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        fallback = Path("output/hpo_review.csv")
        path = fallback if fallback.exists() else path

    if not path.exists():
        return []

    with path.open(newline="", encoding="utf-8") as report_file:
        reader = csv.DictReader(report_file)
        return [{column: row.get(column, "") for column in OUTPUT_COLUMNS} for row in reader]


def summarize(rows: list[dict[str, str]]) -> dict[str, int]:
    summary = {
        "total": len(rows),
        "needs_review": 0,
        "matched": 0,
        "no_terms_found": 0,
        "no_meaningful_note": 0,
        "extraction_failed": 0,
    }
    for row in rows:
        status = row.get("review_status", "")
        if status in summary:
            summary[status] += 1
    return summary


@app.get("/")
def index():
    report_path = Path(request.args.get("path", DEFAULT_REPORT))
    rows = load_review_rows(report_path)
    return render_template(
        "review.html",
        rows=rows,
        summary=summarize(rows),
        report_path=str(report_path),
    )


@app.get("/api/review-report")
def review_report():
    report_path = Path(request.args.get("path", DEFAULT_REPORT))
    rows = load_review_rows(report_path)
    return jsonify({"report_path": str(report_path), "summary": summarize(rows), "rows": rows})


if __name__ == "__main__":
    configure_logging()
    app.run(debug=True, port=5001)
