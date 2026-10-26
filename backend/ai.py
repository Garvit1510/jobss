import os
import json
import re
import asyncio
import time
import logging
from fastapi import HTTPException

log = logging.getLogger("ai")


def _extract_json(text: str):
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.M).strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    for open_c, close_c in (("{", "}"), ("[", "]")):
        s, e = text.find(open_c), text.rfind(close_c)
        if s != -1 and e > s:
            try:
                return json.loads(text[s:e + 1])
            except Exception:
                continue
    raise ValueError("No JSON in AI response")


_cooldown = {}
ATTEMPTS = {"n": 0}


def _split(name):
    return [m.strip() for m in os.environ.get(name, "").split(",") if m.strip()]


def _models():
    keys = _split("GEMINI_API_KEYS") or [os.environ["GEMINI_API_KEY"]]
    models = [os.environ["GEMINI_MODEL"]] + _split("GEMINI_FALLBACK_MODELS")
    chain = [(k, m) for m in models for k in keys]
    now = time.time()
    ready = [c for c in chain if _cooldown.get(c, 0) <= now]
    return ready or sorted(chain, key=lambda c: _cooldown.get(c, 0))


async def _call(key, model, system, prompt):
    from google.genai import types
    config = types.GenerateContentConfig(
        system_instruction=system + "\nRespond ONLY with valid minified JSON. No markdown, no commentary.",
        response_mime_type="application/json",
    )
    response = await asyncio.wait_for(
        _client(key).aio.models.generate_content(model=model, contents=prompt, config=config),
        float(os.environ.get("AI_CALL_TIMEOUT_SEC", "75")),
    )
    if not response.text:
        raise ValueError("Gemini returned an empty response")
    return _extract_json(response.text)


async def ask_json(system: str, prompt: str, rounds: int = 2, max_attempts: int = None):
    last = None
    for rnd in range(rounds):
        if rnd:
            await asyncio.sleep(2)
        for src, model in _models()[:max_attempts]:
            ATTEMPTS["n"] += 1
            try:
                return await _call(src, model, system, prompt)
            except Exception as e:
                last = e
                msg = str(e) or type(e).__name__
                if "PERMISSION_DENIED" in msg or "API_KEY_INVALID" in msg:
                    _cooldown[(src, model)] = time.time() + 86400
                elif "quota" in msg.lower():
                    _cooldown[(src, model)] = time.time() + 1800
                elif "429" in msg or "RESOURCE_EXHAUSTED" in msg or "RateLimit" in msg:
                    _cooldown[(src, model)] = time.time() + 60
                elif isinstance(e, asyncio.TimeoutError) or "503" in msg or "high demand" in msg:
                    _cooldown[(src, model)] = time.time() + 120
                log.warning("AI call failed on key ...%s / %s: %s", src[-4:], model, msg[:200])
    raise HTTPException(status_code=503, detail="The AI is busy right now (free-tier rate limit). Please try again in a few seconds.") from last


def status():
    keys = _split("GEMINI_API_KEYS") or [os.environ["GEMINI_API_KEY"]]
    models = [os.environ["GEMINI_MODEL"]] + _split("GEMINI_FALLBACK_MODELS")
    now = time.time()
    free = lambda k, m: _cooldown.get((k, m), 0) <= now
    keys_ready = sum(1 for k in keys if free(k, models[0]))
    any_ready = any(free(k, m) for m in models for k in keys)
    waits = [_cooldown.get((k, m), 0) - now for m in models for k in keys]
    state = "ok" if keys_ready else "degraded" if any_ready else "busy"
    return {"state": state, "keys": len(keys), "keys_ready": keys_ready, "retry_in": 0 if any_ready else max(0, int(min(waits)))}


_clients = {}


def _client(key):
    from google import genai
    if key not in _clients:
        _clients[key] = genai.Client(api_key=key)
    return _clients[key]


async def ask_structured(system: str, prompt: str, schema: dict, images=None, rounds: int = 2, thinking: str = None, timeout: float = None, max_attempts: int = None):
    """Gemini structured output (response_json_schema). images: list of (bytes, mime)."""
    from google.genai import types
    contents = [types.Part.from_bytes(data=b, mime_type=m) for b, m in (images or [])] + [prompt]
    cfg = types.GenerateContentConfig(system_instruction=system, response_mime_type="application/json", response_json_schema=schema, temperature=0.4)

    def cfg_for(model):
        if not thinking:
            return cfg
        tc = types.ThinkingConfig(thinking_level=thinking) if "gemini-3" in model else types.ThinkingConfig(thinking_budget=1024)
        return cfg.model_copy(update={"thinking_config": tc})
    last = None
    for rnd in range(rounds):
        if rnd:
            await asyncio.sleep(2)
        for key, model in _models()[:max_attempts]:
            ATTEMPTS["n"] += 1
            try:
                r = await asyncio.wait_for(_client(key).aio.models.generate_content(model=model, contents=contents, config=cfg_for(model)),
                                           timeout or float(os.environ.get("AI_CALL_TIMEOUT_SEC", "75")) * 3)
                return json.loads(r.text)
            except Exception as e:
                last = e
                msg = str(e) or type(e).__name__
                if "PERMISSION_DENIED" in msg or "API_KEY_INVALID" in msg:
                    _cooldown[(key, model)] = time.time() + 86400
                elif "quota" in msg.lower():
                    _cooldown[(key, model)] = time.time() + 1800
                elif "429" in msg or "RESOURCE_EXHAUSTED" in msg:
                    _cooldown[(key, model)] = time.time() + 60
                elif isinstance(e, asyncio.TimeoutError) or "503" in msg or "UNAVAILABLE" in msg:
                    _cooldown[(key, model)] = time.time() + 120
                log.warning("Structured AI call failed on key ...%s / %s: %s", key[-4:], model, msg[:200])
    raise HTTPException(status_code=503, detail="The AI is busy right now (rate limit). Please try again in a few seconds.") from last
