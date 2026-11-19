import json
import pytest
from scripts import run_kmt2b_extraction_vote as R


def test_started_vote_cannot_be_repeated(tmp_path):
    (tmp_path/'started.json').write_text('{}')
    with pytest.raises(FileExistsError):R.execute(tmp_path,tmp_path/'proposal.json')


def test_missing_api_key_stops_before_balance_network(tmp_path,monkeypatch):
    monkeypatch.setattr(R.llm,'config',lambda:{'api_key':''})
    with pytest.raises(ValueError,match='environment'):R.balance(tmp_path/'balance.json')
    assert not (tmp_path/'balance.json').exists()
