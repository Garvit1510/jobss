import asyncio
import time
from types import SimpleNamespace

import ai


def test_ask_json_uses_next_key_after_quota(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEYS", "key-one,key-two")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-test")
    monkeypatch.setenv("GEMINI_FALLBACK_MODELS", "")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_MODEL", raising=False)
    ai._cooldown.clear()
    calls = []

    async def fake_call(key, model, system, prompt):
        calls.append(key)
        if key == "key-one":
            raise RuntimeError("429 RESOURCE_EXHAUSTED: quota exceeded")
        return {"ok": True}

    monkeypatch.setattr(ai, "_call", fake_call)
    result = asyncio.run(ai.ask_json("system", "prompt", rounds=1))

    assert result == {"ok": True}
    assert calls == ["key-one", "key-two"]
    assert ai._cooldown[("key-one", "gemini-test")] > time.time()


def test_call_uses_google_genai_json_mode(monkeypatch):
    captured = {}

    class FakeModels:
        async def generate_content(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(text='{"ok":true}')

    monkeypatch.setattr(ai, "_client", lambda key: SimpleNamespace(
        aio=SimpleNamespace(models=FakeModels())
    ))

    result = asyncio.run(ai._call("test-key", "gemini-test", "system", "prompt"))

    assert result == {"ok": True}
    assert captured["model"] == "gemini-test"
    assert captured["contents"] == "prompt"
    assert captured["config"].response_mime_type == "application/json"


def test_ask_json_uses_groq_before_gemini(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "groq-secret")
    monkeypatch.setenv("GROQ_MODEL", "llama-test")
    monkeypatch.setenv("GEMINI_API_KEYS", "gemini-secret")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-test")
    monkeypatch.setenv("GEMINI_FALLBACK_MODELS", "")
    ai._cooldown.clear()
    calls = []

    async def fake_groq(key, model, system, prompt):
        calls.append(("groq", key, model))
        return {"provider": "groq"}

    async def fake_gemini(key, model, system, prompt):
        calls.append(("gemini", key, model))
        return {"provider": "gemini"}

    monkeypatch.setattr(ai, "_call_groq", fake_groq)
    monkeypatch.setattr(ai, "_call", fake_gemini)

    result = asyncio.run(ai.ask_json("system", "prompt", rounds=1))

    assert result == {"provider": "groq"}
    assert calls == [("groq", "groq-secret", "llama-test")]


def test_ask_json_falls_back_to_gemini_when_groq_is_rate_limited(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "groq-secret")
    monkeypatch.setenv("GROQ_MODEL", "llama-test")
    monkeypatch.setenv("GEMINI_API_KEYS", "gemini-secret")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-test")
    monkeypatch.setenv("GEMINI_FALLBACK_MODELS", "")
    ai._cooldown.clear()
    calls = []

    async def fail_groq(key, model, system, prompt):
        calls.append("groq")
        raise RuntimeError("429 rate limit exceeded")

    async def succeed_gemini(key, model, system, prompt):
        calls.append("gemini")
        return {"provider": "gemini"}

    monkeypatch.setattr(ai, "_call_groq", fail_groq)
    monkeypatch.setattr(ai, "_call", succeed_gemini)

    result = asyncio.run(ai.ask_json("system", "prompt", rounds=1))

    assert result == {"provider": "gemini"}
    assert calls == ["groq", "gemini"]
    assert ("groq", "groq-secret", "llama-test") in ai._cooldown


def test_groq_failure_still_reaches_gemini_with_single_attempt_limit(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "groq-secret")
    monkeypatch.setenv("GROQ_MODEL", "llama-test")
    monkeypatch.setenv("GEMINI_API_KEYS", "gemini-secret")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-test")
    monkeypatch.setenv("GEMINI_FALLBACK_MODELS", "")
    ai._cooldown.clear()
    calls = []

    async def fail_groq(key, model, system, prompt):
        calls.append("groq")
        raise RuntimeError("request failed")

    async def succeed_gemini(key, model, system, prompt):
        calls.append("gemini")
        return {"provider": "gemini"}

    monkeypatch.setattr(ai, "_call_groq", fail_groq)
    monkeypatch.setattr(ai, "_call", succeed_gemini)

    result = asyncio.run(ai.ask_json("system", "prompt", rounds=2, max_attempts=1))

    assert result == {"provider": "gemini"}
    assert calls == ["groq", "gemini"]


def test_groq_is_attempted_first_even_during_previous_cooldown(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "groq-secret")
    monkeypatch.setenv("GROQ_MODEL", "llama-test")
    monkeypatch.setenv("GEMINI_API_KEYS", "gemini-secret")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-test")
    monkeypatch.setenv("GEMINI_FALLBACK_MODELS", "")
    ai._cooldown.clear()
    ai._cooldown[("groq", "groq-secret", "llama-test")] = time.time() + 120
    calls = []

    async def succeed_groq(key, model, system, prompt):
        calls.append("groq")
        return {"provider": "groq"}

    async def succeed_gemini(key, model, system, prompt):
        calls.append("gemini")
        return {"provider": "gemini"}

    monkeypatch.setattr(ai, "_call_groq", succeed_groq)
    monkeypatch.setattr(ai, "_call", succeed_gemini)

    result = asyncio.run(ai.ask_json("system", "prompt", rounds=1))

    assert result == {"provider": "groq"}
    assert calls == ["groq"]
    assert ai.status()["providers"]["groq"]["cooling_down"] is True


def test_structured_groq_call_receives_schema_and_image(monkeypatch):
    captured = {}

    class FakeCompletions:
        async def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='{"ok":true}'))])

    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions()))
    monkeypatch.setattr(ai, "_groq_client", lambda key: fake_client)
    schema = {"type": "object", "required": ["ok"], "properties": {"ok": {"type": "boolean"}}}

    result = asyncio.run(ai._call_groq(
        "groq-secret", "vision-test", "system", "read image",
        schema=schema, images=[(b"image-bytes", "image/png")],
    ))

    assert result == {"ok": True}
    assert captured["response_format"] == {"type": "json_object"}
    assert "schema" in captured["messages"][0]["content"]
    assert captured["messages"][1]["content"][1]["image_url"]["url"].startswith("data:image/png;base64,")


