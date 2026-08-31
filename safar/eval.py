"""Eval harness — golden trips + metrics (readme §18). Run: python -m safar.eval

Runs a fixed suite of scenarios through the full planner and reports:
constraint-satisfaction (no hard violation among shown plans), feasibility,
grounding, and advisory counts. A regression gate would fail the build if
`with_3_candidates` or `grounded` drops.
"""
from .orchestrator import plan_trip

GOLDEN = [
    {"name": "Japan food+culture ₹2L",
     "input": {"destination": "Tokyo", "days": 5, "budget_inr": 200000,
               "interests": ["food", "culture"], "travel_month": 11}},
    {"name": "Dubai city+shopping ₹1.5L",
     "input": {"destination": "Dubai", "days": 4, "budget_inr": 150000,
               "interests": ["city", "shopping"], "travel_month": 12}},
    {"name": "Tokyo tight budget ₹80k",
     "input": {"destination": "Tokyo", "days": 5, "budget_inr": 80000,
               "interests": ["food"], "travel_month": 6}},
]


def _metrics(state) -> dict:
    cands = [c for k in ("saver", "comfort", "balanced")
             if (c := state.candidates.get(k))]
    feasible = [c for c in cands if c.get("feasible")]
    return {
        "has_3": len(cands) == 3,
        "feasibility": round(len(feasible) / max(len(cands), 1), 2),
        "no_hard_violation": len(state.errors) == 0,
        "grounded": bool((state.grounding.get("geo") or {}).get("lat")),
        "advisories": len(state.warnings),
    }


def run(verbose: bool = True):
    rows = []
    for g in GOLDEN:
        m = _metrics(plan_trip(g["input"]))
        rows.append((g["name"], m))
        if verbose:
            print(f"  {g['name']:28} {m}")
    agg = {
        "trips": len(rows),
        "with_3_candidates": sum(r[1]["has_3"] for r in rows),
        "grounded": sum(r[1]["grounded"] for r in rows),
        "avg_feasibility": round(sum(r[1]["feasibility"] for r in rows) / len(rows), 2),
    }
    if verbose:
        print("  AGGREGATE:", agg)
    return rows, agg


if __name__ == "__main__":
    print("SAFAR eval — golden trips")
    run()
