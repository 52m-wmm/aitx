"""Step 3d: bespoke therapies (Tier 3, hypothetical layer). Contract: docs/step3d_contract.md.

Six modalities are judged for every diagnosis branch, each with a verdict and the reason for it. Everything
here is a deterministic judgement on step 1 facts; the disease mechanism is the only input that comes from a
source (GeneReviews, quoted and support-checked by the caller in established-style, never guessed by the LLM).

Verdict vocabulary (contract section 3):
  three ASO modalities      eligible / likely_eligible / unlikely_eligible / not_eligible / unable_to_assess
                            (N1C VARIANT guidelines, PMID 40139194; definitions quoted in the contract)
  gene replacement, editing  theoretically_possible / not_applicable / unable_to_assess
  upregulation of the WT allele   not_graded (N1C does not define eligibility classes for it) / unable_to_assess

Deferred data sources (decision 2026-11-05): UniProt domain annotation, gene-dosage scores (pLI / LOEUF /
ClinGen) and any mechanism source other than GeneReviews are not connected. A judgement that needs one of
them is "unable_to_assess" with the missing input named in `unassessable_reason`, so the acceptance run can
count how often that happens and the review can decide whether to connect them.
"""
from __future__ import annotations

import re

SECTION = "bespoke_therapies"
MODALITIES = ("aso_splice_correction", "aso_exon_skipping", "rna_knockdown", "wt_upregulation",
              "gene_replacement", "base_or_prime_editing")

AAV_CAPACITY_NT = 4700          # wild-type AAV genome size, the threshold set by review (2026-11-05)
AAV_MEASURED_NT = 5200          # "packaged AAV vector genomes never exceeded 5.2 kb" (Wu 2010, PMID 19904234)
DOMAIN_SHARE_LIMIT = 10.0       # "skipping an exon that encodes for more than 10% of the protein" (N1C Data S1)
STOPS = ("TAA", "TAG", "TGA")

# mechanism words the mechanism extractor may return (the quote itself is kept beside them in the ledger)
LOF = ("loss_of_function", "haploinsufficiency")
TOXIC = ("gain_of_function", "dominant_negative")

NO_MECHANISM = "disease mechanism not stated in GeneReviews (no other mechanism source is connected)"
NO_DOMAIN = "functional domains of the exon not checked (UniProt domain annotation not connected)"
NO_NATURAL = "no search for natural exon skipping or in-frame deletions (ClinVar / gnomAD / PubMed not connected here)"
NO_DOSAGE = "gene dosage sensitivity not checked (pLI / LOEUF / ClinGen haploinsufficiency score not connected)"
NO_SPLICE = "no RNA-level evidence that this variant changes splicing (splice prediction not connected; N1C: " \
            "in silico predictions are not to be used as substitutes for RNAseq and qPCR data)"
NO_PAM = "whether a suitable PAM and editing window exist is not assessed"
NO_PHASING = "needs haplotype (phasing) information: which allele carries the targeted SNP"


# ------------------------------------------------------------------ exon facts (deterministic)

def coding_exons(tr) -> list[dict]:
    """Every exon that carries coding sequence, with its coding length and reading-frame phase.

    `tr` is an aitx.variant.transcript.Transcript (step 1 already fetched and cached it). UTR-only exons are
    left out, because N1C judges the first and last CODING exons, not the first and last exons.
    """
    out, before = [], 0
    for n, (start, end) in enumerate(tr.exons, start=1):
        lo, hi = max(start, tr.cds_start), min(end, tr.cds_end)
        if lo > hi:
            continue
        nt = hi - lo + 1
        out.append({"number": n, "coding_nt": nt, "in_frame": nt % 3 == 0, "phase_in": before % 3,
                    "phase_out": (before + nt) % 3, "mrna": (lo, hi)})
        before += nt
    return out


