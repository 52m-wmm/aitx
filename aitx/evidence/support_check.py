"""Does the quoted source text support a claim? An independent LLM judgement, item by item.

Generic: used for drafted rules (step 3.0) and later for report claims (step 5). The caller splits a
claim into items (e.g. each condition, the conclusion, the scope); a separate LLM call, which sees only
the quotes and the items (never the reasoning that produced the claim), judges each item:

  supported            the quotes state it
  partially_supported  the quotes state something weaker or different: a frequency difference or odds
                       ratio presented as a rule, one case generalized, a condition broader than the quotes
                       (a condition that is a special case of what the quotes state counts as supported)
  not_supported        the quotes do not state it, or contradict it

The overall verdict is computed by code, not taken from the LLM: supported only if every item is
supported; not_supported if any item is not supported; otherwise partially_supported. Items the LLM
does not answer count as not supported.
"""
from __future__ import annotations

from aitx.disease import extract as X

PROMPT_VERSION = "support-check-v2"
VERDICTS = ("supported", "partially_supported", "not_supported")

SYSTEM = """You check whether quoted source text supports each part of a claim. Judge ONLY from the quotes;
do not use outside knowledge and do not give the claim the benefit of the doubt.
For each numbered item answer one verdict:
  "supported"            the quotes explicitly state it
  "partially_supported"  the quotes state something weaker, broader or different: e.g. a difference in frequency
                         or an odds ratio presented as a rule, a single case generalized, a condition that does not
                         match the one in the quotes (e.g. one variant vs two variants)
A condition that is the same as, or a special case of, what the quotes state is "supported" (if the quotes say
"in-frame mutations cause X", the condition "in-frame deletions" is supported). A condition broader than the quotes
is not.
  "not_supported"        the quotes do not state it or contradict it
Return only JSON: {"items": [{"item": <number>, "verdict": "...", "reason": "<one short sentence>"}]}"""


def overall(verdicts: list[str]) -> str:
    if not verdicts or "not_supported" in verdicts:
        return "not_supported"
    return "supported" if all(v == "supported" for v in verdicts) else "partially_supported"


def check_support(claim: str, items: list[str], quotes: list[str], *, use_cache: bool = True) -> dict:
    """{overall, items: [{item, verdict, reason}], llm}. `items` are plain sentences, judged one by one."""
    lines = [f"Claim: {claim}", "", "Items to judge:"] + [f"  {i}. {t}" for i, t in enumerate(items, 1)]
    lines += ["", "Quotes from the sources:"] + [f'  [{i}] "{q}"' for i, q in enumerate(quotes, 1)]
    r = X._cached_chat([{"role": "system", "content": SYSTEM}, {"role": "user", "content": "\n".join(lines)}], 0,
                       use_cache, prompt_version=PROMPT_VERSION)
    got = {}
    for a in (X._parse(r)["parsed"].get("items") or []):
        try:
            n = int(a.get("item"))
        except (TypeError, ValueError):
            continue
        if 1 <= n <= len(items) and a.get("verdict") in VERDICTS:
            got[n] = {"verdict": a["verdict"], "reason": str(a.get("reason") or "")}
    out_items = [{"item": t, **got.get(i, {"verdict": "not_supported", "reason": "no verdict returned"})}
                 for i, t in enumerate(items, 1)]
    return {"overall": overall([x["verdict"] for x in out_items]), "items": out_items,
            "llm": {"llm": X.llm.config()["model"], "served_model": r.get("served_model"), "prompt_version": PROMPT_VERSION}}


# ------------------------------------------------------------ rules (step 3.0)

_CLASS = {"frameshift": "frameshift", "nonsense": "nonsense (stop-gain)", "missense": "missense",
          "start_lost": "start-loss", "inframe_deletion": "in-frame deletion", "inframe_insertion": "in-frame insertion",
          "inframe_indel": "in-frame insertion-deletion", "synonymous": "synonymous", "splice": "splice-site"}
_ZYG = {"heterozygous": "a single heterozygous variant (one variant, on one allele)",
        "homozygous": "a homozygous variant (the same variant on both alleles)",
        "hemizygous": "a hemizygous variant (single copy, e.g. X-linked in a male)"}


def rule_items(rule: dict, labels: dict[str, str]) -> list[str]:
    """A drafted rule split into separately judged items: each condition, the conclusion, the scope."""
    gene, c = rule["gene"], rule.get("applies_when") or {}
    items = []
    if c.get("variant_class"):
        items.append(f"Condition: the rule is about {gene} " + " or ".join(_CLASS.get(v, v) for v in c["variant_class"]) + " variants.")
    if c.get("zygosity"):
        items.append(f"Condition: the rule is about patients with " + " or ".join(_ZYG.get(v, v) for v in c["zygosity"]) + f" in {gene}.")
    if c.get("protein_position"):
        a, b = c["protein_position"]
        items.append(f"Condition: the rule is about {gene} variants affecting protein residue{'s' if a != b else ''} {a}" + (f"-{b}" if a != b else "") + ".")
    if c.get("exon"):
        a, b = c["exon"]
        items.append(f"Condition: the rule is about {gene} variants in exon{'s' if a != b else ''} {a}" + (f"-{b}" if a != b else "") + ".")
    if c.get("nmd_prediction"):
        items.append(f"Condition: the rule is about {gene} variants whose transcript is predicted: {', '.join(c['nmd_prediction'])} (NMD).")
    sup = [labels.get(o, o) for o in rule["effect"].get("supports", [])]
    ag = [labels.get(o, o) for o in rule["effect"].get("argues_against", [])]
    concl = "Conclusion: such variants point to " + (" or ".join(sup) if sup else "(no disease)")
    if ag:
        concl += " rather than " + " or ".join(ag)
    items.append(concl + ".")
    items.append(f"Scope: this is stated as a general association for such {gene} variants, not only for a single "
                 "reported patient or family, and not only as a difference in frequency between patient groups.")
    return items


def check_rule(rule: dict, labels: dict[str, str], *, use_cache: bool = True) -> dict:
    return check_support(rule["statement"], rule_items(rule, labels), [s["quote"] for s in rule["sources"]],
                         use_cache=use_cache)
