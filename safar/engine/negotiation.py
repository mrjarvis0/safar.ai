"""Negotiation engine — the differentiator. Owner: sush.

conflicts -> weighted utility -> 3 candidates (Saver / Comfort / Balanced).
See readme.md section 8 (and the 8.6 pseudocode).

Conflict axes: flight (cheap vs comfort) x hotel (cheap vs stars). We enumerate
flight x hotel bundles, prune anything breaking the hard budget, score each on a
weighted utility, then return the three archetypes off the Pareto front. Each
candidate carries a day-by-day itinerary (see engine.itinerary).

Group travel (§8.5): when the trip has a `party` of travellers with their own
weights, the Balanced pick maximises the Nash bargaining product (product of
each traveller's utility gain over their disagreement point), which favours
balanced outcomes over crushing any one person. Single traveller uses plain
weighted utility.
"""
from ..util import norm
from ..tools.budget import total_cost
from ..tools.currency import convert
from . import itinerary

DEFAULT_W = {"cost": 0.9, "comfort": 0.7, "experience": 0.8, "safety": 0.6, "risk": 0.5}
SAFETY_BASELINE = 0.7   # placeholder until the Risk team (Phase 2) grounds this


def _utility(comp: dict, w: dict) -> float:
    w = {**DEFAULT_W, **(w or {})}
    return round(w["experience"] * comp["experience"] + w["comfort"] * comp["comfort"]
                 + w["safety"] * comp["safety"] - w["cost"] * comp["cost_norm"], 3)


def negotiate(state) -> dict:
    flights = state.options.get("flights", [])
    hotels = state.options.get("hotels", [])
    if not flights or not hotels:
        return {"saver": None, "comfort": None, "balanced": None,
                "note": "Missing flight or hotel options.", "considered": 0,
                "feasible_count": 0}

    acts = _select_activities(state)
    days = state.trip.get("days", 5)
    pace = state.trip.get("pace", "relaxed")
    nights = max(days - 1, 1)
    budget = state.constraints.get("hard", {}).get("budget_inr", 10 ** 12)
    household_w = state.weights or dict(DEFAULT_W)

    # 1. enumerate bundles + cost + feasibility
    combos = []
    for f in flights:
        for h in hotels:
            plan = {"flight": f, "hotel": h, "activities": acts,
                    "days": days, "nights": nights}
            plan["cost_inr"] = total_cost(plan)
            plan["feasible"] = plan["cost_inr"] <= budget
            combos.append(plan)

    feasible = [c for c in combos if c["feasible"]]
    pool = feasible or combos     # if nothing fits, show closest + flag it

    # 2. score every bundle: weight-independent components + household utility
    costs = [c["cost_inr"] for c in pool]
    clo, chi = min(costs), max(costs)
    act_val = _act_value(acts)
    for c in pool:
        comp = {
            "comfort": round(0.5 * c["flight"]["scores"]["comfort"]
                             + 0.5 * c["hotel"]["scores"]["comfort"], 3),
            "experience": round(0.7 * act_val + 0.3 * c["hotel"]["scores"]["comfort"], 3),
            "cost_norm": round(norm(c["cost_inr"], clo, chi), 3),
            "safety": SAFETY_BASELINE,
        }
        c["comp"] = comp
        c["scores"] = {**comp, "utility": _utility(comp, household_w)}

    utils = [c["scores"]["utility"] for c in pool]
    umin, umax = min(utils), max(utils)

    # 3. archetypes off the front
    saver = min(pool, key=lambda c: c["cost_inr"])
    comfort = max(pool, key=lambda c: c["comp"]["comfort"] + c["comp"]["experience"])

    party = state.trip.get("party") or []
    group = None
    if len(party) > 1:
        balanced, group = _nash_pick(pool, party)
    else:
        balanced = max(pool, key=lambda c: c["scores"]["utility"])

    out = {
        "saver": _pack(saver, "saver", umin, umax, days, pace),
        "comfort": _pack(comfort, "comfort", umin, umax, days, pace),
        "balanced": _pack(balanced, "balanced", umin, umax, days, pace),
        "considered": len(combos),
        "feasible_count": len(feasible),
        "note": None if feasible else
                "No bundle fits the hard budget — showing the closest options. "
                "Relax the budget or the star minimum (RelaxationRequest, §8.6).",
    }
    if group:
        out["group"] = group
    return out


def _nash_pick(pool: list, party: list):
    """Maximise the Nash bargaining product over each traveller's utility gain."""
    for c in pool:
        c["util_by"] = {p["name"]: _utility(c["comp"], p.get("weights", {}))
                        for p in party}
    disagree = {p["name"]: min(c["util_by"][p["name"]] for c in pool) for p in party}

    def nash(c):
        prod = 1.0
        for p in party:
            prod *= max(c["util_by"][p["name"]] - disagree[p["name"]], 1e-6)
        return prod

    best = max(pool, key=nash)
    return best, {
        "method": "nash-bargaining",
        "per_person": {p["name"]: round(best["util_by"][p["name"]], 3) for p in party},
        "fairness_min": round(min(best["util_by"].values()), 3),
    }


def _select_activities(state) -> list:
    acts = state.options.get("activities", [])
    interests = set(state.trip.get("interests", []))
    # interest matches first, then the rest — so multi-day trips still fill up
    return sorted(acts, key=lambda a: 0 if interests & set(a["raw"].get("tags", []))
                  else 1)


def _act_value(acts: list) -> float:
    if not acts:
        return 0.5
    return round(sum(a["scores"].get("fit", 0.5) for a in acts) / len(acts), 3)


def _pack(plan: dict, archetype: str, umin: float, umax: float,
          days: int, pace: str) -> dict:
    util = plan["scores"]["utility"]
    confidence = round(0.83 + 0.14 * norm(util, umin, umax), 2) if umax > umin else 0.90
    acts_raw = [a["raw"] for a in plan["activities"]]
    return {
        "archetype": archetype,
        "flight": plan["flight"]["summary"],
        "hotel": plan["hotel"]["summary"],
        # option ids + bookability so the saga (§13) can price/book the real offer
        "flight_id": plan["flight"]["raw"].get("id"),
        "hotel_id": plan["hotel"]["raw"].get("id"),
        "flight_bookable": bool(plan["flight"]["raw"].get("bookable")),
        "refundable": bool(plan["flight"]["raw"].get("refundable")),
        "activities": [a["name"] for a in acts_raw],
        "itinerary": itinerary.build(plan["hotel"]["raw"], acts_raw, days, pace),
        "cost_inr": plan["cost_inr"],
        "cost_jpy": convert(plan["cost_inr"], "INR", "JPY"),
        "feasible": plan["feasible"],
        "scores": plan["scores"],
        "confidence": confidence,
        "why": _why(plan, archetype),
    }


def _why(plan: dict, archetype: str) -> str:
    f, h = plan["flight"]["raw"], plan["hotel"]["raw"]
    plural = "s" if f["stops"] != 1 else ""
    base = (f'{f["airline"]} ({f["stops"]} stop{plural}, ₹{f["price_inr"]:,}) '
            f'+ {h["name"]} ({h["stars"]}★, {h["area"]})')
    if archetype == "saver":
        return (f'Cheapest feasible bundle — {base}. Lowest total cost; trades some '
                f'comfort (e.g. {f["depart"]} departure, {h["transit_min"]}min transit).')
    if archetype == "comfort":
        return f'Most comfortable — {base}. Fewer stops / higher-star stay; costs more.'
    return f'Best overall at your weights — {base}. Balances cost, comfort, and experience.'