def junction_codon(tr, exons: list[dict], number: int) -> str | None:
    """The codon formed at the new exon-exon boundary when this exon is skipped, or None when the exon starts
    and ends on codon boundaries (phase 0) and no new codon is formed."""
    i = next((k for k, e in enumerate(exons) if e["number"] == number), None)
    if i is None or i == 0 or i == len(exons) - 1 or exons[i]["phase_in"] == 0:
        return None
    up, down = exons[i - 1], exons[i + 1]
    take = exons[i]["phase_in"]                      # nucleotides contributed by the upstream exon
    left = tr.seq[up["mrna"][1] - take + 1 - 1:up["mrna"][1]]
    right = tr.seq[down["mrna"][0] - 1:down["mrna"][0] - 1 + (3 - take)]
    codon = (left + right).upper()
    return codon if len(codon) == 3 else None


# ------------------------------------------------------------------ 3.1 splice correction

def splice_correction(variant_class: str | None, splicing_evidence: bool = False) -> dict:
    """Only variants shown to change splicing are candidates; step 1 gives no splicing evidence, so a splice
    variant is "unable to assess" and anything else is "not applicable" with the reason stated (contract 3.1)."""
    if splicing_evidence:
        return {"classification": "likely_eligible", "criteria_met": ["the variant is reported to change splicing"],
                "note": "an ASO shown to correct this very variant would make it 'eligible' (N1C)"}
    if variant_class == "splice":
        return {"classification": "unable_to_assess", "unassessable_reason": [NO_SPLICE],
                "criteria_met": ["the variant lies at a splice site"]}
    return {"classification": "not_applicable",
            "failed_criterion": "no evidence that this variant changes splicing; this is a limit of our inputs, "
                                "not evidence that splicing is unaffected",
            "unassessable_reason": []}


# ------------------------------------------------------------------ 3.2 canonical exon skipping

def exon_skipping(tr, number: int, mechanism: str | None) -> dict:
    """Judge the exon that carries the variant (N1C judges exons, not variants)."""
    exons = coding_exons(tr)
    out: dict = {"classification": None, "criteria_met": [], "exceptions": [], "unassessable_reason": [],
                 "coding_exons": len(exons), "exon_number": number}
    here = next((e for e in exons if e["number"] == number), None)
    if here is None:
        return {**out, "classification": "unable_to_assess",
                "unassessable_reason": ["the variant does not lie in a coding exon"]}
    share = round((here["coding_nt"] / 3) / tr.protein_length * 100, 1)
    out["exon_share_percent"] = share
    out["junction_codon"] = junction_codon(tr, exons, number)

    def fail(why, cls="not_eligible"):
        return {**out, "classification": cls, "failed_criterion": why}

    if len(exons) == 1:
        return fail("the gene has exactly one coding exon, so no exon can be skipped")
    if number == exons[0]["number"]:
        return fail("this is the first coding exon: skipping it would remove the start codon",
                    ) | {"exceptions": ["N1C: theoretically possible if a nearby in-frame start codon exists"]}
    if number == exons[-1]["number"]:
        return fail("this is the last coding exon: skipping it would remove the stop codon")
    if not here["in_frame"]:
        if mechanism in TOXIC:
            out["exceptions"].append("N1C: for gain-of-function or dominant-negative variants an out-of-frame exon "
                                     "may be skipped to lower transcript levels - that is a knockdown idea, judged "
                                     "under RNA knockdown")
            return {**out, "classification": "unlikely_eligible",
                    "failed_criterion": f"exon coding length {here['coding_nt']} nt is not a multiple of 3, so "
                                        "skipping it disrupts the reading frame"}
        out["exceptions"] = [
            "N1C: consecutive out-of-frame exons may be skipped together to keep the reading frame (designing such "
            "an ASO is itself difficult)",
            "N1C: an out-of-frame exon may be skipped when a whole out-of-frame exon is already deleted",
        ]
        return fail(f"exon coding length {here['coding_nt']} nt is not a multiple of 3, so skipping it disrupts the "
                    "reading frame (restoring the frame is the aim for loss-of-function variants)")
    out["criteria_met"].append(f"an internal coding exon (exon {number} of {len(exons)} coding exons)")
    out["criteria_met"].append(f"in frame ({here['coding_nt']} nt, a multiple of 3)")
    if out["junction_codon"] in STOPS:
        out["exceptions"].append("N1C: theoretically possible in the penultimate exon if the protein keeps some "
                                 "function (unlikely eligible)")
        return fail(f"joining the neighbouring exons forms the stop codon {out['junction_codon']} at the new "
                    "exon-exon boundary")
    if out["junction_codon"]:
        out["criteria_met"].append(f"the new exon-exon boundary codes {out['junction_codon']}, not a stop codon")
    if share > DOMAIN_SHARE_LIMIT:
        return {**out, "classification": "unlikely_eligible",
                "failed_criterion": f"the exon codes {share}% of the protein, more than 10%; N1C expects functional "
                                    "evidence before such an exon is considered skippable",
                "unassessable_reason": [NO_DOMAIN, NO_NATURAL]}
    out["criteria_met"].append(f"the exon codes {share}% of the protein, within the 10% limit")
    out["unassessable_reason"] = [NO_DOMAIN, NO_NATURAL]
    out["classification"] = "unable_to_assess"
    out["classification_ceiling"] = "likely_eligible"
    return out


