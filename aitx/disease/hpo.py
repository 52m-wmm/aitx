"""HPO ontology: term lookup, ancestors, information content, phenotype score.

Score (contract 4c) for patient terms P (present), X (explicitly absent) and
disease annotations D:

    match(p)  = max over d in D of IC(most informative common ancestor of p, d)
    score     = mean over p in P of match(p)  -  penalty
    penalty   = mean over x in X of IC(x) * freq(x), where freq is the highest
                frequency of any disease annotation equal to x or below it
                (unknown frequency counts as 0.5)

IC(t) = -ln(n_t / N): n_t = diseases annotated with t or a descendant, N = all
annotated diseases. Rare features therefore weigh more than common ones.
A disease with no annotations gets score None ("no annotation data"), never 0.

Onset (contract v2.3): the patient's age at onset is compared with the
disease's Onset-branch annotations (aspect C). Penalty only: a clear
mismatch subtracts ONSET_PENALTY, a match adds nothing, so diseases that
happen to have onset annotations gain no advantage over those without.
Never a veto. When only the current age is known, onset <= age, so only a
disease that starts later than the patient's age is penalised.
"""
from __future__ import annotations

import json
import math
import re
from collections import defaultdict
from dataclasses import dataclass

from aitx.disease.datasets import LocalFile
from aitx.disease.sources import Annotation, HpoAnnotations

PHENOTYPIC_ABNORMALITY = "HP:0000118"
UNKNOWN_FREQ = 0.5
ONSET = "HP:0003674"
ONSET_PENALTY = 1.0
INF = float("inf")
# Age at onset in months, [low, high), from the HPO term definitions.
ONSET_MONTHS = {
    "HP:0030674": (-10, 0),      # Antenatal (embryonal, fetal, trimesters below it)
    "HP:0003577": (0, 1),        # Congenital
    "HP:0003623": (0, 1),        # Neonatal (first 28 days)
    "HP:0003593": (1, 12),       # Infantile
    "HP:0011463": (12, 60),      # Childhood (1-5 y)
    "HP:0003621": (60, 192),     # Juvenile (5-15 y)
    "HP:0410280": (0, 192),      # Pediatric
    "HP:0003581": (192, INF),    # Adult (>= 16 y)
    "HP:0011462": (192, 480),    # Young adult (16-40 y)
    "HP:0025708": (192, 228),    # Early young adult (16-19 y)
    "HP:0025709": (228, 300),    # Intermediate young adult (19-25 y)
    "HP:0025710": (300, 480),    # Late young adult (25-40 y)
    "HP:0003596": (480, 720),    # Middle age (40-60 y)
    "HP:0003584": (720, INF),    # Late (> 60 y)
}


def _curie(iri: str) -> str:
    return iri.rsplit("/", 1)[-1].replace("_", ":", 1)


@dataclass
class Term:
    id: str
    label: str
    synonyms: list[str]
    obsolete: bool
    replaced_by: str | None


