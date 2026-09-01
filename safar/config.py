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

# --- Live flight status (Phase 2b): delays feed the On-Trip Copilot re-plan ---
# Free tiers, keyed. AviationStack is primary; AeroDataBox is the fallback. Leave
# both blank to use the built-in demo status (so the flow always works offline).
AVIATIONSTACK_API_KEY = get("AVIATIONSTACK_API_KEY")            # https://aviationstack.com (free: 100/mo)
AVIATIONSTACK_BASE_URL = get("AVIATIONSTACK_BASE_URL", "http://api.aviationstack.com/v1")
AERODATABOX_API_KEY = get("AERODATABOX_API_KEY")               # RapidAPI free tier
AERODATABOX_HOST = get("AERODATABOX_HOST", "aerodatabox.p.rapidapi.com")

# --- Routing (Phase 2c): OSRM, FREE + KEYLESS public server ---
# Multiple road routes with fallback (taxi/bus can't reach -> next route). The
# public demo server is car-only + rate-limited; self-host for bike/foot profiles.
OSRM_BASE_URL = get("OSRM_BASE_URL", "https://router.project-osrm.org")

# --- NVIDIA Earth-2 FourCastNet (AI weather; SELF-HOSTED NIM, deploy-only) ---
# FourCastNet is not a hosted API — deploy the NIM container (GPU) and set its
# URL here (e.g. http://localhost:8000). Blank = disabled -> fall back to
# Open-Meteo. The key defaults to NVIDIA_API_KEY (same nvapi credential).
FOURCASTNET_URL = get("FOURCASTNET_URL", "")
FOURCASTNET_API_KEY = get("FOURCASTNET_API_KEY") or NVIDIA_API_KEY

# ============================================================================
# Phase 3 — real transactions + production (readme §13, §15). Everything below
# is OPTIONAL: blank keys keep Safar in safe simulate/mock mode. Nothing charges
# money or books a real seat until you supply your own keys AND a human confirms
# at the payment step — capture is NEVER autonomous (readme §10/§13).
# ============================================================================

# --- Booking mode: 'simulate' (default, no external calls) | 'live' ---------
# 'live' lets the saga call the real flight-booking + payment-order APIs, but
# still hands the actual card payment (capture) to a human. Requires the keys
# below; falls back to 'simulate' if they are missing.
SAFAR_BOOKING_MODE = get("SAFAR_BOOKING_MODE", "simulate").strip().lower()

# --- Payment PSP (order creation only; capture/refund are human-gated) -------
# Provider: 'mock' (default) | 'razorpay' | 'stripe'. Safar creates a pending
# payment ORDER server-side (this does NOT charge anyone) and hands the checkout
# to the human. Safar never sees, stores, or enters card data (PCI stays out of
# scope, readme §13).
PAYMENT_PROVIDER = get("PAYMENT_PROVIDER", "mock").strip().lower()
RAZORPAY_KEY_ID = get("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = get("RAZORPAY_KEY_SECRET")
STRIPE_SECRET_KEY = get("STRIPE_SECRET_KEY")
STRIPE_PUBLISHABLE_KEY = get("STRIPE_PUBLISHABLE_KEY")

# --- Ground transport inventory (bus/train) — partner/paid APIs --------------
# Blank = deterministic mock inventory (demo never breaks). Set a base URL + key
# to wire a real aggregator (RedBus-class bus API, IRCTC-class rail aggregator).
REDBUS_API_KEY = get("REDBUS_API_KEY")
REDBUS_BASE_URL = get("REDBUS_BASE_URL", "")
RAIL_API_KEY = get("RAIL_API_KEY")
RAIL_BASE_URL = get("RAIL_BASE_URL", "")

# --- Production data layer (readme §15) — swap the stand-ins in when scaling --
# DATABASE_URL: postgres DSN (postgresql://user:pass@host:5432/safar). Blank =
# local SQLite (data/safar.db). REDIS_URL: redis://host:6379/0 for the shared
# gateway cache / rate-limit; blank = in-process dict.
DATABASE_URL = get("DATABASE_URL", "")
REDIS_URL = get("REDIS_URL", "")


def booking_mode() -> str:
    """Effective booking mode. 'live' only when explicitly set AND at least one
    real booking credential is present; otherwise 'simulate' (safe default)."""
    if SAFAR_BOOKING_MODE != "live":
        return "simulate"
    has_pay = PAYMENT_PROVIDER in ("razorpay", "stripe")
    has_air = bool(AMADEUS_CLIENT_ID and AMADEUS_CLIENT_SECRET)
    return "live" if (has_pay or has_air) else "simulate"