# ------------------------------------------------------------------ 3.3 RNA knockdown

def knockdown(mechanism: str | None, copies_affected: int | None, zygosity: str | None,
              allele_specific: bool) -> dict:
    out: dict = {"allele_specific": allele_specific, "criteria_met": [], "unassessable_reason": []}
    if mechanism is None:
        return {**out, "classification": "unable_to_assess", "unassessable_reason": [NO_MECHANISM]}
    if mechanism in LOF:
        return {**out, "classification": "not_applicable",
                "failed_criterion": "the mechanism is loss of function, so knocking the transcript down would "
                                    "reduce the remaining function further"}
    out["criteria_met"].append(f"the mechanism ({mechanism.replace('_', ' ')}) is one knockdown is meant for")
    if not allele_specific:
        return {**out, "classification": "unable_to_assess", "unassessable_reason": [NO_DOSAGE],
                "note": "N1C also asks whether the disease caused by losing one copy is milder than the disease "
                        "caused by this variant - a clinical comparison, outside this section"}
    if zygosity in ("homozygous", "hemizygous") or (copies_affected or 0) >= 2:
        return {**out, "classification": "not_applicable",
                "failed_criterion": f"{zygosity or 'this genotype'} leaves no normal allele to spare, so an "
                                    "allele-specific knockdown has nothing to preserve"}
    out["criteria_met"].append("one normal allele remains, which an allele-specific approach would preserve")
    out["target"] = "the variant itself"
    out["classification"] = "theoretically_possible"
    out["note"] = ("targeting a SNP on the same allele instead would need haplotype information: " + NO_PHASING +
                   ". An ASO already developed for another variant in this gene does not make it usable here; "
                   "N1C still calls the gene eligible, but a new ASO would have to be designed")
    return out


# ------------------------------------------------------------------ 3.4 upregulation from the WT allele

def upregulation(mechanism: str | None, copies_affected: int | None, zygosity: str | None) -> dict:
    note = ("N1C defines no eligibility classes for this approach: \"Assessment strategies are provided for "
            "upregulation from the WT allele, but classifications toward eligibility are not defined because this "
            "area of ASO therapeutics is less established to date.\"")
    out: dict = {"classification": "not_graded", "note": note, "criteria_met": [], "unassessable_reason": []}
    if mechanism is None:
        return {**out, "classification": "unable_to_assess", "unassessable_reason": [NO_MECHANISM],
                "premises_met": False}
    if zygosity in ("homozygous", "hemizygous") or (copies_affected or 0) >= 2:
        return {**out, "premises_met": False,
                "failed_criterion": f"{zygosity or 'this genotype'} leaves no normal copy to raise"}
    if mechanism not in LOF:
        return {**out, "premises_met": False,
                "failed_criterion": f"the mechanism ({mechanism.replace('_', ' ')}) is not a shortage of product, "
                                    "so making more from the normal copy does not address it"}
    out["premises_met"] = True
    out["criteria_met"] = ["one normal copy remains", f"the mechanism ({mechanism.replace('_', ' ')}) is a shortage "
                           "of gene product"]
    out["unassessable_reason"] = ["no upregulation target looked up for this gene (uORF, NMD exon or antisense "
                                  "transcript: N1C Table S2 not read yet)"]
    return out


