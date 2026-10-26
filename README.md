# JOBLENSAI-PVT

## AI provider configuration

The backend tries Groq first and falls back to Gemini when the Groq request fails. Configure these variables on the backend host (for example, Render):

- `GROQ_API_KEY`: Groq API key.
- `GROQ_MODEL`: Groq chat-completions model name.
- `GROQ_VISION_MODEL` (optional): vision-capable Groq model for image-based requests; defaults to `GROQ_MODEL`.
- `GEMINI_API_KEYS` (or legacy `GEMINI_API_KEY`): Gemini API key(s), comma-separated when using the plural variable.
- `GEMINI_MODEL` and optional `GEMINI_FALLBACK_MODELS`: Gemini primary and fallback model names.

Keep provider API keys on the backend host only. Do not put them in Netlify frontend variables or commit them to the repository. The `/api/ai/status` endpoint reports configuration and local cooldown readiness; it does not validate keys with live provider requests.