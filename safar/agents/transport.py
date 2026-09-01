"""Transport agent — real road routes with fallback (readme §6, §2c).

For the day's key legs (hotel -> activities) this asks OSRM (free, keyless) for
the driving route AND its alternatives, so if the primary route can't be used
(closure, no through-path) the traveler/Copilot already has the next one. If OSRM
itself is unreachable it degrades to a straight-line time/distance estimate — a
leg is never left without an answer, keeping the live demo crash-proof.

Deterministic apart from the live OSRM lookup; every call is guarded.
"""
from ..gateway import gateway
from ..tools.distance import km_between

CITY_KMH = 18.0          # matches engine.itinerary door-to-door city speed
MAX_LEGS = 4             # keep public-OSRM usage light + the demo fast


def _pt(x: dict):
    lat, lon = x.get("lat"), x.get("lon")
    return (lat, lon) if lat is not None and lon is not None else None


def _leg_routes(a, b) -> dict:
    """Primary + alternative routes for one leg, with graceful fallback.

    OSRM alternatives give real 'first route fails -> take the next' options; if
    OSRM returns nothing we fall back to a haversine time/distance estimate.
    """
    routes = gateway.osrm_route(a, b, profile="driving", alternatives=True)
    if routes:
        return {"source": "osrm:driving", "routes": routes, "fallback": False}
    km = km_between(a, b) if (a and b) else None
    if km is None:
        return {"source": "none", "routes": [], "fallback": True}
    return {"source": "estimate:haversine",
            "routes": [{"distance_km": km,
                        "duration_min": max(5, round(km / CITY_KMH * 60)),
                        "profile": "estimate"}],
            "fallback": True}


def run(state) -> dict:
    """Route the hotel -> activities legs; report primary + backup per leg."""
    hotels = state.options.get("hotels", [])
    acts = state.options.get("activities", [])
    hotel = (hotels[0].get("raw") if hotels else None) or {}

    # Chain: hotel -> a1 -> a2 ... (first few activities that carry coordinates)
    stops = [{"name": hotel.get("name", "Hotel"), "pt": _pt(hotel)}]
    for a in acts:
        r = a.get("raw", a)
        pt = _pt(r)
        if pt:
            stops.append({"name": r.get("name", "?"), "pt": pt})
        if len(stops) > MAX_LEGS:
            break

    legs, total_km, live_ok, fallbacks = [], 0.0, False, 0
    for i in range(1, len(stops)):
        s, e = stops[i - 1], stops[i]
        info = _leg_routes(s["pt"], e["pt"])
        rts = info["routes"]
        primary = rts[0] if rts else None
        if info["source"].startswith("osrm"):
            live_ok = True
        if info["fallback"]:
            fallbacks += 1
        if primary:
            total_km += primary["distance_km"]
        legs.append({
            "from": s["name"], "to": e["name"],
            "source": info["source"],
            "primary": primary,
            "alternatives": rts[1:],          # backup routes ('next' if first fails)
            "fallback": info["fallback"],
        })

    return {
        "legs": legs,
        "leg_count": len(legs),
        "total_km": round(total_km, 1),
        "routing": "osrm-driving + alternatives, haversine fallback",
        "live": live_ok,
        "fallbacks": fallbacks,
        "note": ("Live road routes via OSRM (with backups)." if live_ok
                 else "OSRM unreachable — straight-line estimates used."),
        "sources": ["osrm:project-osrm.org" if live_ok else "derived:haversine"],
    }
