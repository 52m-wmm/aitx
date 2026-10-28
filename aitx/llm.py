"""Model-agnostic LLM interface (OpenAI-compatible Chat Completions).

Switching models is configuration only — no code changes:

    AITX_LLM_BASE_URL   e.g. https://api.deepseek.com            (default)
                             https://openrouter.ai/api/v1
    AITX_LLM_MODEL      e.g. deepseek-flash, deepseek/deepseek-v4-flash-0423
    AITX_LLM_API_KEY    your key

Every call is appended to runs/llm_calls.jsonl with the model name the
server actually reports, so a silent alias change (as happened when
deepseek-v4-flash started serving V4.1-Flash-1017) is caught.
Not used by step 1, which is fully deterministic.
"""
from __future__ import annotations

import json
import os
import time
import urllib.request
from pathlib import Path

LOG = Path(os.environ.get("AITX_RUN_DIR", "runs")) / "llm_calls.jsonl"


class ModelMismatch(RuntimeError):
    pass


def config() -> dict:
    return {
        "base_url": os.environ.get("AITX_LLM_BASE_URL", "https://api.deepseek.com").rstrip("/"),
        "model": os.environ.get("AITX_LLM_MODEL", "deepseek-flash"),
        "api_key": os.environ.get("AITX_LLM_API_KEY", ""),
        "expect_model_prefix": os.environ.get("AITX_EXPECT_MODEL_PREFIX", ""),
    }


def chat(messages: list[dict], *, tools: list[dict] | None = None, temperature: float = 1.0,
         max_tokens: int = 8192, **extra) -> dict:
    """One chat completion. Returns the raw response JSON (choices, usage, model)."""
    cfg = config()
    if not cfg["api_key"]:
        raise RuntimeError("set AITX_LLM_API_KEY")
    body = {"model": cfg["model"], "messages": messages, "temperature": temperature,
            "max_tokens": max_tokens, **extra}
    if tools:
        body["tools"] = tools
    req = urllib.request.Request(
        cfg["base_url"] + "/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {cfg['api_key']}", "Content-Type": "application/json"},
    )
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=600) as r:
        resp = json.loads(r.read().decode())
    served = resp.get("model", "")

    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a") as f:
        f.write(json.dumps({"ts": int(t0), "requested": cfg["model"], "served": served,
                            "base_url": cfg["base_url"], "usage": resp.get("usage"),
                            "seconds": round(time.time() - t0, 2)}) + "\n")
    if cfg["expect_model_prefix"] and not served.startswith(cfg["expect_model_prefix"]):
        raise ModelMismatch(f"requested {cfg['model']} but server reports {served!r}")
    return resp
