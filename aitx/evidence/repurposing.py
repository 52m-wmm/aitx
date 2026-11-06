"""Step 3e: drug repurposing (Tier 3, hypothetical layer). Contract: docs/step3e_contract.md.

One chain per candidate, with a resolvable database record at every hop:

    the patient's gene -> a Reactome pathway it takes part in
      -> a drug acting on that target (or on another member of the pathway): Open Targets, ChEMBL
        -> the drug's direction against the patient's defect: ChEMBL action_type / Open Targets mechanism
          -> in vitro or animal evidence in this disease: PubMed

Everything in this module is deterministic. The only LLM call in 3e is the extraction of an evidence sentence
from a paper, which the caller passes in; a candidate without one is "target_rationale_only".

The direction rule is the section's safety: Open Targets lists 31 drug candidates for GRIN2B, nearly all NMDA
antagonists, while the practice patient's variant is loss of function. An antagonist there would be the worst
kind of mistake this project can make, so direction is decided by code from a controlled vocabulary - never by
the LLM - and a candidate whose direction is unknown is not written at all.
"""
from __future__ import annotations

import re

SECTION = "drug_repurposing"
N_CANDIDATES = 10               # per branch, as in 3b's per-criterion cap
N_RATIONALE_ONLY = 3            # per branch, of those with no experimental evidence (decision 2026-11-06)

# ---- direction vocabulary (ChEMBL action_type, then the mechanism text). Longest phrases first, so that
# "negative allosteric modulator" is never read as the bare "modulator".
DOWN_WORDS = ("negative allosteric modulator", "negative modulator", "inverse agonist", "antagonist", "inhibitor",
              "blocker", "degrader", "disrupting agent", "suppressor", "downregulator")
UP_WORDS = ("positive allosteric modulator", "positive modulator", "partial agonist", "agonist", "activator",
            "opener", "potentiator", "chaperone", "stabiliser", "stabilizer", "upregulator", "enhancer")
PARTIAL_WORDS = ("partial agonist",)
NEEDED = {"loss_of_function": "up", "haploinsufficiency": "up", "gain_of_function": "down",
          "dominant_negative": None}

NO_MECHANISM = ("no disease mechanism from a source (step 3d): without it the direction a drug would have to act "
                "in cannot be decided, so no candidate is proposed")
DN_NOTE = ("the mechanism is dominant negative: lowering the abnormal product is a bespoke-therapy question (3d), "
           "so this section proposes nothing")


def needed_direction(mechanism: str | None) -> str | None:
    """Which way a drug must act for this mechanism, or None when 3e must not propose anything."""
    return NEEDED.get(mechanism or "")


def direction_of(action_type: str | None, mechanism_text: str | None = "") -> str | None:
    """"up" / "down" / "partial_up" from the record's own words, or None when it does not say which way."""
    for source in (action_type or "", mechanism_text or ""):
        s = source.lower()
        for w in PARTIAL_WORDS:
            if w in s:
                return "partial_up"
        down = min((s.index(w) for w in DOWN_WORDS if w in s), default=None)
        up = min((s.index(w) for w in UP_WORDS if w in s), default=None)
        if down is not None and (up is None or down <= up):
            return "down"
        if up is not None:
            return "up"
    return None


def direction_ok(mechanism: str | None, direction: str | None) -> bool:
    """Does this direction address this mechanism? A partial agonist counts only where more activity is wanted."""
    need = needed_direction(mechanism)
    if need is None or direction is None:
        return False
    return direction == need or (need == "up" and direction == "partial_up")


def gate(mechanism: str | None) -> dict:
    """Whether 3e may produce anything for this branch at all (contract 3.1)."""
    if mechanism is None:
        return {"produce": False, "reason": NO_MECHANISM, "needed": None}
    need = needed_direction(mechanism)
    if need is None:
        return {"produce": False, "reason": DN_NOTE, "needed": None}
    return {"produce": True, "reason": None, "needed": need}


