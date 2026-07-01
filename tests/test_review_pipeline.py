import csv
import unittest

from src.config import ReviewSettings
from src.rag_hpo_client import MockRagHpoClient, RagHpoClient, RagHpoClientError
from src.review_pipeline import HpoReviewPipeline


class FailingClient(RagHpoClient):
    def extract_hpo_terms(self, clinical_note: str) -> list[str]:
        raise RagHpoClientError("service unavailable")


class HpoReviewPipelineTests(unittest.TestCase):
    def test_handling_empty_clinical_notes(self):
        pipeline = HpoReviewPipeline(MockRagHpoClient(), ReviewSettings(min_note_length=20))

        output = pipeline.process_row(
            {"case_id": "CASE-EMPTY", "clinical_note": "", "existing_hpo_terms": "HP:0001250"},
            row_number=2,
        )

        self.assertEqual(output["no_meaningful_note"], "true")
        self.assertEqual(output["review_status"], "no_meaningful_note")
        self.assertEqual(output["suggested_hpo_terms"], "")

    def test_generating_output_rows_for_review(self):
        pipeline = HpoReviewPipeline(MockRagHpoClient(), ReviewSettings(min_note_length=10))

        output = pipeline.process_row(
            {
                "case_id": "CASE-001",
                "clinical_note": "Patient has seizures and hypotonia.",
                "existing_hpo_terms": "HP:0001250",
            },
            row_number=2,
        )

        self.assertEqual(output["case_id"], "CASE-001")
        self.assertEqual(output["existing_hpo_terms"], "HP:0001250")
        self.assertEqual(output["suggested_hpo_terms"], "HP:0001250;HP:0001252")
        self.assertEqual(output["matched_terms"], "HP:0001250")
        self.assertEqual(output["missing_from_manual_entry"], "HP:0001252")
        self.assertEqual(output["extra_from_model"], "HP:0001252")
        self.assertEqual(output["review_status"], "needs_review")

    def test_failed_api_calls_are_reported(self):
        pipeline = HpoReviewPipeline(FailingClient(), ReviewSettings(min_note_length=10))

        output = pipeline.process_row(
            {
                "case_id": "CASE-FAIL",
                "clinical_note": "Patient has seizures and hypotonia.",
                "existing_hpo_terms": "HP:0001250",
            },
            row_number=2,
        )

        self.assertEqual(output["review_status"], "extraction_failed")
        self.assertIn("service unavailable", output["notes"])

    def test_malformed_csv_rows_are_flagged(self):
        pipeline = HpoReviewPipeline(MockRagHpoClient(), ReviewSettings(min_note_length=10))

        output = pipeline.process_row(
            {
                "case_id": "CASE-BAD",
                "clinical_note": "Patient has seizures.",
                "existing_hpo_terms": "HP:0001250",
                None: ["unexpected"],
            },
            row_number=2,
        )

        self.assertIn("Malformed CSV row", output["notes"])

    def test_run_writes_expected_csv(self):
        from tempfile import TemporaryDirectory
        from pathlib import Path

        with TemporaryDirectory() as temp_dir:
            input_csv = Path(temp_dir) / "input.csv"
            output_csv = Path(temp_dir) / "output.csv"
            input_csv.write_text(
                "case_id,clinical_note,existing_hpo_terms\n"
                'CASE-001,"Patient has seizures and hypotonia.",HP:0001250\n',
                encoding="utf-8",
            )

            pipeline = HpoReviewPipeline(MockRagHpoClient(), ReviewSettings(min_note_length=10))
            pipeline.run(input_csv=input_csv, output_csv=output_csv)

            with output_csv.open(newline="", encoding="utf-8") as output_file:
                rows = list(csv.DictReader(output_file))

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["case_id"], "CASE-001")
        self.assertEqual(rows[0]["review_status"], "needs_review")


if __name__ == "__main__":
    unittest.main()
