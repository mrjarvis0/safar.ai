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
NVIDIA_MODEL = get("NVIDIA_MODEL", "nvidia/nemotron-3.5-lightning-30b-a3b")

# --- Optional keyed data APIs (the keyless ones need nothing) ---
AMADEUS_CLIENT_ID = get("AMADEUS_CLIENT_ID")
AMADEUS_CLIENT_SECRET = get("AMADEUS_CLIENT_SECRET")
# Amadeus Self-Service: use the free test host by default; switch to
# https://api.amadeus.com once you have production keys.
AMADEUS_BASE_URL = get("AMADEUS_BASE_URL", "https://test.api.amadeus.com")
ORIGIN_IATA = get("ORIGIN_IATA", "DEL")            # traveler's home airport

# Public transport (GTFS): a static feed .zip URL (per-agency, free). Optional.
GTFS_FEED_URL = get("GTFS_FEED_URL", "")
# Google Places (paid): premium POI/hours over OSM. Optional.
GOOGLE_PLACES_API_KEY = get("GOOGLE_PLACES_API_KEY")

# --- NVIDIA Earth-2 FourCastNet (AI weather; SELF-HOSTED NIM, deploy-only) ---
# FourCastNet is not a hosted API — deploy the NIM container (GPU) and set its
# URL here (e.g. http://localhost:8000). Blank = disabled -> fall back to
# Open-Meteo. The key defaults to NVIDIA_API_KEY (same nvapi credential).
FOURCASTNET_URL = get("FOURCASTNET_URL", "")
FOURCASTNET_API_KEY = get("FOURCASTNET_API_KEY") or NVIDIA_API_KEY