# ---- ChEMBL target levels: a mechanism may be recorded on the subunit, the complex or the family group
LEVELS = {"SINGLE PROTEIN": "subunit", "PROTEIN COMPLEX": "complex", "PROTEIN COMPLEX GROUP": "family_group",
          "PROTEIN FAMILY": "family_group", "SELECTIVITY GROUP": "family_group"}
SELECTIVITY_CAVEAT = "selectivity for this gene's subunit is unknown"


def target_level(target_type: str | None) -> str | None:
    return LEVELS.get((target_type or "").upper())


# ---- ranking: the more complete the evidence chain, the higher
# experimental evidence of either kind outranks none; within a tier the species is only a tiebreak, because
# neither a cell nor a mouse is a human (2026-11-06)
_EVIDENCE_RANK = {"in_vitro": 0, "animal_model": 0, "target_rationale_only": 1}
_SPECIES_RANK = {"animal_model": 0, "in_vitro": 1}
_LEVEL_RANK = {"subunit": 0, "complex": 1, "family_group": 2}
_STAGE_RANK = {"APPROVAL": 0, "PHASE_4": 1, "PHASE_3": 2, "PHASE_2": 3, "PHASE_1": 4, "PRECLINICAL": 5}
_ROUTE_RANK = {"same_target": 0, "same_pathway": 1}


def rank_key(c: dict):
    """Experimental evidence first, then the target level, then how the candidate was reached, then how far it
    has gone clinically. Direction is a hard filter, not a weight (contract 3.3)."""
    return (_EVIDENCE_RANK.get(c.get("evidence_level"), 2),
            _LEVEL_RANK.get(c.get("target_level"), 3),
            _ROUTE_RANK.get(c.get("route"), 2),
            _SPECIES_RANK.get(c.get("evidence_level"), 2),
            _STAGE_RANK.get(c.get("max_clinical_stage"), 6),
            (c.get("drug") or "").lower())


def pick(candidates: list[dict]) -> tuple[list[dict], list[dict]]:
    """(kept, dropped) under both caps: 10 per branch, of which at most 3 have no experimental evidence."""
    kept, dropped, n_rationale = [], [], 0
    for c in sorted(candidates, key=rank_key):
        only = c.get("evidence_level") == "target_rationale_only"
        if only and n_rationale >= N_RATIONALE_ONLY:
            dropped.append({**c, "why": "over the cap for candidates with no experimental evidence"})
            continue
        if len(kept) >= N_CANDIDATES:
            dropped.append({**c, "why": f"over the cap of {N_CANDIDATES} candidates for this branch"})
            continue
        kept.append(c)
        n_rationale += int(only)
    return kept, dropped


def rows_for_target(candidates: list[dict], symbol: str) -> list[dict]:
    """Keep only the mechanism rows that are about this gene's own target.

    A drug carries one row per mechanism, and the rows may be about quite different targets: acamprosate is an
    NMDA receptor ANTAGONIST in one row and a GABA-A receptor POSITIVE MODULATOR in another. Without this
    filter the GABA-A row would make acamprosate look like an "increase activity" candidate for a GRIN2B
    loss-of-function patient (2026-11-06).
    """
    return [c for c in candidates if symbol.upper() in {str(t).upper() for t in c.get("mechanism_targets") or []}]


def one_direction(rows: list[dict]) -> tuple[str | None, str | None]:
    """(direction, why it is unusable) over a drug's rows for one target: rows pointing both ways are refused."""
    dirs = {direction_of(r.get("action_type"), r.get("mechanism_text")) for r in rows}
    dirs.discard(None)
    if not dirs:
        return None, "the records do not say which way the drug acts on this target"
    ups = {d for d in dirs if d in ("up", "partial_up")}
    if ups and "down" in dirs:
        return None, "the records point both ways for this target (both an increase and a decrease)"
    if len(ups) == 2:                       # a full and a partial agonist: the weaker claim stands
        return "partial_up", None
    return next(iter(dirs)), None