class Ontology:
    def __init__(self, lf: LocalFile):
        g = json.loads(lf.path.read_text(encoding="utf-8"))["graphs"][0]
        self.snapshot = lf.snapshot
        self.version = g.get("meta", {}).get("version", "")
        self.terms: dict[str, Term] = {}
        self.alt: dict[str, str] = {}
        for n in g["nodes"]:
            if not n["id"].startswith("http://purl.obolibrary.org/obo/HP_"):
                continue
            tid, meta = _curie(n["id"]), n.get("meta", {})
            repl = None
            for bp in meta.get("basicPropertyValues", []):
                if bp["pred"].endswith("hasAlternativeId"):
                    self.alt[bp["val"]] = tid
                elif bp["pred"].endswith("IAO_0100001"):  # term replaced by
                    repl = bp["val"]
            self.terms[tid] = Term(tid, n.get("lbl", ""), [s["val"] for s in meta.get("synonyms", [])],
                                   bool(meta.get("deprecated")), repl)
        self.parents: dict[str, set[str]] = defaultdict(set)
        for e in g.get("edges", []):
            if e["pred"] == "is_a":
                self.parents[_curie(e["sub"])].add(_curie(e["obj"]))
        self._anc: dict[str, frozenset[str]] = {}
        self.ic: dict[str, float] = {}
        self._max_ic = 0.0
        self._index: dict[str, list[str]] | None = None
        self._search: dict | None = None
        self.former: dict[str, list[str]] = defaultdict(list)   # former labels/synonyms of current terms
        for t in self.terms.values():                             # "obsolete X" replaced by Y -> X is a name of Y
            if t.obsolete and t.replaced_by in self.terms and t.label.lower().startswith("obsolete "):
                self._add_former(t.replaced_by, t.label[9:])

    # ---- lookup
    def resolve(self, tid: str) -> tuple[str | None, str]:
        """Return (current id, note). None if unknown or obsolete without replacement."""
        if tid in self.alt:
            return self.alt[tid], f"{tid} is an alternative id of {self.alt[tid]}"
        t = self.terms.get(tid)
        if t is None:
            return None, f"{tid} not in HPO {self.version}"
        if t.obsolete:
            if t.replaced_by and t.replaced_by in self.terms:
                return t.replaced_by, f"{tid} is obsolete, replaced by {t.replaced_by}"
            return None, f"{tid} is obsolete"
        return tid, ""

    def ancestors(self, tid: str) -> frozenset[str]:
        if tid not in self._anc:
            out, stack = {tid}, [tid]
            while stack:
                for p in self.parents.get(stack.pop(), ()):
                    if p not in out:
                        out.add(p)
                        stack.append(p)
            self._anc[tid] = frozenset(out)
        return self._anc[tid]

    def is_phenotype(self, tid: str) -> bool:
        return PHENOTYPIC_ABNORMALITY in self.ancestors(tid) and tid != PHENOTYPIC_ABNORMALITY

    def _add_former(self, tid: str, name: str) -> None:
        current = {normalize(n) for n in [self.terms[tid].label, *self.terms[tid].synonyms, *self.former[tid]]}
        if name and normalize(name) not in current:
            self.former[tid].append(name)
            self._index = self._search = None

    def add_former_names(self, lf: LocalFile) -> int:
        """Labels/synonyms an older HPO release used for terms that still exist (renamed terms)."""
        g = json.loads(lf.path.read_text(encoding="utf-8"))["graphs"][0]
        before = sum(len(v) for v in self.former.values())
        for n in g["nodes"]:
            if not n["id"].startswith("http://purl.obolibrary.org/obo/HP_"):
                continue
            cur, _ = self.resolve(_curie(n["id"]))
            if not cur:
                continue
            for name in [n.get("lbl", ""), *(x["val"] for x in n.get("meta", {}).get("synonyms", []))]:
                self._add_former(cur, name[9:] if name.lower().startswith("obsolete ") else name)
        return sum(len(v) for v in self.former.values()) - before

    def names(self, tid: str) -> list[str]:
        t = self.terms[tid]
        return [t.label, *t.synonyms, *self.former.get(tid, [])]

    def exact_lookup(self, text: str) -> list[str]:
        """Current phenotype terms whose label, synonym or former name equals `text`.

        Case/punctuation-insensitive; a plural form ("Seizures", "developmental delays") also matches.
        """
        if self._index is None:
            self._index = defaultdict(list)
            for t in self.terms.values():
                if not t.obsolete:
                    for n in self.names(t.id):
                        self._index[normalize(n)].append(t.id)
        out: list[str] = []
        for key in (normalize(text), " ".join(_singular(w) for w in normalize(text).split())):
            out += [t for t in self._index.get(key, []) if self.is_phenotype(t) and t not in out]
            if out:
                break
        return out

    def search(self, text: str, k: int = 10) -> list[dict]:
        """Lexical retrieval (BM25 over all names) of the k closest phenotype terms."""
        if self._search is None:
            docs, df = [], defaultdict(int)
            for t in self.terms.values():
                if t.obsolete or not self.is_phenotype(t.id):
                    continue
                for n in self.names(t.id):
                    toks = _tokens(n)
                    if toks:
                        docs.append((t.id, n, toks))
                        for w in set(toks):
                            df[w] += 1
            avg = sum(len(d[2]) for d in docs) / len(docs)
            self._search = {"docs": docs, "df": df, "n": len(docs), "avg": avg}
        ix = self._search
        q = set(_tokens(text))
        best: dict[str, tuple[float, str]] = {}
        for tid, name, toks in ix["docs"]:
            hit = q.intersection(toks)
            if not hit:
                continue
            sc = 0.0
            for w in hit:
                idf = math.log(1 + (ix["n"] - ix["df"][w] + 0.5) / (ix["df"][w] + 0.5))
                sc += idf * 2.2 / (1 + 1.2 * (0.25 + 0.75 * len(toks) / ix["avg"]))
            if sc > best.get(tid, (0.0, ""))[0]:
                best[tid] = (sc, name)
        ranked = sorted(best.items(), key=lambda x: (-x[1][0], x[0]))[:k]
        return [{"hpo_id": tid, "label": self.terms[tid].label, "matched_name": name, "score": round(sc, 3)}
                for tid, (sc, name) in ranked]

    # ---- information content
    def build_ic(self, ann: HpoAnnotations) -> None:
        counts: dict[str, int] = defaultdict(int)
        n = 0
        for items in ann.phenotypes.values():
            terms = set()
            for a in items:
                if not a.negated:
                    cur, _ = self.resolve(a.hpo_id)
                    if cur:
                        terms |= self.ancestors(cur)
            if terms:
                n += 1
                for t in terms:
                    counts[t] += 1
        self.ic = {t: -math.log(c / n) for t, c in counts.items()}
        self._max_ic = -math.log(1 / n)

    def term_ic(self, tid: str) -> float:
        return self.ic.get(tid, self._max_ic)

    def mica(self, a: str, b: str) -> tuple[str, float]:
        common = self.ancestors(a) & self.ancestors(b)
        best = max(common, key=lambda t: (self.term_ic(t) if self.is_phenotype(t) else 0.0, t), default=None)
        if best is None or not self.is_phenotype(best):
            return PHENOTYPIC_ABNORMALITY, 0.0
        return best, self.term_ic(best)


