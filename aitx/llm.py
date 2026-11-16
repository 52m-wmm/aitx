"""Model-agnostic LLM interface (OpenAI-compatible Chat Completions).

Switching models is configuration only — no code changes:

    AITX_LLM_BASE_URL   e.g. https://api.deepseek.com            (default)
                             https://openrouter.ai/api/v1
    AITX_LLM_MODEL      e.g. deepseek-flash, deepseek/deepseek-v4-flash-0423
    AITX_LLM_API_KEY    your key
    AITX_LLM_STREAM=0      ask for a non-streamed response (default: streamed, assembled here)
    AITX_LLM_CACHE_ONLY=1  never call the server: callers' cached answers are used and any
                           uncached call raises CacheOnly (lets checks run during peak-price hours)

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
# one call's time limit: fail early and retry rather than wait on a stalled connection (2026-11-03: 600 -> 120 s)
TIMEOUT_S = int(os.environ.get("AITX_LLM_TIMEOUT", "120"))


STREAM = os.environ.get("AITX_LLM_STREAM", "1") != "0"


def _read_stream(r) -> dict:
    """Server-sent events (OpenAI-compatible chunks) -> the same shape as a non-streamed response."""
    content, reasoning, finish, model, usage, rid = [], [], None, "", None, None
    for raw in r:
        line = raw.decode("utf-8", errors="replace").strip()
        if not line.startswith("data:"):
            continue                      # blank lines and ': keep-alive' comments
        data = line[5:].strip()
        if data == "[DONE]":
            break
        chunk = json.loads(data)
        model = chunk.get("model") or model
        rid = chunk.get("id") or rid
        usage = chunk.get("usage") or usage
        for ch in chunk.get("choices") or []:
            d = ch.get("delta") or {}
            content.append(d.get("content") or "")
            reasoning.append(d.get("reasoning_content") or "")
            finish = ch.get("finish_reason") or finish
    msg = {"role": "assistant", "content": "".join(content)}
    if any(reasoning):
        msg["reasoning_content"] = "".join(reasoning)
    return {"id": rid, "model": model, "choices": [{"index": 0, "message": msg, "finish_reason": finish}], "usage": usage}


class NoServedModel(RuntimeError):
    """The response carried no model name, so the served model could not be confirmed (retryable)."""


class ModelMismatch(RuntimeError):
    pass


class CacheOnly(RuntimeError):
    """An uncached LLM call was needed while AITX_LLM_CACHE_ONLY=1."""


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
    if os.environ.get("AITX_LLM_CACHE_ONLY") == "1":
        raise CacheOnly("AITX_LLM_CACHE_ONLY=1: this call is not cached; run it off-peak")
    cfg = config()
    if not cfg["api_key"]:
        raise RuntimeError("set AITX_LLM_API_KEY")
    body = {"model": cfg["model"], "messages": messages, "temperature": temperature,
            "max_tokens": max_tokens, **extra}
    if tools:
        body["tools"] = tools
    elif STREAM:
        # streamed: bytes keep flowing while the model reasons, so long calls are not cut as idle connections
        # (2026-11-04: non-streamed calls over ~60 s ended in IncompleteRead(0 bytes read) on every retry)
        body["stream"] = True
        body["stream_options"] = {"include_usage": True}
    req = urllib.request.Request(
        cfg["base_url"] + "/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {cfg['api_key']}", "Content-Type": "application/json"},
    )
    t0 = time.time()
    from scripts.llm_cost import request_reservation
    reserved = request_reservation(messages, max_tokens, t0, tools)
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
        resp = _read_stream(r) if body.get("stream") else json.loads(r.read().decode())
    served = resp.get("model", "")

    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a") as f:
        f.write(json.dumps({"ts": int(t0), "requested": cfg["model"], "served": served,
                            "base_url": cfg["base_url"], "usage": resp.get("usage"), "reserved_usd": reserved,
                            "seconds": round(time.time() - t0, 2)}) + "\n")
    if cfg["expect_model_prefix"] and not served:
        # no chunk of the stream carried a model name: we cannot confirm who answered, but this is a stream
        # artifact rather than a model switch, so the caller retries it (2026-11-06: it lost a whole case)
        raise NoServedModel(f"the response carried no model name (requested {cfg['model']}); not accepted "
                            f"without confirming the model")
    if cfg["expect_model_prefix"] and not served.startswith(cfg["expect_model_prefix"]):
        raise ModelMismatch(f"requested {cfg['model']} but server reports {served!r}")
    return dict(resp, reserved_usd=reserved)
