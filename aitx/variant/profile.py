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
from aitx.variant.translate import aa3, retranslate

SCHEMA_VERSION = "variant-profile-v1.1"
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
    retranslation: dict = field(default_factory=dict)
    normal_residues_retained: int | None = None      # residues of the normal sequence before the change
    frameshift_tail_aa: int | None = None            # frameshift: novel (out-of-frame) residues before the stop
    transcript_layout: dict = field(default_factory=dict)   # exons, CDS, variant / new stop, junctions (for the viewer)

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


def _check_retranslation(pv: PVariant, rt: dict) -> Check:
    """Self-check 6: the p. notation must agree with the protein re-translated from the c. change.

    Records rt["comparison"] = {what, stated, computed, agree} for the viewer.
    """
    def done(what: str, stated, computed, agree: bool, extra: str = "") -> Check:
        rt["comparison"] = {"what": what, "stated": stated, "computed": computed, "agree": agree}
        status = "pass" if agree else "fail"
        if agree and extra:
            status = "warn"
        return Check("independent_translation", status,
                     f"{what}: stated {stated}, computed {computed}" + (f"; {extra}" if extra else ""))

    if not rt.get("reference_translation_matches_record", True):
        return Check("independent_translation", "fail",
                     "translating the RefSeq mRNA does not reproduce the record's protein; cannot re-check")
    if rt["status"] == "not_computable":
        rt["comparison"] = {"what": "not computable", "stated": pv.raw, "computed": None, "agree": None}
        return Check("independent_translation", "warn", rt["reason"])
    fc = rt.get("first_changed_aa") or {}
    if pv.kind == "start_lost" or rt["status"] == "start_lost":
        agree = pv.kind == "start_lost" and rt["status"] == "start_lost"
        alt_note = ""
        if agree and pv.alt_aa and fc.get("variant") != pv.alt_aa:
            alt_note = f"start codon now reads {fc.get('variant')}, notation says {pv.alt_aa}"
        return done("start codon", f"{pv.ref_aa}{pv.pos}{pv.alt_aa}",
                    f"{rt['start_codon']['reference']}>{rt['start_codon']['variant']} ({fc.get('variant')})",
                    agree, alt_note)
    first_note = ""
    if fc and pv.pos is not None and fc["position"] != pv.pos:
        first_note = f"first changed residue stated {pv.pos}, computed {fc['position']}"
    if pv.kind in ("frameshift", "nonsense"):
        stop = rt.get("stop_position")
        if pv.kind == "frameshift":
            stated = f"Ter{pv.fs_ter}" if pv.fs_ter else "Ter?"
            computed = f"Ter{stop - fc['position'] + 1}" if stop and fc else "no stop in transcript"
            agree = (pv.fs_ter is None and stop is None) or (stop is not None and fc and pv.pos is not None
                                                             and stop == pv.pos + (pv.fs_ter or 0) - 1)
            if agree and pv.alt_aa and fc.get("variant") != pv.alt_aa:
                first_note = "; ".join(x for x in (first_note, f"first new residue stated {pv.alt_aa}, computed {fc.get('variant')}") if x)
            if stop:
                computed += f" (stop at residue {stop})"
            if pv.fs_ter and pv.pos is not None:
                stated += f" (stop at residue {pv.pos + pv.fs_ter - 1})"
            return done("stop position", stated, computed, bool(agree), first_note)
        return done("stop position", f"Ter at {pv.pos}", f"Ter at {stop}" if stop else "no stop", stop == pv.pos)
    if pv.kind == "missense":
        stated, computed = f"{pv.ref_aa}{pv.pos}{pv.alt_aa}", f"{fc.get('reference')}{fc.get('position')}{fc.get('variant')}"
        one = rt.get("reference_span", [0, -1])[1] - rt.get("reference_span", [0, -1])[0] == 0 and len(rt.get("inserted", "")) == 3
        return done("new amino acid", stated, computed, stated == computed and one)
    if pv.kind == "synonymous":
        return done("protein change", "none", rt.get("change", "changed"), rt.get("change") == "none")
    span = rt.get("reference_span")
    if pv.kind == "inframe_deletion":
        stated = f"del {pv.ref_aa}{pv.pos}_{pv.end_ref_aa}{pv.end_pos}"
        computed = f"del {span[0]}_{span[1]} ({len(rt['deleted']) // 3} aa)" + (f" ins {rt['inserted']}" if rt["inserted"] else "")
        return done("deleted residues", stated, computed, span == [pv.pos, pv.end_pos] and not rt["inserted"])
    if pv.kind == "inframe_duplication":
        stated = f"dup {pv.ref_aa}{pv.pos}_{pv.end_ref_aa}{pv.end_pos}"
        computed = f"ins {rt['inserted']} after residue {span[0] - 1}"
        copied = "".join(aa3(a) for a in rt["variant_protein"][pv.pos - 1:pv.end_pos])   # same as normal up to here
        agree = span[0] == pv.end_pos + 1 and not rt["deleted"] and rt["inserted"] == copied
        return done("inserted residues", stated, computed, agree)
    if pv.kind in ("inframe_insertion", "inframe_delins"):
        ins = pv.extra.get("inserted", "")
        stated = f"{pv.kind} {pv.pos}_{pv.end_pos} {ins}"
        computed = f"{span[0]}_{span[1]} del {rt['deleted'] or '-'} ins {rt['inserted'] or '-'}"
        if pv.kind == "inframe_insertion":
            agree = span[0] == pv.end_pos and not rt["deleted"] and rt["inserted"] == ins
        else:
            agree = span == [pv.pos, pv.end_pos] and rt["inserted"] == ins
        return done("inserted residues", stated, computed, agree)
    rt["comparison"] = {"what": pv.kind, "stated": pv.raw, "computed": None, "agree": None}
    return Check("independent_translation", "warn", f"no comparison rule for {pv.kind}")


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


