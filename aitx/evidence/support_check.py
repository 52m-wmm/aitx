"""Does the quoted source text support a claim? An independent LLM judgement, item by item.

Generic: used for drafted rules (step 3.0) and later for report claims (step 5). The caller splits a
claim into items (e.g. each condition, the conclusion, the scope); a separate LLM call, which sees only
the quotes and the items (never the reasoning that produced the claim), judges each item:

  supported            the quotes state it
  partially_supported  the quotes state something weaker or different: a frequency difference or odds
                       ratio presented as a rule, one case generalized, a condition broader than the quotes
                       (a condition that is a special case of what the quotes state counts as supported)
  not_supported        the quotes do not state it, or contradict it

The judgement is made N_CHECKS times independently. An item is supported only if every judgement says
supported (unanimous); otherwise it is not_supported if any judgement says so, else partially_supported.
The overall verdict is computed by code, not taken from the LLM: supported only if every item is
supported; not_supported if any item is not supported; otherwise partially_supported. Items the LLM
does not answer count as not supported. Conditions of a rule are conjunctive, so they are judged as one item.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from aitx.disease import extract as X

PROMPT_VERSION = "support-check-v4"
N_CHECKS = 3          # independent judgements per claim; an item is supported only if all of them say so
VERDICTS = ("supported", "partially_supported", "not_supported")

SYSTEM = """You check whether quoted source text supports each part of a claim. Judge ONLY from the quotes;
do not use outside knowledge and do not give the claim the benefit of the doubt.
For each numbered item answer one verdict:
  "supported"            the quotes explicitly state it
  "partially_supported"  the quotes state something weaker, broader or different: e.g. a difference in frequency
                         or an odds ratio presented as a rule, a single case generalized, a condition that does not
                         match the one in the quotes (e.g. one variant vs two variants)
The conclusion may not be stronger than the quotes: a difference in proportions between groups does not support
excluding a diagnosis or preferring one over another; a single case or family does not support a general rule; an
association does not support causation. If the claim is stronger than the quotes in any of these ways, the item is
at most "partially_supported".
A condition that is the same as, or a special case of, what the quotes state is "supported" (if the quotes say
"in-frame mutations cause X", the condition "in-frame deletions" is supported). A condition broader than the quotes
is not.
  "not_supported"        the quotes do not state it or contradict it
