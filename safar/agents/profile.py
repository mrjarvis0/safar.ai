"""Traveler Profile agent — build + update the preference model (readme §6, §14).

Cold start: runs a short elicitation (targeted questions + sensible defaults),
marks each field as `assumed` vs `confirmed`.  Learning loop: updates preference
weights from implicit signals (which candidate was approved).

Works with safar/memory.py for persistence.
"""
from .. import memory

# Default assumptions for cold-start (trip #1, no history).
_DEFAULTS = {
    "hotel_preference": {"value": "mid-range (3-4★)", "state": "assumed"},
    "pace": {"value": "relaxed", "state": "assumed"},
    "early_flights": {"value": "avoid", "state": "assumed"},
    "food_preference": {"value": "local cuisine", "state": "assumed"},
    "transport": {"value": "public transit preferred", "state": "assumed"},
    "budget_style": {"value": "value-conscious", "state": "assumed"},
}


def run(state) -> dict:
    """Build / load the traveler profile and apply to state."""
    user_id = getattr(state, "user_id", "demo")
    profile = memory.load(user_id)
    weights = profile.get("weights", {})
    history = profile.get("history", [])

    cold_start = len(history) == 0

    # Build assumption map
    assumptions = dict(_DEFAULTS)

    # Override assumptions from explicit user input
    trip = state.trip or {}
    if trip.get("pace"):
        assumptions["pace"] = {"value": trip["pace"], "state": "confirmed"}
    if state.constraints.get("soft", {}).get("hotel_stars_min"):
        stars = state.constraints["soft"]["hotel_stars_min"]
        tier = "budget" if stars <= 2 else "mid-range (3-4★)" if stars <= 4 else "luxury (5★)"
        assumptions["hotel_preference"] = {"value": tier, "state": "confirmed"}
    if state.constraints.get("soft", {}).get("avoid_early_flights") is False:
        assumptions["early_flights"] = {"value": "ok", "state": "confirmed"}

    # Infer preferences from history
    inferred: list[str] = []
    if history:
        dests = [h.get("dest") for h in history if h.get("dest")]
        picks = [h.get("pick") for h in history if h.get("pick")]
        if picks.count("comfort") > picks.count("saver"):
            inferred.append("tends to pick comfort over savings")
        elif picks.count("saver") > picks.count("comfort"):
            inferred.append("tends to pick budget-friendly options")
        if len(set(dests)) < len(dests):
            inferred.append("revisits favorite destinations")

    return {
        "user_id": user_id,
        "cold_start": cold_start,
        "weights": weights,
        "assumptions": assumptions,
        "inferred_preferences": inferred,
        "history_length": len(history),
        "elicitation_note": ("First trip — using sensible defaults. "
                             "Your preferences will improve with each trip."
                             if cold_start else
                             f"Profile built from {len(history)} past trip(s)."),
        "sources": ["sqlite:profiles"],
    }
