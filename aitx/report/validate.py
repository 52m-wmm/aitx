"""Step 4 format checks (contract docs/step4_contract.md section 11). Deterministic, no network."""
from __future__ import annotations

import json
import re

# the official template, in order (CLAUDE.md "比赛"; contract section 2)
HEADINGS = [
    "## Summary",
    "## Tier 1: Established",
    "### Existing Targeted Therapies",
    "### Supportive Management",
    "### Contraindications & Precautions",
    "## Tier 2: Emerging",
    "### Clinical Trial Eligibility",
    "### Off-label or Expanded-Access Therapies",
    "## Tier 3: Hypothetical",
    "### Bespoke Therapies",
    "### Drug Repurposing",
    "### Outcome Measures & Ranking",
]
SECTION_HEADINGS = [h for h in HEADINGS if h.startswith("### ")] + ["## Summary"]
CITATION = re.compile(r"\[(?:GeneReviews NBK\d+|PMID \d+|NCT\d{8}|FDA label [0-9a-f-]{36}|Guideline [^\]]+)[^\]]*\]")


def check_markdown(md: str) -> list[str]:
    """Problems with one report: every template heading present once, in order, each section non-empty."""
    bad = []
    lines = md.splitlines()
    pos = []
    for h in HEADINGS:
        idx = [i for i, l in enumerate(lines) if l.strip() == h]
        if len(idx) != 1:
            bad.append(f"heading {h!r} found {len(idx)} times (want 1)")
            pos.append(None)
        else:
            pos.append(idx[0])
    got = [p for p in pos if p is not None]
    if got != sorted(got):
        bad.append("headings out of the template order")
    for h, p in zip(HEADINGS, pos):
        if p is None or h not in SECTION_HEADINGS:
            continue
        nxt = next((q for q in pos[pos.index(p) + 1:] if q is not None), len(lines))
        body = [l for l in lines[p + 1:nxt] if l.strip()]
        if not body:
            bad.append(f"section {h!r} is empty")
    return bad


def check_submission(text: str) -> list[str]:
    """Problems with the upload file: a JSON array of {id, report_markdown}, each report passing check_markdown."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        return [f"not valid JSON: {e}"]
    if not isinstance(data, list):
        return ["the upload must be a JSON array"]
    bad = []
    for i, r in enumerate(data):
        if not isinstance(r, dict) or set(r) != {"id", "report_markdown"}:
            bad.append(f"item {i}: must have exactly the keys id and report_markdown")
            continue
        if not isinstance(r["id"], str) or not isinstance(r["report_markdown"], str):
            bad.append(f"item {i}: id and report_markdown must be strings")
            continue
        bad += [f"{r['id']}: {p}" for p in check_markdown(r["report_markdown"])]
    ids = [r.get("id") for r in data if isinstance(r, dict)]
    if len(ids) != len(set(ids)):
        bad.append("duplicate ids")
    return bad
