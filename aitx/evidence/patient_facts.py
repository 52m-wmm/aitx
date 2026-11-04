"""Extra patient facts for step 3b onward (contract docs/step3b_contract.md, step 6; decision 5).

Step 2 extracts age, sex, onset, family history and phenotypes. Trial criteria also ask about lab values,
gestational age at birth, current and prior treatments, other-trial participation and organ function. One
extraction per case:

  LLM   copies, for each fact, the exact words of the clinical description and the number it states
  code  keeps a fact only if its quote is verbatim in the description and its number is in the quote;
        normalizes lab analytes and reads units with aitx/evidence/labs.py (an unstated unit is never assumed
        unless only one unit is physiologically plausible)

The result goes to the ledger's patient_context.extra_facts; later sub-steps read it from there.
"""
from __future__ import annotations

import re
import time

from aitx.disease import extract as X
from aitx.evidence import labs as LABS
from aitx.evidence import ledger as LG

PROMPT_VERSION = "patient-facts-v1"
KINDS = ("lab", "organ_function", "gestational_age", "current_medication", "prior_therapy", "other_trial", "condition")

SYSTEM = """You list facts stated in a short clinical description of one patient. Use only the text given.
For each fact return one item:
{"kind": "lab" | "organ_function" | "gestational_age" | "current_medication" | "prior_therapy" | "other_trial" | "condition",
 "name": "<lab analyte, organ (liver / kidney / heart), drug or therapy name, or condition; short>",
 "value": <the number as written, or null when the text gives no number>,
 "unit": "<the unit exactly as written, or empty when no unit is written>",
 "status": "present" | "absent" | "normal" | "abnormal" | "",
 "quote": "<the exact words stating the fact, copied character for character>"}
lab: a measured value ("Hemoglobin 5"). organ_function: a statement about liver, kidney or other organ function
("Normal liver labs" -> status normal). gestational_age: weeks of gestation at birth. other_trial: participation in
other clinical trials ("Not enrolled in other trials" -> status absent). current_medication / prior_therapy: a named
treatment, with status absent when the text says it was not given. condition: another stated diagnosis.
Do not add units, numbers or facts that are not written. Return only JSON: {"facts": [...]}"""


def _llm(text: str, use_cache: bool) -> tuple[dict, dict]:
    t = time.time()
    r = X._cached_chat([{"role": "system", "content": SYSTEM}, {"role": "user", "content": f"Clinical description:\n{text}"}],
                       0, use_cache, prompt_version=PROMPT_VERSION)
    if time.time() - t > 1:
        print(f"[3b] LLM patient facts: {time.time() - t:.0f}s", flush=True)
    return X._parse(r)["parsed"], {"llm": X.llm.config()["model"], "served_model": r.get("served_model"),
                                   "prompt_version": PROMPT_VERSION}


def _number_in(value, quote: str) -> bool:
    if value is None:
        return True
    try:
        v = float(value)
    except (TypeError, ValueError):
        return False
    return any(abs(float(n) - v) < 1e-9 for n in re.findall(r"\d+(?:\.\d+)?", quote))


def verify(raw: list, text: str, table: dict | None = None) -> tuple[list[dict], list[dict]]:
    """(kept facts, dropped facts with the reason). Code only."""
    kept, dropped = [], []
    for f in raw or []:
        if not isinstance(f, dict):
            continue
        quote, kind = str(f.get("quote") or ""), f.get("kind")
        why = ("unknown kind" if kind not in KINDS else
               "quote not verbatim in the clinical description" if not LG.quote_in(quote, text) else
               "number not in the quote" if not _number_in(f.get("value"), quote) else
               "unit not in the quote" if f.get("unit") and not LG.quote_in(str(f["unit"]), quote) else None)
        if why:
            dropped.append({**f, "dropped": why})
            continue
        fact = {"kind": kind, "name": str(f.get("name") or "").strip(), "value": f.get("value"),
                "unit": str(f.get("unit") or "").strip(), "status": f.get("status") or "", "quote": quote}
        if kind == "lab" and fact["value"] is not None:
            interp = LABS.interpret(fact["name"], float(fact["value"]), fact["unit"] or None, table=table, who="patient value")
            fact["analyte"] = LABS.analyte_of(fact["name"], table if table is not None else LABS.load())
            fact["interpretation"] = interp            # ok / assumed (assumption written out) / unknown (with candidates)
        kept.append(fact)
    return kept, dropped


def extract(case: dict, *, use_cache: bool = True) -> dict:
    """{facts, dropped, produced_by, source_text} for one case; cached with the LLM answer."""
    text = (case.get("patient") or {}).get("clinical_context") or ""
    if not text.strip():
        return {"facts": [], "dropped": [], "produced_by": "code", "source_text": text}
    parsed, pb = _llm(text, use_cache)
    facts, dropped = verify(parsed.get("facts"), text)
    return {"facts": facts, "dropped": dropped, "produced_by": pb, "source_text": text}


def find(extra: dict, kind: str, name: str | None = None) -> list[dict]:
    """Facts of one kind, optionally whose name mentions `name` (case-insensitive, whole words)."""
    out = [f for f in (extra or {}).get("facts", []) if f["kind"] == kind]
    if name:
        n = re.escape(name.lower())
        out = [f for f in out if re.search(rf"(?<![a-z0-9]){n}(?![a-z0-9])", f["name"].lower())
               or re.search(rf"(?<![a-z0-9]){n}(?![a-z0-9])", f["quote"].lower())]
    return out