def level_from_rows(rows: list[dict], symbol: str, subunit_molecules: set[str] | None = None) -> str:
    """At which level this drug's mechanism is actually recorded (contract 2, lesson 1).

    A mechanism row that names only this gene is subunit level. One that names several subunits is a claim about
    the receptor family, whatever level the gene's own ChEMBL target records sit at: the selectivity for this
    subunit is unknown (2026-11-06: all three GRIN2B candidates list seven GRIN targets). A drug that also has a
    mechanism record on the subunit's own ChEMBL target counts as subunit level.
    """
    if subunit_molecules and any(r.get("chembl_id") in subunit_molecules for r in rows):
        return "subunit"
    for r in rows:
        targets = {str(t).upper() for t in r.get("mechanism_targets") or []}
        if targets == {symbol.upper()}:
            return "subunit"
    return "family_group"


# ---- boundaries with the other sections

def drug_key(c: dict) -> str:
    return f"drug:chembl:{c['chembl_id']}" if c.get("chembl_id") else f"drug:name:{(c.get('drug') or '').lower()}"


def elsewhere(c: dict, earlier: dict, aliases: list[dict]) -> dict | None:
    """The 3a / 3b / 3c record that already carries this drug, or None (no action in two sections)."""
    if drug_key(c) in earlier:
        return earlier[drug_key(c)]
    name = (c.get("drug") or "").strip().lower()
    for key, rec in earlier.items():
        if name and name == str(rec.get("label") or "").strip().lower():
            return rec
    for a in aliases or []:
        if name and name in str(a.get("quote") or "").lower():
            return a
    return None


def belongs_to_3c(c: dict) -> bool:
    """A human treated with this drug for this disease makes it a precedent, which is 3c's subject, not 3e's."""
    return bool(c.get("human_precedent"))


# ---- wording (code-made, never stronger than the records)

_ACTION_WORDS = {"up": "increases the activity of", "down": "reduces the activity of",
                 "partial_up": "acts as a partial agonist at"}


def sentence(c: dict) -> str:
    """The one sentence the report may carry for a candidate."""
    how = _ACTION_WORDS.get(c.get("direction"), "acts on")
    where = c.get("target") or "the target"
    via = ("" if c.get("route") == "same_target" else
           f", reached through the pathway {c.get('pathway') or '?'} in which {c.get('member_target') or where} "
           f"takes part")
    out = f"A hypothesis only: {c['drug']} {how} {where}{via}"
    if c.get("target_level") == "family_group":
        out += f" ({SELECTIVITY_CAVEAT})"
    if c.get("evidence_level") == "target_rationale_only":
        return out + ". There is no experimental evidence in this disease and no human precedent."
    what = {"in_vitro": "in cells", "animal_model": "in an animal model"}.get(c.get("evidence_level"), "")
    quote = f' "{c["evidence_quote"]}"' if c.get("evidence_quote") else ""
    pmids = f" (PMID {', '.join(c.get('pmids') or [])})" if c.get("pmids") else ""
    return (out + f". Reported {what}:{quote}{pmids}. No human has been treated with it for this disease.")


# ---- ledger rows

