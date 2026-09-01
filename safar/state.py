"""TripState — the single source of truth every module reads/writes. Owner: mr.jarvis0.

Keep it structured (dataclass) so modules pass data, never free text.
Full schema: readme.md section 17.1.
"""
from dataclasses import dataclass, field
from typing import Any


@dataclass
class TripState:
    trip_id: str = ""
    user_id: str = "demo"
    status: str = "INTAKE"  # INTAKE|DISCOVER|NEGOTIATE|VALIDATE|AWAITING_APPROVAL|BOOKED|LIVE|CLOSED
    trip: dict[str, Any] = field(default_factory=dict)          # destination, dates, days, pace
    constraints: dict[str, Any] = field(default_factory=dict)   # hard + soft
    weights: dict[str, float] = field(default_factory=dict)     # objective weights
    profile: dict[str, Any] = field(default_factory=dict)       # applied preference vector (§14)
    options: dict[str, list] = field(default_factory=dict)      # logistics agents: flights/hotels/...
    discovery: dict[str, Any] = field(default_factory=dict)     # destination/local/food/events
    risk: dict[str, Any] = field(default_factory=dict)          # weather/safety/health/insurance
    support: dict[str, Any] = field(default_factory=dict)       # transport/packing/culture
    candidates: dict[str, Any] = field(default_factory=dict)    # saver / comfort / balanced
    conflicts: list = field(default_factory=list)
    errors: list = field(default_factory=list)                  # hard-constraint failures
    warnings: list = field(default_factory=list)                # soft advisories (temporal/geo/weather/visa)
    grounding: dict[str, Any] = field(default_factory=dict)     # geo/seasonality/wikivoyage/visa
    bookings: list = field(default_factory=list)                # saga output (§13)
    approval: dict[str, Any] = field(default_factory=dict)
    # --- v2 additions ---
    provenance: list = field(default_factory=list)              # §11: [{claim, source, retrieved_at, expires_at, confidence}]
    itinerary: dict[str, Any] = field(default_factory=dict)     # §17.1: {days: [{date, items, route}]}
    # Phase 2+ agent outputs
    seasonality: dict[str, Any] = field(default_factory=dict)   # seasonality agent output
    connection_risk: dict[str, Any] = field(default_factory=dict)   # connection-risk agent output
    fare_rules: dict[str, Any] = field(default_factory=dict)    # fare-rules agent output
    route_opt: dict[str, Any] = field(default_factory=dict)     # route optimizer output
    document: dict[str, Any] = field(default_factory=dict)      # document agent output
    connectivity: dict[str, Any] = field(default_factory=dict)  # connectivity agent output
    sustainability: dict[str, Any] = field(default_factory=dict)    # sustainability agent output
    emergency: dict[str, Any] = field(default_factory=dict)     # emergency agent output
    traveler_profile: dict[str, Any] = field(default_factory=dict)  # profile agent output
    ground: dict[str, Any] = field(default_factory=dict)        # Phase 3b: intercity bus/train
    transport: dict[str, Any] = field(default_factory=dict)     # §2c: OSRM road routes + fallback
    # Phase 1 — "identity" agents
    intercity: dict[str, Any] = field(default_factory=dict)     # §1a: flight vs train/bus/taxi comparison
    enroute: dict[str, Any] = field(default_factory=dict)       # §1c: attractions sampled along the road route
