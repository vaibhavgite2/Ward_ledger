"""Complaint Parser agent (SPEC §6.1).

Claude Haiku (batched, cached) when available; otherwise a deterministic multilingual keyword
classifier. Output is a *claim*; promotion to fact happens in rules.promote.
"""
from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor

import config
from agents import claude_client as cc

CATEGORIES = [
    "Pothole", "Waterlogging", "Open or broken manhole", "Choked drain / nullah overflow",
    "Road cave-in", "Broken paver blocks", "Other",
]
VERSION = "v1"
BATCH = 25

# Ordered: first match wins. Covers English, Hinglish, Hindi and Marathi surface forms.
_KEYWORDS: list[tuple[str, list[str]]] = [
    ("Open or broken manhole", [
        "manhole", "man hole", "dhakkan", "dhakan", "झाकण", "ढक्कन", "chamber cover", "grating missing", "cover missing",
    ]),
    ("Road cave-in", [
        "cave-in", "cave in", "caved", "caving", "sunk", "sinking", "subsid", "धंस", "धसल", "खचल", "ढह", "पाइपलाइन",
    ]),
    ("Broken paver blocks", [
        "paver", "पेवर", "paving block", "tiles uprooted", "interlocking",
    ]),
    ("Choked drain / nullah overflow", [
        "choked", "nullah", "nala ", "culvert", "gutter", "नाला", "नाले", "गटार", "chocked", "sewer", "drain overflow",
        "drain block", "drainage",
    ]),
    ("Waterlogging", [
        "waterlog", "water log", "water-log", "flood", "paani", "pani ", "पानी", "पाणी", "जलभराव", "जल भराव",
        "send pump", "send a pump", "pump bhej", "dewater", "पंप पाठवा", "पंप भेज", "knee deep", "knee-deep", "inundat", "water level", "water accumulat", "standing water",
    ]),
    ("Pothole", [
        "pothole", "potholes", "gaddha", "gadda", "gadde", "khadda", "khadde", "गड्ढ", "खड्ड", "खड्डे", "crater",
        "pot hole", "hole in", "big hole", "road damaged", "patch work", "patchwork", "reopened", "उखडले", "उखड",
    ]),
]
_EXPLICIT = re.compile(r"^(?:caller reports|as per caller|complainant states|citizen informs)\s+(.+?)\s+at\s", re.I)
_NOISE = {"test", "asdfgh", "testing", "xxx", "abc"}
_NOT_ROAD = ["garbage", "kachra", "कचरा", "stray", "dog ", "noise", "streetlight", "street light", "tree fall", "tree fell"]


def classify_keyword(description: str, reported: str | None = None, photo: str | None = None) -> dict:
    """Deterministic fallback. Returns {category, confidence, reason}."""
    description = description if isinstance(description, str) else ""
    photo = photo if isinstance(photo, str) else None
    reported = reported if isinstance(reported, str) else None
    text = description.strip().lower()
    if len(text) < 8 or text in _NOISE:
        return {"category": "Other", "confidence": 0.3, "reason": "Too short / test message"}
    # Helpline/operator notes state the category outright ("Caller reports pothole at X ..."); the
    # trailing sentence is generic filler shared across categories, so classify the phrase alone.
    m = _EXPLICIT.match(text)
    if m:
        phrase = m.group(1).strip()
        for cat in CATEGORIES:
            if phrase == cat.lower():
                return {"category": cat, "confidence": 0.9, "reason": f"explicit statement '{phrase}'"}
    padded = text + " "
    for cat, kws in _KEYWORDS:
        for kw in kws:
            if kw in padded:
                return {"category": cat, "confidence": 0.7, "reason": f"keyword '{kw.strip()}' in description"}
    if any(k in padded for k in _NOT_ROAD):
        return {"category": "Other", "confidence": 0.6, "reason": "not a road/drain issue"}
    if photo:
        p = photo.lower() + " "
        for cat, kws in _KEYWORDS:
            for kw in kws:
                if kw in p:
                    return {"category": cat, "confidence": 0.5, "reason": f"keyword '{kw.strip()}' in photo description"}
    if reported in CATEGORIES:
        return {"category": reported, "confidence": 0.35, "reason": "no keyword; kept reported category"}
    return {"category": "Other", "confidence": 0.3, "reason": "could not determine"}


def _system_prompt() -> str:
    return (config.PROMPTS_DIR / "complaint_parser.md").read_text(encoding="utf-8")


def _claude_batch(items: list[dict]) -> dict[str, dict]:
    payload = [{"id": i["complaint_id"], "text": i["description"], "reported_category": i["category_reported"],
                "photo": i.get("photo_description")} for i in items]
    res = cc.complete(config.MODEL_FAST, _system_prompt(), json.dumps(payload, ensure_ascii=False),
                      agent="complaint-parser", version=VERSION, max_tokens=4000, temperature=0.0)
    if res is None:
        return {}
    arr = cc.parse_json(res.text)
    if not isinstance(arr, list):
        return {}
    out = {}
    for o in arr:
        if not isinstance(o, dict) or o.get("category") not in CATEGORIES:
            continue
        try:
            conf = max(0.0, min(1.0, float(o.get("confidence", 0.6))))
        except (TypeError, ValueError):
            conf = 0.6
        out[str(o.get("id"))] = {
            "category": o["category"], "confidence": conf, "reason": str(o.get("reason", ""))[:200],
            "locality_mentioned": o.get("locality_mentioned"), "language": o.get("language"),
            "extractor": res.extractor, "prompt_hash": res.prompt_hash,
        }
    return out


def parse_all(complaints: list[dict]) -> dict[str, dict]:
    """complaint_id -> parse result (always present for every complaint)."""
    results: dict[str, dict] = {}
    if config.CLAUDE_ENABLED:
        batches = [complaints[i:i + BATCH] for i in range(0, len(complaints), BATCH)]
        with ThreadPoolExecutor(max_workers=4) as ex:
            for part in ex.map(_claude_batch, batches):
                results.update(part)
    kw_extractor = f"keyword-classifier@{VERSION}"
    for c in complaints:
        cid = c["complaint_id"]
        if cid not in results:
            r = classify_keyword(c.get("description"), c.get("category_reported"), c.get("photo_description"))
            r.update({"extractor": kw_extractor, "prompt_hash": None, "locality_mentioned": None, "language": None})
            results[cid] = r
    return results


def normalise_reported(cat: str | None) -> str:
    """Map the citizen-picked label onto our canonical set (vague labels -> 'Other')."""
    if cat in CATEGORIES:
        return cat
    return "Other"


