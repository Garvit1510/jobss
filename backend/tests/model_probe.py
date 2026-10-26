import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv(Path(__file__).resolve().parents[1] / ".env")


async def one(client, model):
    try:
        response = await client.aio.models.generate_content(
            model=model,
            contents="Say OK",
            config=types.GenerateContentConfig(system_instruction="hi"),
        )
        return model, "OK", (response.text or "")[:20]
    except Exception as e:
        return model, "ERR", str(e)[:400]


async def main():
    keys = [key.strip() for key in os.environ.get("GEMINI_API_KEYS", "").split(",") if key.strip()]
    if not keys:
        raise RuntimeError("Set GEMINI_API_KEYS in backend/.env before running this probe.")
    client = genai.Client(api_key=keys[0])
    models = ["gemini-3-flash-preview", "gemini-3.5-flash", "gemini-3.6-flash",
              "gemini-3.7-flash", "gemini-3.8-flash", "gemini-3.1-pro-preview"]
    for model in models:
        print(*(await one(client, model)))


asyncio.run(main())
