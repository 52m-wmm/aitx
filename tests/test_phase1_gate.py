import json
from scripts import run_kmt2b_phase1 as R

def test_gate_ignores_medical_gaps_but_stops_for_truncation_or_missing_block(tmp_path,monkeypatch):
    (tmp_path/'state.json').write_text(json.dumps({'sources_completed':1,'status':'one new extraction vote complete; stopped pending user approval','medical_gaps':['504 missing']}))
    (tmp_path/'execution_proposal.json').write_text('{"first_requests":1}')
    (tmp_path/'execution.log').write_text('done')
    (tmp_path/'raw_extractions').mkdir();(tmp_path/'raw_extractions/x.json').write_text('{}')
    monkeypatch.setattr(R.llm_cost,'summarize',lambda *a:{'usd':.03,'missing_usage':0,'peak_calls':0})
    assert R.operational_anomalies(tmp_path)[0]==[]
    (tmp_path/'execution.log').write_text('output truncated; retry succeeded')
    assert 'truncation occurred' in R.operational_anomalies(tmp_path)[0]
    (tmp_path/'raw_extractions/x.json').unlink()
    assert 'response/input cache gap' in R.operational_anomalies(tmp_path)[0]
