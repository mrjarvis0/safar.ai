"""Flight agent — score flight options. Owner: adi.

Reads options from the gateway, scores each on cost / comfort / duration, and
returns them in the shared envelope (readme.md section 17.2). Deterministic
scoring; the "why" is composed by the negotiation engine.
"""
from ..gateway.gateway import get_flights
from ..util import norm


def run(state) -> list[dict]:
    opts = get_flights(state.trip)
    if not opts:
        return []
    prices = [o["price_inr"] for o in opts]
    durs = [o["duration_h"] for o in opts]
    lo, hi = min(prices), max(prices)
    dlo, dhi = min(durs), max(durs)
    avoid_early = state.constraints.get("soft", {}).get("avoid_early_flights", True)

    out = []
    for o in opts:
        cost = norm(o["price_inr"], lo, hi, invert=True)        # 1 = cheapest
        dur = norm(o["duration_h"], dlo, dhi, invert=True)      # 1 = shortest
        stops_s = {0: 1.0, 1: 0.6}.get(o["stops"], 0.3)
        early_pen = 0.2 if (avoid_early and int(o["depart"].split(":")[0]) < 8) else 0.0
        refund = 0.1 if o.get("refundable") else 0.0
        comfort = max(0.0, min(1.0, 0.5 * dur + 0.4 * stops_s + refund - early_pen))
        plural = "s" if o["stops"] != 1 else ""
        out.append({
            "option_id": o["id"],
            "summary": f'{o["airline"]} · {o["stops"]} stop{plural} · '
                       f'₹{o["price_inr"]:,} · {o["depart"]}→{o["arrive"]}',
            "scores": {"cost": round(cost, 2), "comfort": round(comfort, 2),
                       "duration": round(dur, 2)},
            "raw": o,
            "sources": ["mock:data/tokyo.json#flights"],
        })
    return out
