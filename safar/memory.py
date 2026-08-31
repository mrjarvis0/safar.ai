"""Memory & personalization (readme §14) — SQLite-backed preference weights.

Cold start: sensible defaults, marked `assumed`. Learning loop: after the human
approves a candidate, nudge the weight vector toward that archetype (implicit
signal) so the next trip starts smarter. Not a Vector DB yet — a weight vector in
SQLite, same call sites.
"""
from . import store

DEFAULTS = {"cost": 0.9, "comfort": 0.7, "experience": 0.8, "safety": 0.6, "risk": 0.5}
STEP = 0.15


def load(user_id: str = "demo") -> dict:
    p = store.load_profile(user_id)
    if p:
        return p
    store.save_profile(user_id, dict(DEFAULTS), [])
    return {"weights": dict(DEFAULTS), "history": []}


def apply(state) -> None:
    """Seed state.weights from the stored profile unless the user passed explicit ones."""
    p = load(getattr(state, "user_id", "demo"))
    if not state.weights or state.weights == DEFAULTS:
        state.weights = dict(p["weights"])
    state.profile = {"applied": dict(state.weights),
                     "history_len": len(p["history"]),
                     "cold_start": len(p["history"]) == 0}


def learn(state) -> dict:
    """Implicit-signal update from the approved pick; persists the new vector."""
    pick = (state.approval or {}).get("pick", "balanced")
    p = load(getattr(state, "user_id", "demo"))
    w = dict(p["weights"])
    if pick == "comfort":
        w["comfort"] = round(w["comfort"] + STEP, 2)
        w["cost"] = round(max(0.1, w["cost"] - STEP), 2)
    elif pick == "saver":
        w["cost"] = round(w["cost"] + STEP, 2)
        w["comfort"] = round(max(0.1, w["comfort"] - STEP), 2)
    history = (p["history"] + [{"trip": state.trip_id, "pick": pick,
                                "dest": state.trip.get("destination")}])[-20:]
    store.save_profile(getattr(state, "user_id", "demo"), w, history)
    return w