def record(c: dict, branch: str) -> dict:
    """One row per candidate. It is a hypothesis about a drug, not a judgement about this patient, so it carries
    no requirement lines and no per-branch status (the ledger's own check skips those for such rows)."""
    return {"section": SECTION, "action_key": drug_key(c), "label": c["drug"], "applies_to": [branch],
            "requirements": [], "status_by_branch": {}, "evidence_ids": c.get("evidence_ids") or [],
            "modality": None, "hypothesis": True,
            "conclusion": sentence(c),
            "route": c.get("route"), "pathway": c.get("pathway"), "member_target": c.get("member_target"),
            "target": c.get("target"), "target_level": c.get("target_level"),
            "direction": c.get("direction"), "action_type": c.get("action_type"),
            # the mechanism the candidate was judged against travels with it: without it there is nothing to
            # match, so the row is marked unmatched and the check refuses it (2026-11-06)
            "mechanism": c.get("mechanism"),
            "direction_match": direction_ok(c.get("mechanism"), c.get("direction")),
            "evidence_level": c.get("evidence_level"), "pmids": c.get("pmids") or [],
            "records": {k: v for k, v in {"chembl_target": c.get("chembl_target"), "chembl_drug": c.get("chembl_id"),
                                          "reactome_pathway": c.get("pathway"),
                                          "open_targets": c.get("ensembl_id")}.items() if v},
            "max_clinical_stage": c.get("max_clinical_stage"),
            "approved_elsewhere": c.get("max_clinical_stage") == "APPROVAL",
            "premises_complete": bool(c.get("chembl_id") and c.get("direction") and c.get("target")),
            "human_precedent": c.get("human_precedent")}


# ---- checks (contract section 4)

_STRONG = re.compile(r"\b(recommended|effective|efficacious|proven|cures?|will work|should be (?:given|tried))\b", re.I)
_DOSE = re.compile(r"\b\d+\s*(?:mg|mcg|µg|g|ml|mg/kg|units?)\b|\bdose\b|\bdosage\b", re.I)


def problems(actions: list[dict], branches: list[str], earlier: dict, searched: dict | None = None) -> list[str]:
    bad, mine = [], [a for a in actions if a.get("section") == SECTION]
    for b in branches:
        if not any(b in a.get("applies_to", []) for a in mine) and not (searched or {}).get(b):
            bad.append(f"{b}: no candidate and no recorded search for this branch")
    for a in mine:
        tag = a.get("label") or a.get("action_key")
        if not a.get("direction") or not a.get("direction_match"):
            bad.append(f"{tag}: direction {a.get('direction')!r} does not address the mechanism, or is unknown")
        if not (a.get("records") or {}).get("chembl_drug"):
            bad.append(f"{tag}: no resolvable drug record id")
        if not a.get("target"):
            bad.append(f"{tag}: no record id for the target hop")
        if a.get("evidence_level") not in ("in_vitro", "animal_model", "target_rationale_only"):
            bad.append(f"{tag}: unknown evidence level {a.get('evidence_level')!r}")
        if a.get("evidence_level") in ("in_vitro", "animal_model") and not a.get("pmids"):
            bad.append(f"{tag}: experimental evidence without a PMID")
        if a.get("human_precedent"):
            bad.append(f"{tag}: has a human precedent, so it belongs in 3c, not here")
        if a.get("action_key") in earlier:
            bad.append(f"{tag}: already in {earlier[a['action_key']].get('section')}")
        if _STRONG.search(a.get("conclusion") or ""):
            bad.append(f"{tag}: conclusion claims efficacy")
        if _DOSE.search(a.get("conclusion") or ""):
            bad.append(f"{tag}: conclusion carries a dose, which has no human basis here")
        if not str(a.get("conclusion") or "").startswith("A hypothesis only:"):
            bad.append(f"{tag}: conclusion is not marked as a hypothesis")
    return bad


# ------------------------------------------------------------------ the three databases (all free, all cached)

OT_GRAPHQL = "https://api.platform.opentargets.org/api/v4/graphql"
REACTOME = "https://reactome.org/ContentService"
CHEMBL = "https://www.ebi.ac.uk/chembl/api/data"

_OT_TARGET = """{target(ensemblId:"%s"){approvedSymbol proteinIds{id source}
 pathways{pathwayId pathway topLevelTerm}
 drugAndClinicalCandidates{count rows{id maxClinicalStage drug{id name drugType maximumClinicalStage
  mechanismsOfAction{rows{mechanismOfAction actionType targets{id approvedSymbol}}}}}}}}"""