# ------------------------------------------------------------------ 3.5 gene replacement (AAV)

def gene_replacement(cds_nt: int | None, mechanism: str | None) -> dict:
    out: dict = {"criteria_met": [], "unassessable_reason": [], "cds_nt": cds_nt}
    if cds_nt is not None:
        out["cds_fits_aav"] = cds_nt <= AAV_CAPACITY_NT
        if not out["cds_fits_aav"]:
            return {**out, "classification": "not_applicable", "used_mechanism": False,
                    "failed_criterion": f"the coding sequence is {cds_nt} nt, beyond the roughly 4.7 kb an AAV "
                                        f"vector carries (measured ceiling {AAV_MEASURED_NT} nt, Wu 2010), so the "
                                        "full-length cDNA does not fit in a single vector"}
    if mechanism is None:
        return {**out, "classification": "unable_to_assess", "unassessable_reason": [NO_MECHANISM],
                "used_mechanism": True}
    if mechanism in TOXIC:
        return {**out, "classification": "not_applicable", "used_mechanism": True,
                "failed_criterion": f"the mechanism is {mechanism.replace('_', ' ')}: adding a normal copy does not "
                                    "remove the abnormal protein's effect"}
    out["used_mechanism"] = True
    out["criteria_met"] = [f"the mechanism ({mechanism.replace('_', ' ')}) is one a normal copy could address",
                           f"the coding sequence is {cds_nt} nt, within the roughly 4.7 kb capacity"]
    out["classification"] = "theoretically_possible"
    out["note"] = ("only the coding sequence is counted here; whether the promoter, polyA and other elements also "
                   "fit depends on the vector design, which is not sized in this report")
    return out


# ------------------------------------------------------------------ 3.6 base and prime editing

_SNV = re.compile(r"c\.-?\*?\d+([+-]\d+)?([ACGT])>([ACGT])$", re.I)
_TRANSITION = {("G", "A"), ("A", "G"), ("C", "T"), ("T", "C")}
_SMALL = re.compile(r"c\.[-*\d_+]+(del|dup|ins|delins)", re.I)


def editing(cdna: str) -> dict:
    """Which editor could in principle revert this change, from the HGVS alone (contract 3.6)."""
    c = (cdna or "").strip()
    m = _SNV.search(c)
    if m:
        ref, alt = m.group(2).upper(), m.group(3).upper()
        if (ref, alt) in _TRANSITION:
            which = "an adenine base editor (A>G on one strand)" if (ref, alt) in (("G", "A"), ("C", "T")) \
                else "a cytosine base editor (C>T on one strand)"
            return {"classification": "theoretically_possible", "editor": "base_editing",
                    "reason": f"{ref}>{alt} is a transition, which {which} could revert",
                    "note": NO_PAM, "unassessable_reason": [NO_PAM]}
        return {"classification": "theoretically_possible", "editor": "prime_editing",
                "reason": f"{ref}>{alt} is a transversion, which base editors do not make; only prime editing "
                          "could revert it",
                "note": NO_PAM, "unassessable_reason": [NO_PAM]}
    m = _SMALL.search(c)
    if m:
        span = _span(c)
        kind = {"del": "deletion", "dup": "insertion (duplication)", "ins": "insertion",
                "delins": "insertion-deletion"}[m.group(1).lower()]
        if span is not None and span > 100:
            why = (f"a large {kind} of about {span} nt: neither base nor prime editing restores a segment of "
                   "this size")
            return {"classification": "not_applicable", "editor": None, "reason": why,
                    "failed_criterion": why, "unassessable_reason": []}
        return {"classification": "theoretically_possible", "editor": "prime_editing",
                "reason": f"a small {kind}, which base editors cannot make; only prime editing could revert it",
                "note": NO_PAM, "unassessable_reason": [NO_PAM]}
    return {"classification": "unable_to_assess", "editor": None,
            "reason": "the change could not be read from the HGVS name",
            "unassessable_reason": ["variant type not recognised"]}


