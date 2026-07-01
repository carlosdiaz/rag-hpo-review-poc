"""Comparison helpers for manual and model-suggested HPO terms."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HpoComparison:
    matched_terms: list[str]
    missing_from_manual_entry: list[str]
    extra_from_model: list[str]


def compare_hpo_terms(existing_terms: list[str], suggested_terms: list[str]) -> HpoComparison:
    """Compare model suggestions against manual terms.

    `missing_from_manual_entry` means the model suggested an HPO ID not currently
    present in the manual source-of-truth list. `extra_from_model` is retained as
    an explicit duplicate column for review readability in this POC; no automatic
    overwrite or addition is performed.
    """
    existing = set(existing_terms)
    suggested = set(suggested_terms)
    model_only = sorted(suggested - existing)

    return HpoComparison(
        matched_terms=sorted(existing & suggested),
        missing_from_manual_entry=model_only,
        extra_from_model=model_only,
    )
