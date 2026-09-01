"""Inter-city transport agent — Flight vs Train vs Bus vs Taxi (readme §1a, §17.2).

Turns "how do I get from home to the destination?" into one apples-to-apples
comparison. All four modes are estimated from the SAME distance so the numbers are
coherent regardless of what the flight agent's offers look like:

  * air distance  (haversine)      -> flight estimate
  * road distance (free OSRM)      -> train / bus / taxi estimates

Ground modes are only offered when the leg is actually reachable by road (OSRM
returns a route within GROUND_MAX_KM) — an overseas trip like Tokyo yields flight
only, which is the honest answer. Each mode is emitted in the shared agent
envelope (§17.2); `negotiation_feed()` hands the feasible GROUND modes to the
negotiation engine so it ranks flight vs train vs bus vs taxi together (§8) —
we never drop the flight agent's real offers, only add ground alternatives.

Fares/times are transparent per-km estimates (constants below), not live prices —
every option is tagged `estimate: True` and carries its sources. Keyless; guarded.
"""
from .. import config, data_optd
from ..gateway import gateway
from ..tools.distance import km_between
from ..util import norm

GROUND_MAX_KM = 1500      # beyond this a land leg stops making sense (fly instead)
DEPART_H = 8.0            # synthetic 08:00 departure, so schedules are comparable

# mode -> transparent estimate model. base ₹ + ₹/km; avg km/h; fixed overhead (h).
_MODES = {
    "flight": {"base": 1800, "per_km": 6.0,  "kmh": 750, "overhead": 3.0,
               "icon": "✈️", "label": "Flight"},   # ✈ airport/security/transfer
    "train":  {"base": 80,   "per_km": 1.5,  "kmh": 60,  "overhead": 0.5,
               "icon": "\U0001F686", "label": "Train"},      # 🚆
    "bus":    {"base": 50,   "per_km": 2.0,  "kmh": 45,  "overhead": 0.5,
               "icon": "\U0001F68C", "label": "Bus"},        # 🚌
    "taxi":   {"base": 150,  "per_km": 16.0, "kmh": 50,  "overhead": 0.3,
               "icon": "\U0001F695", "label": "Taxi"},       # 🚕
}
GROUND = ("train", "bus", "taxi")
_MAX_KM = {"train": GROUND_MAX_KM, "bus": GROUND_MAX_KM, "taxi": 700}  # a 700km taxi is absurd


def endpoints(state) -> tuple[dict | None, dict | None]:
    """(origin, destination), each {name, lat, lon, country}.

    Origin = the configured home airport (config.ORIGIN_IATA, offline OPTD lookup);
    destination = the trip's destination city (offline OPTD, OSM geocode fallback).
    Either side is None when it can't be resolved to coordinates. Shared with the
    Enroute agent (§1c) so both use the same endpoints.
    """
    home = data_optd.airport(config.ORIGIN_IATA) or {}
    origin = {"name": home.get("name") or config.ORIGIN_IATA,
              "lat": home.get("lat"), "lon": home.get("lon"),
              "country": home.get("country")}
    name = state.trip.get("destination", "")
    d = data_optd.resolve_city(name) or {}
    if d.get("lat") is not None:
        dest = {"name": name, "lat": d["lat"], "lon": d["lon"], "country": d.get("country")}
    else:
        g = gateway.osm_geocode(name)
        dest = {"name": name, "lat": g.get("lat"), "lon": g.get("lon"), "country": None}
    origin = origin if origin["lat"] is not None else None
    dest = dest if dest.get("lat") is not None else None
    return origin, dest


