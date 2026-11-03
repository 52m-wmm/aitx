"""Rule drafting checks (step 3.0 contract 4, rule 5) and GeneReviews section parsing. Offline."""
import pytest

from aitx.evidence import drafting as DR
from aitx.evidence import genereviews as GR

CANDS = [{"key": "M:BMD", "label": "Becker muscular dystrophy", "omim": [{"id": "OMIM:300376"}]},
         {"key": "M:DMD", "label": "Duchenne muscular dystrophy", "omim": [{"id": "OMIM:310200"}]},
         {"key": "M:XLID", "label": "X-linked intellectual disability", "omim": []}]
SRC = [{"type": "pmid", "id": "16770791", "url": "https://pubmed.ncbi.nlm.nih.gov/16770791/", "text_url": "u",
        "accessed_at": 1, "text": "In Becker patients, in-frame mutations allow the synthesis of internally deleted, "
                                  "but largely functional dystrophins. Variants at Ser331 cause severe disease."}]


def draft(**over):
    d = {"statement": "In-frame DMD variants point to Becker.", "applies_when": {"variant_class": ["inframe_deletion"]},
         "supports": [1], "argues_against": [2], "strength": "established",
         "evidence": [{"source": 1, "quote": "In Becker patients, in-frame mutations allow the synthesis"}]}
    d.update(over)
    return d


def test_good_draft_becomes_rule():
    rule, why = DR.check_draft(draft(), CANDS, SRC)
    assert why == [] and rule["effect"] == {"type": "diagnosis", "supports": ["OMIM:300376"], "argues_against": ["OMIM:310200"]}
    assert rule["sources"][0]["id"] == "16770791" and rule["sources"][0]["quote_verified"]


@pytest.mark.parametrize("over,reason", [
    ({"evidence": [{"source": 1, "quote": "in-frame mutations always cause Becker"}]}, "not verbatim"),
    ({"evidence": [{"source": 7, "quote": "In Becker patients"}]}, "source number"),
    ({"applies_when": {"patient_age": [0, 5]}}, "not a step 1 field"),
    ({"applies_when": {"variant_class": ["deletion"]}}, "not allowed"),
    ({"applies_when": {"protein_position": [39, 39]},
      "evidence": [{"source": 1, "quote": "Variants at Ser331 cause severe disease."}]}, "number 39 does not appear"),
    ({"supports": [9]}, "not in the candidate list"),
    ({"supports": [3], "argues_against": []}, "without an OMIM number"),
    ({"strength": "certain"}, "strength"),
    ({"supports": [], "argues_against": []}, "no candidate"),
])
def test_bad_drafts_rejected(over, reason):
    rule, why = DR.check_draft(draft(**over), CANDS, SRC)
    assert rule is None and any(reason in w for w in why), why


def test_position_number_found_in_quote_is_accepted():
    rule, why = DR.check_draft(draft(applies_when={"protein_position": [331, 331]},
                                     evidence=[{"source": 1, "quote": "Variants at Ser331 cause severe disease."}]), CANDS, SRC)
    assert why == []


def test_disease_query_words():
    assert DR.disease_words("amyotrophic lateral sclerosis 27, juvenile") == ["amyotrophic", "lateral", "sclerosis"]
    assert DR.disease_words("neuropathy, hereditary sensory and autonomic, type 1A")[:3] == ["neuropathy", "hereditary", "sensory"]


NXML = """<book-part><body>
<sec><title>Clinical Characteristics</title><p>Intro text.</p>
  <sec><title>Genotype-Phenotype Correlations</title><p>Variants at Ser331 cause severe disease.</p></sec>
</sec>
<sec><title>Management</title><sec><title>Agents/Circumstances to Avoid</title><p>Avoid neurotoxic drugs.</p></sec></sec>
</body></book-part>"""


def test_genereviews_sections(tmp_path, monkeypatch):
    p = tmp_path / "x.nxml"
    p.write_text(NXML)
    monkeypatch.setattr(GR, "extract_chapters", lambda nbks: {"NBK1": p})
    secs = GR.sections("NBK1")
    assert secs["Clinical Characteristics / Genotype-Phenotype Correlations"] == "Variants at Ser331 cause severe disease."
    assert GR.find_section("NBK1", "agents/circumstances to avoid") == ("Management / Agents/Circumstances to Avoid",
                                                                         "Avoid neurotoxic drugs.")
    assert GR.find_section("NBK1", "Nothing here") is None
