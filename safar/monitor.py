"""Flight monitor — poll live status, push onto the event bus (readme §2b, §12).

Bridges a live flight-status source (gateway.flight_status) to the in-process
event bus (safar.events). When a delay crosses the threshold it publishes a
`flight.status` event; the On-Trip Copilot — once attached (copilot.attach) —
picks it up and proposes a minimal-disruption re-plan on its own.

Keyless-friendly: if no status API is configured (or it errors), poll() falls
back to a deterministic demo status so the flow always works in the live demo.
"""
from . import events
from .gateway import gateway

DEFAULT_THRESHOLD_MIN = 45          # ignore trivial slips; re-plan on real delays


def resolve_flight_no(state, given: str | None = None) -> str | None:
    """Pick the flight number to track: explicit arg, else the first option that
    carries one (Amadeus fills `flight_no`; mock flights don't)."""
    if given and given.strip():
        return given.strip().upper()
    for f in (state.options.get("flights") or []):
        fn = (f.get("raw") or {}).get("flight_no")
        if fn:
            return fn
    return None


def _demo_status(flight_no: str | None, delay: int) -> dict:
    return {"flight_no": flight_no or "DEMO",
            "status": "delayed" if delay else "on time",
            "delay_minutes": delay, "source": "demo"}


def poll(state, flight_no: str | None = None, date: str | None = None,
         threshold_min: int = DEFAULT_THRESHOLD_MIN,
         demo_delay: int | None = None) -> dict:
    """Fetch live status for the trip's flight and, on a real delay, fan it out.

    Returns {flight_no, status, live, delay_minutes, threshold_min, reactions,
    replanned}. `reactions` holds whatever the bus subscribers returned — i.e. the
    Copilot's re-plan proposal when it is attached. `demo_delay` only applies when
    no live source answers (lets the demo simulate a delay); a real API wins.
    """
    fn = resolve_flight_no(state, flight_no)
    status = gateway.flight_status(fn, date) if fn else {}
    live = bool(status)
    if not status:
        status = _demo_status(fn, int(demo_delay or 0))
    delay = int(status.get("delay_minutes") or 0)

    reactions: list = []
    if delay >= threshold_min:
        reactions = events.publish("flight.status", {**status, "delay_minutes": delay})

    return {"flight_no": fn, "status": status, "live": live,
            "delay_minutes": delay, "threshold_min": threshold_min,
            "reactions": reactions, "replanned": bool(reactions)}
