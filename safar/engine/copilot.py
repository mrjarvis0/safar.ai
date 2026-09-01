"""On-Trip Copilot — event -> impact -> minimal-disruption replan (readme §12).

Subscribes to the live event bus. High-impact events (flight delay, closure,
weather alert) compute a blast radius and require a human "yes" before the plan
changes; low-impact ones update TripState in place. Replanning changes as little
as possible (change-cost aware).
"""
import copy

from .. import events, store

HIGH_IMPACT = {"flight_delay", "attraction_closed", "weather_alert"}

# Trips whose Copilot is already subscribed to the bus (avoid duplicate handlers
# across Streamlit reruns / repeated attach calls).
_ATTACHED: set[str] = set()


def attach(state) -> None:
    """Subscribe this trip's Copilot to the live event bus (§2b). Idempotent.

    A `flight.status` event carrying a delay auto-triggers react() — this is the
    link that lets safar.monitor push a live delay and have the plan adjust with
    no extra glue. Still human-gated: flight_delay is HIGH_IMPACT, so react()
    returns a proposal (needs_approval) and never mutates the plan on its own.
    """
    if state.trip_id in _ATTACHED:
        return

    def _on_status(payload: dict):
        delay = int(payload.get("delay_minutes", 0) or 0)
        if delay <= 0:
            return None
        return react(state, {"type": "flight_delay", "minutes": delay,
                             "flight_no": payload.get("flight_no")})

    events.subscribe("flight.status", _on_status)
    _ATTACHED.add(state.trip_id)


def _mins(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def _add(hhmm: str, delta: int) -> str:
    t = (_mins(hhmm) + delta) % (24 * 60)
    return f"{t // 60:02d}:{t % 60:02d}"


def react(state, event: dict) -> dict:
    """event = {'type': 'flight_delay'|'attraction_closed'|'weather_alert', ...}."""
    store.append_event(state.trip_id, "live_event", event)
    cand = state.candidates.get("balanced") or {}
    itin = copy.deepcopy(cand.get("itinerary") or [])
    et = event.get("type")
    changes: list[str] = []

    if et == "flight_delay" and itin:
        delay = int(event.get("minutes", 0))
        day = itin[0]
        for it in day["items"]:
            it["arrive"], it["depart"] = _add(it["arrive"], delay), _add(it["depart"], delay)
        kept = [it for it in day["items"] if _mins(it["depart"]) <= 22 * 60]
        dropped = [it["name"] for it in day["items"] if it not in kept]
        day["items"] = kept
        changes.append(f"Day 1 shifted +{delay} min (flight delay)")
        if dropped:
            changes.append("Dropped as too late: " + ", ".join(dropped))

    elif et == "attraction_closed":
        name = event.get("name")
        used = {it["name"] for d in itin for it in d["items"]}
        alt = next((a["raw"]["name"] for a in state.options.get("activities", [])
                    if a["raw"]["name"] not in used), None)
        for d in itin:
            for it in list(d["items"]):
                if it["name"] == name:
                    d["items"].remove(it)
                    if alt:
                        d["items"].append({**it, "name": alt, "within_hours": True})
                        changes.append(f"Swapped closed '{name}' → '{alt}'")
                    else:
                        changes.append(f"Removed '{name}' (no alternative available)")

    elif et == "weather_alert":
        day_no = event.get("day")
        for d in itin:
            if d["day"] == day_no:
                outs = [it["name"] for it in d["items"] if it.get("outdoor")]
                if outs:
                    changes.append(f"Day {day_no}: move indoors / add flex — {', '.join(outs)}")

    impact = {"changes": changes or ["No change needed"]}
    needs_approval = et in HIGH_IMPACT
    result = {"event": event, "impact": impact, "new_itinerary": itin,
              "needs_approval": needs_approval}
    if not needs_approval:              # low-impact: apply immediately
        cand["itinerary"] = itin
    events.publish("copilot.reacted", result)
    return result
