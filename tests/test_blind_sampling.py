"""Blind-test B1 split into single-gene chapter (L1) and overview only (L2), decision 2026-11-11. Offline."""
import importlib.util
from pathlib import Path

_p = Path(__file__).resolve().parents[1] / "scripts" / "sample_blind_cases.py"
_spec = importlib.util.spec_from_file_location("sample_blind_cases", _p)
S = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(S)

TITLES = {"NBK1358": "Charcot-Marie-Tooth Hereditary Neuropathy Overview",
          "NBK195854": "RRM2B Mitochondrial DNA Maintenance Defects",
          "NBK9": "A Disease With Two Genes"}


def kind(nbk, n):
    return S.chapter_kind(nbk, n, title_of=TITLES.get)


def test_the_pipeline_title_rule_decides():
    assert kind("NBK1358", 36)["kind"] == "overview"
    assert kind("NBK195854", 1)["kind"] == "chapter"
    # a multi-gene chapter on one disease is still a chapter: the title, not the gene count, decides
    assert kind("NBK9", 2)["kind"] == "chapter"


def test_without_a_local_title_the_gene_count_decides_and_says_so():
    k = kind("NBK404", 12)
    assert k["kind"] == "overview" and "gene count" in k["rule"]
    assert kind("NBK405", 1)["kind"] == "chapter"


def test_subgroups():
    assert S.subgroup_of([kind("NBK1358", 36)]) == "B1-L2"
    assert S.subgroup_of([kind("NBK1358", 36), kind("NBK195854", 1)]) == "B1-L1"   # any chapter wins, as in 3a


def test_regroup_labels_without_redrawing(tmp_path, monkeypatch):
    import json
    monkeypatch.setattr(S, "ROOT", tmp_path)
    monkeypatch.setattr(S, "index_gene_counts", lambda: {"NBK1358": 36, "NBK195854": 1})
    d = tmp_path / "out" / "blind" / "x"
    d.mkdir(parents=True)
    cases = [{"group": "B1", "gene": "MPZ", "chapters": ["NBK1358"], "variant": {"v": 1}},
             {"group": "B1", "gene": "RRM2B", "chapters": ["NBK195854"], "variant": {"v": 2}},
             {"group": "B2", "gene": "FOXF1", "chapters": [], "variant": {"v": 3}}]
    (d / "sample.json").write_text(json.dumps({"seed": "s", "cases": cases}))
    s = S.regroup("x", title_of=TITLES.get)
    assert [c["subgroup"] for c in s["cases"]] == ["B1-L2", "B1-L1", "B2"]
    assert [c["variant"] for c in s["cases"]] == [{"v": 1}, {"v": 2}, {"v": 3}] and s["seed"] == "s"
    assert s["regrouped"][0]["subgroups"] == {"MPZ": "B1-L2", "RRM2B": "B1-L1", "FOXF1": "B2"}
