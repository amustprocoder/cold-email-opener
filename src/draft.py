"""Step 2 (model): site text in, a 3-line opener out, with the quote from the site that backs each line.

Step 3 (code again): check every quote really appears in the site text. A line whose quote is not on the
page is marked unverified and dropped, so the tool never sends a founder a "fact" the model invented.
"""

from __future__ import annotations

import json
import os
import re
import time

import requests

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
# Cheapest first: this is a short, factual task. The dearer Flash is a fallback when Lite is busy or retired.
MODELS = ["gemini-3.5-flash-lite", "gemini-3.8-flash", "gemini-flash-lite-latest"]
TIMEOUT = 30

SYSTEM = (
    "You write the first three lines of a cold email from Om, a generalist at an early-stage startup, to the "
    "founder of the company whose website text you are given. Plain English, no flattery, no exclamation marks, "
    "no 'I hope this finds you well'. Each line is one sentence under 25 words. Line 1: something specific the "
    "site says about what they do or who they serve. Line 2: a detail that shows you actually read the site "
    "(a feature, a number, a customer type, a recent change). Line 3: a short, honest bridge to why you are "
    "writing: you help small software companies see the numbers that run the business. Use only facts that "
    "appear in the text. If the text is too thin to be specific, say so in the 'note' field and keep lines generic."
)

SCHEMA_HINT = {
    "company": "company name as the site writes it",
    "founder_hint": "founder or CEO name if the text names one, else null",
    "lines": ["line 1", "line 2", "line 3"],
    "evidence": ["exact short quote from the text that backs line 1", "quote for line 2", "quote for line 3 or null"],
    "note": "one sentence on anything thin or uncertain, else null",
}


def _extract_json(text: str) -> dict:
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not m:
            raise
        return json.loads(m.group(0))


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def ground(out: dict, site_text: str) -> dict:
    """Lines 1-2 are grounded only if (a) the evidence quote appears in the site text and (b) every number in the
    line also appears there. Line 3 is the bridge about us, so it carries no site fact and is not checked."""
    hay = _norm(site_text)
    evidence = out.get("evidence") or []
    checks = []
    for i, line in enumerate(out.get("lines", [])[:3]):
        ev = evidence[i] if i < len(evidence) else None
        if i == 2:
            checks.append({"line": line, "evidence": None, "grounded": None, "kind": "bridge"})
            continue
        quote_ok = bool(ev) and len(_norm(ev)) >= 4 and _norm(ev) in hay
        nums = re.findall(r"\d[\d,.]*", line)
        nums_ok = all(_norm(n) in hay for n in nums)
        checks.append({"line": line, "evidence": ev, "grounded": quote_ok and nums_ok, "kind": "fact"})
    out["checks"] = checks
    out["grounded"] = sum(1 for c in checks if c["grounded"])
    return out


def _call(model: str, body: dict, headers: dict) -> tuple[dict, dict, str]:
    url = GEMINI_URL.format(model=model)
    cfg = dict(body["generationConfig"])
    cfg["thinkingConfig"] = {"thinkingLevel": "low"}       # short factual task; low thinking is faster and cheaper
    for _ in range(2):
        try:
            r = requests.post(url, json={**body, "generationConfig": cfg}, headers=headers, timeout=TIMEOUT)
        except requests.Timeout:
            raise RuntimeError(f"{model}: timed out") from None
        except requests.RequestException as e:
            raise RuntimeError(f"{model}: network error ({type(e).__name__})") from None
        if r.status_code == 400 and "thinkingConfig" in cfg:
            cfg.pop("thinkingConfig")
            continue
        if r.status_code == 404:
            raise RuntimeError(f"{model}: retired")
        if r.status_code == 429 or r.status_code >= 500:
            raise RuntimeError(f"{model}: HTTP {r.status_code} (busy or rate limited)")
        if r.status_code != 200:
            raise RuntimeError(f"{model}: HTTP {r.status_code} ({r.text[:120]})")
        data = r.json()
        try:
            out = _extract_json(data["candidates"][0]["content"]["parts"][0]["text"])
        except (KeyError, IndexError, json.JSONDecodeError):
            cand = (data.get("candidates") or [{}])[0]
            raise RuntimeError(f"{model}: no usable answer ({cand.get('finishReason', 'unknown')})") from None
        usage = data.get("usageMetadata", {})
        return out, usage, data.get("modelVersion") or model
    raise RuntimeError(f"{model}: rejected the request")


def draft_opener(site: dict) -> dict:
    """site = output of fetch.fetch_site_text(). Returns lines, evidence, checks, tokens, model, seconds."""
    key = os.environ.get("GEMINI_API_KEY", "").strip().strip('"\'')
    if not key:
        raise RuntimeError("GEMINI_API_KEY is not set. Get a free key at aistudio.google.com and set it.")
    if site["chars"] == 0:
        raise RuntimeError("Could not fetch that site (wrong address, down, or it blocks bots).")
    if site["chars"] < 200:
        raise RuntimeError("Could not read enough text from that site (JavaScript-only or blocked).")
    prompt = (
        f"Website: {site['final_url']}\n\nSITE TEXT (trimmed):\n\"\"\"\n{site['text']}\n\"\"\"\n\n"
        "Return ONE JSON object with exactly these keys and shapes:\n" + json.dumps(SCHEMA_HINT, indent=1)
    )
    body = {
        "systemInstruction": {"parts": [{"text": SYSTEM}]},
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"response_mime_type": "application/json", "maxOutputTokens": 600},
    }
    headers = {"x-goog-api-key": key, "Content-Type": "application/json"}
    errors = []
    t0 = time.time()
    for model in MODELS:
        try:
            out, usage, used = _call(model, body, headers)
            break
        except RuntimeError as e:
            errors.append(str(e))
    else:
        raise RuntimeError("No model answered: " + "; ".join(errors))
    out = ground(out, site["text"])
    out["model"] = used
    out["tokens_in"] = int(usage.get("promptTokenCount", 0))
    # candidates + thinking tokens are both billed as output
    out["tokens_out"] = int(usage.get("candidatesTokenCount", 0)) + int(usage.get("thoughtsTokenCount", 0))
    out["seconds"] = round(time.time() - t0, 1)
    out["errors"] = errors
    return out
