"""Independent re-translation: apply the c. change to the mRNA and translate it again.

This does not read the p. notation. It edits the RefSeq mRNA sequence the way the
c. notation says, translates from the start codon to the first stop codon, and
compares the new protein with the normal one. The result is then checked against
the stated p. notation (profile._check_retranslation):

  frameshift / nonsense   stop position (Ter)
  missense                position and new amino acid
  in-frame del / ins      deleted or inserted residues
  start_lost              start codon no longer ATG
  synonymous              protein unchanged

Software analogy: the p. notation is a cached result; this recomputes it from the
source (mRNA + c. edit) and diffs the two.
"""
from __future__ import annotations

from aitx.variant.hgvs import AA1_TO_3, CVariant
from aitx.variant.transcript import Transcript

_BASES = "TCAG"
_AA = "FFLLSSSSYY**CC*WLLLLPPPPHHQQRRRRIIIMTTTTNNKKSSRRVVVVAAAADDEEGGGG"
CODON_TABLE = {a + b + c: _AA[16 * i + 4 * j + k]
               for i, a in enumerate(_BASES) for j, b in enumerate(_BASES) for k, c in enumerate(_BASES)}
WINDOW_CODONS = 8


def translate(seq: str, start: int) -> tuple[str, int | None]:
    """Translate seq from 1-based mRNA position `start` to the first stop.

    Returns (protein without the stop, mRNA position of the stop codon's first base
    or None when the sequence ends before any stop codon).
    """
    prot = []
    i = start - 1
    while i + 3 <= len(seq):
        aa = CODON_TABLE.get(seq[i:i + 3], "X")
        if aa == "*":
            return "".join(prot), i + 1
        prot.append(aa)
        i += 3
    return "".join(prot), None


def apply_variant(t: Transcript, cv: CVariant) -> str | None:
    """mRNA sequence with the c. change applied; None if it cannot be placed on the mRNA."""
    if cv.start.intronic or cv.end.intronic:
        return None
    s, e = t.c_to_mrna(cv.start.base, cv.start.utr3), t.c_to_mrna(cv.end.base, cv.end.utr3)
    seq = t.seq
    if not (1 <= s <= e <= len(seq)):
        return None
    if cv.kind == "sub":
        return seq[:s - 1] + cv.alt + seq[s:]
    if cv.kind == "del":
        return seq[:s - 1] + seq[e:]
    if cv.kind == "dup":
        return seq[:e] + seq[s - 1:e] + seq[e:]
    if cv.kind == "ins":
        return seq[:s] + cv.alt + seq[s:]          # c.X_X+1insN: between the two flanking bases
    if cv.kind == "delins":
        return seq[:s - 1] + cv.alt + seq[e:]
    return None


def aa3(a: str) -> str:
    return "Ter" if a == "*" else AA1_TO_3.get(a, "Xaa")


def _codons(seq: str, start: int, first: int, n: int) -> list[dict]:
    """n codons of the frame starting at mRNA `start`, from codon number `first` (1-based)."""
    out = []
    for k in range(first, first + n):
        p = start + 3 * (k - 1) - 1
        cod = seq[p:p + 3]
        if len(cod) < 3:
            break
        out.append({"n": k, "codon": cod, "aa": aa3(CODON_TABLE.get(cod, "X"))})
    return out


def retranslate(t: Transcript, cv: CVariant) -> dict:
    """Facts computed from the mRNA alone (no use of the p. notation)."""
    ref_prot, ref_stop = translate(t.seq, t.cds_start)
    out: dict = {"method": "apply c. change to the RefSeq mRNA, translate from the CDS start to the first stop",
                 "reference_translation_matches_record": ref_prot == t.protein}
    mut = apply_variant(t, cv)
    if mut is None:
        out["status"] = "not_computable"
        out["reason"] = "intronic or out-of-range position; the change cannot be applied to the mRNA"
        return out
    start_codon = mut[t.cds_start - 1:t.cds_start + 2]
    out["start_codon"] = {"reference": t.seq[t.cds_start - 1:t.cds_start + 2], "variant": start_codon}
    if start_codon != "ATG":
        # no normal start; report what the first codon now encodes and the next in-frame ATG
        out["status"] = "start_lost"
        out["first_changed_aa"] = {"position": 1, "reference": "Met", "variant": aa3(CODON_TABLE.get(start_codon, "X"))}
        nxt = next((k for k in range(2, len(ref_prot) + 1) if ref_prot[k - 1] == "M"), None)
        out["next_inframe_met"] = nxt
        out["codon_window"] = _window(t, mut, 1)
        return out
    mut_prot, mut_stop = translate(mut, t.cds_start)
    out["status"] = "computed"
    out["stop_found"] = mut_stop is not None
    out["variant_protein_length"] = len(mut_prot)
    out["stop_position"] = len(mut_prot) + 1 if mut_stop is not None else None    # Ter residue number
    out["variant_protein"] = mut_prot
    if mut_prot == ref_prot:
        out["change"] = "none"
        out["codon_window"] = _window(t, mut, max(1, (cv.start.base + 2) // 3) if not cv.start.utr3 else 1)
        return out
    # longest common prefix / suffix: what is left in the middle is the change
    # (taking the prefix first puts an ambiguous indel at its most 3' position, as HGVS does)
    p = 0
    while p < min(len(ref_prot), len(mut_prot)) and ref_prot[p] == mut_prot[p]:
        p += 1
    s = 0
    while s < min(len(ref_prot), len(mut_prot)) - p and ref_prot[-1 - s] == mut_prot[-1 - s]:
        s += 1
    first = p + 1
    out["first_changed_aa"] = {"position": first,
                               "reference": aa3(ref_prot[p]) if p < len(ref_prot) else "Ter",
                               "variant": aa3(mut_prot[p]) if p < len(mut_prot) else "Ter"}
    out["reference_span"] = [first, len(ref_prot) - s]          # changed residues in the normal protein
    out["deleted"] = "".join(aa3(a) for a in ref_prot[p:len(ref_prot) - s])
    out["inserted"] = "".join(aa3(a) for a in mut_prot[p:len(mut_prot) - s])
    out["same_frame_after_change"] = s > 0
    out["codon_window"] = _window(t, mut, first)
    return out


def _window(t: Transcript, mut: str, first_aa: int) -> dict:
    """Codons around the first changed residue, normal frame vs variant frame (for the viewer)."""
    lo = max(1, first_aa - WINDOW_CODONS // 2 + 1)
    ref, var = _codons(t.seq, t.cds_start, lo, WINDOW_CODONS), _codons(mut, t.cds_start, lo, WINDOW_CODONS)
    by_n = {c["n"]: c["codon"] for c in ref}
    for c in var:
        c["changed"] = by_n.get(c["n"]) != c["codon"]
    return {"first_codon": lo, "changed_codon": first_aa, "reference": ref, "variant": var}
