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


# --- LLM (NVIDIA NIM, OpenAI-compatible) ---
LLM_PROVIDER = get("LLM_PROVIDER", "mock")          # nvidia | mock
NVIDIA_API_KEY = get("NVIDIA_API_KEY") or get("LLM_API_KEY")
NVIDIA_BASE_URL = get("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
NVIDIA_MODEL = get("NVIDIA_MODEL", "meta/llama-3.3-70b-instruct")

# --- Optional keyed data APIs (the keyless ones need nothing) ---
AMADEUS_CLIENT_ID = get("AMADEUS_CLIENT_ID")
AMADEUS_CLIENT_SECRET = get("AMADEUS_CLIENT_SECRET")
