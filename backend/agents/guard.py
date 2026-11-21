"""Output guards: numbers must come from the input (SPEC §9.4); public text must stay neutral (§6.4)."""
from __future__ import annotations

import json
import re

BANNED_PUBLIC = [
    "fraud", "scam", "suspicious", "corrupt", "theft", "loot", "embezzl", "bribe", "red flag",
    "घोटाळा", "भ्रष्टाचार", "घोटाला", "भ्रष्ट",
]

_DEV = str.maketrans("०१२३४५६७८९", "0123456789")
_NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")


def banned_words(text: str) -> list[str]:
    low = text.lower()
    return [w for w in BANNED_PUBLIC if w.lower() in low]


def _values(obj, out: set[float]):
    if isinstance(obj, bool) or obj is None:
        return
    if isinstance(obj, (int, float)):
        out.add(float(obj))
        # derived forms an LLM may legitimately write
        out.add(round(float(obj)))
        out.add(round(float(obj), 1))
        out.add(round(float(obj) * 100))          # fraction -> percent
        out.add(round(float(obj) * 100, 1))
        out.add(round(float(obj) / 1e5, 1))       # lakh
        out.add(round(float(obj) / 1e7, 2))       # crore
        out.add(round(float(obj) / 1e5, 2))
        out.add(round(float(obj) / 1e7, 1))
    elif isinstance(obj, str):
        for n in _NUM.findall(obj.translate(_DEV)):
            try:
                out.add(float(n.replace(",", "")))
            except ValueError:
                pass
    elif isinstance(obj, dict):
        for v in obj.values():
            _values(v, out)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            _values(v, out)


def allowed_numbers(payload) -> set[float]:
    s: set[float] = set()
    _values(payload, s)
    return s


def unsupported_numbers(text: str, payload, extra=()) -> list[str]:
    """Numbers in `text` that do not appear (in any common formatting) in `payload`."""
    allowed = allowed_numbers(payload) | set(extra)
    bad = []
    for tok in _NUM.findall(text.translate(_DEV)):
        try:
            v = float(tok.replace(",", ""))
        except ValueError:
            continue
        if v in allowed or round(v) in allowed:
            continue
        if any(abs(v - a) <= max(0.51, abs(a) * 0.005) for a in allowed):
            continue
        bad.append(tok)
    return bad


def numbers_ok(text: str, payload, extra=(0, 1, 2, 3, 4, 5, 10, 30, 100)) -> bool:
    return not unsupported_numbers(text, payload, extra)


def payload_json(payload) -> str:
    return json.dumps(payload, ensure_ascii=False, default=str, indent=1)
