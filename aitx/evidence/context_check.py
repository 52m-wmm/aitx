"""Context check (fix plan, decision 2026-11-11): one LLM judgement per written entry, with the whole passage and the
patient in view, answering a fixed list of questions; code decides what the answers change.

Why one step instead of one rule per mistake: every semantic error in the blind test came from judging a sentence
without its context - who the patients were (GEMIN5 coenzyme Q10), which gene the evidence was about (avoid bright
light: rhodopsin animal models), why the drug was given (voriconazole worsened a neuropathy), whether a clause was an
exemption (valproic acid "only in exceptional circumstances"), how strong a condition was ("significant acidosis" vs a
raised lactate), which patients a recommendation was limited to ("milder form"). The reading rules are
docs/clinical_reading_rules.md; the prompt below states their principles only - never their examples, which are the
regression set (data/eval/support_check_regression.json) and must not leak into the prompt.

Each entry: the questions that apply to it, answered together in one call, the call made N_CHECKS times
independently. An answer counts only when every judgement gives it (unanimous); otherwise the question is "split".
The LLM never sets a status: `decide_3a` / `decide_3c` turn the answers into requirement lines or precedent fields,
and the ledger computes the status from those as before.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from aitx.disease import extract as X
from aitx.evidence import ledger as LG

PROMPT_VERSION = "context-check-v3"   # v2: compact answers, reasoning_effort "low"; v3: disease / gene apart,
                                     # evidence as a choice, limit tied to the entry's quote (validation 2026-11-11)
N_CHECKS = 3
# the DeepSeek chat API takes reasoning_effort none / low / high / max, default high (api-docs.deepseek.com, read
# 2026-11-11); the context check runs at "low" to fit the budget (decision 2026-11-11, validated on judged entries)
CALL_PARAMS = {"temperature": 0, "max_tokens": 16384, "response_format": {"type": "json_object"},
               "reasoning_effort": "low"}
ENABLED = True        # tests that predate the context check switch it off (tests/conftest.py)
YES_NO = ("yes", "no", "not_stated")
DIRECTIONS = ("improved", "not_improved", "worsened", "mixed", "not_stated")

SYSTEM = """You read a passage from a medical source and answer numbered questions about it for one patient.
Principles:
1. Use only the passage and the patient information given. Do not use outside knowledge.
2. Read the whole passage: its title, headings, table headers and other sentences can say whom the advice or the
   report is about.
3. Advice or findings about another disease, another subtype, another gene, or only about animals or cells are not
   advice or findings about this patient's disease.
4. A drug given for another reason, or a drug that caused or worsened a problem, is not a treatment of the disease.
5. In advice to avoid something, words such as "only in", "unless" or "except" introduce exceptions in which it may
   be used - not the situations in which it must be avoided.
6. A condition with a degree (significant, severe, refractory, prolonged) is met only by a patient finding of that
   degree; a related finding of unknown degree does not meet it.
