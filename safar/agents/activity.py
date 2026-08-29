"""Activity agent — pick & rank activities by interests. Owner: adi.

Respect opening hours + duration + area so the day is geographically sane.
"""
from ..llm import llm
# from ..gateway.gateway import get_activities


def run(state) -> list[dict]:
    # TODO(adi): options = get_activities(state.trip)
    # TODO(adi): filter by interests, return scored options in the shared envelope
    return []
