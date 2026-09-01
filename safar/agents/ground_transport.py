"""Ground transport agent — intercity bus + train ranking. Owner: adi.

Phase 3b. Reads bus/train inventory from the gateway (real aggregator when keys
are set, deterministic mock otherwise), scores each option on cost / speed /
comfort, and returns the shared envelope (readme §17.2). Deterministic scoring;
the On-Trip Copilot can call `search()` directly when a "train cancelled" event
fires (readme §12) to find an alternative.
"""
import re

from ..gateway import ground_transport as gt
from ..util import norm

# comfort priors by vehicle class (0..1) — sleeper/AC beats seater/non-AC.
_BUS_COMFORT = [("sleeper", 0.9), ("volvo", 0.8), ("ac", 0.7), ("multi-axle", 0.75)]
_TRAIN_COMFORT = {"1A": 1.0, "2A": 0.85, "CC": 0.75, "3A": 0.7, "SL": 0.5, "2S": 0.4}


def _score(options: list, kind: str, src: str = "mock") -> list:
    """Score a homogeneous list (buses OR trains) into envelope rows."""
    if not options:
        return []
    prices = [o["price_inr"] for o in options]
    durs = [o["duration_h"] for o in options]
    lo, hi = min(prices), max(prices)
    dlo, dhi = min(durs), max(durs)
    out = []
    for o in options:
        cost = norm(o["price_inr"], lo, hi, invert=True)          # 1 = cheapest
        speed = norm(o["duration_h"], dlo, dhi, invert=True)      # 1 = fastest
        comfort = _comfort(o, kind)
        seats = o.get("seats_available", 0)
        summary = (f'{o.get("operator") or o.get("name")} · {o.get("type") or o.get("class")}'
                   f' · ₹{o["price_inr"]:,} · {o["depart"]}→{o["arrive"]} '
                   f'({o["duration_h"]}h)')
        out.append({
            "option_id": o["id"],
            "summary": summary,
            "scores": {"cost": round(cost, 2), "speed": round(speed, 2),
                       "comfort": round(comfort, 2)},
            "bookable": seats > 0,
            "raw": o,
            "sources": [f"{src}:ground_transport#{kind}"],
        })
    # sold-out (waitlist) options sink to the bottom
    return sorted(out, key=lambda r: (not r["bookable"], -r["scores"]["comfort"]))


def _comfort(o: dict, kind: str) -> float:
    if kind == "train":
        return _TRAIN_COMFORT.get(o.get("class", ""), 0.6)
    t = (o.get("type") or "").lower()
    for key, val in _BUS_COMFORT:
        if key in t:
            return val
    return 0.6


def search(origin: str, dest: str, date: str | None = None) -> dict:
    """Scored bus + train options between two cities. Direct-callable (Copilot)."""
    inv = gt.search_ground(origin, dest, date)
    src = inv["source"]
    return {"origin": inv["origin"], "destination": inv["destination"],
            "date": inv["date"], "source": src,
            "buses": _score(inv["buses"], "bus", src),
            "trains": _score(inv["trains"], "train", src)}


# match "Tokyo, Kyoto" / "Tokyo & Kyoto" / "Tokyo to Kyoto" / "Tokyo - Kyoto"
_LEG = re.compile(r"\s*(?:,|&|/|\bto\b|-|–|and)\s*", re.IGNORECASE)


def detect_leg(destination: str) -> tuple[str, str] | None:
    """Split a multi-city destination into (from, to). None if single-city."""
    parts = [p.strip() for p in _LEG.split(destination or "") if p.strip()]
    if len(parts) >= 2:
        return parts[0], parts[1]
    return None


def run(state) -> dict:
    """Auto-detect an intercity leg from the destination; search it if present."""
    dest = state.trip.get("destination", "")
    leg = detect_leg(dest)
    if not leg:
        return {"available": True, "leg": None,
                "note": "Single-city trip — no intercity leg. Use the Plan-tab "
                        "search for bus/train between any two cities.",
                "status": gt.status()}
    res = search(leg[0], leg[1])
    res["available"] = True
    res["leg"] = list(leg)
    res["recommendation"] = _recommend(res)
    return res


def _recommend(res: dict) -> str:
    best_train = res["trains"][0] if res["trains"] else None
    best_bus = res["buses"][0] if res["buses"] else None
    if best_train and best_bus:
        cheaper = min(best_train, best_bus, key=lambda r: r["raw"]["price_inr"])
        return f"Cheapest bookable: {cheaper['summary']}"
    if best_train:
        return f"Train: {best_train['summary']}"
    if best_bus:
        return f"Bus: {best_bus['summary']}"
    return "No bookable ground option found."
