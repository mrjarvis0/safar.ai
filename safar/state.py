"""TripState — the single source of truth every module reads/writes. Owner: mr.jarvis0.

Keep it structured (dataclass) so modules pass data, never free text.
Full schema: readme.md section 17.1.
"""
from dataclasses import dataclass, field
from typing import Any


@dataclass
class TripState:
    trip_id: str = ""
    status: str = "INTAKE"  # INTAKE|DISCOVER|NEGOTIATE|VALIDATE|AWAITING_APPROVAL|DONE
    trip: dict[str, Any] = field(default_factory=dict)          # destination, dates, days, pace
    constraints: dict[str, Any] = field(default_factory=dict)   # hard + soft
    weights: dict[str, float] = field(default_factory=dict)     # objective weights
    options: dict[str, list] = field(default_factory=dict)      # agent outputs: flights/hotels/...
    candidates: dict[str, Any] = field(default_factory=dict)    # saver / comfort / balanced
    conflicts: list = field(default_factory=list)
    approval: dict[str, Any] = field(default_factory=dict)

    # TODO(lead): finalize the fields with the team on Day 0
