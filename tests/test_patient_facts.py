"""patient_facts: the LLM gives quotes and numbers; code keeps only what is verbatim (offline)."""
from aitx.evidence import labs as LABS
from aitx.evidence import patient_facts as PF

TEXT = "seizures and global developmental delay. Age 2 months, Hemoglobin 5, Normal liver labs, Not enrolled in other trials"


def test_verbatim_facts_kept_and_hemoglobin_without_unit_is_not_assumed():
    raw = [{"kind": "lab", "name": "Hemoglobin", "value": 5, "unit": "", "quote": "Hemoglobin 5"},
           {"kind": "organ_function", "name": "liver", "value": None, "status": "normal", "quote": "Normal liver labs"},
           {"kind": "other_trial", "name": "other trials", "value": None, "status": "absent", "quote": "Not enrolled in other trials"}]
    kept, dropped = PF.verify(raw, TEXT, LABS.load())
    assert [f["kind"] for f in kept] == ["lab", "organ_function", "other_trial"] and not dropped
    hb = kept[0]
    assert hb["analyte"] == "hemoglobin" and hb["interpretation"]["status"] == "unknown"   # g/dL or mmol/L


def test_invented_quote_number_or_unit_dropped():
    raw = [{"kind": "lab", "name": "Hemoglobin", "value": 5, "unit": "g/dL", "quote": "Hemoglobin 5"},     # unit not written
           {"kind": "lab", "name": "Hemoglobin", "value": 7, "unit": "", "quote": "Hemoglobin 5"},          # number not in quote
           {"kind": "lab", "name": "ALT", "value": 40, "unit": "", "quote": "ALT 40"},                      # not in the text
           {"kind": "diet", "name": "x", "value": None, "quote": "seizures"}]                               # unknown kind
    kept, dropped = PF.verify(raw, TEXT, LABS.load())
    assert not kept and [d["dropped"] for d in dropped] == [
        "unit not in the quote", "number not in the quote", "quote not verbatim in the clinical description", "unknown kind"]


def test_find_by_kind_and_name():
    kept, _ = PF.verify([{"kind": "organ_function", "name": "liver", "status": "normal", "quote": "Normal liver labs"}],
                        TEXT, LABS.load())
    extra = {"facts": kept}
    assert PF.find(extra, "organ_function", "liver") and not PF.find(extra, "organ_function", "kidney")
