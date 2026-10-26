import os
import json
import re
import base64
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
    keys = _split("GEMINI_API_KEYS") or ([os.environ["GEMINI_API_KEY"]] if os.environ.get("GEMINI_API_KEY") else [])
    models = ([os.environ["GEMINI_MODEL"]] if os.environ.get("GEMINI_MODEL") else []) + _split("GEMINI_FALLBACK_MODELS")
    chain = [(k, m) for m in models for k in keys]
    now = time.time()
    ready = [c for c in chain if _cooldown.get(c, 0) <= now]
    return ready or sorted(chain, key=lambda c: _cooldown.get(c, 0))


def _attempts(images=None):
    attempts = []
    groq_key = os.environ.get("GROQ_API_KEY", "").strip()
    if groq_key:
        model = os.environ.get("GROQ_VISION_MODEL" if images else "GROQ_MODEL", "").strip()
        if not model and images:
            model = os.environ.get("GROQ_MODEL", "").strip()
        if model:
            attempts.append(("groq", groq_key, model))
    attempts.extend(("gemini", key, model) for key, model in _models())
    return attempts


def _limit_attempts(attempts, max_attempts):
    if max_attempts is None:
        return attempts
    limited = attempts[:max_attempts]
    if any(provider == "groq" for provider, _, _ in limited) and not any(
        provider == "gemini" for provider, _, _ in limited
    ):
        fallback = next((attempt for attempt in attempts if attempt[0] == "gemini"), None)
        if fallback:
            limited.append(fallback)
    return limited


def _cooldown_key(provider, key, model):
    return (key, model) if provider == "gemini" else (provider, key, model)


def _record_failure(provider, key, model, error):
    message = str(error) or type(error).__name__
    lower = message.lower()
    status = getattr(error, "status_code", None)
    cooldown = 0
    if status in (401, 403) or "permission_denied" in lower or "api_key_invalid" in lower or "invalid api key" in lower:
        cooldown = 86400
    elif "quota" in lower or "daily limit" in lower or "per-day" in lower:
        cooldown = 1800
    elif status == 429 or "429" in lower or "resource_exhausted" in lower or "ratelimit" in lower or "rate limit" in lower:
        cooldown = 60
    elif isinstance(error, asyncio.TimeoutError) or (status is not None and status >= 500) or "503" in lower or "unavailable" in lower or "high demand" in lower:
        cooldown = 120
    elif status == 404 or "model not found" in lower or "no longer available" in lower:
        cooldown = 86400
    if cooldown:
        _cooldown[_cooldown_key(provider, key, model)] = time.time() + cooldown
    identity = f"key ...{key[-4:]}" if provider == "gemini" else "Groq"
    log.warning("AI call failed on %s / %s: %s", identity, model, message[:200])


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


def _groq_client(key):
    if key not in _groq_clients:
        from openai import AsyncOpenAI
        _groq_clients[key] = AsyncOpenAI(api_key=key, base_url="https://api.groq.com/openai/v1")
    return _groq_clients[key]


async def _call_groq(key, model, system, prompt, schema=None, images=None, timeout=None):
    system_message = system
    if schema is not None:
        system_message += "\nReturn a JSON object that follows this schema:\n" + json.dumps(schema, separators=(",", ":"))
    system_message += "\nRespond ONLY with valid JSON. Do not use markdown or commentary."
    user_content = prompt
    if images:
        user_content = [{"type": "text", "text": prompt}]
        for data, mime in images:
            encoded = base64.b64encode(data).decode("ascii")
            user_content.append({
                "type": "image_url",
                "image_url": {"url": f"data:{mime};base64,{encoded}"},
            })
    response = await asyncio.wait_for(
        _groq_client(key).chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_content},
            ],
            response_format={"type": "json_object"},
            temperature=0.4,
            timeout=timeout or float(os.environ.get("AI_CALL_TIMEOUT_SEC", "75")),
        ),
        timeout or float(os.environ.get("AI_CALL_TIMEOUT_SEC", "75")),
    )
    content = response.choices[0].message.content
    if not content:
        raise ValueError("Groq returned an empty response")
    result = _extract_json(content)
    if schema is not None:
        import jsonschema
        jsonschema.validate(result, schema)
    return result


async def ask_json(system: str, prompt: str, rounds: int = 2, max_attempts: int = None):
    last = None
    groq_attempted = False
    for rnd in range(rounds):
        if rnd:
            await asyncio.sleep(2)
        attempts = _limit_attempts(_attempts(), max_attempts)
        for provider, key, model in attempts:
            if provider == "groq" and groq_attempted:
                continue
            if provider == "groq":
                groq_attempted = True
            ATTEMPTS["n"] += 1
            try:
                log.info("AI request attempting %s / %s", provider.upper(), model)
                if provider == "groq":
                    result = await _call_groq(key, model, system, prompt)
                else:
                    result = await _call(key, model, system, prompt)
                log.info("AI request succeeded using %s / %s", provider.upper(), model)
                return result
            except Exception as e:
                last = e
                _record_failure(provider, key, model, e)
    raise HTTPException(status_code=503, detail="The AI is busy right now (free-tier rate limit). Please try again in a few seconds.") from last