def _clock(dep_h: float, dur_h: float) -> str:
    """08:00 + duration -> 'HH:MM' (with ' +Nd' when it spills past midnight)."""
    arr = dep_h + dur_h
    day = int(arr // 24)
    rem = arr % 24
    hh = int(rem)
    mm = int(round((rem - hh) * 60))
    if mm == 60:
        hh, mm = hh + 1, 0
    if hh >= 24:
        hh, day = hh - 24, day + 1
    return f"{hh:02d}:{mm:02d}" + (f" +{day}d" if day else "")


def _comfort(mode: str, hours: float) -> float:
    """0..1 comfort — a private/faster mode scores higher; long road legs fatigue."""
    if mode == "flight":
        return 0.85
    if mode == "train":
        return max(0.50, 0.80 - 0.02 * max(0.0, hours - 8))
    if mode == "taxi":
        return max(0.30, 0.72 - 0.05 * max(0.0, hours - 3))
    return max(0.25, 0.50 - 0.03 * max(0.0, hours - 4))    # bus


def _mode_option(mode: str, dist_km: float, feasible: bool) -> dict:
    m = _MODES[mode]
    hours = round(m["overhead"] + dist_km / m["kmh"], 2)
    return {
        "mode": mode, "icon": m["icon"], "label": m["label"],
        "feasible": feasible, "estimate": True,
        "fare_inr": round(m["base"] + m["per_km"] * dist_km),
        "duration_h": hours, "depart": _clock(DEPART_H, 0.0),
        "arrive": _clock(DEPART_H, hours), "comfort": round(_comfort(mode, hours), 2),
        "distance_km": round(dist_km, 1),
    }


def _score(modes: list) -> None:
    """Fill display scores (cost/duration), normalised within the mode set."""
    fares = [m["fare_inr"] for m in modes]
    durs = [m["duration_h"] for m in modes]
    flo, fhi, dlo, dhi = min(fares), max(fares), min(durs), max(durs)
    for m in modes:
        m["cost_score"] = norm(m["fare_inr"], flo, fhi, invert=True)   # 1 = cheapest
        m["dur_score"] = norm(m["duration_h"], dlo, dhi, invert=True)  # 1 = fastest


def _rank(m: dict) -> float:
    return 0.45 * m["cost_score"] + 0.30 * m["comfort"] + 0.25 * m["dur_score"]


def _envelope(m: dict) -> dict:
    """Shared agent envelope (§17.2) — schema-compatible with the flight agent so
    negotiation can rank a train/bus/taxi option exactly like a flight."""
    summary = (f'{m["icon"]} {m["label"]} · est. · ₹{m["fare_inr"]:,} · '
               f'{m["depart"]}→{m["arrive"]} · {m["duration_h"]}h')
    return {
        "option_id": f'T-{m["mode"].upper()}',
        "summary": summary,
        "scores": {"cost": m["cost_score"], "comfort": m["comfort"],
                   "duration": m["dur_score"]},
        "raw": {                                   # keys negotiation._why / total_cost read
            "mode": m["mode"], "feasible": m["feasible"], "estimate": True,
            "airline": f'{m["label"]} (est.)', "stops": 0,
            "price_inr": m["fare_inr"], "duration_h": m["duration_h"],
            "depart": m["depart"], "arrive": m["arrive"], "refundable": False,
        },
        "sources": ["osrm:project-osrm.org", "derived:mode-estimate"],
    }


def _note(ground_reachable: bool, road_km, ground_km) -> str:
    if ground_reachable:
        km = road_km if road_km is not None else ground_km
        return (f"Road-reachable (~{km:,.0f} km) — comparing flight vs train/bus/taxi; "
                f"feasible ground modes feed the ranking.")
    return "No overland route (likely overseas) — fly direct; ground modes N/A."


def run(state) -> dict:
    """Build the multi-modal comparison + the envelopes to feed negotiation."""
    origin, dest = endpoints(state)
    base = {"origin": origin, "destination": dest,
            "sources": ["osrm:project-osrm.org", "optd:offline", "derived:mode-estimate"]}
    if not (origin and dest):
        return {**base, "modes": [], "options": [], "ground_reachable": False,
                "recommended": None, "air_km": None, "road_km": None,
                "note": "Couldn't resolve both endpoints — flight options only."}

    o_pt = (origin["lat"], origin["lon"])
    d_pt = (dest["lat"], dest["lon"])
    air_km = km_between(o_pt, d_pt)

    # OSRM road route decides whether ground modes are physically possible.
    route = gateway.osrm_route_line(o_pt, d_pt)
    road_km = route.get("distance_km")
    same_country = bool(origin.get("country") and origin["country"] == dest.get("country"))
    if road_km is not None:
        ground_km = road_km
        ground_reachable = road_km <= GROUND_MAX_KM
    else:
        # OSRM unreachable: only assume a land leg for a same-country, sane-distance
        # trip — never invent an overland leg across an ocean.
        ground_km = round(air_km * 1.25, 1) if air_km else None
        ground_reachable = bool(same_country and ground_km and ground_km <= GROUND_MAX_KM)

    modes = [_mode_option("flight", air_km, feasible=True)]  # air always comparable
    if ground_reachable and ground_km:
        for gm in GROUND:
            modes.append(_mode_option(gm, ground_km, feasible=ground_km <= _MAX_KM[gm]))

    _score(modes)
    feas = [m for m in modes if m["feasible"]]
    rec = max(feas, key=_rank) if feas else None

    return {
        **base,
        "air_km": round(air_km, 1) if air_km else None,
        "road_km": road_km,
        "ground_km": ground_km,
        "ground_reachable": ground_reachable,
        "modes": modes,
        "options": [_envelope(m) for m in modes],
        "recommended": rec["mode"] if rec else None,
        "note": _note(ground_reachable, road_km, ground_km),
    }


def negotiation_feed(comparison: dict) -> list:
    """Feasible GROUND-mode envelopes to merge alongside the flight agent's options,
    so negotiation ranks flight vs train vs bus vs taxi together (§8). Empty for
    overseas trips (no ground modes) — flights are then left exactly as they were.
    """
    return [o for o in comparison.get("options", [])
            if o["raw"]["mode"] in GROUND and o["raw"]["feasible"]]
