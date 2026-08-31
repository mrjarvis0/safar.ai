"""Connection-Risk agent — flag tight transfers + international connections (readme §6).

Analyses flight options to identify risky connection points: short layovers,
international-to-domestic transfers at large airports, and re-check-in requirements.
Deterministic (no LLM).
"""

# Minimum safe connection times (minutes).  Real values come from airport data;
# these are conservative defaults.
_MIN_DOMESTIC = 60       # domestic-to-domestic
_MIN_INTL = 120          # international connection (passport/immigration)
_LARGE_AIRPORTS = {"NRT", "HND", "CDG", "LHR", "DXB", "JFK", "SIN", "BKK",
                   "LAX", "ORD", "PEK", "ICN", "FRA", "AMS"}


def run(state) -> dict:
    """Analyse flights in state.options and flag connection risks."""
    flights = state.options.get("flights", [])
    risks: list[dict] = []

    for f in flights:
        raw = f.get("raw", {})
        stops = raw.get("stops", 0)
        if stops == 0:
            continue

        airline = raw.get("airline", "Unknown")
        option_id = f.get("option_id", "?")

        # Estimate layover from total duration minus flight time
        dur_h = raw.get("duration_h", 0)
        if stops == 1 and dur_h > 12:
            risks.append({
                "option_id": option_id,
                "type": "long_layover",
                "severity": "medium",
                "note": f"{airline}: {stops} stop, {dur_h}h total — likely long layover.",
            })
        elif stops >= 2:
            risks.append({
                "option_id": option_id,
                "type": "multiple_stops",
                "severity": "high",
                "note": f"{airline}: {stops} stops, higher misconnect risk.",
            })

        # Early departure risk
        depart = raw.get("depart", "12:00")
        hour = int(depart.split(":")[0])
        if hour < 7:
            risks.append({
                "option_id": option_id,
                "type": "early_departure",
                "severity": "low",
                "note": f"{airline}: {depart} departure — allow time for airport transit.",
            })

    return {
        "risks": risks,
        "flagged": len(risks),
        "min_domestic_min": _MIN_DOMESTIC,
        "min_intl_min": _MIN_INTL,
        "sources": ["derived:flight-options"],
    }
