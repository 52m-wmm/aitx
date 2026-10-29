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

    def names(self, tid: str) -> list[str]:
        t = self.terms[tid]
        return [t.label, *t.synonyms]

    def exact_lookup(self, text: str) -> list[str]:
        """Current phenotype terms whose label or synonym equals `text` (case/punctuation-insensitive)."""
        if self._index is None:
            self._index = defaultdict(list)
            for t in self.terms.values():
                if not t.obsolete:
                    for n in [t.label, *t.synonyms]:
                        self._index[normalize(n)].append(t.id)
        return [t for t in self._index.get(normalize(text), []) if self.is_phenotype(t)]

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


# ----------------------------------------------------------- lexical checks

_STOP = {"of", "the", "and", "or", "with", "without", "in", "a", "an", "to", "at", "on", "by", "for",
         "abnormal", "abnormality", "abnormalities", "increased", "decreased", "reduced", "impaired",
         "mild", "severe", "progressive", "recurrent", "episodes", "episode", "episodic", "history",
         "positive", "chronic", "early", "onset", "overt", "type", "finding", "findings", "signs", "sign"}
# A few lay / adjective forms that share no prefix with the HPO wording.
_EQUIV = [{"ophthalmic", "ocular", "eye", "eyes", "ophthalmologic", "visual"},
          {"renal", "kidney", "nephro"}, {"hepatic", "liver"}, {"cardiac", "heart"},
          {"cerebral", "brain"}, {"cutaneous", "skin", "dermal"}, {"thin", "underweight", "cachexia", "cachectic", "emaciat"},
          {"intellectual", "cognitive", "mental"}, {"motor", "movement"}]


def normalize(s: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", s.lower()).split())


def _stem(w: str) -> str:
    for suf in ("ies", "es", "s"):
        if w.endswith(suf) and len(w) - len(suf) >= 4:
            return w[: -len(suf)]
    return w


def content_words(s: str) -> set[str]:
    return {_stem(w) for w in normalize(s).split() if w not in _STOP and len(w) > 1}


def _related(a: str, b: str) -> bool:
    if a == b:
        return True
    k = 0
    for x, y in zip(a, b):
        if x != y:
            break
        k += 1
    if k >= 5:
        return True
    return any(any(a.startswith(e) for e in g) and any(b.startswith(e) for e in g) for g in _EQUIV)


def lexical_overlap(quote: str, names: list[str]) -> list[str]:
    """Content words of `quote` that also appear (loosely) in any of the term names."""
    q = content_words(quote)
    hits = set()
    for n in names:
        for w in content_words(n):
            hits |= {x for x in q if _related(x, w)}
    return sorted(hits)
