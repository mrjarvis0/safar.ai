"""Orchestrator — the loop that ties everything together. Owner: mr.jarvis0.

Flow (team-work.md section 3):
  intake -> run agents (flight/hotel/activity) -> negotiate -> validate -> approval
"""
from .state import TripState
# from .agents import flight, hotel, activity
# from .tools import budget
# from .engine import negotiation, validation


def plan_trip(user_input: dict) -> TripState:
    state = TripState()
    # TODO(lead): fill state.trip / constraints / weights from user_input
    # TODO(lead): state.options = {"flights": flight.run(state),
    #                              "hotels":  hotel.run(state),
    #                              "activities": activity.run(state)}
    # TODO(lead): state.candidates = negotiation.negotiate(state)
    # TODO(lead): validation.validate(state)
    # TODO(lead): state.status = "AWAITING_APPROVAL"
    return state