7. When the passage limits advice to some patients, that limit stands.
8. When the passage or the patient information does not say, answer "not_stated".
Answer every question with one of the answers listed for it, and the shortest verbatim quote from the passage it
rests on (at most 20 words; "" if none). No explanations.
Return only JSON: {"answers": [{"q": <number>, "answer": "<one of the listed answers>", "quote": "..."}]}"""


# ------------------------------------------------------------------ prompt parts (code)

def patient_text(pf: dict, branch: dict) -> str:
    """The patient as the checker sees it: diagnosis, variant, stated facts and phenotypes; nothing else."""
    d = (branch.get("diagnosis") or {}).get("label") or "not stated"
    lines = [f"Diagnosis: {d}"]
    vs = [v for v in pf.get("variants") or [] if v.get("gene") == branch.get("gene")] or pf.get("variants") or []
    if vs:
        lines.append("Variant: " + "; ".join(v["quote"] for v in vs))
    age = pf.get("age_months")
    lines.append(f"Age: {age / 12:g} years" if age is not None else "Age: not stated")
    lines.append(f"Sex: {pf.get('sex') or 'not stated'}")
    present = [x.get("label") for x in pf.get("present") or [] if x.get("label")]
    excluded = [x.get("label") for x in pf.get("excluded") or [] if x.get("label")]
    lines.append("Findings present: " + ("; ".join(present) if present else "none stated"))
    if excluded:
        lines.append("Findings stated as absent: " + "; ".join(excluded))
    return "\n".join(lines)


def messages(header: str, passage: str, patient: str, questions: list[dict]) -> list[dict]:
    qs = "\n".join(f"{i}. {q['text']} Answers: {' / '.join(q['allowed'])}." for i, q in enumerate(questions, 1))
    user = (f"Source: {header}\nPassage:\n\"\"\"\n{passage}\n\"\"\"\n\nPatient:\n{patient}\n\nQuestions:\n{qs}")
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]


# ------------------------------------------------------------------ one check

def majority(answers: list, value: str) -> bool:
    """More than half of the judgements gave `value` (a missing judgement counts against it)."""
    return sum(1 for a in answers if a == value) * 2 > max(len(answers), 1)


def combine(answers: list[str]) -> str:
    """Unanimous answer, else "split"; a missing answer makes the question split."""
    return answers[0] if answers and None not in answers and len(set(answers)) == 1 else "split"


def ask(header: str, passage: str, patient: str, questions: list[dict], *, use_cache: bool = True,
        n_checks: int = N_CHECKS) -> dict:
    """{questions: [{id, text, final, answers, quotes, reasons}], n_checks, llm}. Quotes are kept only when they are
    verbatim in the passage."""
    if not questions:
        return {"questions": [], "n_checks": 0, "llm": None}
    msgs = messages(header, passage, patient, questions)

    def one(k):
        r = X._parse(X._cached_chat(msgs, k, use_cache, prompt_version=PROMPT_VERSION, call_params=CALL_PARAMS))
        got = {}
        for a in (r["parsed"].get("answers") or []):
            try:
                i = int(a.get("q"))
            except (TypeError, ValueError):
                continue
            if 1 <= i <= len(questions) and a.get("answer") in questions[i - 1]["allowed"]:
                got[i] = a
        return r, got
    with ThreadPoolExecutor(max_workers=n_checks) as pool:
        runs = list(pool.map(one, range(n_checks)))
    out = []
    for i, q in enumerate(questions, 1):
        given = [got.get(i) for _, got in runs]
        answers = [g.get("answer") if g else None for g in given]
        quotes = [str(g.get("quote") or "") for g in given if g and g.get("quote") and LG.quote_in(str(g["quote"]), passage)]
        out.append({**q, "final": combine(answers), "answers": answers, "quotes": list(dict.fromkeys(quotes)),
                    "reasons": [str(g.get("reason") or "") for g in given if g]})
    first = runs[0][0]
    return {"questions": out, "n_checks": n_checks, "call_ids": [r.get("call_id") for r, _ in runs],
            "llm": {"served_model": first.get("served_model"), "prompt_version": PROMPT_VERSION}}


def summary(res: dict) -> dict:
    """What the ledger keeps: each question's final answer, the unanimous quote if any, the model."""
    return {"prompt_version": PROMPT_VERSION, "n_checks": res.get("n_checks"), "llm": res.get("llm"),
            "call_ids": res.get("call_ids") or [],
            "answers": {q["id"]: {"final": q["final"], "answers": q["answers"], "quote": (q["quotes"] or [None])[0]}
                        for q in res.get("questions", [])}}


# ------------------------------------------------------------------ 3a: Tier 1 entries

AVOID_SECTION = "contraindications_precautions"


EVIDENCE = ("this_disease_patients", "other_gene_or_subtype_patients", "animals_or_cells", "not_stated")
WEAK_EVIDENCE = ("other_gene_or_subtype_patients", "animals_or_cells")


