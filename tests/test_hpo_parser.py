import unittest

from src.hpo_parser import format_hpo_terms, parse_hpo_terms


class HpoParserTests(unittest.TestCase):
    def test_parse_existing_hpo_terms_from_mixed_delimiters(self):
        raw = "HP:0001250; developmental delay (HP:0001263), hp:0001252 | HP:0001250"

        self.assertEqual(parse_hpo_terms(raw), ["HP:0001250", "HP:0001263", "HP:0001252"])

    def test_parse_missing_hpo_terms_returns_empty_list(self):
        self.assertEqual(parse_hpo_terms(""), [])
        self.assertEqual(parse_hpo_terms(None), [])
        self.assertEqual(parse_hpo_terms("seizures; developmental delay"), [])

    def test_format_hpo_terms_uses_semicolons(self):
        self.assertEqual(format_hpo_terms(["HP:0001250", "HP:0001263"]), "HP:0001250;HP:0001263")


if __name__ == "__main__":
    unittest.main()
