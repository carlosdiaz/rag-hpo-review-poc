"""CSV review pipeline for HPO term comparison."""

from __future__ import annotations

import csv
import logging
from pathlib import Path

from src.config import ReviewSettings
from src.hpo_comparator import compare_hpo_terms
from src.hpo_parser import format_hpo_terms, parse_hpo_terms
from src.rag_hpo_client import RagHpoClient, RagHpoClientError

logger = logging.getLogger(__name__)

INPUT_COLUMNS = {"case_id", "clinical_note", "existing_hpo_terms"}
OUTPUT_COLUMNS = [
    "case_id",
    "existing_hpo_terms",
    "suggested_hpo_terms",
    "matched_terms",
    "missing_from_manual_entry",
    "extra_from_model",
    "no_meaningful_note",
    "review_status",
    "notes",
]


class HpoReviewPipeline:
    def __init__(self, client: RagHpoClient, review_settings: ReviewSettings) -> None:
        self.client = client
        self.review_settings = review_settings

    def run(self, input_csv: Path, output_csv: Path) -> None:
        logger.info("Reading input CSV from %s.", input_csv)
        output_csv.parent.mkdir(parents=True, exist_ok=True)

        with input_csv.open("r", newline="", encoding="utf-8-sig") as input_file:
            reader = csv.DictReader(input_file)
            self._validate_header(reader.fieldnames)
            rows = [self.process_row(row, row_number=index) for index, row in enumerate(reader, start=2)]

        with output_csv.open("w", newline="", encoding="utf-8") as output_file:
            writer = csv.DictWriter(output_file, fieldnames=OUTPUT_COLUMNS)
            writer.writeheader()
            writer.writerows(rows)

        logger.info("Wrote %s review rows to %s.", len(rows), output_csv)

    def process_row(self, row: dict[str, str | None], row_number: int = 0) -> dict[str, str | bool]:
        notes: list[str] = []
        if None in row:
            notes.append("Malformed CSV row contained unexpected extra fields.")

        case_id = (row.get("case_id") or "").strip()
        clinical_note = (row.get("clinical_note") or "").strip()
        existing_raw = row.get("existing_hpo_terms") or ""

        if not case_id:
            case_id = f"row_{row_number}"
            notes.append("Missing case_id; generated row identifier.")

        existing_terms = parse_hpo_terms(existing_raw)
        if existing_raw.strip() and not existing_terms:
            notes.append("Existing HPO field did not contain valid HP:0000000 identifiers.")
        elif not existing_terms:
            notes.append("No existing manual HPO terms provided.")

        no_meaningful_note = len(clinical_note) < self.review_settings.min_note_length
        suggested_terms: list[str] = []

        if no_meaningful_note:
            notes.append("Clinical note empty or too short for meaningful extraction.")
            review_status = "no_meaningful_note"
        else:
            try:
                suggested_terms = self.client.extract_hpo_terms(clinical_note)
            except RagHpoClientError as exc:
                logger.exception("RAG-HPO extraction failed for case_id=%s.", case_id)
                notes.append(str(exc))
                review_status = "extraction_failed"
            except Exception as exc:
                logger.exception("Unexpected extraction failure for case_id=%s.", case_id)
                notes.append(f"Unexpected extraction failure: {exc}")
                review_status = "extraction_failed"
            else:
                if not suggested_terms:
                    notes.append("RAG-HPO returned no suggested HPO terms.")
                    review_status = "needs_review" if existing_terms else "no_terms_found"
                else:
                    review_status = "needs_review"

        comparison = compare_hpo_terms(existing_terms, suggested_terms)
        if review_status == "needs_review" and comparison.missing_from_manual_entry:
            notes.append("Model suggested terms not present in manual source-of-truth list.")
        if review_status == "needs_review" and not comparison.missing_from_manual_entry:
            review_status = "matched"

        return {
            "case_id": case_id,
            "existing_hpo_terms": format_hpo_terms(existing_terms),
            "suggested_hpo_terms": format_hpo_terms(suggested_terms),
            "matched_terms": format_hpo_terms(comparison.matched_terms),
            "missing_from_manual_entry": format_hpo_terms(comparison.missing_from_manual_entry),
            "extra_from_model": format_hpo_terms(comparison.extra_from_model),
            "no_meaningful_note": str(no_meaningful_note).lower(),
            "review_status": review_status,
            "notes": " ".join(notes),
        }

    @staticmethod
    def _validate_header(fieldnames: list[str] | None) -> None:
        if not fieldnames:
            raise ValueError("Input CSV is missing a header row.")

        missing = INPUT_COLUMNS - set(fieldnames)
        if missing:
            raise ValueError(f"Input CSV missing required columns: {', '.join(sorted(missing))}")