def status():
    gemini_keys = _split("GEMINI_API_KEYS") or ([os.environ["GEMINI_API_KEY"]] if os.environ.get("GEMINI_API_KEY") else [])
    gemini_models = ([os.environ["GEMINI_MODEL"]] if os.environ.get("GEMINI_MODEL") else []) + _split("GEMINI_FALLBACK_MODELS")
    now = time.time()
    groq_key = os.environ.get("GROQ_API_KEY", "").strip()
    groq_model = os.environ.get("GROQ_MODEL", "").strip()
    groq_configured = bool(groq_key and groq_model)
    groq_cooldown_until = _cooldown.get(("groq", groq_key, groq_model), 0)
    groq_ready = groq_configured
    groq_cooling_down = bool(groq_configured and groq_cooldown_until > now)
    gemini_ready = sum(1 for key in gemini_keys for model in gemini_models if _cooldown.get((key, model), 0) <= now)
    gemini_configured = bool(gemini_keys and gemini_models)
    any_ready = groq_ready or gemini_ready > 0
    waits = []
    if groq_cooling_down:
        waits.append(groq_cooldown_until - now)
    waits.extend(_cooldown.get((key, model), 0) - now for key in gemini_keys for model in gemini_models)
    retry_in = 0 if any_ready else max(0, int(min(waits))) if waits else 0
    state = "ok" if groq_ready or (not groq_configured and gemini_ready) else "degraded" if any_ready else "busy"
    keys_ready = int(groq_ready) if groq_configured else gemini_ready
    return {
        "state": state,
        "keys": len(gemini_keys),
        "keys_ready": keys_ready,
        "retry_in": retry_in,
        "providers": {
            "groq": {"configured": groq_configured, "ready": groq_ready, "cooling_down": groq_cooling_down, "model": groq_model or None},
            "gemini": {"configured": gemini_configured, "ready": gemini_ready, "keys": len(gemini_keys)},
        },
    }


_clients = {}
_groq_clients = {}


def _client(key):
    from google import genai
    if key not in _clients:
        _clients[key] = genai.Client(api_key=key)
    return _clients[key]


async def ask_structured(system: str, prompt: str, schema: dict, images=None, rounds: int = 2, thinking: str = None, timeout: float = None, max_attempts: int = None):
    """Generate schema-shaped JSON, using Groq first and Gemini as fallback."""
    from google.genai import types
    contents = [types.Part.from_bytes(data=b, mime_type=m) for b, m in (images or [])] + [prompt]
    cfg = types.GenerateContentConfig(system_instruction=system, response_mime_type="application/json", response_json_schema=schema, temperature=0.4)

    def cfg_for(model):
        if not thinking:
            return cfg
        tc = types.ThinkingConfig(thinking_level=thinking) if "gemini-3" in model else types.ThinkingConfig(thinking_budget=1024)
        return cfg.model_copy(update={"thinking_config": tc})
    last = None
    groq_attempted = False
    for rnd in range(rounds):
        if rnd:
            await asyncio.sleep(2)
        attempts = _limit_attempts(_attempts(images=images), max_attempts)
        for provider, key, model in attempts:
            if provider == "groq" and groq_attempted:
                continue
            if provider == "groq":
                groq_attempted = True
            ATTEMPTS["n"] += 1
            try:
                if provider == "groq":
                    log.info("AI request attempting GROQ / %s", model)
                    result = await _call_groq(key, model, system, prompt, schema=schema, images=images,
                                              timeout=timeout or float(os.environ.get("AI_CALL_TIMEOUT_SEC", "75")) * 3)
                else:
                    log.info("AI request attempting GEMINI / %s", model)
                    r = await asyncio.wait_for(_client(key).aio.models.generate_content(model=model, contents=contents, config=cfg_for(model)),
                                               timeout or float(os.environ.get("AI_CALL_TIMEOUT_SEC", "75")) * 3)
                    if not r.text:
                        raise ValueError("Gemini returned an empty response")
                    result = json.loads(r.text)
                log.info("AI request succeeded using %s / %s", provider.upper(), model)
                return result
            except Exception as e:
                last = e
                _record_failure(provider, key, model, e)
    raise HTTPException(status_code=503, detail="The AI is busy right now (rate limit). Please try again in a few seconds.") from last
