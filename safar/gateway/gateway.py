"""Tool Gateway — all external API calls go through here. Owner: adi.

Real FREE, keyless APIs for weather / currency / geocoding / country info, plus
mock JSON for flights/hotels/activities (no free priced source). Every call is
wrapped in try/except + a short timeout + an in-memory cache so the live demo
can never crash. Keyed APIs (if added) read from safar.config (from .env).
"""
import json
import pathlib
import requests

_DATA = pathlib.Path(__file__).resolve().parents[2] / "data" / "tokyo.json"
_CACHE: dict = {}
_TIMEOUT = 10


def _mock(kind: str) -> list:
    data = json.loads(_DATA.read_text(encoding="utf-8"))
    return data.get(kind, [])


def _get(url: str, params: dict | None = None):
    key = url + json.dumps(params or {}, sort_keys=True)
    if key in _CACHE:
        return _CACHE[key]
    r = requests.get(url, params=params, timeout=_TIMEOUT)
    r.raise_for_status()
    _CACHE[key] = r.json()
    return _CACHE[key]


def _post(url: str, body: dict):
    key = "POST" + url + json.dumps(body, sort_keys=True)
    if key in _CACHE:
        return _CACHE[key]
    r = requests.post(url, json=body, timeout=_TIMEOUT)
    r.raise_for_status()
    _CACHE[key] = r.json()
    return _CACHE[key]


# ---- Flights / hotels / activities: mock (no free priced source) -------------
def get_flights(trip: dict) -> list:
    # TODO(adi): plug a real flight API (e.g. Amadeus) here; keep _mock as fallback.
    return _mock("flights")


def get_hotels(trip: dict) -> list:
    return _mock("hotels")


def get_activities(trip: dict) -> list:
    return _mock("activities")


# ---- Real, keyless enrichment APIs ------------------------------------------
def geocode(city: str) -> dict:
    """City -> {lat, lon, country}. Open-Meteo geocoding (no key)."""
    try:
        d = _get("https://geocoding-api.open-meteo.com/v1/search",
                 {"name": city, "count": 1})
        r = (d.get("results") or [{}])[0]
        return {"lat": r.get("latitude"), "lon": r.get("longitude"),
                "country": r.get("country")}
    except Exception:
        return {"lat": 35.68, "lon": 139.65, "country": "Japan"}  # Tokyo fallback


def get_weather(lat: float, lon: float) -> dict:
    """7-day daily forecast. Open-Meteo (no key)."""
    try:
        return _get("https://api.open-meteo.com/v1/forecast", {
            "latitude": lat, "longitude": lon,
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
            "forecast_days": 7, "timezone": "auto"})
    except Exception:
        return {}


def convert_currency(amount: float, frm: str = "INR", to: str = "JPY") -> float:
    """Real FX via Frankfurter (no key). Returns the input amount on failure."""
    try:
        d = _get("https://api.frankfurter.app/latest", {"from": frm, "to": to})
        return round(amount * d["rates"][to], 2)
    except Exception:
        return amount


def country_info(name: str) -> dict:
    """Currency + capital for a country. countriesnow.space (no key)."""
    out: dict = {"name": name}
    base = "https://countriesnow.space/api/v0.1/countries"
    try:
        d = _post(f"{base}/currency", {"country": name}).get("data", {})
        out["currency"] = d.get("currency")
        out["iso2"] = d.get("iso2")
    except Exception:
        pass
    try:
        d = _post(f"{base}/capital", {"country": name}).get("data", {})
        out["capital"] = d.get("capital")
    except Exception:
        pass
    return out
