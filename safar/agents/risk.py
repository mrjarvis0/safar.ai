"""Risk team — weather, safety, health, insurance. Owner: sush.

Weather grounds on the gateway (Open-Meteo forecast + historical archive). Safety
and Health are HIGH-STAKES (readme §11): static demo guidance that ALWAYS carries
a "verify with the official source" disclaimer and is never acted on autonomously.
Visa lives in agents/visa.py.
"""
from ..gateway import gateway, fourcastnet

_GOV = "Demo guidance — verify with your government travel advisory."
_WHO = "Demo guidance — verify with WHO International Travel & Health / a clinic."

# Tiny static demo tables keyed by destination country.
_SAFETY = {
    "Japan": "Very low crime; typhoon season Aug–Oct; carry cash.",
    "France": "Petty theft in tourist areas; strikes possible; keep copies of docs.",
    "United Arab Emirates": "Very safe; respect local laws on dress and conduct.",
    "Thailand": "Watch scams around temples/taxis; road safety on scooters.",
}
_HEALTH = {
    "Japan": "No special vaccines; tap water safe.",
    "France": "Routine vaccines; tap water safe.",
    "United Arab Emirates": "Routine vaccines; extreme summer heat — hydrate.",
    "Thailand": "Hep A/typhoon; avoid tap water; mosquito precautions.",
}


def _country(state):
    return (state.grounding.get("country")
            or gateway.wikidata_entity(state.trip["destination"]).get("country"))


def weather(state) -> dict:
    geo = gateway.osm_geocode(state.trip["destination"])
    forecast = "unavailable"
    temp_max_c = temp_min_c = rain_prob_max = None      # structured — feeds §1b food rule
    if geo.get("lat"):
        d = gateway.get_weather(geo["lat"], geo["lon"]).get("daily", {})
        tmax = d.get("temperature_2m_max") or []
        tmin = d.get("temperature_2m_min") or []
        pprob = d.get("precipitation_probability_max") or []
        if tmax:
            temp_max_c = round(max(tmax))
            temp_min_c = round(min(tmin)) if tmin else None
            rain_prob_max = max(pprob) if pprob else None
            forecast = (f"next 7d {min(tmax):.0f}–{max(tmax):.0f}°C, "
                        f"max rain prob {rain_prob_max or 0}%")
    seas = state.grounding.get("seasonality") or {}

    # Optional AI grounding: NVIDIA Earth-2 FourCastNet (self-hosted NIM). Adds no
    # latency when FOURCASTNET_URL is unset; falls back to Open-Meteo otherwise.
    fcn = fourcastnet.status()
    ai_status = ("reachable" if fcn.get("reachable")
                 else ("configured" if fcn.get("configured") else "not-deployed"))
    sources = ["open-meteo:forecast", "open-meteo:archive"]
    if fcn.get("reachable"):
        sources.append("nvidia:fourcastnet")

    return {"forecast_7d": forecast,
            "temp_max_c": temp_max_c, "temp_min_c": temp_min_c,
            "rain_prob_max": rain_prob_max,
            "seasonality": seas,
            "ai_model": {"provider": "nvidia", "model": "fourcastnet",
                         "status": ai_status, "endpoint": fcn.get("url")},
            "sources": sources}


def safety(state) -> dict:
    country = _country(state)
    return {"country": country,
            "advisory": _SAFETY.get(country, "Exercise normal caution."),
            "disclaimer": _GOV}


def health(state) -> dict:
    country = _country(state)
    return {"country": country,
            "guidance": _HEALTH.get(country, "Check routine vaccines; verify water safety."),
            "disclaimer": _WHO}


def insurance(state) -> dict:
    days = state.trip.get("days", 5)
    outdoor = "nature" in state.trip.get("interests", [])
    cover = ["medical + evacuation", "trip cancellation", "baggage/theft"]
    if outdoor:
        cover.append("adventure-sports rider")
    if days >= 10:
        cover.append("longer-stay medical top-up")
    return {"recommended_cover": cover,
            "note": "Map trip risk -> coverage; buy before departure."}


def run(state) -> dict:
    return {"weather": weather(state), "safety": safety(state),
            "health": health(state), "insurance": insurance(state)}
