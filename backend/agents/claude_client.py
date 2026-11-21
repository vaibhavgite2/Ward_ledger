"""Thin, cached wrapper over the Anthropic SDK (SPEC §9).

* Every call is cached on disk by sha256(model + system + prompt + temperature), so re-runs are free.
* `complete()` returns None when Claude is disabled or the call fails; callers MUST have a
  deterministic fallback. Claude output is only ever stored as a *claim* or shown as a draft.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass

import config

_client = None


@dataclass
class Result:
    text: str
    extractor: str       # "{model}/{agent}@{version}"
    prompt_hash: str     # sha256(model | system | temperature): identifies the prompt template
    cached: bool = False


def _get_client():
    global _client
    if _client is None:
        import anthropic
        _client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    return _client


def prompt_hash(model: str, system: str, temperature: float) -> str:
    return hashlib.sha256(f"{model}|{system}|{temperature}".encode("utf-8")).hexdigest()


def complete(model: str, system: str, prompt: str, *, agent: str, version: str = "v1",
             max_tokens: int = 1500, temperature: float = 0.0, retries: int = 3) -> Result | None:
    if not config.CLAUDE_ENABLED:
        return None
    ph = prompt_hash(model, system, temperature)
    extractor = f"{model}/{agent}@{version}"
    key = hashlib.sha256(f"{ph}|{prompt}".encode("utf-8")).hexdigest()
    path = config.CACHE_DIR / f"{key}.json"
    if path.exists():
        try:
            return Result(json.loads(path.read_text(encoding="utf-8"))["text"], extractor, ph, True)
        except Exception:
            pass
    delay = 2.0
    for attempt in range(retries):
        try:
            msg = _get_client().messages.create(
                model=model, max_tokens=max_tokens, temperature=temperature, system=system,
                messages=[{"role": "user", "content": prompt}],
            )
            text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
            config.CACHE_DIR.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"text": text, "extractor": extractor}, ensure_ascii=False), encoding="utf-8")
            return Result(text, extractor, ph)
        except Exception:
            if attempt == retries - 1:
                return None
            time.sleep(delay)
            delay *= 2
    return None


def parse_json(text: str):
    """Extract the first JSON object/array from a model reply (tolerates ```json fences)."""
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t, flags=re.S)
    try:
        return json.loads(t)
    except Exception:
        m = re.search(r"(\[.*\]|\{.*\})", t, flags=re.S)
        if m:
            try:
                return json.loads(m.group(1))
            except Exception:
                return None
    return None