def questions_3a(section: str, action: str, disease: str, lines: list[dict], quote: str | None = None) -> list[dict]:
    """The questions for one Tier 1 entry. Polarity is asked only for conditions of an avoidance; "meets" only for
    conditions the code found met from the patient's findings. `quote` is the entry's own words in the passage: the
    limit question is about that advice only (validation 2026-11-11: a limit from the next sentence of the same
    paragraph had been put on another entry)."""
    own = f" - the advice in the quoted words \"{quote}\"" if quote else ""
    qs = [{"id": "subject", "allowed": YES_NO,
           "text": f"Is this passage's advice about '{action}' given for people with {disease} (or for a group of "
                   f"conditions that includes it), and not only for another disease, subtype or gene?"},
          {"id": "evidence", "allowed": EVIDENCE,
           "text": f"What evidence does the passage give for the advice about '{action}': findings in patients with "
                   f"this disease, findings in patients with another gene or subtype, findings in animals or cells, "
                   f"or none stated?"},
          {"id": "limit", "allowed": YES_NO,
           "text": f"Considering only the advice about '{action}'{own}: does the passage limit it to only some "
                   f"patients by a characteristic of the patient (for example severity, age or a particular finding - "
                   f"not where or how a service is provided), beyond these conditions already recorded: "
                   f"{'; '.join(l['requirement'] for l in lines) or 'none'}? If yes, quote the limiting words."}]
    for l in lines:
        if section == AVOID_SECTION and l["result"] == "unknown":
            qs.append({"id": f"exemption:{l['id']}", "allowed": YES_NO, "line": l["id"],
                       "text": f"The passage advises avoiding '{action}'. Is '{l['requirement']}' an exception in which "
                               f"'{action}' may still be used, rather than the situation in which it must be avoided?"})
        if l["result"] == "pass" and (l.get("patient_fact") or {}).get("step") == 2:
            qs.append({"id": f"meets:{l['id']}", "allowed": YES_NO, "line": l["id"],
                       "text": f"Does the patient information show '{l['requirement']}' to the degree the passage "
                               f"states (not a related finding of unknown or lesser degree)?"})
    return qs


def questions_limit(action: str, limit: str) -> list[dict]:
    """Follow-up, asked only when the limit question found a limit (fix 2026-11-12, user decision): is the limit the
    patient's own row / genotype? A separate call, so the questions of every other entry - and their cached answers -
    stay as they were. (CFTR F508del homozygous: the GeneReviews ETI row "heterozygous for p.Phe508del & a minimal
    function variant" is another genotype's row.)"""
    return [{"id": "limit_patient", "allowed": YES_NO,
             "text": f"The passage limits the advice about '{action}' to patients described by \"{limit}\". Is that the "
                     f"group, table row or genotype this patient belongs to, as the patient information shows it (for "
                     f"example the same variant and zygosity)? Answer no if the patient belongs to another row or "
                     f"genotype, not_stated if the patient information does not say."}]


def decide_3a(res: dict, lines: list[dict], ev_id: str, passage: str, branches: list[str],
              limit_followup=None) -> tuple[list[dict], list[str]]:
    """New requirement lines from the answers, and the notes explaining them. Only ever moves an entry towards
    "conditional" - except an unanimous exemption, which stops that condition deciding the avoidance (fix plan S3).
    `limit_followup(quote) -> final answer` asks questions_limit for a limit found: a unanimous "yes" (the limit is
    the patient's own row or genotype, shown by the patient information) keeps it as a note instead of a line."""
    by = {q["id"]: q for q in res.get("questions", [])}
    out, notes = [dict(l) for l in lines], []
    n = len(out)

    def add(text: str, why: str, kind: str = "scope"):
        nonlocal n
        n += 1
        line = LG.requirement(f"r{n}", "other", text, ev_id,
                              {"field": "source scope", "value": None, "quote": None, "step": None}, "unknown", branches,
                              f"context check: {why}")
        line["context_check"] = kind
        out.append(line)
        notes.append(why)
    subj = (by.get("subject") or {}).get("final")
    if subj and subj != "yes":
        add("the source passage concerns this patient's disease", "the passage was not unanimously judged to be about "
            "this disease (another disease, subtype or gene, or not stated)")
    evi = (by.get("evidence") or {}).get("answers") or []
    # validation 2026-11-11: "rests only on animal studies?" swung yes / not stated / no for advice "recommended for all"
    # yet based on animal models of another gene; asking what the evidence is gives a clear answer
    if sum(1 for a in evi if a in WEAK_EVIDENCE) * 2 > max(len(evi), 1):
        add("the evidence for this advice comes from patients with this disease",
            "the passage bases this advice on animals or cells, or on patients with another gene or subtype")
    lim = by.get("limit") or {}
    if lim.get("final") == "yes":                       # unanimous only: a 2-of-3 split had made "In the US" a limit
        q = next((x for x in lim.get("quotes") or [] if LG.quote_in(x, passage)), None)
        if q and not any(LG._norm(q) == LG._norm(l["requirement"]) for l in out):
            if limit_followup is not None and limit_followup(q) == "yes":
                notes.append(f"limit '{q[:80]}' is the patient's own row or genotype: kept as a note")
            else:
                add(q, "the passage limits this advice to some patients", "limit")
    for qid, q in by.items():
        if qid.startswith("exemption:") and q["final"] == "yes":
            for l in out:
                if l["id"] == q["line"]:
                    l.update(patient_status="not_assessed", result="not_assessed", context_check="exemption",
                             note=(l.get("note") or "") + " | context check: an exception to the avoidance, not its "
                                                           "trigger")
                    notes.append(f"'{l['requirement'][:60]}' is an exception to the avoidance")
        if qid.startswith("meets:") and q["final"] != "yes":
            for l in out:
                if l["id"] == q["line"]:
                    l.update(patient_status="unknown", result="unknown", context_check="degree",
                             note=(l.get("note") or "") + " | context check: the patient's finding was not shown to "
                                                           "reach the stated degree")
                    notes.append(f"'{l['requirement'][:60]}' not shown to the stated degree")
    return out, notes


