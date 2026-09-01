"""Orchestrator — the loop that ties everything together. Owner: mr.jarvis0.

Flow (readme.md section 7):
  intake -> run agents (flight/hotel/activity) -> negotiate -> validate
         -> ground -> AWAITING_APPROVAL  ->  approve()
"""
import uuid

from . import config, memory, store, data_optd, grounding
from .llm import llm
from .state import TripState
from .agents import (flight, hotel, activity, visa, discovery, risk, support,
                     seasonality, connection_risk, fare_rules, route_optimizer,
                     document, connectivity, sustainability, emergency, profile,
                     transport, ground_transport, intercity, enroute)
from .engine import negotiation, validation
from .gateway import gateway

DEFAULT_WEIGHTS = {"cost": 0.9, "comfort": 0.7, "experience": 0.8,
                   "safety": 0.6, "risk": 0.5}


def plan_trip(user_input: dict) -> TripState:
    """Take intake dict -> fully planned TripState awaiting human approval."""
    state = TripState(trip_id=uuid.uuid4().hex[:8],
                      user_id=user_input.get("user_id", "demo"), status="DISCOVER")

    state.trip = {
        "destination": user_input.get("destination", "Tokyo"),
        "days": int(user_input.get("days", 5)),
        "interests": user_input.get("interests", ["food", "culture"]),
        "pace": user_input.get("pace", "relaxed"),
        "travel_month": int(user_input.get("travel_month", 11)),
        "home_country": user_input.get("home_country", "India"),
        "party": user_input.get("party", []),          # [{name, weights}] for group travel
    }
    state.constraints = {
        "hard": {"budget_inr": float(user_input.get("budget_inr", 200000))},
        "soft": {"hotel_stars_min": int(user_input.get("hotel_stars_min", 3)),
                 "avoid_early_flights": bool(user_input.get("avoid_early_flights", True))},
    }
    state.weights = user_input.get("weights") or dict(DEFAULT_WEIGHTS)
    memory.apply(state)               # §14: seed weights from the stored profile

    # 1. logistics agents -> priced options
    state.options = {
        "flights": flight.run(state),
        "hotels": hotel.run(state),
        "activities": activity.run(state),
    }

    # 1b. inter-city mode comparison (§1a): flight vs train vs bus vs taxi, all
    # estimated from the same distance. Feasible GROUND modes are merged into the
    # flight pool so negotiation ranks every "how you get there" option together
    # (§8). Overseas trips yield no ground modes -> flights left untouched.
    try:
        state.intercity = intercity.run(state)
        state.options["flights"] = (state.options["flights"]
                                    + intercity.negotiation_feed(state.intercity))
    except Exception:
        pass

    # 2. negotiate -> 3 candidates (each with a day-by-day itinerary)
    state.status = "NEGOTIATE"
    state.candidates = negotiation.negotiate(state)

    # 3. ground on live free sources first (seasonality + visa feed the validators)
    state.grounding = _ground(state)

    # 4. discovery / risk / support teams (Phase 2 breadth; ground on free sources).
    # Risk runs first so the weather-aware food pick (§1b) can read the live forecast.
    try:
        state.risk = risk.run(state)
        state.discovery = discovery.run(state)
        state.support = support.run(state)
    except Exception:
        pass

    # 4b. enroute discovery (§1c): attractions sampled along the road route.
    _safe_run(state, "enroute", lambda: enroute.run(state))

    # 5. Phase 2+ agents — each wrapped so a failure never breaks the plan
    _run_phase2_agents(state)

    # 6. provenance tracking (§11)
    grounding.add_claims_from_grounding(state)

    # 7. validate: hard errors + soft advisories (temporal/geo/weather/visa)
    state.status = "VALIDATE"
    state.errors = validation.validate(state)

    _add_llm_note(state)
    _observe(state)                   # §19: persist snapshot + agent runs
    state.status = "AWAITING_APPROVAL"
    return state


def approve(state: TripState, decision: str = "APPROVE", pick: str = "balanced") -> TripState:
    """Human-in-the-loop gate (§10). Booking is a separate, explicit step (§13)."""
    state.approval = {"gate": "final", "decision": decision, "pick": pick}
    if decision == "APPROVE":
        state.status = "APPROVED"
        memory.learn(state)                                  # §14 learning loop
        store.append_event(state.trip_id, "approved", {"pick": pick})
    elif decision in ("MODIFY", "REPLAN"):
        state.status = "NEGOTIATE"  # affected sub-graph would re-run
    else:
        state.status = "INTAKE"     # REJECT -> restart intake
    store.save_trip(state)
    return state


