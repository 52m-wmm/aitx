"""AlphaFold structure facts for the variant residue (step 1, schema variant-profile-v1.2).

For each variant: find the UniProt entry of the RefSeq protein, download the AlphaFold
predicted structure (cached, with source URL, model version and access time), map the
variant position onto the model, and record
  - pLDDT at the residue (AlphaFold's per-residue confidence, 0-100)
  - relative solvent accessibility (RSA): buried inside the protein or exposed on the surface
  - residues within 8 Å (any heavy atom)
  - for truncating variants, the model range that is lost
These are facts for later steps (e.g. a buried missense change in a confident region is
more likely to destabilize the fold); this module draws no conclusion from them.

RSA method: Shrake & Rupley (1973) numerical SASA, probe 1.4 Å, heavy atoms only, radii
C 1.70 / N 1.55 / O 1.52 / S 1.80 Å (Bondi), 480 points per atom, computed in the context of
the whole model; RSA = residue SASA / theoretical maximum ASA of that amino acid
(Tien et al. 2013, PLoS One 8:e80635). Buried if RSA < 0.20.
AlphaFold models of low-confidence regions (pLDDT < 70) are often extended coils, so their
RSA reads "exposed" whatever the real protein does; such values are flagged unreliable.
"""
from __future__ import annotations

import difflib
import hashlib
import json
import math
import urllib.parse
from pathlib import Path

from aitx import http
from aitx.variant.hgvs import AA1_TO_3

UNIPROT_SEARCH = "https://rest.uniprot.org/uniprotkb/search"
AF_API = "https://alphafold.ebi.ac.uk/api/prediction/{acc}"
STRUCT_DIR = http.CACHE_DIR.parent / "alphafold"

RADII = {"C": 1.70, "N": 1.55, "O": 1.52, "S": 1.80}
PROBE = 1.4
N_POINTS = 480
BURIED_RSA = 0.20
NEIGHBOUR_A = 8.0
RELIABLE_PLDDT = 70.0
# theoretical maximum ASA in Å² (Tien et al. 2013)
MAX_ASA = {"ALA": 129.0, "ARG": 274.0, "ASN": 195.0, "ASP": 193.0, "CYS": 167.0, "GLU": 223.0, "GLN": 225.0,
           "GLY": 104.0, "HIS": 224.0, "ILE": 197.0, "LEU": 201.0, "LYS": 236.0, "MET": 224.0, "PHE": 240.0,
           "PRO": 159.0, "SER": 155.0, "THR": 172.0, "TRP": 285.0, "TYR": 263.0, "VAL": 174.0}
BORDERLINE_RSA = 0.05      # |RSA - threshold| below this is flagged borderline
METHOD = ("Shrake-Rupley SASA (probe 1.4 Å, Bondi radii, 480 points/atom, heavy atoms, whole model) / "
          "theoretical max ASA (Tien et al. 2013); buried if RSA < 0.20. Single-chain model: contacts with "
          "partner proteins, membranes or ligands are not counted. Cross-checked against Biopython "
          "ShrakeRupley on AITX-40002/3/4 (SASA within 6%, same class).")


# ---------------------------------------------------------------- geometry

def parse_pdb(text: str) -> list[dict]:
    atoms = []
    for line in text.splitlines():
        if not line.startswith("ATOM"):
            continue
        el = (line[76:78].strip() or line[12:16].strip()[0]).upper()
        if el == "H":
            continue
        atoms.append({"res": int(line[22:26]), "resname": line[17:20], "name": line[12:16].strip(), "el": el,
                      "xyz": (float(line[30:38]), float(line[38:46]), float(line[46:54])), "b": float(line[60:66])})
    return atoms


def sphere_points(n: int = N_POINTS) -> list[tuple[float, float, float]]:
    """Evenly spread unit vectors (golden-section spiral)."""
    pts, inc = [], math.pi * (3 - math.sqrt(5))
    for k in range(n):
        y = 1 - 2 * (k + 0.5) / n
        r = math.sqrt(1 - y * y)
        pts.append((math.cos(k * inc) * r, y, math.sin(k * inc) * r))
    return pts


