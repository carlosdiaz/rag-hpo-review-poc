"""Utilities for parsing HPO term values from CSV fields and model responses."""

from __future__ import annotations

import re

HPO_ID_PATTERN = re.compile(r"HP:\d{7}")


def parse_hpo_terms(value: object) -> list[str]:
    """Parse HPO terms from comma, semicolon, pipe, or whitespace-separated text.

    The pipeline compares normalized HPO IDs. Descriptive labels can be present,
    but only values matching the HP:0000000 pattern are retained.
    """
    if value is None:
        return []

    text = str(value).strip()
    if not text:
        return []

    seen: set[str] = set()
    terms: list[str] = []
    for match in HPO_ID_PATTERN.findall(text.upper()):
        if match not in seen:
            seen.add(match)
            terms.append(match)
    return terms


def format_hpo_terms(terms: list[str]) -> str:
    return ";".join(terms)
