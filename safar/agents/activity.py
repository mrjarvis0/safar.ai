"""Activity agent — score activities by interest fit. Owner: adi.

Returns the shared envelope; the negotiation engine picks the day's set.
"""
from ..gateway.gateway import get_activities


def run(state) -> list[dict]:
    opts = get_activities(state.trip)
    interests = set(state.trip.get("interests", []))
    out = []
    for o in opts:
        fit = 1.0 if interests & set(o.get("tags", [])) else 0.35
        out.append({
            "option_id": o["id"],
            "summary": f'{o["name"]} · ₹{o["price_inr"]:,} · {o["duration_h"]}h · {o["area"]}',
            "scores": {"fit": fit},
            "raw": o,
            "sources": ["mock:data/tokyo.json#activities"],
        })
    return out
