"""Step 4 format checks (contract docs/step4_contract.md section 11). Deterministic, no network."""
from __future__ import annotations

import json
import re
import html
from collections import Counter
from pathlib import Path

# Downloaded verbatim from https://aitxchallenge.org/assets/md/aitxchallenge_report_template.md.
TEMPLATE = Path(__file__).resolve().parents[2] / "data/aitxchallenge_report_template.md"
TITLE, *HEADINGS = re.findall(r"^#{1,3} .+$", TEMPLATE.read_text(), re.M)
SECTION_HEADINGS = [h for h in HEADINGS if h.startswith("### ")] + ["## Summary"]
CITATION = re.compile(r"\[(?:GeneReviews NBK\d+|PMID \d+|NCT\d{8}|FDA label [0-9a-f-]{36}|Guideline [^\]]+)[^\]]*\]")


def check_markdown(md: str, case_id: str | None = None) -> list[str]:
    """Problems with one report: every template heading present once, in order, each section non-empty."""
    bad = []
    lines = md.splitlines()
    titles = [l for l in lines if l.startswith("# ")]
    title_pattern = re.escape(TITLE).replace("AITX\\-XXXXX", re.escape(case_id) if case_id else r"[A-Za-z0-9-]+")
    if len(titles) != 1 or not re.fullmatch(title_pattern, titles[0]):
        bad.append("patient title differs from the official template or submission id")
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
        bad += [f"{r['id']}: {p}" for p in check_markdown(r["report_markdown"], r["id"])]
    ids = [r.get("id") for r in data if isinstance(r, dict)]
    if len(ids) != len(set(ids)):
        bad.append("duplicate ids")
    return bad


REF = re.compile(r"\[E:([A-Za-z0-9_-]+)\]\(#evidence-([A-Za-z0-9_-]+)\)")
DEFINITION = re.compile(r'^<a id="evidence-([A-Za-z0-9_-]+)"></a>$', re.M)
# Quantities with clinical units; transcript positions and lengths are not drug doses or treatment targets.
QUANTITY = re.compile(r"(?:[<>≤≥]=?\s*)?\d+(?:\.\d+)?(?:\s*[-–]\s*\d+(?:\.\d+)?)?\s*"
                      r"(?:µmol|μmol|mmol|mcg|µg|μg|mg|mL|kg|g|L|%|mmHg)"
                      r"(?:\s*/\s*(?:\d+(?:\.\d+)?\s*)?(?:kg|m\s*[²2]|min|hours?|hrs?|days?|d|h))*(?!\w)", re.I)


def check_report(md: str, ledger: dict, case_id: str) -> list[str]:
    """Step 5's requested deterministic checks; the ledger remains the clinical judgement layer."""
    bad = check_markdown(md, case_id)
    records = ledger["evidence"]
    counts = Counter(e["id"] for e in records)
    bad += [f"duplicate ledger evidence ID: {i}" for i, n in counts.items() if n != 1]
    evidence = {e["id"]: e for e in records}
    definitions = DEFINITION.findall(md)
    bad += [f"duplicate report evidence definition: {i}" for i, n in Counter(definitions).items() if n != 1]
    references = REF.findall(md)
    if any(a != b for a, b in references):
        bad.append("evidence reference and anchor differ")
    for eid in set(definitions) | {a for a, _ in references}:
        if eid not in evidence:
            bad.append(f"report evidence ID not found in ledger: {eid}")
        elif evidence[eid]["status"] != "verified":
            bad.append(f"report cites unverified evidence: {eid}")
    for eid in {a for a, _ in references} - set(definitions):
        bad.append(f"evidence definition missing: {eid}")
    # Count the actual action rows, not trace metadata. An altered visible total must fail.
    from aitx.report.assemble import written, status_of
    section_names = {"### Existing Targeted Therapies": "existing_targeted_therapies",
                     "### Supportive Management": "supportive_management",
                     "### Contraindications & Precautions": "contraindications_precautions",
                     "### Clinical Trial Eligibility": "clinical_trial_eligibility",
                     "### Off-label or Expanded-Access Therapies": "off_label_expanded_access",
                     "### Bespoke Therapies": "bespoke_therapies", "### Drug Repurposing": "drug_repurposing"}
    for heading in SECTION_HEADINGS:
        if heading not in md:
            continue
        body = md.split(heading + "\n", 1)[1]
        body = re.split(r"^#{1,3} ", body, maxsplit=1, flags=re.M)[0].split("#### Evidence table", 1)[0]
        rows = [l for l in body.splitlines() if re.match(r"^- \*\*.+?\*\* —|^\| \*\*", l)]
        shown = re.findall(r"^Listed actions: \*\*(\d+)\*\*\.$", body, re.M)
        if shown and (len(shown) != 1 or int(shown[0]) != len(rows)):
            bad.append(f"action count differs from listed rows: {heading}")
        for line in rows:
            if not REF.search(line):
                bad.append(f"action has no evidence ID: {heading}")
        for m in re.finditer(r"^(\d+) further .+? (do not apply to this patient and are|are) recorded in the evidence ledger and not listed here\.", body, re.M):
            section = section_names[heading]
            candidates = [a for a in ledger['actions'] if a['section'] == section]
            if m[2].startswith("do not apply"):
                want = sum(bool(a.get('action_key')) and status_of(a) == 'not_applicable' for a in candidates)
            else:
                eligible = [a for a in candidates if written(a) or (section == 'off_label_expanded_access'
                            and a.get('efficacy_direction') == 'reported_ineffective')]
                want = len([a for a in eligible if any(evidence[i]['status'] == 'verified' for i in a['evidence_ids'])]) - len(rows)
            if int(m[1]) != want:
                bad.append(f"omitted count differs from ledger entries: {heading}")
    # These sections contain sourced measures and exclusions; unknown/unconfirmed placeholders are metadata.
    for block in ("**Safety**:", "**Efficacy measures**:"):
        if block not in md:
            continue
        body = re.split(r"^\*\*|^#### ", md.split(block, 1)[1], maxsplit=1, flags=re.M)[0]
        for line in body.splitlines():
            if line.startswith("- ") and "unconfirmed" not in line and not REF.search(line):
                bad.append(f"measure or safety conclusion has no evidence ID: {block}")
    obs = re.search(r"^- \*\*Observational studies \((\d+)\)\*\*: (.+)$", md, re.M)
    if obs and int(obs[1]) != len(re.findall(r"; verified [^)]+\)", obs[2])):
        bad.append("observational study count differs from listed studies")
    for m in re.finditer(r"^  - [^\n]+?: (\d+) entr(?:y|ies) depend on it \((.+)\)\.", md, re.M):
        if int(m[1]) != len(m[2].split("<br>")):
            bad.append("missing-information count differs from listed entries")
    # Compare rendered clinical quantities to the verbatim passage(s) cited on that same line.
    for line in md.splitlines():
        quantities = QUANTITY.findall(html.unescape(line))
        if not quantities:
            continue
        ids = [a for a, _ in REF.findall(line) if a in evidence]
        quotes = [re.sub(r"\s+", " ", html.unescape(evidence[i].get("quote", ""))) for i in ids]
        for quantity in quantities:
            normalized = re.sub(r"\s+", " ", quantity)
            if not any(normalized in q for q in quotes):
                bad.append(f"dose/target absent from cited verbatim passage: {quantity}")
    return bad
