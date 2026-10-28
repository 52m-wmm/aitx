"""Build a VariantProfile: the structured facts later steps rely on.

Everything here is deterministic. The mechanism hypothesis is a rule-based
first guess for later steps to confirm or overturn with literature; it is
never written into the report as a conclusion by itself.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field

from aitx.variant.hgvs import AA3_TO_1, CVariant, PVariant, parse_cdna, parse_protein
from aitx.variant.transcript import Transcript

SCHEMA_VERSION = "variant-profile-v1"
NMD_RULES = "nmd-v1"
NMD_JUNCTION_NT = 50
NMD_START_PROXIMAL_NT = 150
NMD_LONG_EXON_NT = 400
BORDERLINE_NT = 6


@dataclass
class Check:
    name: str
    status: str          # pass | warn | fail
    detail: str


@dataclass
class VariantProfile:
    schema_version: str
    gene: str
    transcript: str
    variant_cdna: str
    variant_protein: str
    zygosity: str
    variant_class: str
    protein_length: int
    first_affected_aa: int | None
    ptc_aa_position: int | None
    truncated_protein_length: int | None
    fraction_of_protein_retained: float | None
    exon: dict
    nmd: dict
    mechanism_hypothesis: dict
    allelic_state: dict
    checks: list[Check]
    evidence: list[dict]
    notes: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(c.status != "fail" for c in self.checks)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["ok"] = self.ok
        return d


# ------------------------------------------------------------------ checks

def _check_cdna_ref(cv: CVariant, t: Transcript) -> list[Check]:
    out: list[Check] = []
    if cv.start.intronic or cv.end.intronic:
        return [Check("cdna_reference", "warn", "intronic position; reference base not checkable on mRNA")]
    s = t.c_to_mrna(cv.start.base, cv.start.utr3)
    e = t.c_to_mrna(cv.end.base, cv.end.utr3)
    if not (1 <= s <= e <= len(t.seq)):
        return [Check("cdna_reference", "fail", f"positions {s}-{e} fall outside the transcript")]
    ref_seq = t.seq[s - 1:e]
    stated = cv.ref if cv.kind in ("sub", "del", "dup") else ""
    if stated:
        if stated == ref_seq:
            out.append(Check("cdna_reference", "pass", f"reference {stated} matches transcript"))
        else:
            out.append(Check("cdna_reference", "fail",
                             f"notation says {stated} but transcript has {ref_seq} at {cv.raw}"))
    else:
        out.append(Check("cdna_reference", "pass", f"reference span is {ref_seq} (not stated in notation)"))
    return out


def _check_protein_ref(pv: PVariant, t: Transcript) -> list[Check]:
    out: list[Check] = []
    for label, aa3, pos in (("start", pv.ref_aa, pv.pos), ("end", pv.end_ref_aa, pv.end_pos)):
        if not aa3 or pos is None:
            continue
        if pos > t.protein_length:
            out.append(Check(f"protein_reference_{label}", "fail",
                             f"{aa3}{pos} is beyond protein length {t.protein_length}"))
            continue
        actual = t.protein[pos - 1]
        expected = AA3_TO_1.get(aa3, "?")
        if actual == expected:
            out.append(Check(f"protein_reference_{label}", "pass", f"{aa3}{pos} matches translation"))
        else:
            out.append(Check(f"protein_reference_{label}", "fail",
                             f"notation says {aa3}{pos} but translation has {actual} at {pos}"))
    return out


def _check_codon_math(cv: CVariant, pv: PVariant) -> Check | None:
    """c. position -> codon number should agree with the p. position."""
    if pv.pos is None or cv.start.intronic or cv.start.utr3 or cv.start.base < 1:
        return None
    codon = math.ceil(cv.start.base / 3)
    if cv.kind == "sub":
        ok = codon == pv.pos
        return Check("codon_math", "pass" if ok else "fail",
                     f"c.{cv.start.base} is in codon {codon}; protein notation says {pv.pos}")
    # indels: HGVS shifts to the most 3' position, so the first changed
    # residue can be at or a little after the codon of the first changed base
    if codon <= pv.pos <= codon + 10:
        return Check("codon_math", "pass",
                     f"c.{cv.start.base} is in codon {codon}; first changed residue {pv.pos} (3' shifted ok)")
    return Check("codon_math", "warn",
                 f"c.{cv.start.base} is in codon {codon} but first changed residue is {pv.pos}")


def _check_kind_consistency(cv: CVariant, pv: PVariant) -> Check | None:
    net = cv.net_change
    if net is None:
        return None
    frameshifting = net % 3 != 0
    if pv.kind == "frameshift" and not frameshifting:
        return Check("cdna_protein_consistency", "fail", f"protein says frameshift but c. net change is {net}")
    if pv.kind.startswith("inframe") and frameshifting:
        return Check("cdna_protein_consistency", "fail", f"protein says in-frame but c. net change is {net}")
    return Check("cdna_protein_consistency", "pass", f"c. net change {net:+d} nt agrees with {pv.kind}")


# ------------------------------------------------------------- derivations

def _classify(cv: CVariant, pv: PVariant) -> tuple[str, list[str]]:
    notes = []
    if cv.start.intronic or cv.end.intronic:
        return "splice", ["variant touches an intron; splicing impact needs a splice predictor"]
    kind = pv.kind
    if kind == "nonsense" and cv.kind in ("del", "dup", "ins", "delins") and (cv.net_change or 0) % 3:
        notes.append("indel creating an immediate stop codon; treated as nonsense")
    if kind == "inframe_duplication":
        kind = "inframe_insertion"
    if kind == "inframe_delins":
        kind = "inframe_indel"
    return kind, notes


def _ptc(pv: PVariant) -> int | None:
    if pv.kind == "nonsense":
        return pv.pos
    if pv.kind == "frameshift" and pv.pos is not None and pv.fs_ter is not None:
        return pv.pos + pv.fs_ter - 1
    return None


def _exon_info(cv: CVariant, t: Transcript) -> dict:
    base = cv.start.base
    pos = t.c_to_mrna(base, cv.start.utr3) if not cv.start.intronic else t.c_to_mrna(base, cv.start.utr3)
    idx = t.exon_index(pos)
    info: dict = {"number": idx, "total": len(t.exons), "intronic_offset": cv.start.offset or 0}
    if idx is None:
        return info
    s, e = t.exons[idx - 1]
    coding_s, coding_e = max(s, t.cds_start), min(e, t.cds_start + t.coding_length - 1)
    coding = max(0, coding_e - coding_s + 1)
    info.update({
        "length_nt": e - s + 1,
        "coding_nt": coding,
        "coding_fraction_of_cds": round(coding / t.coding_length, 4),
        "is_last_exon": idx == len(t.exons),
        "c_range": [s - t.cds_start + 1, e - t.cds_start + 1],
    })
    if cv.end.base != cv.start.base and not cv.end.intronic:
        end_idx = t.exon_index(t.c_to_mrna(cv.end.base, cv.end.utr3))
        info["end_exon_number"] = end_idx
        if end_idx and idx and end_idx != idx:
            info["exons_spanned"] = list(range(idx, end_idx + 1))
    return info


def _nmd(pv: PVariant, cv: CVariant, t: Transcript, ptc_aa: int | None) -> dict:
    if ptc_aa is None:
        return {"prediction": "not_applicable", "reasons": ["no premature stop codon"], "rules": NMD_RULES}
    shift = cv.net_change or 0
    # first base of the new stop codon, translated back to reference c. coordinates;
    # a frameshift can read through the normal stop, putting the new stop in the 3'UTR
    ptc_c = 3 * (ptc_aa - 1) + 1 - (shift if pv.kind == "frameshift" else 0)
    ptc_mrna = t.c_to_mrna(max(ptc_c, 1))
    exon = t.exon_index(ptc_mrna)
    reasons: list[str] = []
    out = {"ptc_c_position_approx": ptc_c, "ptc_exon": exon, "rules": NMD_RULES, "borderline": False}
    stop_desc = "premature stop"
    if ptc_aa > t.protein_length:
        out["protein_extended_by_aa"] = ptc_aa - 1 - t.protein_length
        stop_desc = "new stop (frameshift reads past the normal stop codon)"
    if exon is None:
        out.update(prediction="uncertain",
                   reasons=[f"{stop_desc} falls beyond the end of the transcript record; "
                            "no stop codon in the mRNA would mean non-stop decay, not NMD"])
        return out

    if len(t.exons) == 1:
        out.update(prediction="likely_escapes", reasons=["single-exon transcript (no exon junction downstream)"])
        return out
    last_start = t.exons[-1][0]
    dist = last_start - ptc_mrna          # nt upstream of the last exon-exon junction
    out["nt_upstream_of_last_junction"] = dist

    if exon == len(t.exons):
        out.update(prediction="likely_escapes", reasons=[f"{stop_desc} is in the last exon"])
        return out
    if dist <= NMD_JUNCTION_NT:
        reasons.append(f"premature stop is {dist} nt upstream of the last exon junction (<= {NMD_JUNCTION_NT})")
        out.update(prediction="likely_escapes", reasons=reasons,
                   borderline=abs(dist - NMD_JUNCTION_NT) <= BORDERLINE_NT)
        return out
    out["borderline"] = abs(dist - NMD_JUNCTION_NT) <= BORDERLINE_NT
    if ptc_c <= NMD_START_PROXIMAL_NT:
        out.update(prediction="uncertain",
                   reasons=[f"premature stop within the first {NMD_START_PROXIMAL_NT} coding nt; "
                            "translation may reinitiate downstream"])
        return out
    s, e = t.exons[exon - 1]
    if e - s + 1 > NMD_LONG_EXON_NT:
        out.update(prediction="uncertain",
                   reasons=[f"premature stop is in a long exon ({e - s + 1} nt > {NMD_LONG_EXON_NT})"])
        return out
    out.update(prediction="likely_triggers",
               reasons=[f"premature stop is {dist} nt upstream of the last exon junction and not in the last exon"])
    return out


def _mechanism(vclass: str, nmd: dict, retained: float | None) -> dict:
    """Rule-based first guess. Later steps must confirm with literature/ClinVar."""
    if vclass in ("frameshift", "nonsense"):
        if nmd["prediction"] == "likely_triggers":
            return {"hypothesis": "loss_of_function", "confidence": "moderate",
                    "basis": "truncating variant predicted to undergo NMD (little or no protein made)"}
        if "protein_extended_by_aa" in nmd:
            return {"hypothesis": "loss_of_function_or_altered_function", "confidence": "low",
                    "basis": "frameshift reads past the normal stop: the last "
                             f"~{round((1 - (retained or 0)) * 100)}% of the protein is replaced by a novel tail "
                             f"and the protein is ~{nmd['protein_extended_by_aa']} aa longer than normal; "
                             "may act as LOF, dominant-negative or gain-of-function"}
        return {"hypothesis": "loss_of_function_or_altered_function", "confidence": "low",
                "basis": "truncating variant that may escape NMD; a shortened protein could be made "
                         f"(retains ~{round((retained or 0) * 100)}% of length) and might act as LOF, "
                         "dominant-negative or gain-of-function"}
    if vclass == "start_lost":
        return {"hypothesis": "loss_of_function", "confidence": "low",
                "basis": "start codon lost; protein may be absent or start at a downstream methionine"}
    if vclass == "splice":
        return {"hypothesis": "unknown", "confidence": "low", "basis": "needs splice prediction"}
    if vclass == "synonymous":
        return {"hypothesis": "likely_no_protein_change", "confidence": "low",
                "basis": "synonymous; check splicing effects"}
    return {"hypothesis": "unknown", "confidence": "low",
            "basis": f"{vclass}: mechanism (LOF / GOF / dominant-negative) depends on the gene and "
                     "residue; must be established from literature and functional data"}


def _allelic_state(zygosity: str) -> dict:
    z = (zygosity or "").lower()
    if z == "homozygous":
        return {"zygosity": z, "copies_affected": 2,
                "note": "both copies carry this variant (biallelic); consistent with recessive disease"}
    if z == "hemizygous":
        return {"zygosity": z, "copies_affected": 1,
                "note": "only one copy exists (e.g. X-linked gene in a male); no normal backup copy"}
    if z == "heterozygous":
        return {"zygosity": z, "copies_affected": 1,
                "note": "one normal copy remains; dominant mechanism (haploinsufficiency, dominant-negative, "
                        "gain-of-function) or one half of a compound-heterozygous pair"}
    return {"zygosity": z, "copies_affected": None, "note": "unrecognized zygosity"}


# -------------------------------------------------------------------- main

def build_profile(variant: dict, t: Transcript) -> VariantProfile:
    cv = parse_cdna(variant["variant_cdna"])
    pv = parse_protein(variant["variant_protein"])

    checks: list[Check] = []
    if variant.get("transcript") and variant["transcript"] != t.accession:
        checks.append(Check("transcript_version", "fail",
                            f"input names {variant['transcript']} but record is {t.accession}"))
    else:
        checks.append(Check("transcript_version", "pass", t.accession))
    if variant.get("gene") and t.gene and variant["gene"].upper() != t.gene.upper():
        checks.append(Check("gene_symbol", "fail", f"input gene {variant['gene']} but record gene {t.gene}"))
    checks += _check_cdna_ref(cv, t)
    checks += _check_protein_ref(pv, t)
    for c in (_check_codon_math(cv, pv), _check_kind_consistency(cv, pv)):
        if c:
            checks.append(c)

    vclass, notes = _classify(cv, pv)
    ptc_aa = _ptc(pv)
    truncated = ptc_aa - 1 if ptc_aa else None
    if truncated is not None and truncated > t.protein_length:
        truncated = None                   # extended, not truncated (see nmd.protein_extended_by_aa)
    # residues of the NORMAL sequence kept before the change (frameshift tail is not normal)
    normal_kept = (pv.pos - 1) if (ptc_aa and pv.kind == "frameshift") else truncated
    retained = round(normal_kept / t.protein_length, 4) if normal_kept is not None else None
    exon = _exon_info(cv, t)
    nmd = _nmd(pv, cv, t, ptc_aa)

    return VariantProfile(
        schema_version=SCHEMA_VERSION,
        gene=variant.get("gene") or t.gene,
        transcript=t.accession,
        variant_cdna=variant["variant_cdna"],
        variant_protein=variant["variant_protein"],
        zygosity=variant.get("zygosity", ""),
        variant_class=vclass,
        protein_length=t.protein_length,
        first_affected_aa=pv.pos,
        ptc_aa_position=ptc_aa,
        truncated_protein_length=truncated,
        fraction_of_protein_retained=retained,
        exon=exon,
        nmd=nmd,
        mechanism_hypothesis=_mechanism(vclass, nmd, retained),
        allelic_state=_allelic_state(variant.get("zygosity", "")),
        checks=checks,
        evidence=[{"source": t.source_url, "time_accessed": t.accessed_at,
                   "what": f"RefSeq record {t.accession}: exon structure, CDS, translation"}],
        notes=notes + t.notes,
    )


def patient_summary(profiles: list[VariantProfile]) -> dict:
    """Patient-level view across all listed variants."""
    by_gene: dict[str, list[VariantProfile]] = {}
    for p in profiles:
        by_gene.setdefault(p.gene, []).append(p)
    genes = {}
    for g, ps in by_gene.items():
        copies = sum(p.allelic_state["copies_affected"] or 0 for p in ps)
        if any(p.zygosity == "hemizygous" for p in ps):
            model = "hemizygous (single copy, e.g. X-linked)"
        elif copies >= 2:
            model = "biallelic (homozygous or two heterozygous variants; phase not given)"
        else:
            model = "monoallelic (one variant, one normal copy)"
        genes[g] = {"variants": [p.variant_cdna for p in ps], "allelic_model": model}
    return {"genes": genes, "all_checks_pass": all(p.ok for p in profiles)}
