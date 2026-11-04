"""Variant name forms (step 3a): does a label or chapter that names variants cover the patient's variant?

p.Phe508del -> Phe508del, F508del, delF508, ΔF508; p.Gly170Arg -> Gly170Arg, G170R. Matching is done by
code on whole tokens; the LLM never decides whether a patient's variant is listed.
"""
from __future__ import annotations

import re

from aitx.variant.hgvs import AA3_TO_1


def aliases(protein: str) -> list[str]:
    p = protein.strip()
    if p.startswith("p.(") and p.endswith(")"):
        p = "p." + p[3:-1]
    body = p[2:] if p.startswith("p.") else p
    out = {p, body}
    m = re.fullmatch(r"([A-Z][a-z]{2})(\d+)([A-Z][a-z]{2}|Ter|del|dup|fs.*)", body)
    if m:
        ref, pos, alt = m.groups()
        r1 = AA3_TO_1.get(ref)
        if r1:
            if alt == "del":
                out |= {f"{r1}{pos}del", f"del{r1}{pos}", f"Δ{r1}{pos}", f"delta{r1}{pos}"}
            elif alt == "Ter":
                out |= {f"{r1}{pos}X", f"{r1}{pos}*", f"{ref}{pos}*"}
            elif alt in AA3_TO_1:
                out.add(f"{r1}{pos}{AA3_TO_1[alt]}")
    return sorted(out, key=len, reverse=True)


def mentioned(protein: str, text: str) -> str | None:
    """The alias of the patient's variant that the text names as a whole token, or None."""
    for a in aliases(protein):
        if re.search(rf"(?<![A-Za-z0-9]){re.escape(a)}(?![A-Za-z0-9])", text):
            return a
    return None
