"""Enroute agent — what's worth stopping for along the drive (readme §1c, §11).

When origin and destination are road-connected, this pulls the real driving route
line from OSRM (free, keyless), samples a few points spaced evenly BY DISTANCE
along it, and asks OpenStreetMap (Overpass) for nearby attractions at each — so a
point-to-point trip becomes a route with stops. Overseas trips (no road route)
return an honest "fly direct" note. Reuses intercity.endpoints() so both agents
agree on where the trip starts and ends. Guarded end-to-end; keyless.
"""
from ..gateway import gateway
from ..tools.distance import km_between
from . import intercity

MAX_STOPS = 4            # each stop is 1–2 live Overpass calls — keep the demo snappy
POI_RADIUS_M = 12000
MAX_KM = intercity.GROUND_MAX_KM     # past this, enroute stops aren't useful — fly


def _sample(geometry: list, n: int) -> list:
    """n points spaced evenly by cumulative distance along a [[lat,lon],...] line
    (interior only — endpoints skipped, consecutive duplicates removed)."""
    if len(geometry) < 2 or n < 1:
        return []
    cum = [0.0]
    for i in range(1, len(geometry)):
        cum.append(cum[-1] + km_between(tuple(geometry[i - 1]), tuple(geometry[i])))
    total = cum[-1]
    if total <= 0:
        return []
    picks = []
    for k in range(1, n + 1):
        target = total * k / (n + 1)
        j = next((i for i, c in enumerate(cum) if c >= target), len(geometry) - 1)
        p = geometry[j]
        if not picks or picks[-1] != p:
            picks.append(p)
    return picks


def _pois_near(lat: float, lon: float) -> tuple[list, str]:
    """Attractions near a sampled point; fall back to food/roadside stops so a
    plain-highway stretch still surfaces a useful break. Returns (pois, kind)."""
    for kind in ("attraction", "food"):
        try:
            pois = gateway.osm_pois(lat, lon, kind, POI_RADIUS_M, 4)
        except Exception:
            pois = []
        if pois:
            return pois, kind
    return [], ""


def run(state) -> dict:
    origin, dest = intercity.endpoints(state)
    base = {"stops": [],
            "sources": ["osrm:project-osrm.org", "osm:overpass#attraction"]}
    if not (origin and dest):
        return {**base, "status": "unavailable",
                "note": "Couldn't resolve both endpoints for an enroute scan."}

    route = gateway.osrm_route_line((origin["lat"], origin["lon"]),
                                    (dest["lat"], dest["lon"]))
    if not route.get("geometry"):
        return {**base, "status": "no_overland_route",
                "note": f"No drivable route {origin['name']} → {dest['name']} "
                        f"(likely overseas) — fly direct, no enroute stops."}
    if route["distance_km"] > MAX_KM:
        return {**base, "status": "too_far", "distance_km": route["distance_km"],
                "duration_h": route["duration_h"],
                "note": f"Route is ~{route['distance_km']:,.0f} km — too long to break "
                        f"into enroute stops; consider flying."}

    stops = []
    for lat, lon in _sample(route["geometry"], MAX_STOPS):
        pois, kind = _pois_near(lat, lon)
        if pois:
            stops.append({"lat": round(lat, 4), "lon": round(lon, 4),
                          "kind": kind, "near": pois[0]["name"],
                          "pois": [p["name"] for p in pois[:3]]})
    return {
        **base,
        "status": "ok",
        "origin": origin["name"], "destination": dest["name"],
        "distance_km": route["distance_km"], "duration_h": route["duration_h"],
        "stops": stops,
        "note": (f"{len(stops)} stop(s) worth a break along the "
                 f"~{route['distance_km']:,.0f} km drive." if stops else
                 "Road route found, but no notable attractions sampled along it."),
    }