def _span(c: str) -> int | None:
    nums = [int(x) for x in re.findall(r"(?<![-+*\d])(\d+)_(?:\d+)", c)] or None
    m = re.search(r"c\.(\d+)_(\d+)", c)
    return int(m.group(2)) - int(m.group(1)) + 1 if m else (None if nums is None else None)


# ------------------------------------------------------------------ X inactivation / mosaicism

def x_inactivation_caveat(chromosome: str | None, sex: str | None, zygosity: str | None,
                          stated_skew: str | None) -> str | None:
    """The sentence to add when how much normal product is made depends on X inactivation (decision 2026-11-05)."""
    if stated_skew or str(chromosome or "").upper() != "X":
        return None
    if zygosity != "heterozygous" or (sex or "").lower() == "male":
        return None
    return ("unable to assess how much normal product is made: this depends on X inactivation (or the degree of "
            "mosaicism), which the case does not report")


# ------------------------------------------------------------------ records and wording

GRADED = {"eligible", "likely_eligible", "unlikely_eligible", "not_eligible"}
WORDS = {
    "eligible": "eligible by the N1C criteria (functional evidence supports this approach)",
    "likely_eligible": "likely eligible: the molecular criteria are met, with no functional evidence either way",
    "unlikely_eligible": "unlikely eligible: the molecular criteria argue against it, with no functional evidence "
                         "directly against it",
    "not_eligible": "not eligible",
    "unable_to_assess": "cannot be assessed from the information available",
    "not_applicable": "does not apply to this variant",
    "theoretically_possible": "theoretically possible on molecular grounds alone",
    "not_graded": "no eligibility grade exists for this approach",
}
LABEL = {"aso_splice_correction": "ASO splice correction", "aso_exon_skipping": "ASO exon skipping",
         "rna_knockdown": "RNA knockdown", "wt_upregulation": "upregulation from the normal allele",
         "gene_replacement": "gene replacement (AAV)", "base_or_prime_editing": "base or prime editing"}


def sentence(modality: str, res: dict) -> str:
    """The code's own wording: what the verdict is and why. Never stronger than the inputs."""
    head = f"{LABEL[modality]}: {WORDS[res['classification']]}"
    if res.get("failed_criterion"):
        head += f" - {res['failed_criterion']}"
    reasons = res.get("unassessable_reason") or []
    if res["classification"] == "unable_to_assess" and reasons:
        head += " - missing: " + "; ".join(reasons)
    return head + "."


def record(modality: str, res: dict, branch: str) -> dict:
    """One ledger row per branch and modality (contract section 4), with the four fields step 4 ranks on."""
    reasons = res.get("unassessable_reason") or []
    return {"section": SECTION, "modality": modality, "label": LABEL[modality], "applies_to": [branch],
            "action_key": None, "requirements": [], "evidence_ids": [],
            "classification": res["classification"], "conclusion": sentence(modality, res),
            "criteria_met": res.get("criteria_met") or [], "failed_criterion": res.get("failed_criterion"),
            "exceptions": res.get("exceptions") or [], "unassessable_reason": reasons,
            "premises_complete": not reasons,
            "human_precedent": res.get("human_precedent"),
            "approved_or_in_trial": res.get("approved_or_in_trial"),
            "see_also": res.get("see_also") or [], "note": res.get("note"),
            "facts": {k: v for k, v in res.items() if k in ("exon_number", "exon_share_percent", "junction_codon",
                                                            "coding_exons", "cds_nt", "cds_fits_aav", "editor",
                                                            "allele_specific", "target", "premises_met",
                                                            "classification_ceiling", "reason",
                                                            "used_mechanism")}}


# ------------------------------------------------------------------ mechanism, from GeneReviews only

MECH_PROMPT_VERSION = "3d-mech-v1"
MECH_SECTIONS = ("Molecular Genetics / Molecular Pathogenesis", "Molecular Genetics",
                 "Clinical Characteristics / Genotype-Phenotype Correlations")
