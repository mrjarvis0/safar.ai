"""Discovery team — destination, local expert, food, events. Owner: adi.

Grounded on the free/keyless sources already wired in the gateway (Wikidata,
Wikivoyage, OpenStreetMap). Every output carries its sources for observability.
"""
from ..gateway import gateway


def destination(state) -> dict:
    dest = state.trip["destination"]
    wd = gateway.wikidata_entity(dest)
    wv = gateway.wikivoyage(dest)
    return {
        "name": dest, "country": wd.get("country"), "label": wd.get("label"),
        "description": wd.get("description"),
        "summary": (wv.get("summary") or "")[:300], "url": wv.get("url"),
        "sources": [f"wikidata:{wd.get('qid')}", "wikivoyage"],
    }


def local_expert(state) -> dict:
    dest = state.trip["destination"]
    geo = gateway.osm_geocode(dest)
    picks = []
    if geo.get("lat"):
        picks = [p["name"] for p in
                 gateway.osm_pois(geo["lat"], geo["lon"], "attraction", 4000, 8)][:6]
    return {"neighbourhood_picks": picks, "sources": ["osm:overpass#attraction"]}


def _food_weather_hint(state) -> dict:
    """Weather → food rule (§1b): rain→hot/soupy, heat→light, cold→hearty.

    Reads the Risk team's live forecast (risk.weather → temp/rain) when present,
    else the grounded seasonality; degrades to a neutral hint if neither is there.
    """
    wx = (getattr(state, "risk", None) or {}).get("weather") or {}
    seas = (getattr(state, "grounding", None) or {}).get("seasonality") or {}
    tmax = wx.get("temp_max_c")
    if tmax is None:
        tmax = seas.get("avg_high_c")
    rain = wx.get("rain_prob_max")
    rainy_days = seas.get("rainy_days")

    wet = (rain is not None and rain >= 50) or (rainy_days is not None and rainy_days >= 8)
    if wet:
        return {"theme": "warm & soupy",
                "suggestions": ["ramen / noodle soup", "hot pot", "broths & stews",
                                "hot chai / coffee"],
                "reason": "rain likely" + (f" (~{rain}% chance)" if rain is not None
                                           else "") + " — go for hot, soupy dishes",
                "driver": "weather"}
    if tmax is not None and tmax >= 30:
        return {"theme": "light & cooling",
                "suggestions": ["cold noodles / salads", "grilled seafood",
                                "fresh fruit", "chilled drinks"],
                "reason": f"hot days (~{tmax}°C) — keep meals light and cooling",
                "driver": "weather"}
    if tmax is not None and tmax <= 12:
        return {"theme": "hearty & warm",
                "suggestions": ["stews & curries", "grills / BBQ", "baked dishes",
                                "hot desserts"],
                "reason": f"cold spell (~{tmax}°C) — lean into warm, hearty food",
                "driver": "weather"}
    return {"theme": "balanced",
            "suggestions": ["local specialities", "street-food sampler"],
            "reason": ("mild weather — anything goes" if tmax is not None
                       else "weather signal unavailable — general picks"),
            "driver": "weather" if tmax is not None else "none"}


def food(state) -> dict:
    dest = state.trip["destination"]
    geo = gateway.osm_geocode(dest)
    spots = []
    if geo.get("lat"):
        spots = [p["name"] for p in
                 gateway.osm_pois(geo["lat"], geo["lon"], "food", 2500, 8)][:6]
    return {"food_spots": spots, "weather_pick": _food_weather_hint(state),
            "diet_note": "filter by cuisine/diet at booking",
            "sources": ["osm:overpass#food", "open-meteo:forecast"]}


def events(state) -> dict:
    # Honest gap: no free events feed wired yet (Ticketmaster/PredictHQ need keys).
    return {"status": "unavailable", "items": [],
            "note": "No free events source wired (Phase 2: keyed Events API)."}


def run(state) -> dict:
    return {"destination": destination(state), "local_expert": local_expert(state),
            "food": food(state), "events": events(state)}