Disease names: an item may give a disease's standard name followed by "also called: ..." synonyms; a quote that
names the disease by any of these names refers to that disease.
Return only JSON: {"items": [{"item": <number>, "verdict": "...", "reason": "<one short sentence>"}]}"""


def overall(verdicts: list[str]) -> str:
    if not verdicts or "not_supported" in verdicts:
        return "not_supported"
    return "supported" if all(v == "supported" for v in verdicts) else "partially_supported"


def combine(verdicts: list[str]) -> str:
    """One item over the independent judgements: unanimous supported, else the worst."""
    if verdicts and all(v == "supported" for v in verdicts):
        return "supported"
    return "not_supported" if "not_supported" in verdicts or not verdicts else "partially_supported"


def _judge(messages: list[dict], k: int, n_items: int, use_cache: bool) -> tuple[dict, dict]:
    r = X._cached_chat(messages, k, use_cache, prompt_version=PROMPT_VERSION)
    got = {}
    for a in (X._parse(r)["parsed"].get("items") or []):
        try:
            n = int(a.get("item"))
        except (TypeError, ValueError):
            continue
        if 1 <= n <= n_items and a.get("verdict") in VERDICTS:
            got[n] = {"verdict": a["verdict"], "reason": str(a.get("reason") or "")}
    return r, got


def check_support(claim: str, items: list[str], quotes: list[str], *, use_cache: bool = True,
                  n_checks: int = N_CHECKS) -> dict:
    """{overall, items: [{item, verdict, reason, judgements}], llm}. Items are judged n_checks times."""
    lines = [f"Claim: {claim}", "", "Items to judge:"] + [f"  {i}. {t}" for i, t in enumerate(items, 1)]
    lines += ["", "Quotes from the sources:"] + [f'  [{i}] "{q}"' for i, q in enumerate(quotes, 1)]
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": "\n".join(lines)}]
    with ThreadPoolExecutor(max_workers=n_checks) as pool:
        runs = list(pool.map(lambda k: _judge(messages, k, len(items), use_cache), range(n_checks)))
    none = {"verdict": "not_supported", "reason": "no verdict returned"}
    out_items = []
    for i, t in enumerate(items, 1):
        js = [got.get(i, none) for _, got in runs]
        v = combine([j["verdict"] for j in js])
        reason = next((j["reason"] for j in js if j["verdict"] == v), js[0]["reason"])
        out_items.append({"item": t, "verdict": v, "reason": reason, "judgements": [j["verdict"] for j in js]})
    return {"overall": overall([x["verdict"] for x in out_items]), "items": out_items, "n_checks": n_checks,
            "llm": {"llm": X.llm.config()["model"], "served_model": runs[0][0].get("served_model"),
                    "prompt_version": PROMPT_VERSION}}


# ------------------------------------------------------------ rules (step 3.0)

_CLASS = {"frameshift": "frameshift", "nonsense": "nonsense (stop-gain)", "missense": "missense",
          "start_lost": "start-loss", "inframe_deletion": "in-frame deletion", "inframe_insertion": "in-frame insertion",
          "inframe_indel": "in-frame insertion-deletion", "synonymous": "synonymous", "splice": "splice-site"}
_ZYG = {"heterozygous": "a single heterozygous variant (one variant, on one allele)",
        "homozygous": "a homozygous variant (the same variant on both alleles)",
        "hemizygous": "a hemizygous variant (single copy, e.g. X-linked in a male)"}


def disease_name(omim: str, names: dict[str, dict]) -> str:
    """Standard name plus synonyms, supplied by code (step 2 candidate), never the rule's own wording."""
    n = names.get(omim) or {}
    syn = [s for s in n.get("synonyms") or [] if s.lower() != str(n.get("label", "")).lower()][:8]
    return (n.get("label") or omim) + (f" (also called: {'; '.join(syn)})" if syn else "")


def rule_items(rule: dict, names: dict[str, dict]) -> list[str]:
    """A drafted rule split into separately judged items: each condition, the conclusion, the scope.

    The conclusion is built from the rule's effect (OMIM ids picked from the step 2 candidate list) and the
    names code supplies for those ids; the rule's free-text statement does not decide anything."""
    gene, c = rule["gene"], rule.get("applies_when") or {}
    parts = []                                      # conditions hold together (AND): one item
    if c.get("variant_class"):
        parts.append("are " + " or ".join(_CLASS.get(v, v) for v in c["variant_class"]) + " variants")
    if c.get("protein_position"):
        a, b = c["protein_position"]
        parts.append(f"affect protein residue{'s' if a != b else ''} {a}" + (f"-{b}" if a != b else ""))
    if c.get("exon"):
        a, b = c["exon"]
        parts.append(f"lie in exon{'s' if a != b else ''} {a}" + (f"-{b}" if a != b else ""))
    if c.get("nmd_prediction"):
        parts.append("have the NMD prediction " + " or ".join(c["nmd_prediction"]))
    if c.get("zygosity"):
        parts.append("are present as " + " or ".join(_ZYG.get(v, v) for v in c["zygosity"]))
    items = [f"Condition: the rule is about {gene} variants that " + " and that ".join(parts) + "."] if parts else []
    sup = [disease_name(o, names) for o in rule["effect"].get("supports", [])]
    ag = [disease_name(o, names) for o in rule["effect"].get("argues_against", [])]
    concl = "Conclusion: such variants point to " + (" or ".join(sup) if sup else "(no disease)")
    if ag:
        concl += " rather than " + " or ".join(ag)
    items.append(concl + ".")
    items.append(f"Scope: this is stated as a general association for such {gene} variants, not only for a single "
                 "reported patient or family, and not only as a difference in frequency between patient groups.")
    return items


def check_rule(rule: dict, names: dict[str, dict], *, use_cache: bool = True) -> dict:
    """names: OMIM id -> {"label", "synonyms"} from the step 2 candidates."""
    return check_support(rule["statement"], rule_items(rule, names), [s["quote"] for s in rule["sources"]],
                         use_cache=use_cache)
