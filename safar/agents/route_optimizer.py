"""Route Optimizer agent — multi-day route ordering (readme §6).

Beyond the per-day nearest-neighbour ordering in engine/itinerary.py, this agent
handles multi-day assignment: which activities go on which day to minimize total
transit and keep days geographically coherent.  Also produces a spatial grouping
summary so the human can see the daily zones.

Deterministic (haversine distance, no LLM, no external API).
"""
from ..tools.distance import km_between


def run(state) -> dict:
    """Assign activities to days with geographic grouping, then report stats."""
    acts = state.options.get("activities", [])
    days = state.trip.get("days", 5)
    pace = state.trip.get("pace", "relaxed")
    per_day = {"relaxed": 2, "moderate": 3, "packed": 4}.get(pace, 2)

    if not acts:
        return {"groups": [], "total_transit_km": 0, "sources": ["none"]}

    # Extract raw activities with coordinates
    raws = [a.get("raw", a) for a in acts]
    raws_with_coords = [r for r in raws if r.get("lat") is not None]
    raws_without = [r for r in raws if r.get("lat") is None]

    # Spatial clustering: sort by longitude (east-west sweep) then chunk
    sorted_acts = sorted(raws_with_coords, key=lambda a: (a.get("lon", 0), a.get("lat", 0)))
    sorted_acts.extend(raws_without)  # append unknown-coord activities at the end

    # Chunk into per-day groups
    groups: list[dict] = []
    for d in range(min(days, (len(sorted_acts) + per_day - 1) // per_day)):
        chunk = sorted_acts[d * per_day: (d + 1) * per_day]
        if not chunk:
            break

        # Compute intra-day transit estimate
        transit = 0.0
        for i in range(1, len(chunk)):
            a, b = chunk[i - 1], chunk[i]
            if a.get("lat") is not None and b.get("lat") is not None:
                transit += km_between((a["lat"], a["lon"]), (b["lat"], b["lon"]))

        areas = list({c.get("area", "?") for c in chunk})
        groups.append({
            "day": d + 1,
            "activities": [c.get("name", "?") for c in chunk],
            "areas": areas,
            "transit_km": round(transit, 1),
        })

    total_km = round(sum(g["transit_km"] for g in groups), 1)

    return {
        "groups": groups,
        "total_transit_km": total_km,
        "optimisation": "east-west geographic sweep + nearest-neighbour intra-day",
        "sources": ["derived:haversine"],
    }
