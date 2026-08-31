"""Hotel agent — score hotel options. Owner: adi.

Balances price / stars / rating / transit; returns the shared envelope.
Deterministic scoring; the negotiation engine composes the "why".
"""
from ..gateway.gateway import get_hotels
from ..util import norm


def run(state) -> list[dict]:
    opts = get_hotels(state.trip)
    if not opts:
        return []
    prices = [o["price_inr_night"] for o in opts]
    trans = [o["transit_min"] for o in opts]
    lo, hi = min(prices), max(prices)
    tlo, thi = min(trans), max(trans)
    stars_min = state.constraints.get("soft", {}).get("hotel_stars_min", 3)

    out = []
    for o in opts:
        cost = norm(o["price_inr_night"], lo, hi, invert=True)   # 1 = cheapest
        stars_n = o["stars"] / 5
        rating_n = max(0.0, min(1.0, (o["rating"] - 3) / 2))      # 3..5 -> 0..1
        transit_n = norm(o["transit_min"], tlo, thi, invert=True)
        pen = 0.15 if o["stars"] < stars_min else 0.0
        comfort = max(0.0, min(1.0, 0.45 * stars_n + 0.35 * rating_n
                                    + 0.20 * transit_n - pen))
        out.append({
            "option_id": o["id"],
            "summary": f'{o["name"]} · {o["stars"]}★ · ₹{o["price_inr_night"]:,}/night · '
                       f'{o["area"]} · {o["transit_min"]}min to transit',
            "scores": {"cost": round(cost, 2), "comfort": round(comfort, 2)},
            "raw": o,
            "sources": ["mock:data/tokyo.json#hotels"],
        })
    return out