MECH_SYSTEM = """You read one passage of a GeneReviews chapter and report how variants of the kind described cause
the disease. Use only this passage. Copy the quote character for character from it.
Answer with one of these mechanism words, or "not_stated" when the passage does not say:
  loss_of_function     less functional product is made or the product does not work
  haploinsufficiency   one working copy is not enough (the passage says so)
  gain_of_function     the product acquires a new or excessive activity
  dominant_negative    the abnormal product interferes with the product of the normal copy
Return only JSON: {"mechanism": "<word>", "quote": "<the sentence from the passage that says it, or empty>",
 "for_variant_kind": "<the words in the passage naming which variants this applies to, or empty>"}"""


# A passage that only guesses at the mechanism is not a source for it (2026-11-06: a GeneReviews table cell read
# "COL1A1 c.934C>T Unknown; possible dominant-negative activity", and that was taken as dominant-negative).
HEDGES = re.compile(r"\b(unknown|unclear|uncertain|possible|possibly|may|might|could|putative|presumed|presumably|"
                    r"suspected|hypothesi[sz]ed|not (?:yet )?(?:known|established|determined)|remains to be|"
                    r"likely|probable|probably|appears? to|thought to|proposed)\b", re.I)
NO_FIRM_MECHANISM = ("the GeneReviews passage only suggests a mechanism rather than stating one "
                     "(no other mechanism source is connected)")


def hedged(quote: str) -> bool:
    """Does this quote hedge instead of stating the mechanism?"""
    return bool(HEDGES.search(quote or ""))


def mechanism_of(gene: str, nbks: list[str], variant_class: str | None, *, use_cache: bool = True) -> dict:
    """{mechanism, quote, nbk, section, llm} from the archived GeneReviews chapter, or mechanism None.

    No other source is connected (decision 2026-11-05), and the LLM may not infer a mechanism that the passage
    does not state: a quote that is not in the passage, or "not_stated", leaves the mechanism None.
    """
    from aitx.disease import extract as X
    from aitx.evidence import genereviews as GR
    from aitx.evidence import ledger as LG
    rejected = []
    for nbk in nbks:
        for sec in MECH_SECTIONS:
            text = GR.section_text(nbk, sec)
            if not text:
                continue
            user = (f"Gene: {gene}\nVariant kind in this patient: {variant_class or 'not stated'}\n"
                    f"Chapter {nbk}, section {sec}:\n{text[:12000]}")
            r = X._cached_chat([{"role": "system", "content": MECH_SYSTEM}, {"role": "user", "content": user}], 0,
                               use_cache, prompt_version=MECH_PROMPT_VERSION)
            got = X._parse(r)["parsed"]
            mech, quote = got.get("mechanism"), str(got.get("quote") or "")
            llm = {"llm": X.llm.config()["model"], "served_model": r.get("served_model"),
                   "prompt_version": MECH_PROMPT_VERSION}
            if mech in LOF + TOXIC and quote and LG.quote_in(quote, text) and hedged(quote):
                rejected.append({"nbk": nbk, "section": sec, "mechanism": mech, "quote": quote,
                                 "why": NO_FIRM_MECHANISM})
                continue
            if mech in LOF + TOXIC and quote and LG.quote_in(quote, text):
                return {"mechanism": mech, "quote": quote, "nbk": nbk, "section": sec, "source_text": text,
                        "for_variant_kind": str(got.get("for_variant_kind") or ""), "llm": llm}
    return {"mechanism": None, "quote": None, "nbk": None, "section": None, "source_text": None, "llm": None,
            "rejected": rejected or None}


# ------------------------------------------------------------------ the step: one set of records per branch

