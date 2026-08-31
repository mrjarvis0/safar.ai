"""Seasonality agent — peak/rainy/dry season, crowd levels (readme §6).

Wraps the gateway's historical weather archive (Open-Meteo, free/keyless) to
provide seasonality grounding: is it peak season, rainy, cold?  Also flags known
closure windows and crowd expectations.  Deterministic (no LLM).
"""
from ..gateway import gateway


# Very rough crowd/closure heuristics by destination-month.  These are NOT
# ground truth — see the disclaimer.  Production would pull from government
# tourism open-data portals (readme §16, priority #8).
_CROWD = {
    ("Japan", 3): ("peak", "Cherry blossom season — very crowded, book early."),
    ("Japan", 4): ("peak", "Cherry blossom tail + Golden Week start."),
    ("Japan", 10): ("peak", "Autumn colours — popular but manageable."),
    ("Japan", 11): ("moderate", "Late autumn, pleasant; shoulder pricing."),
    ("Japan", 7): ("high", "Summer + Tanabata festivals; hot and humid."),
    ("France", 7): ("peak", "Summer holidays — Paris busy, Provence packed."),
    ("France", 8): ("peak", "Parisians leave; tourists fill the gap."),
    ("France", 12): ("moderate", "Christmas markets; cold but festive."),
    ("Thailand", 12): ("peak", "Dry season starts — ideal beach weather."),
    ("Thailand", 1): ("peak", "High season; cool and dry."),
    ("Thailand", 8): ("low", "Rainy season — cheaper, fewer tourists."),
    ("United Arab Emirates", 12): ("peak", "Cool desert weather — peak tourism."),
    ("United Arab Emirates", 7): ("low", "Extreme heat (>40 °C); indoor-only."),
}


def run(state) -> dict:
    """Return seasonality + crowd + closure guidance for the trip month."""
    dest = state.trip["destination"]
    month = state.trip.get("travel_month", 11)
    country = (state.grounding or {}).get("country")

    # Historical weather from the archive (free, keyless)
    seas = (state.grounding or {}).get("seasonality") or {}
    if not seas:
        geo = gateway.osm_geocode(dest)
        if geo.get("lat"):
            seas = gateway.seasonality(geo["lat"], geo["lon"], month)

    # Crowd heuristic
    crowd_key = (country, month) if country else None
    crowd_info = _CROWD.get(crowd_key, ("unknown", "No crowd data on file."))

    # Rainy-season flag
    rainy = seas.get("rainy_days", 0) >= 8
    cold = (seas.get("avg_low_c") or 99) < 10

    return {
        "month": month,
        "seasonality": seas,
        "crowd_level": crowd_info[0],
        "crowd_note": crowd_info[1],
        "rainy_season": rainy,
        "cold_season": cold,
        "closure_note": "Check local holiday closures for this period.",
        "sources": ["open-meteo:archive", "static:crowd-heuristic"],
    }