def test_ask_structured_falls_back_to_gemini_after_groq_failure(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "groq-secret")
    monkeypatch.setenv("GROQ_MODEL", "llama-test")
    monkeypatch.setenv("GEMINI_API_KEYS", "gemini-secret")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-test")
    monkeypatch.setenv("GEMINI_FALLBACK_MODELS", "")
    ai._cooldown.clear()
    calls = []

    async def fail_groq(key, model, system, prompt, **kwargs):
        calls.append("groq")
        raise RuntimeError("429 rate limit exceeded")

    class FakeModels:
        async def generate_content(self, **kwargs):
            calls.append("gemini")
            return SimpleNamespace(text='{"ok":true}')

    monkeypatch.setattr(ai, "_call_groq", fail_groq)
    monkeypatch.setattr(ai, "_client", lambda key: SimpleNamespace(
        aio=SimpleNamespace(models=FakeModels())
    ))

    result = asyncio.run(ai.ask_structured(
        "system", "prompt", {"type": "object", "properties": {"ok": {"type": "boolean"}}},
        rounds=1,
    ))

    assert result == {"ok": True}
    assert calls == ["groq", "gemini"]


def test_status_reports_groq_primary_and_gemini_fallback(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "groq-secret")
    monkeypatch.setenv("GROQ_MODEL", "llama-test")
    monkeypatch.setenv("GEMINI_API_KEYS", "gemini-one,gemini-two")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-test")
    monkeypatch.setenv("GEMINI_FALLBACK_MODELS", "")
    ai._cooldown.clear()

    result = ai.status()

    assert result["state"] == "ok"
    assert result["keys_ready"] == 1
    assert result["providers"]["groq"] == {
        "configured": True,
        "ready": True,
        "cooling_down": False,
        "model": "llama-test",
    }
    assert result["providers"]["gemini"] == {"configured": True, "ready": 2, "keys": 2}
