"""End-to-end smoke test of the step 1 CLI, offline (synthetic record pre-seeded in the cache)."""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from aitx.variant.transcript import efetch_url
from tests import synthetic as S

ROOT = Path(__file__).resolve().parents[1]


def test_cli_end_to_end(tmp_path):
    cache = tmp_path / "cache"
    cache.mkdir()
    url = efetch_url("NM_TEST01.1")
    (cache / (hashlib.sha256(url.encode()).hexdigest() + ".json")).write_text(
        json.dumps({"url": url, "text": S.genbank_text(), "accessed_at": 1761600000}))

    case = {"id": "TEST-1", "patient": {"genotype": [
        {"gene": "TEST1", "transcript": "NM_TEST01.1", "variant_cdna": "c.300dup",
         "variant_protein": f"p.({S.aa3(101)}101CysfsTer3)", "zygosity": "homozygous"}],
        "clinical_context": "synthetic"}}
    cases = tmp_path / "case.json"
    cases.write_text(json.dumps(case))
    out = tmp_path / "out"

    env = {**os.environ, "AITX_CACHE_DIR": str(cache), "NCBI_API_KEY": "", "AITX_SKIP_STRUCTURE": "1"}
    env.pop("NCBI_API_KEY")
    r = subprocess.run([sys.executable, str(ROOT / "scripts/step1_variant.py"), str(cases), "--out", str(out)],
                       capture_output=True, text=True, env=env, cwd=tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "[OK  ] TEST-1 TEST1 c.300dup | frameshift" in r.stdout

    res = json.loads((out / "TEST-1.json").read_text())
    var = res["variants"][0]
    assert var["nmd"]["prediction"] == "likely_triggers"
    assert var["evidence"][0]["source"] == "https://www.ncbi.nlm.nih.gov/nuccore/NM_TEST01.1"
    assert var["evidence"][0]["time_accessed"] == 1761600000
    assert res["patient_summary"]["all_checks_pass"] is True
