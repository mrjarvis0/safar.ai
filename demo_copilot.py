"""Safar — On-Trip Copilot demo (readme §12).  python demo_copilot.py

Plans a trip, approves it, then fires live events and shows minimal-disruption
replanning. High-impact events flag `needs_approval` (never autonomous).
"""
import sys

from safar.orchestrator import plan_trip, approve
from safar.engine import copilot
from safar import events

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

LINE = "─" * 72


def show_itin(itin, label):
    print(f"  {label}")
    for day in itin:
        names = ", ".join(f"{i['arrive']} {i['name']}" for i in day["items"])
        print(f"    Day {day['day']}: {names or '(empty)'}")


def main():
    state = plan_trip({"destination": "Tokyo", "days": 5, "budget_inr": 200000,
                       "interests": ["food", "culture"], "travel_month": 11})
    approve(state, "APPROVE", pick="balanced")

    # subscribe an observer to the bus
    events.subscribe("copilot.reacted",
                     lambda r: print(f"    [bus] copilot.reacted "
                                     f"(needs_approval={r['needs_approval']})"))

    print(LINE)
    print(f"LIVE TRIP {state.trip_id} — Balanced plan approved. Now things change:")
    show_itin(state.candidates["balanced"]["itinerary"], "Baseline itinerary:")

    for event in [
        {"type": "flight_delay", "minutes": 180},
        {"type": "attraction_closed", "name": "Senso-ji Temple"},
        {"type": "weather_alert", "day": 2},
    ]:
        print(LINE)
        print(f"EVENT: {event}")
        result = copilot.react(state, event)
        for ch in result["impact"]["changes"]:
            print(f"    → {ch}")
        if result["needs_approval"]:
            print("    ⚠ HIGH IMPACT — needs a human 'yes' before applying (not autonomous).")
        show_itin(result["new_itinerary"], "Proposed itinerary:")
    print(LINE)


if __name__ == "__main__":
    main()