def _run_phase2_agents(state: TripState) -> None:
    """Run Phase 2+ agents. Each is wrapped so a failure never breaks the plan."""
    _safe_run(state, "seasonality", lambda: seasonality.run(state))
    _safe_run(state, "connection_risk", lambda: connection_risk.run(state))
    _safe_run(state, "fare_rules", lambda: fare_rules.run(state))
    _safe_run(state, "route_opt", lambda: route_optimizer.run(state))
    _safe_run(state, "document", lambda: document.run(state))
    _safe_run(state, "connectivity", lambda: connectivity.run(state))
    _safe_run(state, "sustainability", lambda: sustainability.run(state))
    _safe_run(state, "emergency", lambda: emergency.run(state))
    _safe_run(state, "traveler_profile", lambda: profile.run(state))
    _safe_run(state, "transport", lambda: transport.run(state))
    _safe_run(state, "ground", lambda: ground_transport.run(state))   # Phase 3b


def _safe_run(state: TripState, field: str, fn) -> None:
    """Run an agent function and store its output in state.<field>."""
    try:
        setattr(state, field, fn())
    except Exception:
        pass


def _observe(state: TripState) -> None:
    """Observability + persistence (§19). Best-effort; never blocks a plan."""
    try:
        store.save_trip(state)
        store.append_event(state.trip_id, "planned",
                           {"candidates": list(state.candidates.keys())})
        conf = (state.candidates.get("balanced") or {}).get("confidence", 0.9)
        all_agents = ("flight", "hotel", "activity", "discovery", "risk",
                      "support", "seasonality", "connection_risk", "fare_rules",
                      "route_optimizer", "document", "connectivity",
                      "sustainability", "emergency", "profile", "transport",
                      "ground_transport", "intercity", "enroute")
        for agent in all_agents:
            store.log_agent_run(state.trip_id, agent, confidence=conf,
                                sources=["gateway"])
        # Persist provenance records (§11)
        if getattr(state, "provenance", None):
            store.save_provenance(state.trip_id, state.provenance)
    except Exception:
        pass


def _ground(state: TripState) -> dict:
    """Grounding layer (§11): geocode + seasonality + a Wikivoyage snippet.

    All keyless + wrapped so a network blip never breaks the plan.
    """
    dest = state.trip["destination"]
    out: dict = {}
    try:
        geo = gateway.osm_geocode(dest)
        out["geo"] = geo
        if geo.get("lat"):
            out["seasonality"] = gateway.seasonality(
                geo["lat"], geo["lon"], state.trip["travel_month"])
    except Exception:
        pass
    try:
        wv = gateway.wikivoyage(dest)
        out["wikivoyage"] = (wv.get("summary") or "")[:260]
        out["wikivoyage_url"] = wv.get("url")
    except Exception:
        pass
    # offline OPTD reference (IATA + timezone + country) — keyless, always available
    optd = data_optd.resolve_city(dest)
    if optd:
        out["optd"] = {"iata": optd.get("iata"), "timezone": optd.get("timezone"),
                       "country": optd.get("country")}

    # visa (high-stakes §11): resolve destination country via Wikidata, OPTD fallback
    country = None
    try:
        country = gateway.wikidata_entity(dest).get("country")
    except Exception:
        pass
    if not country and optd:
        country = optd.get("country")
    out["country"] = country
    out["visa"] = visa.check(state.trip.get("home_country", "India"), country)
    return out


def _add_llm_note(state: TripState) -> None:
    """Optional one-line LLM rationale for the Balanced pick (skipped on mock)."""
    if not (config.LLM_PROVIDER == "nvidia" and config.NVIDIA_API_KEY):
        return
    b = state.candidates.get("balanced")
    if not b:
        return
    try:
        note = llm(f"In ONE short sentence, tell the traveler why this fits their "
                   f"{state.trip['interests']} trip: {b['flight']}; {b['hotel']}; "
                   f"total ₹{b['cost_inr']:,.0f}.", max_tokens=80)
        if note and "MOCK_LLM_RESPONSE" not in note:
            b["llm_note"] = note.strip()
    except Exception:
        pass