_OT_BY_SYMBOL = """{search(queryString:"%s",entityNames:["target"]){hits{id entity name}}}"""


def _ot(query: str, use_cache: bool = True) -> dict:
    from aitx import http
    import json as _json
    r = http.post_json(OT_GRAPHQL, {"query": query}, use_cache=use_cache, timeout=60)
    got = _json.loads(r.text)
    if got.get("errors"):
        raise RuntimeError(f"Open Targets: {got['errors'][0].get('message', '')[:200]}")
    return {"data": got.get("data") or {}, "accessed_at": r.accessed_at}


def ensembl_id(gene: str, use_cache: bool = True) -> str | None:
    """The Ensembl gene id Open Targets knows this symbol by (its own search, so the id is theirs, not ours)."""
    hits = (_ot(_OT_BY_SYMBOL % gene, use_cache)["data"].get("search") or {}).get("hits") or []
    for h in hits:
        if (h.get("name") or "").upper() == gene.upper() and str(h.get("id", "")).startswith("ENSG"):
            return h["id"]
    return next((h["id"] for h in hits if str(h.get("id", "")).startswith("ENSG")), None)


def target_facts(gene: str, use_cache: bool = True) -> dict:
    """{ensembl_id, symbol, uniprot, pathways, candidates, accessed_at} for one gene, or empty when unknown."""
    ens = ensembl_id(gene, use_cache)
    if not ens:
        return {"ensembl_id": None, "symbol": gene, "uniprot": None, "pathways": [], "candidates": [],
                "accessed_at": None, "error": f"Open Targets does not know the symbol {gene}"}
    got = _ot(_OT_TARGET % ens, use_cache)
    t = got["data"].get("target") or {}
    uni = next((p["id"] for p in t.get("proteinIds") or [] if p.get("source") == "uniprot_swissprot"), None)
    cands = []
    for row in ((t.get("drugAndClinicalCandidates") or {}).get("rows") or []):
        d = row.get("drug") or {}
        for m in ((d.get("mechanismsOfAction") or {}).get("rows") or [{}]):
            cands.append({"chembl_id": d.get("id"), "drug": d.get("name"), "drug_type": d.get("drugType"),
                          "max_clinical_stage": d.get("maximumClinicalStage") or row.get("maxClinicalStage"),
                          "mechanism_text": m.get("mechanismOfAction"), "action_type": m.get("actionType"),
                          "mechanism_targets": [x.get("approvedSymbol") for x in m.get("targets") or []]})
    return {"ensembl_id": ens, "symbol": t.get("approvedSymbol") or gene, "uniprot": uni,
            "pathways": t.get("pathways") or [], "candidates": cands, "accessed_at": got["accessed_at"]}


def pathway_members(stid: str, use_cache: bool = True) -> list[str]:
    """Gene symbols taking part in a Reactome pathway (its own participant records)."""
    from aitx import http
    import json as _json
    r = http.get(f"{REACTOME}/data/participants/{stid}/referenceEntities", use_cache=use_cache, timeout=60)
    out: set[str] = set()
    for x in _json.loads(r.text):
        for g in x.get("geneName") or []:
            if re.fullmatch(r"[A-Z][A-Z0-9-]{1,14}", g or ""):
                out.add(g)
    return sorted(out)


def chembl_targets(uniprot: str, use_cache: bool = True) -> list[dict]:
    """ChEMBL target records for one protein, each with the level its mechanisms would be recorded at."""
    from aitx import http
    import json as _json
    r = http.get(f"{CHEMBL}/target.json?target_components__accession={uniprot}&limit=20",
                 use_cache=use_cache, timeout=60)
    out = []
    for t in _json.loads(r.text).get("targets") or []:
        lvl = target_level(t.get("target_type"))
        if lvl:
            out.append({"chembl_target": t.get("target_chembl_id"), "name": t.get("pref_name"),
                        "target_type": t.get("target_type"), "target_level": lvl})
    return sorted(out, key=lambda t: _LEVEL_RANK.get(t["target_level"], 3))