def add_bespoke(led, case: dict, step1: dict, step2: dict, *, use_cache: bool = True) -> None:
    """3d for every diagnosis branch: six modalities, each with a verdict, its reason and its evidence."""
    import time

    from aitx.evidence import established as E
    from aitx.evidence import ledger as LG
    from aitx.variant.transcript import fetch_transcript

    pf = E.facts(step1, step2)
    earlier = {a.get("action_key"): a for a in led.actions if a.get("action_key")}
    for b in [b for b in led.branches if b.get("diagnosis")]:
        bid, gene = b["id"], b.get("gene")
        v = next((x for x in step1["variants"] if x["gene"] == gene), None) or (step1["variants"] or [{}])[0]
        nbks = [ch["nbk"] for ch in (step2.get("genereviews") or {}).get(gene, [])]
        mech = mechanism_of(gene, nbks, v.get("variant_class"), use_cache=use_cache)
        led.bespoke_mechanism[bid] = {k: mech[k] for k in ("mechanism", "quote", "nbk", "section", "llm",
                                                           "for_variant_kind") if k in mech}
        mech_ev = None
        if mech["mechanism"]:
            mech_ev = led.add(LG.sourced(
                f"{gene}: the disease mechanism is {mech['mechanism'].replace('_', ' ')}", SECTION, [bid],
                {"type": "nbk", "id": mech["nbk"], "url": f"https://www.ncbi.nlm.nih.gov/books/{mech['nbk']}/",
                 "section": mech["section"]}, mech["quote"], mech["source_text"], int(time.time()),
                produced_by=mech["llm"], retrieved_by="3d genereviews"))
        else:
            led.note_missing("disease mechanism", f"{gene} bespoke therapies", NO_MECHANISM, "3d")

        tr = None
        if v.get("transcript"):
            try:
                tr = fetch_transcript(v["transcript"])
            except Exception as e:                                  # noqa: BLE001 - recorded, not fatal
                led.bespoke_mechanism[bid]["transcript_error"] = f"{type(e).__name__}: {e}"[:200]
        cds_nt = (tr.coding_length if tr else None)
        caveat = x_inactivation_caveat(step1.get("chromosome") or _chrom(v), pf.get("sex"), v.get("zygosity"),
                                       _stated_skew(step2))
        results = {
            "aso_splice_correction": splice_correction(v.get("variant_class")),
            "aso_exon_skipping": (_skip_or_frame_kept(v, tr, mech["mechanism"]) if tr and
                                  (v.get("exon") or {}).get("number") else
                                  {"classification": "unable_to_assess",
                                   "unassessable_reason": ["the transcript or the variant's exon is not known"]}),
            "rna_knockdown": _knockdown_both(mech["mechanism"], v, caveat),
            "wt_upregulation": _with_caveat(upregulation(mech["mechanism"], (v.get("allelic_state") or {})
                                                         .get("copies_affected"), v.get("zygosity")), caveat),
            "gene_replacement": gene_replacement(cds_nt, mech["mechanism"]),
            "base_or_prime_editing": editing(v.get("variant_cdna") or ""),
        }
        for modality, res in results.items():
            rec = record(modality, res, bid)
            rec["evidence_ids"] = [mech_ev["id"]] if mech_ev and modality in _NEEDS_MECHANISM else []
            rec["approved_or_in_trial"] = _cross_refs(earlier, led, bid)
            led.actions.append(rec)
            for why in rec["unassessable_reason"]:
                led.bespoke_unassessable.append({"branch": bid, "modality": modality, "reason": why})
        led.sections_status[SECTION] = "searched"


_NEEDS_MECHANISM = ("rna_knockdown", "wt_upregulation", "gene_replacement")


def _skip_or_frame_kept(v: dict, tr, mechanism: str | None) -> dict:
    """A deletion that already keeps the reading frame has nothing for exon skipping to restore, whatever the
    skipped exon's own frame would be (contract 3.2)."""
    if (v.get("retranslation") or {}).get("same_frame_after_change") and "deletion" in (v.get("variant_class") or ""):
        return {"classification": "not_applicable", "criteria_met": [], "unassessable_reason": [],
                "failed_criterion": "the deletion already keeps the reading frame, so there is no frame for exon "
                                    "skipping to restore",
                "exon_number": (v.get("exon") or {}).get("number")}
    return exon_skipping(tr, (v.get("exon") or {}).get("number"), mechanism)


def _knockdown_both(mech: str | None, v: dict, caveat: str | None) -> dict:
    """Allele-specific is reported when it is the one that can apply; otherwise the total-knockdown verdict."""
    copies = (v.get("allelic_state") or {}).get("copies_affected")
    spec = knockdown(mech, copies, v.get("zygosity"), allele_specific=True)
    total = knockdown(mech, copies, v.get("zygosity"), allele_specific=False)
    best = spec if spec["classification"] == "theoretically_possible" else total
    best = dict(best)
    best["note"] = " ".join(x for x in (best.get("note"), f"total knockdown: {total['classification']}"
                                        if best is not total else None) if x)
    return _with_caveat(best, caveat)