def _d2(a, b) -> float:
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2


def residue_sasa(atoms: list[dict], res: int, n_points: int = N_POINTS) -> float:
    """Solvent accessible surface area (Å²) of one residue inside the whole structure."""
    pts = sphere_points(n_points)
    mine = [a for a in atoms if a["res"] == res]
    total = 0.0
    for a in mine:
        ra = RADII.get(a["el"], 1.8) + PROBE
        near = [(b["xyz"], (RADII.get(b["el"], 1.8) + PROBE) ** 2) for b in atoms
                if b is not a and _d2(a["xyz"], b["xyz"]) < (ra + RADII.get(b["el"], 1.8) + PROBE) ** 2]
        free = 0
        for p in pts:
            q = (a["xyz"][0] + ra * p[0], a["xyz"][1] + ra * p[1], a["xyz"][2] + ra * p[2])
            if all(_d2(q, c) >= r2 for c, r2 in near):
                free += 1
        total += 4 * math.pi * ra * ra * free / n_points
    return total


def neighbours(atoms: list[dict], res: int, cutoff: float = NEIGHBOUR_A) -> list[dict]:
    mine = [a for a in atoms if a["res"] == res]
    best: dict[int, tuple[float, str]] = {}
    for b in atoms:
        if b["res"] == res:
            continue
        d = min(math.sqrt(_d2(a["xyz"], b["xyz"])) for a in mine)
        if d <= cutoff and (b["res"] not in best or d < best[b["res"]][0]):
            best[b["res"]] = (d, b["resname"])
    return [{"position": r, "aa": n.capitalize(), "min_distance_A": round(d, 2)} for r, (d, n) in sorted(best.items())]


def plddt_band(v: float) -> str:
    return "very_high" if v > 90 else "confident" if v >= 70 else "low" if v >= 50 else "very_low"


# ---------------------------------------------------------------- mapping

def map_position(refseq: str, model: str, pos: int) -> dict:
    """Map a RefSeq protein position onto the model sequence."""
    if refseq == model:
        return {"model_position": pos, "method": "identical sequence"}
    sm = difflib.SequenceMatcher(None, refseq, model, autojunk=False)
    for a, b, size in sm.get_matching_blocks():
        if a < pos <= a + size:
            flank = min(pos - 1 - a, a + size - pos)
            return {"model_position": b + (pos - a), "method": "identical sequence block",
                    "block": [a + 1, a + size], "flank_aa": flank,
                    "note": f"model is a different isoform; residue lies in an identical block of {size} aa "
                            f"({flank} aa to the nearest block edge)"}
    return {"model_position": None, "method": "not mapped",
            "note": "residue lies in a region that differs between the RefSeq protein and the model"}


# ---------------------------------------------------------------- sources

def uniprot_for(protein_id: str, gene: str) -> tuple[str, str]:
    """(accession, isoform accession) of the reviewed human UniProt entry listing this RefSeq protein."""
    q = urllib.parse.urlencode({"query": f"xref:refseq-{protein_id}", "fields": "accession,xref_refseq", "format": "tsv"})
    rows = http.get(f"{UNIPROT_SEARCH}?{q}").text.strip().splitlines()[1:]
    if not rows:
        q = urllib.parse.urlencode({"query": f"gene_exact:{gene} AND organism_id:9606 AND reviewed:true",
                                    "fields": "accession,xref_refseq", "format": "tsv"})
        rows = http.get(f"{UNIPROT_SEARCH}?{q}").text.strip().splitlines()[1:]
    if not rows:
        raise LookupError(f"no UniProt entry for {protein_id} / {gene}")
    acc, xrefs = (rows[0].split("\t") + [""])[:2]
    iso = acc
    for x in xrefs.split(";"):
        if x.strip().startswith(protein_id) and "[" in x:
            iso = x.split("[")[1].rstrip("]").strip()
    return acc, iso