def chembl_mechanisms(target_chembl_id: str, use_cache: bool = True) -> list[dict]:
    """Mechanism records on one ChEMBL target: molecule, action type, wording and reference count."""
    from aitx import http
    import json as _json
    r = http.get(f"{CHEMBL}/mechanism.json?target_chembl_id={target_chembl_id}&limit=200",
                 use_cache=use_cache, timeout=60)
    return [{"chembl_id": m.get("molecule_chembl_id"), "action_type": m.get("action_type"),
             "mechanism_text": m.get("mechanism_of_action"), "direct": bool(m.get("direct_interaction")),
             "n_refs": len(m.get("mechanism_refs") or [])}
            for m in _json.loads(r.text).get("mechanisms") or []]


# ------------------------------------------------------------------ the step

LIT_PROMPT_VERSION = "3e-lit-v1"
LIT_SYSTEM = """You read one article and report whether it tests a named drug in cells or in animals for a named
genetic disease (or for variants in a named gene). Use only this article. Copy the quote character for character.
Return only JSON: {"tested": true|false, "level": "in_vitro"|"animal_model"|"", 
 "quote": "<the sentence reporting what the drug did in that experiment, or empty>",
 "human": true|false, "human_quote": "<the sentence saying a person received it, or empty>"}
"tested" is false for reviews, for articles that only propose the drug, and for human-only reports."""


