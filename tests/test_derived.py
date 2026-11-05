import pytest

from aitx.evidence import derived as D


def test_ckd_epi_2021_reference_values():
    # computed by hand from the published equation (Inker et al. 2021)
    assert D.egfr(1.0, 50, "male")["value"] == pytest.approx(92.0, abs=0.6)
    assert D.egfr(0.7, 40, "female")["value"] == pytest.approx(112.1, abs=0.2)     # 142 x 0.9938^40 x 1.012


def test_bedside_schwartz_needs_height():
    assert D.egfr(0.5, 7, "male", height_cm=120)["value"] == pytest.approx(99.1, abs=0.1)
    r = D.egfr(0.5, 7, "male")
    assert r["value"] is None and r["missing"] == ["height"]          # never a default height


@pytest.mark.parametrize("args,missing", [((None, 40, "male"), ["creatinine (mg/dL)"]), ((1.0, None, "male"), ["age"]),
                                           ((1.0, 40, None), ["sex"])])
def test_missing_inputs_are_unknown(args, missing):
    r = D.egfr(*args)
    assert r["value"] is None and r["missing"] == missing
