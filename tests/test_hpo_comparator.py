import unittest

from src.hpo_comparator import compare_hpo_terms


class HpoComparatorTests(unittest.TestCase):
    def test_compare_hpo_term_lists(self):
        comparison = compare_hpo_terms(
            existing_terms=["HP:0001250", "HP:0001263"],
            suggested_terms=["HP:0001250", "HP:0001252"],
        )

        self.assertEqual(comparison.matched_terms, ["HP:0001250"])
        self.assertEqual(comparison.missing_from_manual_entry, ["HP:0001252"])
        self.assertEqual(comparison.extra_from_model, ["HP:0001252"])

    def test_compare_hpo_terms_sorts_output(self):
        comparison = compare_hpo_terms(
            existing_terms=["HP:0001263", "HP:0001250"],
            suggested_terms=["HP:0001252", "HP:0001263"],
        )

        self.assertEqual(comparison.matched_terms, ["HP:0001263"])
        self.assertEqual(comparison.missing_from_manual_entry, ["HP:0001252"])


if __name__ == "__main__":
    unittest.main()