def add_repurposing(led, case: dict, step1: dict, step2: dict, *, use_cache: bool = True,
                    literature=None) -> None:
    """3e for every diagnosis branch (contract docs/step3e_contract.md).

    `literature(gene, names, drug)` -> {"level", "quote", "pmids", "human_precedent"} or None. The caller passes
    it so this step can run without the LLM; without it every candidate stays "target_rationale_only".
    """
    import time

    from aitx.evidence import established as E
    from aitx.evidence import ledger as LG

    earlier = {a.get("action_key"): a for a in led.actions
               if a.get("action_key") and a["section"] in ("existing_targeted_therapies", "supportive_management",
                                                           "contraindications_precautions",
                                                           "clinical_trial_eligibility", "off_label_expanded_access")}
    for b in [b for b in led.branches if b.get("diagnosis")]:
        bid, gene = b["id"], b.get("gene")
        mech = (led.bespoke_mechanism.get(bid) or {}).get("mechanism")
        g = gate(mech)
        rec: dict = {"mechanism": mech, "needed_direction": g["needed"], "produced": g["produce"]}
        led.repurposing_searches[bid] = rec
        if not g["produce"]:
            rec["reason"] = g["reason"]
            led.add(LG.negative(SECTION, [bid], database="open targets / chembl / reactome", endpoint=OT_GRAPHQL,
                                query=f"not searched for {gene}", queried_at=int(time.time()),
                                n_results=0, response_count=0, claim=g["reason"]))
            led.sections_status[SECTION] = "searched"
            continue
        try:
            facts = target_facts(gene, use_cache)
        except (RuntimeError, ValueError, KeyError) as e:
            rec["error"] = f"{type(e).__name__}: {e}"[:300]
            continue
        rec.update({k: facts.get(k) for k in ("ensembl_id", "uniprot", "error")})
        rec["pathways"] = [{"id": p["pathwayId"], "name": p["pathway"]} for p in facts["pathways"]]
        levels = {t["chembl_target"]: t for t in (chembl_targets(facts["uniprot"], use_cache)
                                                  if facts.get("uniprot") else [])}
        rec["chembl_targets"] = list(levels.values())
        # molecules with a mechanism recorded on the subunit's own ChEMBL target: those are subunit level
        subunit_mol: set[str] = set()
        for t in levels.values():
            if t["target_level"] == "subunit":
                subunit_mol |= {m["chembl_id"] for m in chembl_mechanisms(t["chembl_target"], use_cache)
                                if m.get("chembl_id")}
        rec["subunit_level_molecules"] = len(subunit_mol)
        names = E.disease_names(b, step2)
        # the unit of exclusion is a drug, not a mechanism row: one drug may have several rows, and the ledger's
        # negative record requires every returned record to be listed with a reason (2026-11-06)
        all_drugs: dict[str, list[dict]] = {}
        for row in facts["candidates"]:
            all_drugs.setdefault(row["chembl_id"] or row["drug"], []).append(row)
        by_drug: dict[str, list[dict]] = {}
        for row in rows_for_target(facts["candidates"], facts["symbol"]):
            by_drug.setdefault(row["chembl_id"] or row["drug"], []).append(row)
        cands, excluded = [], []
        for key, rows in all_drugs.items():
            if key not in by_drug:
                excluded.append({**_slim({"drug": rows[0]["drug"], "chembl_id": rows[0]["chembl_id"]}),
                                 "why": f"its mechanism records are about other targets, not {facts['symbol']}"})
        for rows in by_drug.values():
            direction, why = one_direction(rows)
            r0 = rows[0]
            c = {"drug": r0["drug"], "chembl_id": r0["chembl_id"], "target": facts["symbol"],
                 "target_level": level_from_rows(rows, facts["symbol"], subunit_mol),
                 "ensembl_id": facts["ensembl_id"],
                 "chembl_target": next((t for t in levels), None), "direction": direction,
                 "action_type": r0.get("action_type"), "mechanism_text": r0.get("mechanism_text"),
                 "route": "same_target", "mechanism": mech, "evidence_level": "target_rationale_only",
                 "max_clinical_stage": r0.get("max_clinical_stage"), "pmids": []}
            if direction is None:
                excluded.append({**_slim(c), "why": why})
                continue
            if not direction_ok(mech, direction):
                excluded.append({**_slim(c), "why": f"direction {direction} does not address {mech}"})
                continue
            was = elsewhere(c, earlier, [])
            if was:
                excluded.append({**_slim(c), "why": f"already in {was.get('section')}"})
                continue
            if literature:
                lit = literature(gene, names, c["drug"]) or {}
                if lit.get("human_precedent"):
                    c["human_precedent"] = lit["human_precedent"]
                    excluded.append({**_slim(c), "why": "a human has been treated with it: belongs in 3c"})
                    continue
                if lit.get("level"):
                    c.update(evidence_level=lit["level"], evidence_quote=lit.get("quote"),
                             pmids=lit.get("pmids") or [])
            cands.append(c)
        kept, dropped = pick(cands)
        rec.update({"drugs_returned": len(all_drugs), "drugs_for_this_target": len(by_drug),
                    "candidates": len(cands), "kept": len(kept), "excluded": excluded,
                    "dropped": [{"drug": d["drug"], "why": d["why"]} for d in dropped],
                    "queried_at": facts.get("accessed_at")})
        for c in kept:
            led.actions.append(record(c, bid))
        if not kept:
            led.add(LG.negative(SECTION, [bid], database="open targets / chembl", endpoint=OT_GRAPHQL,
                                query=f"target {facts['ensembl_id']} candidates, direction {g['needed']}",
                                queried_at=int(time.time()), n_results=len(all_drugs),
                                response_count=len(all_drugs), excluded=excluded,
                                claim=(f"No repurposing candidate was kept for {facts['symbol']}: "
                                       f"{len(all_drugs)} drugs returned, {len(excluded)} excluded (another "
                                       f"target, direction, duplication or a human precedent).")))
        led.sections_status[SECTION] = "searched"


def _slim(c: dict) -> dict:
    return {k: c.get(k) for k in ("drug", "chembl_id", "direction", "action_type", "max_clinical_stage")}
