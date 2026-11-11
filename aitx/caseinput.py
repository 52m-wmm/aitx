"""The patient's clinical description: one field, read in one place, never silently empty.

2026-11-11 (blind test): the blind case files put the description under `clinical_description`; the pipeline read
`patient.get("clinical_context", "")`, got an empty string, and ran ten cases with no phenotypes, no patient facts
and no symptomatic tier - without a single warning. A case the pipeline cannot read is now an input error that stops
the run before any LLM call (fix plan O1, docs/post_blind_fix_plan.md).
"""
from __future__ import annotations

FIELD = "clinical_context"          # the field the official and practice case files use
EXIT_CODE = 5                       # run_pipeline: input error, nothing run (3 = peak hours, 4 = daily budget)


class MissingDescription(ValueError):
    """The case has no readable clinical description."""


def clinical_context(case: dict) -> str:
    """The description text; raises MissingDescription when the field is missing, not text, or blank."""
    cid = case.get("id", "?")
    patient = case.get("patient") or {}
    if FIELD not in patient:
        others = sorted(k for k in patient if k != "genotype")
        hint = f" (the patient has {others}; the pipeline reads only '{FIELD}')" if others else ""
        raise MissingDescription(f"{cid}: patient.{FIELD} is missing{hint}")
    text = patient[FIELD]
    if not isinstance(text, str) or not text.strip():
        raise MissingDescription(f"{cid}: patient.{FIELD} is empty")
    return text


def problems(cases: list[dict]) -> list[str]:
    """One message per case whose description cannot be read (empty list when all are fine)."""
    out = []
    for c in cases:
        try:
            clinical_context(c)
        except MissingDescription as e:
            out.append(str(e))
    return out