def disease_terms(ont: Ontology, anns: list[Annotation]) -> tuple[dict[str, float | None], set[str]]:
    """(present term -> max frequency, negated terms), ids resolved to current terms."""
    present: dict[str, float | None] = {}
    negated: set[str] = set()
    for a in anns:
        cur, _ = ont.resolve(a.hpo_id)
        if not cur or not ont.is_phenotype(cur):
            continue
        if a.negated:
            negated.add(cur)
            continue
        old = present.get(cur, -1.0)
        f = a.frequency
        present[cur] = f if old == -1.0 else (None if f is None and old is None else max(x for x in (f, old) if x is not None))
    return present, negated


def score(ont: Ontology, patient_present: list[str], patient_absent: list[str],
          anns: list[Annotation]) -> dict:
    present, _neg = disease_terms(ont, anns)
    if not present:
        return {"score": None, "note": "no annotation data in phenotype.hpoa", "matches": [], "penalties": []}
    matches = []
    for p in patient_present:
        best = max(((d, *ont.mica(p, d)) for d in present), key=lambda x: (x[2], x[0]))
        d, anc, ic = best
        matches.append({"patient_term": p, "disease_term": d if ic > 0 else None,
                        "common_ancestor": anc if ic > 0 else None, "ic": round(ic, 3)})
    penalties = []
    for x in patient_absent:
        hits = [d for d in present if x in ont.ancestors(d)]
        if not hits:
            continue
        freq = max((present[d] if present[d] is not None else UNKNOWN_FREQ) for d in hits)
        penalties.append({"patient_absent_term": x, "disease_terms": sorted(hits)[:5],
                          "frequency": round(freq, 3), "penalty": round(ont.term_ic(x) * freq, 3)})
    n = max(len(patient_present), 1)
    s = sum(m["ic"] for m in matches) / n - sum(p["penalty"] for p in penalties) / n
    return {"score": round(s, 4), "note": "", "matches": matches, "penalties": penalties,
            "annotated_terms": len(present)}


# ------------------------------------------------------------------- onset

def onset_range(ont: Ontology, tid: str) -> tuple[float, float] | None:
    """Month range of an Onset term, from the term itself or its nearest listed ancestor."""
    cur, _ = ont.resolve(tid)
    if not cur or ONSET not in ont.ancestors(cur):
        return None
    if cur in ONSET_MONTHS:
        return ONSET_MONTHS[cur]
    hits = [ONSET_MONTHS[a] for a in ont.ancestors(cur) if a in ONSET_MONTHS]
    return min(hits, key=lambda r: r[1] - r[0]) if hits else None


def onset_fit(ont: Ontology, patient: dict, disease_clinical: list[tuple[str, int]]) -> dict:
    """patient: {"min", "max", "kind": "onset" | "age_upper_bound"} in months (or {} if unknown)."""
    terms = []
    for tid, line in disease_clinical:
        r = onset_range(ont, tid)
        if r is not None:
            terms.append({"term": tid, "label": ont.terms[ont.resolve(tid)[0]].label,
                          "months": [r[0], None if r[1] == INF else r[1]], "line": line})
    out = {"patient": patient or None, "disease_onsets": terms, "result": "unknown", "adjustment": 0.0}
    if not terms or not patient or patient.get("max") is None:
        out["note"] = "no disease onset annotation" if not terms else "patient onset unknown"
        return out
    lo = patient["min"] if patient.get("min") is not None else 0
    lo, hi = lo * 0.8 - 1, patient["max"] * 1.25 + 1        # tolerance: category edges are fuzzy
    overlap = any(t["months"][0] < hi and lo < (INF if t["months"][1] is None else t["months"][1]) for t in terms)
    if patient.get("kind") == "age_upper_bound":
        if not overlap:
            out.update(result="mismatch", adjustment=-ONSET_PENALTY,
                       note="every annotated onset is later than the patient's current age")
        else:
            out.update(result="compatible", note="only an upper bound (current age) is known; no bonus")
        return out
    if overlap:
        out.update(result="match", note="consistent with annotated onset; no bonus (penalty-only rule)")
    else:
        out.update(result="mismatch", adjustment=-ONSET_PENALTY)
    return out


# ------------------------------------------------------------- text helpers

def normalize(s: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", s.lower()).split())


_SEARCH_STOP = {"of", "the", "and", "or", "in", "a", "an", "to", "at", "on", "by", "for", "with", "is", "are", "their"}


def _singular(w: str) -> str:
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith("s") and not w.endswith(("ss", "is", "us")) and len(w) > 3:
        return w[:-1]
    return w


def _tokens(s: str) -> list[str]:
    return [_singular(w) for w in normalize(s).split() if w not in _SEARCH_STOP]
