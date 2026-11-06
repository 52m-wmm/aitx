"""Test defaults: no test may depend on the real runs/llm_calls.jsonl or on the wall clock's peak window."""
import pytest

from aitx import budget as B
from aitx import peak as P


@pytest.fixture(autouse=True)
def _no_live_guards(monkeypatch):
    """The daily spend cap and the off-peak guard are off unless a test sets them itself.

    Without this, every test that walks the LLM call loop would read the real spend log and fail once the day's
    real spend passed the cap (2026-11-05).
    """
    monkeypatch.setenv(B.ENV, "off")
    monkeypatch.delenv(P.ENV, raising=False)