def _with_caveat(res: dict, caveat: str | None) -> dict:
    """X inactivation / mosaicism decides how much normal product there is, so a verdict that depends on the
    normal copy becomes unable_to_assess (decision 2026-11-05)."""
    if not caveat or res["classification"] not in ("theoretically_possible", "not_graded"):
        return res
    out = dict(res, classification="unable_to_assess")
    out["unassessable_reason"] = list(res.get("unassessable_reason") or []) + [caveat]
    return out


def _chrom(v: dict) -> str | None:
    loc = str((v.get("gene_location") or v.get("chromosome") or "") or "")
    m = re.match(r"([0-9XYxy]+)", loc)
    return m.group(1).upper() if m else None


def _stated_skew(step2: dict) -> str | None:
    f = (step2.get("patient_facts") or {})
    for k in ("x_inactivation", "mosaicism"):
        if (f.get(k) or {}).get("quote"):
            return f[k]["quote"]
    return None


def _cross_refs(earlier: dict, led, bid: str) -> list[dict]:
    """Approved (3a) or recruiting (3b) products of the same kind, so 3d never repeats them as its own action."""
    out = []
    for a in led.actions:
        if a["section"] in ("existing_targeted_therapies", "clinical_trial_eligibility") and bid in a.get("applies_to", []):
            out.append({"section": a["section"], "label": a.get("label"), "action_key": a.get("action_key"),
                        "nct": a.get("nct")})
    return out[:10]


# ------------------------------------------------------------------ checks (contract section 4)

_STRONG = re.compile(r"\b(recommended|effective|efficacious|proven|cures?|will work)\b", re.I)


def problems(actions: list[dict], branches: list[str]) -> list[str]:
    """What is wrong with the 3d rows of a ledger (empty list: nothing)."""
    bad, mine = [], [a for a in actions if a.get("section") == SECTION]
    for b in branches:
        have = {a["modality"] for a in mine if b in a.get("applies_to", [])}
        missing = [m for m in MODALITIES if m not in have]
        if missing:
            bad.append(f"{b}: no judgement for {', '.join(missing)}")
        twice = [m for m in MODALITIES if sum(1 for a in mine if a.get("modality") == m
                                              and b in a.get("applies_to", [])) > 1]
        if twice:
            bad.append(f"{b}: {', '.join(twice)} judged more than once")
    for a in mine:
        key = f"{a.get('modality')} ({a.get('applies_to')})"
        if a.get("classification") not in GRADED | {"unable_to_assess", "not_applicable", "theoretically_possible",
                                                    "not_graded"}:
            bad.append(f"{key}: unknown classification {a.get('classification')!r}")
        if a["modality"] not in ("aso_splice_correction", "aso_exon_skipping", "rna_knockdown") \
                and a.get("classification") in GRADED:
            bad.append(f"{key}: uses an N1C eligibility grade, which is defined only for the ASO approaches")
        if a.get("classification") == "unable_to_assess" and not a.get("unassessable_reason"):
            bad.append(f"{key}: 'unable to assess' without saying what is missing")
        if a.get("classification") in ("not_applicable", "not_eligible", "unlikely_eligible") \
                and not a.get("failed_criterion"):
            bad.append(f"{key}: a negative verdict without the criterion it failed")
        if _STRONG.search(a.get("conclusion") or ""):
            bad.append(f"{key}: conclusion claims efficacy")
        if a["modality"] in _NEEDS_MECHANISM and a.get("classification") != "unable_to_assess" \
                and (a.get("facts") or {}).get("used_mechanism") and not a.get("evidence_ids"):
            bad.append(f"{key}: rests on a mechanism but cites no evidence for it")
        if a.get("action_key"):
            bad.append(f"{key}: 3d rows are modality judgements, not drug actions (action_key set)")
    return bad
