"""Flight agent — rank flight options. Owner: adi.

Reads options from the gateway, uses llm() to rank + explain,
returns scored options in the shared envelope (readme.md section 17.2).
"""
from ..llm import llm
# from ..gateway.gateway import get_flights


def run(state) -> list[dict]:
    # TODO(adi): options = get_flights(state.trip)
    # TODO(adi): rank on price / duration / stops / prefs (use llm for the "why")
    # TODO(adi): return [{"option_id", "summary", "scores": {...}, "sources": [...]}]
    return []
