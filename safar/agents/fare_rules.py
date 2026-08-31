"""Fare-Rules agent — compare refund / change / baggage rules (readme §6).

Analyses flight options to surface refundability, change fees, and baggage
inclusion so the negotiation engine and the human can make informed trade-offs.
Deterministic (no LLM).
"""


def run(state) -> dict:
    """Extract and compare fare rules across flight options."""
    flights = state.options.get("flights", [])
    rules: list[dict] = []

    for f in flights:
        raw = f.get("raw", {})
        option_id = f.get("option_id", "?")
        airline = raw.get("airline", "Unknown")
        refundable = raw.get("refundable", False)

        rule = {
            "option_id": option_id,
            "airline": airline,
            "refundable": refundable,
            "change_fee": "Free" if refundable else "Paid (carrier policy)",
            "baggage": _baggage_estimate(raw),
            "cancellation": "Full refund" if refundable else "Non-refundable (credit only)",
            "flexibility_score": 1.0 if refundable else 0.3,
        }
        rules.append(rule)

    # Find the most flexible and least flexible
    best = max(rules, key=lambda r: r["flexibility_score"]) if rules else None
    worst = min(rules, key=lambda r: r["flexibility_score"]) if rules else None

    return {
        "rules": rules,
        "most_flexible": best["option_id"] if best else None,
        "least_flexible": worst["option_id"] if worst else None,
        "recommendation": _recommendation(rules),
        "sources": ["derived:flight-options"],
    }


def _baggage_estimate(raw: dict) -> str:
    """Estimate baggage inclusion from airline type (heuristic)."""
    airline = (raw.get("airline") or "").lower()
    lcc = {"airasia", "indigo", "go first", "spirit", "ryanair", "easyjet",
           "scoot", "peach", "jetstar", "wizz air"}
    if any(l in airline for l in lcc):
        return "Cabin only (check-in bag is extra)"
    return "Likely included (full-service carrier)"


def _recommendation(rules: list) -> str:
    refundable = [r for r in rules if r["refundable"]]
    if not refundable:
        return ("No refundable options available — consider travel insurance "
                "for cancellation protection.")
    if len(refundable) == len(rules):
        return "All options are refundable — good flexibility."
    return (f"{len(refundable)}/{len(rules)} options are refundable. "
            f"Choose refundable if your dates might change.")
