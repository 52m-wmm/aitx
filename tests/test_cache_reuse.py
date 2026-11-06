"""Cross-endpoint LLM cache reuse (decision 2026-11-05): only with an exactly equal served model name."""
import json

from aitx.disease import extract as X

MSG = [{"role": "user", "content": "hi"}]
OLD = {"base_url": "https://api.deepseek.com", "model": "deepseek-flash", "api_key": "", "expect_model_prefix": ""}
NEW = {"base_url": "https://trial.example", "model": "deepseek-flash", "api_key": "", "expect_model_prefix": "deepseek-flash"}


def _put(tmp_path, cfg, served):
    path = tmp_path / f"{X.cache_key(MSG, 0, cfg, 'v1')}.json"
    path.write_text(json.dumps({"served_model": served, "content": "{}", "call_params": X.CALL_PARAMS}))


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(X, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(X.llm, "LOG", tmp_path / "runs" / "llm_calls.jsonl")
    monkeypatch.delenv("AITX_LLM_CACHE_FROM", raising=False)


def test_reused_when_served_name_is_exactly_the_expected_one(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    _put(tmp_path, OLD, "deepseek-flash")
    e = X.cache_lookup(MSG, 0, NEW, "v1")
    assert e["provider"] == "https://api.deepseek.com" and e["reused_on"] == "https://trial.example"
    assert (tmp_path / "runs" / "cache_reuse.jsonl").read_text().count("\n") == 1


def test_not_reused_for_a_different_or_longer_served_name(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    _put(tmp_path, OLD, "deepseek-flash-0423")             # a prefix match is not enough
    assert X.cache_lookup(MSG, 0, NEW, "v1") is None


def test_not_reused_without_an_expected_name(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    _put(tmp_path, OLD, "deepseek-flash")
    assert X.cache_lookup(MSG, 0, dict(NEW, expect_model_prefix=""), "v1") is None


def test_same_endpoint_hit_records_its_provider(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    _put(tmp_path, OLD, "deepseek-flash")
    e = X.cache_lookup(MSG, 0, OLD, "v1")
    assert e["provider"] == "https://api.deepseek.com" and "reused_on" not in e


def test_other_sources_are_configurable(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    monkeypatch.setenv("AITX_LLM_CACHE_FROM", "https://elsewhere.example|other-model")
    _put(tmp_path, OLD, "deepseek-flash")
    assert X.cache_lookup(MSG, 0, NEW, "v1") is None        # the default source is no longer listed