# ------------------------------------------------------------------ 3c: one precedent (one article)

GENE_ANSWERS = ("yes", "other_gene", "not_stated")


def questions_3c(drug: str, disease: str, gene: str | None) -> list[dict]:
    """Disease and gene are asked apart (validation 2026-11-11: "a patient with Leigh syndrome" matched the disease, so
    one combined question never asked whether the report says which gene - reading rule R3)."""
    qs = [{"id": "disease", "allowed": YES_NO,
           "text": f"Did the patients who received {drug} in this report have {disease} (or a group of conditions "
                   f"that includes it)? Quote the words that say which disease they had."}]
    if gene:
        qs.append({"id": "gene", "allowed": GENE_ANSWERS,
                   "text": f"Does the report say that these patients had variants in {gene}? Answer other_gene if it "
                           f"names a different gene, not_stated if it names none. Quote the words."})
    return qs + [
            {"id": "purpose", "allowed": YES_NO,
             "text": f"Was {drug} given to treat {disease} or one of its manifestations (not for another condition)?"},
            {"id": "harm", "allowed": YES_NO,
             "text": f"Does the report describe {drug} as causing or worsening a problem in these patients?"},
            {"id": "direction", "allowed": DIRECTIONS,
             "text": f"After {drug}, how does the report describe the treated patients' outcome? Quote the words."}]


DIRECTION_OF = {"improved": "positive", "not_improved": "negative", "worsened": "negative", "mixed": "mixed"}


def decide_3c(res: dict) -> dict:
    """{treatment, adverse, subject, direction, direction_quote, subject_quote} for one precedent."""
    by = {q["id"]: q for q in res.get("questions", [])}
    f = lambda k: (by.get(k) or {}).get("final")
    q1 = lambda k: ((by.get(k) or {}).get("quotes") or [None])[0]
    treatment = f("purpose") == "yes"                 # a treatment precedent only when unanimous
    # side effects during treatment do not disqualify a precedent (trial run 2026-11-11: L-serine and memantine had
    # been dropped for "irritability", "rare adverse events"); only a drug given for something else that then harmed is
    # an adverse report - a precaution candidate, never a contraindication (decision 2026-11-11)
    dis, gen = f("disease"), (f("gene") if "gene" in by else "yes")
    subject = ("other" if dis == "no" or gen == "other_gene" else
               "same" if dis == "yes" and gen == "yes" else "not_stated")
    return {"treatment": treatment,
            "adverse": not treatment and majority((by.get("harm") or {}).get("answers") or [], "yes"),
            "side_effects": treatment and f("harm") == "yes",
            "subject": subject,
            "subject_quote": q1("gene") or q1("disease"),
            "direction": DIRECTION_OF.get(f("direction"), "not_reported"),
            "direction_quote": q1("direction")}
