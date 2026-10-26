import asyncio
import time
from types import SimpleNamespace

import ai


def test_ask_json_uses_next_key_after_quota(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEYS", "key-one,key-two")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-test")
    monkeypatch.setenv("GEMINI_FALLBACK_MODELS", "")
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