def alphafold_model(acc: str, iso: str, refseq: str) -> dict:
    """Pick the AlphaFold entry for this protein and make sure its PDB is cached locally."""
    api = AF_API.format(acc=acc)
    entries = json.loads(http.get(api).text)
    seq = lambda e: e.get("uniprotSequence") or e.get("sequence") or ""  # noqa: E731
    pick = (next((e for e in entries if seq(e) == refseq), None)
            or next((e for e in entries if e["uniprotAccession"] in (iso, acc)), None) or entries[0])
    pdb = http.get(pick["pdbUrl"], timeout=120)
    STRUCT_DIR.mkdir(parents=True, exist_ok=True)
    local = STRUCT_DIR / pick["pdbUrl"].rsplit("/", 1)[1]
    if not local.exists() or local.read_text() != pdb.text:
        local.write_text(pdb.text)
    return {"entry": pick, "pdb_text": pdb.text, "api_url": api, "accessed_at": pdb.accessed_at, "local": local,
            "sha256": hashlib.sha256(pdb.text.encode()).hexdigest()}


# ---------------------------------------------------------------- main

def annotate(protein_id: str, gene: str, refseq: str, pos: int | None, lost_from: int | None = None) -> dict:
    """Structure facts for the residue at RefSeq position `pos` (None -> source only).

    lost_from: first RefSeq residue not present in the variant protein (truncating variants)."""
    acc, iso = uniprot_for(protein_id, gene)
    m = alphafold_model(acc, iso, refseq)
    e = m["entry"]
    model_seq = e.get("uniprotSequence") or e.get("sequence") or ""
    out: dict = {"status": "ok", "source": {
        "uniprot": acc, "uniprot_isoform_of_refseq": iso, "alphafold_entry": e["entryId"],
        "alphafold_isoform": e["uniprotAccession"], "model_version": e.get("latestVersion"),
        "model_created": e.get("modelCreatedDate"), "pdb_url": e["pdbUrl"], "api_url": m["api_url"],
        "accessed_at": m["accessed_at"], "local_file": m["local"].name, "sha256": m["sha256"],
        "mean_plddt": e.get("globalMetricValue")},
        "model_length": len(model_seq), "refseq_length": len(refseq), "notes": []}
    if model_seq != refseq:
        out["notes"].append(f"AlphaFold model is {e['uniprotAccession']} ({len(model_seq)} aa); the RefSeq protein "
                            f"{protein_id} is {iso} ({len(refseq)} aa); positions mapped by sequence")
    if lost_from:
        a = map_position(refseq, model_seq, lost_from)["model_position"]
        out["lost_model_range"] = [a, len(model_seq)] if a else None
    if pos is None:
        return out
    mp = map_position(refseq, model_seq, pos)
    out["mapping"] = {"refseq_position": pos, **mp}
    mpos = mp["model_position"]
    if mpos is None:
        out["status"] = "residue_not_in_model"
        return out
    atoms = parse_pdb(m["pdb_text"])
    res_atoms = [a for a in atoms if a["res"] == mpos]
    resname = res_atoms[0]["resname"]
    want = AA1_TO_3.get(refseq[pos - 1], "?").upper()
    out["residue"] = {"model_position": mpos, "model_aa": resname.capitalize(), "refseq_aa": want.capitalize(),
                      "match": resname == want}
    if resname != want:
        out["notes"].append(f"model residue {mpos} is {resname}, RefSeq residue {pos} is {want}")
    pl = round(res_atoms[0]["b"], 2)
    out["plddt"] = {"value": pl, "band": plddt_band(pl), "reliable": pl >= RELIABLE_PLDDT,
                    "note": "AlphaFold per-residue confidence; < 70 means the local structure is not reliable"}
    sasa = residue_sasa(atoms, mpos)
    rsa = sasa / MAX_ASA[resname]
    out["rsa"] = {"value": round(rsa, 3), "sasa_A2": round(sasa, 1), "max_asa_A2": MAX_ASA[resname],
                  "class": "buried" if rsa < BURIED_RSA else "exposed", "threshold": BURIED_RSA,
                  "borderline": abs(rsa - BURIED_RSA) < BORDERLINE_RSA,
                  "reliable": pl >= RELIABLE_PLDDT, "method": METHOD}
    out["neighbours_8A"] = neighbours(atoms, mpos)
    return out

