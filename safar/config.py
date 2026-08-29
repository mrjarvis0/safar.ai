"""Config / secrets loader. Owner: mr.jarvis0.

Reads keys from `.env` (never hard-code keys; never commit `.env`).
"""
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass


def get(key: str, default: str = "") -> str:
    return os.getenv(key, default)


LLM_PROVIDER = get("LLM_PROVIDER", "mock")
LLM_API_KEY = get("LLM_API_KEY")