def _layout(cv: CVariant, t: Transcript, nmd: dict) -> dict:
    """Transcript drawn to scale: exons (mRNA coordinates), CDS, variant and new-stop positions,
    and each exon-exon junction marked relative to the new stop (EJC rule used by NMD)."""
    var = None
    if not (cv.start.intronic or cv.end.intronic):
        var = [t.c_to_mrna(cv.start.base, cv.start.utr3), t.c_to_mrna(cv.end.base, cv.end.utr3)]
    ptc_c = nmd.get("ptc_c_position_approx")
    stop = t.c_to_mrna(max(ptc_c, 1)) if ptc_c is not None else None
    junctions = []
    for i, (_, e) in enumerate(t.exons[:-1], start=1):
        dist = None if stop is None else e - stop          # junction nt downstream of the new stop
        junctions.append({"after_exon": i, "mrna_position": e,
                          "nt_downstream_of_new_stop": dist,
                          "downstream_of_new_stop": dist is not None and dist > 0,
                          "more_than_50nt_downstream": dist is not None and dist > NMD_JUNCTION_NT})
    return {"mrna_length": len(t.seq), "cds": [t.cds_start, t.cds_end],
            "exons": [{"number": i, "start": s, "end": e, "length": e - s + 1}
                      for i, (s, e) in enumerate(t.exons, start=1)],
            "variant_mrna": var, "new_stop_mrna": stop,
            "new_stop_note": "stop position from the stated p. notation, confirmed by self-check 6" if stop else None,
            "junctions": junctions}


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
    rt = retranslate(t, cv)
    checks.append(_check_retranslation(pv, rt))

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
        retranslation=rt,
        normal_residues_retained=normal_kept,
        frameshift_tail_aa=(ptc_aa - pv.pos) if (ptc_aa and pv.kind == "frameshift" and pv.pos) else None,
        transcript_layout=_layout(cv, t, nmd),
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
