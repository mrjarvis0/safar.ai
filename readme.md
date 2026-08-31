# Safar — A Multi-Agent Travel Operating System

> Build a multi-agent trip planner that **divides tasks among specialized agents**,
> **resolves competing priorities through negotiation**, and **requires human approval
> before finalizing a plan** — then keeps working *during* the trip: monitoring,
> reacting, and re-planning when reality changes.

Safar (Hindi/Urdu for *journey*) is **not an itinerary generator**. It is a *Travel Operating
System*: a network of
specialized agents, deterministic tools, a shared state store, a constraint engine, a
negotiation engine, a verification layer, and a human-in-the-loop gate — all working as one
system across the whole trip lifecycle (before → during → after).

```
Travel OS = Agents + Tools + Shared State + Constraint Engine
          + Negotiation Engine + Verification + Human-in-the-Loop + Replanning
```

---

## Implementation status (what actually runs today)

This document is the full design. A large slice of it is **built and verified end-to-end**
(`python demo.py`, `python demo_copilot.py`, `python -m safar.eval`, `streamlit run app.py`).
The build runs entirely on **free / open sources**; the parts that stay mocked or substituted
are called out honestly below — nothing here is faked.

| Area | Status | Notes |
| --- | --- | --- |
| Grounding data (OSM, Wikidata, Wikivoyage, Open-Meteo forecast+archive, FX) | ✅ built | free + keyless, live |
| Logistics + Discovery + Risk + Support + Visa agents | ✅ built | ~15 agents, grounded on the sources above |
| Negotiation (Pareto candidates + Nash group), validators (temporal/geo/weather/visa/budget), itinerary | ✅ built | see §8, §9 |
| On-Trip Copilot + replanning, Memory/personalization | ✅ built | §12, §14 |
| Persistence + observability + event bus | ✅ built | **SQLite + in-process bus** (MVP-right stand-in; see §15) |
| Eval harness + synthetic generator | ✅ built | §18 |
| Streamlit UI + observability dashboard | ✅ built | Plan / On-Trip / Dashboard tabs |
| Flight/hotel **prices** (Amadeus) | ◐ code-ready | needs free Amadeus **test** keys; mock JSON until then (§16) |
| Google Places, Events API | ◐ optional | Places has a free monthly quota (needs a billing-enabled key); Events needs a keyed feed |
| Booking saga | ◐ simulated | full saga + compensation + idempotency, but **no real payment** (§13) |
| Postgres / Redis / Vector DB / Kafka / LangGraph | ⬜ deferred | all free to self-host; SQLite / in-process / sequential Python are the right MVP choice — swap in when scaling |
| Real payment capture, GDPR/DPDP program | ⬜ deferred | needs money / legal, not a code task |

**One thing is genuinely not "free forever":** unlimited, global, real-time flight/hotel
*prices*. Amadeus' free test tier is enough to build against; production volume is metered.

---

## Table of Contents

1. [Overview & Vision](#1-overview--vision)
2. [Why this is genuinely *agentic*](#2-why-this-is-genuinely-agentic)
3. [What a traveler actually needs](#3-what-a-traveler-actually-needs)
4. [System Architecture](#4-system-architecture)
5. [Core Concepts](#5-core-concepts)
6. [The Agent Roster](#6-the-agent-roster)
7. [Execution Model](#7-execution-model)
8. [The Negotiation Engine](#8-the-negotiation-engine-the-heart)
9. [Constraint & Validation Engine](#9-constraint--validation-engine)
10. [Human-in-the-Loop (HITL)](#10-human-in-the-loop-hitl)
11. [Grounding & Truth Layer](#11-grounding--truth-layer)
12. [On-Trip Copilot & Replanning](#12-on-trip-copilot--replanning)
13. [Booking & Execution (Saga)](#13-booking--execution-saga)
14. [Memory & Personalization](#14-memory--personalization)
15. [Data Architecture](#15-data-architecture)
16. [Tool Gateway](#16-tool-gateway)
17. [Technical Spec (build-ready)](#17-technical-spec-build-ready)
18. [Evaluation & Testing](#18-evaluation--testing)
19. [Observability, Security & Compliance](#19-observability-security--compliance)
20. [MVP & Roadmap](#20-mvp--roadmap)
21. [Appendix: v1 → v2 Improvements](#21-appendix-v1--v2-improvements)

---

## 1. Overview & Vision

A frequent traveler doesn't want "10 places to visit." They want a *team*: someone to find
flights, someone to weigh the hotel trade-offs, someone watching visas and safety, someone
who argues that a ₹3,000-cheaper 6 AM flight isn't worth a 7-hour airport wait — and a
manager who forces those voices to reconcile into **one plan the human approves**.

Safar models exactly that team.

**The core loop:**

```
Understand → Decompose → Delegate → Gather → Detect conflicts
   → Negotiate → Generate candidate plans → Validate → HUMAN APPROVAL
   → Execute (book) → Monitor → Re-plan on change
```

Three properties make it a *system* and not a prompt chain:

- **Shared state.** Every agent reads from and writes to one structured `TripState`. No agent
  guesses what another decided.
- **Negotiation.** Agents produce *scored, sourced* recommendations that can be challenged;
  conflicts are resolved by an explicit multi-objective mechanism, not by whoever ran last.
- **Human authority.** Nothing irreversible — booking, payment, sharing personal data —
  happens without an explicit human "yes."

---

## 2. Why this is genuinely *agentic*

Most "AI travel planners" are a single prompt dressed up: `user request → one LLM call →
itinerary`. They hallucinate opening hours, ignore visa reality, and can't react when a
flight slips.

Safar is different on four axes:

| Property | Prompt-chain planner | Safar |
| --- | --- | --- |
| **Task division** | One model does everything | Specialized agents own domains; a DAG schedules them |
| **Conflict handling** | Last write wins / ignored | Explicit conflict types + negotiation engine + Pareto candidates |
| **Grounding** | Answers from model memory | Agents must cite *tool output*; high-stakes facts require official sources |
| **Human control** | None, or a single "looks good?" | 4 HITL gates; irreversible actions are never autonomous |
| **Lifecycle** | Plan once, done | Monitors live signals and re-plans mid-trip |

The differentiator is not "more agents." It's that the agents **disagree productively** and a
defined mechanism resolves it — with a human holding the final pen.

---

## 3. What a traveler actually needs

The requirement backbone. Every need below maps to an owning agent/section (see §6).

**Before the trip**
Destination & dates · visa/passport rules · flights · hotel · local transport · activities ·
weather · currency · SIM/eSIM · insurance · budget · documents · packing · local laws &
customs · safety · food preferences · accessibility · best area to stay · airport→hotel→sights
movement · cancellation rules.

**During the trip**
Flight delay/gate change · hotel problem · sudden bad weather · attraction closed · traffic ·
train cancelled · budget overrun · a new nearby opportunity · schedule too tight · emergency ·
*"I have 4 free hours right now — what should I do?"*

**After the trip**
Expense summary · booking history · memories/photos · places visited · **preference learning**
· next-trip recommendations.

Design consequence: the system must span **planning, live operation, and learning** — three
different modes, one shared memory.

---

## 4. System Architecture

```
                          ┌──────────────────────┐
                          │        USER          │
                          │  goals + preferences │
                          └──────────┬───────────┘
                                     │ (intake + clarification loop)
                                     ▼
                     ┌──────────────────────────────┐
                     │     TRAVEL ORCHESTRATOR       │
                     │ intent → constraints → tasks  │
                     │      owns the execution DAG   │
                     └───────────────┬───────────────┘
                                     │  reads/writes
                     ┌───────────────▼───────────────┐
                     │          TRIP STATE            │  ◄── single source of truth
                     │  (event-sourced, versioned)    │      (no free-text chatter)
                     └───────────────┬───────────────┘
        ┌────────────────────────────┼────────────────────────────┐
        ▼                            ▼                            ▼
  DISCOVERY TEAM               LOGISTICS TEAM                 RISK TEAM
  Destination                  Flight                        Visa / Border
  Local Expert                 Hotel                         Safety / Risk
  Experience                   Transport                     Weather
  Food                         Route Optimizer               Health
  Events                       Budget                        Insurance
        └────────────────────────────┼────────────────────────────┘
                                     ▼
                     ┌───────────────────────────────┐
                     │       NEGOTIATION ENGINE       │
                     │ conflicts → utilities → Pareto │
                     │  candidates: cheap/comfort/bal │
                     └───────────────┬───────────────┘
                                     ▼
                     ┌───────────────────────────────┐
                     │   CONSTRAINT + VALIDATION      │
                     │ temporal·geo·budget·visa·wx    │
                     └───────────────┬───────────────┘
                       fail ▲        │ pass
                            └────────┤ (feed back into negotiation)
                                     ▼
                     ┌───────────────────────────────┐
                     │     HUMAN APPROVAL GATE        │
                     │ APPROVE · MODIFY · REPLAN · ✗  │
                     └───────────────┬───────────────┘
                                     ▼
                     ┌───────────────────────────────┐
                     │  EXECUTION / BOOKING (saga)    │  ← never autonomous
                     └───────────────┬───────────────┘
                                     ▼
                     ┌───────────────────────────────┐
                     │      ON-TRIP COPILOT           │
                     │ event bus → impact → replan    │
                     └───────────────────────────────┘

  Cross-cutting layers (touch everything above):
  ── Tool Gateway (vendor failover, rate-limit, cache)
  ── Grounding & Truth layer (citations + freshness)
  ── Memory (short-term / long-term / episodic)
  ── Observability + Security + Compliance
```

---

## 5. Core Concepts

### 5.1 Agents vs. deterministic tools *(a deliberate split)*

Not everything should be an LLM. Making currency conversion an "agent" is slow, costly, and
*less* reliable than a function.

- **Reasoning agents (LLM):** judgment, trade-offs, ranking, natural-language synthesis —
  Orchestrator, Negotiator, Local Expert, Destination, Flight/Hotel *ranking*, Copilot.
- **Deterministic tools (pure functions):** currency conversion, timezone/DST math, distance &
  ETA, price summation, date arithmetic, constraint checks. **No LLM.**

Rule of thumb: *if the output is a fact or a calculation, it's a tool; if it's a judgment, it's
an agent.* This keeps the system cheaper, faster, and more testable.

### 5.2 `TripState` — the single source of truth

Agents never exchange free-text "WhatsApp messages." They read and write **one structured,
versioned `TripState`** (schema in §17.1). This eliminates drift ("which flight did we pick?")
and makes every decision auditable.

### 5.3 Structured message protocol

When an agent reports, it returns a **typed envelope** (schema in §17.2): recommendations,
constraints it checked, conflicts it detected, a confidence score, and **sources**. This is
what makes negotiation and grounding possible.

### 5.4 Hard vs. soft constraints (with weights)

- **Hard constraints** — must never break: `budget ≤ ₹2L`, visa obtainable, fixed dates,
  passport validity. A plan that violates one is *invalid*, full stop.
- **Soft constraints** — optimize, weighted by the traveler: hotel ≥ 4★, walking < 8 km/day,
  ≤ 1 stop, relaxed pace. These become terms in the utility function (§8).

---

## 6. The Agent Roster

~27 specialized agents across four teams. Each row notes whether it's an LLM **agent** or a
deterministic **tool**, its model tier (see §7), and how fresh its data must be.

### Meta / control

| Agent | Responsibility | Type | Tier |
| --- | --- | --- | --- |
| Orchestrator | Intent → constraints → task DAG → conflict routing | Agent | High |
| Traveler Profile | Build & update the preference model; cold-start elicitation | Agent | Mid |
| Negotiator | Resolve conflicts, generate Pareto candidates | Agent | High |
| Itinerary Optimizer | Multi-objective day/route optimization | Agent + tools | Mid |
| Validator | Run all validators, route failures back to negotiation | Tools + Agent | Low |
| Human-Approval Controller | Drive the 4 HITL gates | Agent | Mid |
| On-Trip Copilot | Monitor events, assess impact, trigger replan | Agent | High |
| Emergency | Crisis playbooks (lost passport, medical, disaster) | Agent | High |

### Discovery team

| Agent | Responsibility | Data source | Freshness |
| --- | --- | --- | --- |
| Destination | Discover & score destinations | Places, guides | Slow |
| Local Expert | Neighborhood-level, "what a local recommends" | Places, reviews | Daily |
| Experience/Activity | Attractions, hidden gems, day-trips (with hours, duration) | Activities API | Daily |
| Food | Cuisine/diet/halal/vegan, authentic-vs-tourist, hours | Places | Daily |
| Events | Concerts, festivals, markets on the travel dates | Events API | Daily |
| Seasonality | Peak/rainy season, closures, crowd levels | Guides, weather | Slow |

### Logistics team

| Agent | Responsibility | Data source | Freshness |
| --- | --- | --- | --- |
| Flight (search+rank) | Price/duration/stops/baggage/refund/airline fit | Amadeus | Minutes |
| Connection-Risk | Flag tight/international/large-airport transfers | Derived | Minutes |
| Fare-Rules | Compare refund/change/baggage rules | Amadeus | Minutes |
| Hotel | Location, transit, safety, cancellation, amenities | Booking / Amadeus | Minutes |
| Transport | Airport transfer, transit, taxi, rental, intercity | Google Routes | Hours |
| Route Optimizer | Order daily sights to minimize backtracking | Google Routes | Hours |
| Map/Spatial | Geographically group each day | Google Places | Hours |
| Budget (planner+guardian) | Full cost model + live overrun alerts | Tools | Minutes |
| Currency | INR/JPY/EUR/USD, cash-vs-card, ATM | Tool (FX) | Hours |

### Risk team

| Agent | Responsibility | Data source | Freshness |
| --- | --- | --- | --- |
| Visa / Border | Visa/eVisa/transit, passport validity, proof-of-funds | **IATA/Timatic** | Very high |
| Safety / Risk | Advisories, crime, scams, unrest, strikes | Advisory feeds | Hours |
| Weather | Forecast, rain probability, alerts, activity suitability | Google Weather | Hours |
| Health | Vaccination guidance, disease/altitude/water risk | **WHO** | High |
| Insurance | Map trip-type → risk → coverage needed | Insurance APIs | Slow |

### Support (before/around trip)

| Agent | Responsibility | Type |
| --- | --- | --- |
| Packing | Dynamic list from destination/season/activities | Agent |
| Document | Travel wallet; ingest booking emails/PDFs/passport scans | Agent + tools |
| Local Law & Culture | Dress, alcohol, photography, drone, tipping, etiquette | Agent |
| Connectivity | eSIM vs local SIM vs roaming decision | Agent |
| Sustainability | Emissions, rail alternatives, local businesses | Agent |
| Group Preference | Aggregate multiple travelers' priorities fairly | Agent |
| Time & Calendar | Timezone/DST, holidays, opening hours, jet-lag | **Tool** |

> Deterministic on purpose: currency, timezone/DST, distance/ETA, price totals, date math.

---

## 7. Execution Model

Running 27 LLM agents naively is a **cost and latency bomb**. Safar treats the plan as an
**execution DAG**, not a loop.

### 7.1 Phases (a LangGraph state machine)

```
INTAKE ──► DISCOVER ──► PLAN ──► NEGOTIATE ──► VALIDATE ──► APPROVE ──► EXECUTE ──► MONITOR
  │            │(parallel)  │(parallel)   │            │  ▲ fail │            │           │
  └─clarify◄───┘            │             │            └──┘      └─replan◄────┘◄──────────┘
```

- **DISCOVER** (fan-out, parallel): Destination, Experience, Food, Events, Weather, Safety,
  Visa all run concurrently — they don't depend on each other.
- **PLAN** (partly parallel): Flight, Hotel, Transport run in parallel; Route Optimizer &
  Budget run after (they consume the above).
- **NEGOTIATE / VALIDATE / APPROVE / EXECUTE / MONITOR**: mostly sequential.

### 7.2 Parallel vs. sequential (the DAG)

```
                 ┌─► Destination ─┐
                 ├─► Experience ──┤
   INTAKE ──────►├─► Food ────────┼─► (join) ─► NEGOTIATE ─► VALIDATE ─► APPROVE
                 ├─► Events ──────┤        ▲
                 ├─► Weather ─────┤        │
                 ├─► Safety ──────┤   ┌─► Flight ─┐
                 └─► Visa ────────┘   ├─► Hotel ──┼─► Route ─► Budget ─┘
                                      └─► Transport┘
```

### 7.3 Model tiering (cost control)

| Tier | Used by | Rationale |
| --- | --- | --- |
| **High** (frontier) | Orchestrator, Negotiator, Copilot, Emergency | Hard reasoning & trade-offs |
| **Mid** | Rankers, Local Expert, Profile | Structured judgment |
| **Low / cheap** | Summarizers, formatters, simple extractors | Cheap, high-volume |
| **None (tool)** | FX, timezone, distance, totals, validators | Deterministic |

### 7.4 Per-agent resilience

Every agent node declares: **timeout**, **retry policy** (exponential backoff), and a
**fallback/degradation** path. If the Flight API is down: retry → fail over to an alternate
vendor (§16) → if still down, mark that slice `DEGRADED` in `TripState` and surface it to the
user rather than fabricating data.

### 7.5 Budgets

Each trip carries a **cost budget** (max LLM $/trip) and a **latency budget** (target wall-clock
for a first candidate plan). Caching (§16) and parallelism keep both bounded. If a budget is
about to blow, the Orchestrator drops low-tier "nice-to-have" agents first.

---

## 8. The Negotiation Engine *(the heart)*

The goal explicitly asks for **negotiation and conflict resolution**. This is the mechanism —
not just a label.

### 8.1 Conflicts are typed

```
Conflict = {
  type: HARD_VIOLATION | RESOURCE | PREFERENCE,
  resource?: TIME | MONEY | ENERGY,
  agents: [...],        # who is in tension
  claim_a, claim_b,     # the opposing structured claims
  severity: 0..1
}
```

- **HARD_VIOLATION** — a hard constraint is broken (over budget, visa impossible). Non-negotiable:
  the offending option is discarded.
- **RESOURCE** — competition over a shared budget of time / money / energy.
- **PREFERENCE** — soft-constraint tension (cheap vs. comfortable).

### 8.2 Objectives & utility

Each candidate plan is scored on weighted objectives. Weights come from the traveler profile
(and are shown to the user, so it's explainable):

```
Utility(plan) =  w_exp · Experience
               + w_com · Comfort
               + w_saf · Safety
               + w_fit · PreferenceMatch
               − w_cost · CostNorm
               − w_time · TravelTimeNorm
               − w_risk · Risk
               − w_wait · Waiting
               − w_back · Backtracking
subject to:    all HARD constraints satisfied  (else Utility = −∞)
```

Each term is normalized to `[0,1]` by a deterministic tool so scores are comparable.

### 8.3 The protocol: propose → challenge → resolve

```
1. Each agent PROPOSES its best option(s) as scored, sourced claims.
2. The Orchestrator detects CONFLICTS (typed, above).
3. For each conflict, involved agents may CHALLENGE:
   e.g. Flight: "6 AM flight is cheapest."
        Schedule: "6 AM arrival → 7-hour wait before 2 PM check-in."
        Comfort:  "User dislikes early flights (profile)."
        Budget:   "Comfortable alt is +₹3,000."
4. The Negotiator RESOLVES by computing Utility across combinations and
   producing the Pareto front (no candidate dominates another).
```

### 8.4 Output: three candidates on the Pareto front

The engine never returns one answer. It returns a small, meaningful set:

```
Candidate A — "Saver"     : maximize (−cost), accept some discomfort
Candidate B — "Comfort"   : maximize experience+comfort, higher cost
Candidate C — "Balanced"  : best overall Utility at profile weights
```

Tie-breaking: highest Utility → then higher confidence → then fewer soft-constraint violations
→ then lower cost. Ties beyond that are surfaced to the human, not silently broken.

### 8.5 Group travel (social choice)

For multiple travelers with conflicting priorities (A: budget, B: nightlife, C: food, D:
relaxation), individual utilities are combined via **Nash bargaining** (maximize the product of
each person's utility gain over their disagreement point) — which favors *balanced* outcomes
over ones that crush any single traveler. A simpler **weighted-sum** fallback is available.
Fairness note + per-person satisfaction scores are shown to the group.

### 8.6 Pseudocode

```python
def negotiate(options_by_agent, hard_constraints, weights, travelers):
    # 1. enumerate feasible combinations (prune anything breaking a hard constraint)
    combos = feasible_combinations(options_by_agent, hard_constraints)
    if not combos:
        return RelaxationRequest(find_binding_constraints(options_by_agent))

    # 2. score every feasible combo
    scored = []
    for combo in combos:
        if len(travelers) > 1:
            u = nash_bargaining_utility(combo, travelers, weights)
        else:
            u = utility(combo, weights)          # §8.2
        scored.append((u, combo))

    # 3. Pareto front, then pick the 3 archetypes
    front = pareto_front(scored, objectives=OBJECTIVES)
    return {
        "saver":    argmin(front, key=cost),
        "comfort":  argmax(front, key=comfort_plus_experience),
        "balanced": argmax(front, key=lambda c: utility(c, weights)),
        "conflicts_resolved": explain(front),    # for user-facing "why"
    }
```

If **no** feasible combination exists, the engine returns a `RelaxationRequest` identifying the
binding constraint (e.g. "no plan fits ₹2L *and* 4★ hotels — relax one?") instead of failing
silently. That request goes to the human (§10).

---

## 9. Constraint & Validation Engine

Before anything reaches the human, candidate plans pass a battery of validators. **A failure
does not dead-end** — it is routed back into negotiation as a new constraint.

| Validator | Checks | Example failure |
| --- | --- | --- |
| Temporal | Opening hours vs. arrival times, no overlaps | Museum closes 17:00, plan arrives 17:30 |
| Geographic | Feasible daily routing, no zig-zag | Hotel → A → B → A backtrack |
| Budget | Total ≤ hard budget (incl. reserve) | ₹2,14,000 > ₹2,00,000 |
| Visa | Destination + **transit** countries covered | Transit country needs a visa |
| Weather | Outdoor activity vs. severe forecast | Trek at 15:00, 80% rain |
| Booking | Check-in after arrival, dates consistent | Check-in before flight lands |
| Accessibility | Step-free routes / rooms if required | Walk-up-only attraction booked |

Deterministic validators are **tools**, not agents — fast and repeatable. The Validator agent
only orchestrates them and writes structured results to `TripState`.

---

## 10. Human-in-the-Loop (HITL)

The goal requires **human approval before finalizing**. Safar goes further: HITL at **four**
points, not one.

1. **Intake gate — clarification.** Ambiguous request ("somewhere warm, cheap, December")? The
   Orchestrator asks targeted questions and **logs assumptions** it had to make.
2. **Mid-plan gate — before anything irreversible or expensive.** Non-refundable fares, large
   spends, sharing personal data → confirm first.
3. **Final approval gate — the plan.** The human sees the candidates and chooses:

   ```
   AI Proposed Plan — Candidate C (Balanced)   Confidence 93%
   Cost ₹1,84,500 · Risk Low · Walking 7.2 km/day · 1 stop

   [ APPROVE ]   [ MODIFY ]   [ REPLAN ]   [ REJECT ]
   ```

   - **APPROVE** → proceed to execution (§13).
   - **MODIFY** → the user edits a lever (raise hotel budget, avoid early flights). The change
     becomes a new constraint; only the *affected* sub-graph re-runs (not the whole plan).
   - **REPLAN** → re-run negotiation with a fresh emphasis (e.g. "prioritize comfort").
   - **REJECT** → discard and restart intake.
4. **On-trip gate — live decisions.** During the trip, high-impact reactions (rebooking a
   flight, spending on a new transfer) require a quick human "yes."

**Hard rule:** booking, payment, accepting terms, or transmitting personal data is **never**
autonomous. The system prepares and explains; the human confirms.

---

## 11. Grounding & Truth Layer

The most dangerous failure mode is a confident wrong fact (a wrong visa rule can get someone
denied boarding). Countermeasures:

- **Cite tool output, not memory.** Every factual claim carries provenance:

  ```json
  {
    "claim": "Museum open until 20:00",
    "source": "places_api/place/ChIJ...",
    "retrieved_at": "2026-08-29T09:12:00Z",
    "confidence": 0.94,
    "expires_at": "2026-08-30T00:00:00Z"
  }
  ```

- **Freshness rules per data class:**

  | Data | Max age |
  | --- | --- |
  | Visa / border rules | Very high — re-verify per trip |
  | Flight / hotel price | Minutes |
  | Weather | Hours |
  | Restaurant / attraction hours | Daily |
  | Travel-guide/background | Slow |

- **High-stakes guardrails.** Visa, Health, and Safety agents **must** ground on official
  sources (IATA/Timatic, WHO, government advisories), attach a **"verify with the official
  source"** disclaimer, and are **never autonomous**. If they can't ground a claim, they return
  "unknown — check official source," not a guess.
- **Structured-output validation.** Every agent reply is schema-validated (§17.2); malformed or
  unsourced claims are rejected before they can influence a plan.

---

## 12. On-Trip Copilot & Replanning

This is where Safar stops being a planner and becomes an *agent*.

```
Trip live ─► Event bus ─► Detect event ─► Assess impact ─► Generate alternatives
          ─► Negotiate ─► (ask human if high-impact) ─► Re-plan ─► Update TripState
```

- **Event triggers:** flight status change/delay/gate change, weather alert, attraction
  closure, traffic/transit disruption, budget overrun, a new nearby opportunity.
- **Impact assessment.** A flight delayed 3h cascades: airport transfer, hotel check-in, dinner
  reservation, next-day activity, sleep/jet-lag. The Copilot computes the full blast radius.
- **Minimal-disruption replanning.** Items are **locked** (already booked/paid) or **flexible**.
  Replanning changes as little as possible and is *change-cost aware* — it won't rebook a paid
  hotel to save 10 minutes.
- **Offline resilience.** A traveler abroad may have no data. The itinerary, offline maps, and
  emergency numbers are cached on-device; the Copilot degrades to SMS/local fallback.
- **Emergency mode** (lost passport, missed flight, medical, disaster, theft): returns immediate
  action → nearest relevant service → local emergency number → embassy/consular guidance →
  documents needed → safe next steps.

---

## 13. Booking & Execution (Saga)

*(**Built as a simulated saga** — `safar/engine/booking.py`: authorize → book steps → capture,
with reverse-order compensation and idempotency keys. **No real payment is made and no card
data is touched** — capturing money stays a human action, integrated later.)*

Multi-step booking (flight + hotel + transfer + activity) is a **distributed transaction**. If
the flight books but the hotel fails, you must not leave the traveler half-committed.

- **Saga with compensation.** Each booking step has a matching *compensating action* (cancel/
  refund within the free window). On partial failure, executed steps are compensated in reverse.
- **Idempotency.** Every booking call carries an idempotency key so a retry never double-books.
- **Payment: authorize vs. capture.** Authorize on approval; capture only when the whole saga
  succeeds. PCI scope is isolated; Safar never stores raw card data.
- **Approval interplay.** The human approves the *bundle* (§10 mid-plan gate) before any capture.

```
[approve bundle] → auth payment → book flight ─ok─► book hotel ─fail─► compensate flight
                                     │                                   (cancel in free window)
                                     └──ok─► book transfer ─ok─► capture payment ✔
```

---

## 14. Memory & Personalization

Three layers:

- **Short-term** — the current trip's working state (`TripState`).
- **Long-term (traveler)** — preferences, budget habits, favored airlines/hotels, food, pace.
- **Episodic** — named past trips ("Paris 2026", "Tokyo 2027") for recall and comparison.

**Cold start (trip #1, no history).** The Profile agent runs a short **elicitation** (a few
targeted questions) + sensible defaults (mid-range hotel, moderate pace), and marks each field
as `assumed` vs `confirmed`. Assumptions are visible and easily overridden.

**Learning loop.** During the trip, implicit signals (accepted vs. rejected suggestions) and
after the trip, explicit ratings, update a **preference vector**. Next trip starts smarter:
*"you prefer 4★, public transit, and dislike early-morning activities."*

---

## 15. Data Architecture

```
                    ┌─────────────┐
                    │ PostgreSQL  │  structured facts: users, trips, bookings, audit
                    └──────┬──────┘
                           │
                  ┌────────▼────────┐
                  │   Trip State    │  event-sourced, versioned (source of truth)
                  └────────┬────────┘
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
      Redis            Vector DB          Event Bus
   fast state /       preferences &      live signals:
   cache              semantic memory    flight/weather/events
```

- **PostgreSQL** — durable structured data + audit log.
- **Redis** — hot `TripState` cache, rate-limit counters, locks.
- **Vector DB** — preference embeddings + semantic recall (RAG over past trips/guides).
- **Event bus** — flight/weather/event notifications drive the Copilot.

> **What's built today:** the MVP ships this as **SQLite** (`safar/store.py` — event-sourced
> trips, `agent_runs`, bookings, provenance) and an **in-process event bus** (`safar/events.py`).
> That is the right choice at MVP scale, not a compromise: SQLite is durable and event-sourced,
> and the call sites don't change. PostgreSQL, Redis, a Vector DB (e.g. `pgvector`), and Kafka
> are all **free to self-host** and slot in behind the same interfaces when concurrency and
> multi-worker scale actually demand them.

**Concurrency & consistency.** Many agents write `TripState` concurrently. Writes are
**event-sourced** (append-only events → derived state) with **optimistic concurrency** (version
check on write; conflicting writes are re-based, not lost). No agent overwrites another blindly.

---

## 16. Tool Gateway

Agents never call vendor APIs directly. One **gateway** mediates every external call.

```
Tool Gateway
├── Places · POI · geography          → OpenStreetMap (Nominatim/Overpass)  ┐ free, keyless
├── World knowledge graph             → Wikidata (SPARQL)                   ├─ primary
├── Human travel knowledge            → Wikivoyage (MediaWiki API)          ┘  (grounding)
├── Flight / Hotel / Activities price → Amadeus (keyed, free self-service)  ┐
├── Hotel (availability)              → Booking / Amadeus                   ├─ vendor failover
├── Current POI / hours / ratings     → Google Places (keyed; free monthly quota) ← over OSM ┘
├── Public transport                  → GTFS + GTFS-RT (per-agency feeds, free)
├── Maps · Routes                     → Google Maps Platform (keyed)
├── Weather (forecast)                → Open-Meteo / Google Weather
├── Historical weather (seasonality)  → Open-Meteo Archive / ERA5 (free)
├── Tourism statistics                → government open-data portals
├── Timezone / FX                     → deterministic tools
├── Visa / Travel Docs                → IATA / Timatic-class
├── Safety / Advisories               → government feeds
├── Health                            → WHO
└── Booking / Payment                 → saga simulated; real PSP capture later
```

The gateway adds what raw APIs lack: **rate-limiting**, **retry with backoff**, **circuit
breakers**, **response caching** (keyed by query + freshness class), and **multi-vendor
failover** (Amadeus down → alternate source; mark `DEGRADED` if all fail). Swapping a vendor is
a gateway change, not an agent rewrite.

---

## 17. Technical Spec (build-ready)

### 17.1 `TripState` schema

```jsonc
// TripState — the single source of truth (event-sourced, versioned)
{
  "trip_id": "uuid",
  "version": 42,                       // optimistic-concurrency guard
  "status": "DISCOVER|PLAN|NEGOTIATE|VALIDATE|AWAITING_APPROVAL|BOOKED|LIVE|CLOSED",

  "traveler": {
    "user_id": "uuid",
    "profile_ref": "uuid",             // long-term preferences (Vector DB)
    "party": [ { "name": "str", "weight": 1.0 } ],   // group travel
    "accessibility": { "step_free": false, "wheelchair": false }
  },

  "trip": {
    "origin": "India",
    "destination": ["Tokyo", "Kyoto"],
    "dates": { "start": "2026-11-05", "end": "2026-11-15", "flexible_days": 2 },
    "duration_days": 10,
    "interests": ["food", "culture"],
    "pace": "relaxed"
  },

  "constraints": {
    "hard": { "budget_inr": 200000, "visa_required_ok": true, "dates_fixed": false },
    "soft": { "hotel_stars_min": 4, "max_walk_km_day": 8, "max_stops": 1,
              "max_daily_travel_hours": 3, "avoid_early_flights": true }
  },
  "weights": { "cost":0.9,"comfort":0.7,"experience":0.8,"safety":0.6,"risk":0.5 },

  "candidate_options": { "flights": [], "hotels": [], "activities": [], "transport": [] },
  "candidates": { "saver": {}, "comfort": {}, "balanced": {} },   // Pareto output

  "itinerary": { "days": [ { "date": "", "items": [], "route": [] } ] },
  "bookings": [ { "type": "flight", "status": "AUTH|BOOKED|FAILED", "idempotency_key": "" } ],

  "weather": {}, "risks": {}, "budget": { "planned": {}, "actual": {} },

  "agent_decisions": [ /* structured message envelopes, §17.2 */ ],
  "conflicts": [ /* typed conflicts, §8.1 */ ],
  "assumptions": [ { "field": "hotel_stars_min", "value": 4, "state": "assumed" } ],
  "approval": { "gate": "final", "decision": null, "at": null },

  "provenance": [ /* claim/source/retrieved_at/expires_at, §11 */ ]
}
```

### 17.2 Agent message protocol

```jsonc
// Every agent returns this typed envelope — enables negotiation + grounding
{
  "agent": "flight_agent",
  "task_id": "T123",
  "status": "complete | degraded | failed | needs_input",
  "recommendations": [
    { "option_id": "F1", "summary": "NRT 09:40, 1 stop, ₹58,200",
      "scores": { "cost": 0.7, "comfort": 0.6, "duration": 0.5 },
      "sources": ["amadeus/flight-offers/..."] }
  ],
  "constraints_checked": ["max_stops<=1", "avoid_early_flights"],
  "conflicts": [ { "type": "PREFERENCE", "with": "budget_agent", "note": "comfort +₹3,000" } ],
  "confidence": 0.91,
  "cost_usd": 0.004,             // for observability + budget
  "latency_ms": 820
}
```

### 17.3 LangGraph node/edge (illustrative)

```python
from langgraph.graph import StateGraph, END

g = StateGraph(TripState)

# nodes
g.add_node("intake",   intake_agent)
for a in ["destination","experience","food","events","weather","safety","visa"]:
    g.add_node(a, discovery_agents[a])          # run in parallel
for a in ["flight","hotel","transport"]:
    g.add_node(a, logistics_agents[a])
g.add_node("route", route_optimizer); g.add_node("budget", budget_agent)
g.add_node("negotiate", negotiator); g.add_node("validate", validator)
g.add_node("approve", human_approval_gate); g.add_node("execute", booking_saga)
g.add_node("monitor", on_trip_copilot)

# edges
g.set_entry_point("intake")
g.add_conditional_edges("intake",
    lambda s: "clarify" if s.ambiguous else "discover",
    {"clarify": "intake", "discover": "destination"})     # loop back on ambiguity
# fan-out discovery + logistics → join at negotiate
for a in DISCOVERY + ["route","budget"]:
    g.add_edge(a, "negotiate")
g.add_edge("negotiate", "validate")
g.add_conditional_edges("validate",
    lambda s: "negotiate" if s.validation_failed else "approve")   # failures feed back
g.add_conditional_edges("approve",
    lambda s: {"APPROVE":"execute","MODIFY":"negotiate",
               "REPLAN":"negotiate","REJECT":"intake"}[s.approval.decision])
g.add_edge("execute", "monitor")
g.add_conditional_edges("monitor",
    lambda s: "negotiate" if s.replan_needed else END)
```

### 17.4 Folder structure

```
voyager/
├── orchestrator/          # intake, task DAG, conflict routing
├── agents/
│   ├── discovery/         # destination, local_expert, experience, food, events, seasonality
│   ├── logistics/         # flight, hotel, transport, route, budget, currency
│   ├── risk/              # visa, safety, weather, health, insurance
│   ├── support/           # packing, document, culture, connectivity, sustainability, group
│   └── meta/              # profile, negotiator, optimizer, validator, approval, copilot, emergency
├── engine/
│   ├── negotiation/       # conflict types, utility, pareto, nash, protocol
│   ├── constraints/       # hard/soft model + validators (tools)
│   └── graph/             # LangGraph definition + node wiring
├── tools/                 # deterministic: fx, timezone, distance, totals, date math
├── gateway/               # vendor adapters, failover, rate-limit, cache, circuit-breaker
├── state/                 # TripState schema, event store, projections
├── memory/                # short-term, long-term (vector), episodic
├── data/                  # postgres models, redis, vector db, event bus
├── grounding/             # provenance, freshness, schema validation, disclaimers
├── hitl/                  # 4 approval gates + UI contracts
├── observability/         # tracing, cost/latency metrics, audit
├── eval/                  # golden trips, metrics, regression harness
└── api/                   # app entrypoints
```

### 17.5 Database schema (core tables)

```sql
users(id, created_at, locale, home_country, consent_flags jsonb)
profiles(user_id, preferences jsonb, preference_vector vector, updated_at)
trips(id, user_id, status, origin, destination jsonb, dates jsonb,
      constraints jsonb, weights jsonb, created_at)
trip_events(id, trip_id, seq, type, payload jsonb, created_at)   -- event sourcing
agent_runs(id, trip_id, agent, task_id, status, confidence,
           cost_usd, latency_ms, sources jsonb, created_at)      -- observability
conflicts(id, trip_id, type, resource, agents jsonb, severity, resolved bool)
candidates(id, trip_id, archetype, plan jsonb, utility, created_at)
bookings(id, trip_id, type, vendor, status, idempotency_key,
         compensation jsonb, created_at)                         -- saga
approvals(id, trip_id, gate, decision, decided_by, at)
provenance(id, trip_id, claim, source, retrieved_at, expires_at, confidence)
```

---

## 18. Evaluation & Testing

You cannot improve what you don't measure. Safar ships with an eval harness.

- **Golden test-trips.** A fixed suite of scenarios (e.g. "10-day Japan, ₹2L, food+culture,
  relaxed"; "3-day Dubai business"; "group of 4, mixed priorities") with known-good constraints.
- **Metrics:**
  - **Constraint-satisfaction rate** — % of hard constraints never violated (target 100%).
  - **Budget accuracy** — |planned − actual| / budget.
  - **Feasibility** — % of plans passing all validators.
  - **Plan-acceptance rate** — approved without major modification.
  - **Replan latency** — time from event → updated plan.
  - **Grounding rate** — % of factual claims with a fresh, valid source.
- **Regression harness.** Run the golden suite on every change; block merges that drop
  constraint-satisfaction or grounding below thresholds.

---

## 19. Observability, Security & Compliance

**Observability (dev-facing).** Every agent run records: inputs, tools called, decision,
*reasoning*, sources, latency, cost, confidence. Without this, a 27-agent system is
undebuggable. **Explainability (user-facing)** is separate: each recommendation shows *why*
(which agent, which trade-off) — traceable back to the human.

**Security.** API-key vault; OAuth; encrypted traveler data; PII separation; scoped permissions;
audit logs; human approval for every irreversible action; payment isolation (§13).

**Compliance.** Passport, visa, health, and payment data are sensitive.
- **GDPR** (EU trips) and **India DPDP** — lawful basis, consent, purpose limitation.
- **Health data** = special category → stricter handling, minimal retention.
- **Retention per data class** (prices are ephemeral; documents are user-controlled).
- **Consent management**, **data residency**, and **right-to-delete** are first-class.
- **Safety-critical disclaimers.** Visa/health/safety outputs always carry "verify with the
  official source" and are never acted on autonomously.

---

## 20. MVP & Roadmap

27 agents is not a first build. Prove the **core loop** first. Status markers below reflect
the current repo (✅ built & verified · ◐ partial · ⬜ not started).

**✅ MVP (demonstrates the goal end-to-end):**
`Orchestrator → {Flight, Hotel, Activity} → Budget(tool) → Negotiator → Validator → Human
Approval.` Single traveler + **group** (Nash), gateway with free live sources (mock priced
fallback), `TripState` + structured protocol, three Pareto candidates, day-by-day itinerary,
and the approval gate with `MODIFY`/`REPLAN`. *Shows task-division + negotiation +
conflict-resolution + human approval — the whole goal.*

**✅ Phase 2 — trust & breadth:** Visa, Safety, Weather, Health (grounded + disclaimers);
Discovery/Support teams; itinerary route-ordering (basic Route Optimizer); eval harness.
*Remaining:* Fare-Rules, Connection-Risk, Events feed (keyed).

**✅ Phase 3 — lifecycle:** On-Trip Copilot + event bus + replanning; Memory & personalization.
*Remaining:* Document ingestion (booking emails/PDFs), offline/SMS resilience.

**◐ Phase 4 — execution:** Booking saga + compensation + idempotency + auth/capture is built
**as a simulation**; group negotiation ✅. *Remaining:* real payment capture (needs a PSP —
deliberately not faked), connectivity/sustainability/emergency agents.

**Infra note:** the build runs on SQLite + in-process bus + sequential Python by design (§15).
Postgres/Redis/Vector-DB/Kafka/LangGraph are free to self-host and are a *scale-later*
decision, not a blocker — don't adopt them before concurrency actually demands it.

---

## 21. Appendix: v1 → v2 Improvements

The original research (v1) was an excellent *taxonomy* but a *catalogue of parts*, not a system
design. This table is the visible record of every gap found and the fix baked into v2.

| # | Gap in v1 | Fix in v2 (§) |
| --- | --- | --- |
| 1 | Negotiation named "the heart" but no algorithm | Conflict types + utility + Pareto + protocol + pseudocode (§8) |
| 2 | Conflicts never represented | Typed conflicts: hard/resource/preference (§8.1) |
| 3 | Human approval only at the end | 4 HITL gates; `MODIFY` loop defined (§10) |
| 4 | Group preferences unsolved | Nash bargaining / weighted utility + fairness (§8.5) |
| 5 | 27 LLM agents = cost/latency bomb | Execution DAG + model tiering + budgets (§7) |
| 6 | No orchestration/execution model | LangGraph state machine + retries/timeouts/fallback (§7, §17.3) |
| 7 | Concurrent state writes undefined | Event-sourcing + optimistic concurrency (§15) |
| 8 | Tool gateway lacked resilience | Rate-limit, backoff, circuit-breaker, cache, vendor failover (§16) |
| 9 | Grounding thin | Cite tool output, schema-validate, "unknown" paths (§11) |
| 10 | High-stakes agents unguarded | Official-source citation + disclaimers, never autonomous (§11) |
| 11 | No evaluation strategy | Golden trips + metrics + regression harness (§18) |
| 12 | Booking/payment undefined | Saga + compensation + idempotency + auth/capture (§13) |
| 13 | No user-facing explainability | "Why" on every recommendation, traceable (§19) |
| 14 | Cold-start personalization | Elicitation + defaults + assumed/confirmed flags (§14) |
| 15 | No offline resilience | Cached itinerary/maps/emergency + SMS fallback (§12) |
| 16 | Real-world input ignored | Document agent ingests emails/PDFs/passport (§6, §20) |
| 17 | Accessibility only a profile field | Propagated as a hard constraint into routing/hotels (§9) |
| 18 | No localization | Currency/units/dates + translation for on-ground (§6) |
| 19 | Time/fatigue under-modeled | Jet-lag, rest days, daily-energy budget (§8.2, §12) |
| 20 | Intake ambiguity unhandled | Clarification loop + logged assumptions (§10) |
| 21 | Compliance shallow | GDPR/DPDP, health = sensitive, retention-per-class (§19) |
| 22 | Post-trip learning unspecified | Ratings → preference-vector update (§14) |
| 23 | No MVP / build phasing | Lean 6-agent MVP + phased roadmap (§20) |
| 24 | Safety disclaimers/liability absent | Standing disclaimers; non-autonomous high-stakes (§11, §19) |

---

## Data sources (prioritized)

Sources ranked by priority. Free/keyless ones are the primary grounding layer and match the
"free live APIs" direction — they replace the mock `data/*.json` for geography, POI, knowledge,
and transport. Keyed sources add live pricing (Amadeus) and premium POI (Google Places).

| Pri | Source | Use | Owning agent(s) | Freshness | Key? |
| --- | --- | --- | --- | --- | --- |
| 🔥🔥🔥 | **OpenStreetMap** (Nominatim/Overpass) | places + geography | Map/Spatial, Local Expert, Food, Transport, Route | slow/daily | free, keyless |
| 🔥🔥🔥 | **Wikidata** (SPARQL) | world knowledge graph (coords, country, links) | Destination, Local Expert, Culture, Seasonality | slow | free, keyless |
| 🔥🔥🔥 | **Wikivoyage** (MediaWiki API) | human travel knowledge (districts, get-around, stay-safe) | Destination, Experience, Local Expert, Culture | slow | free, keyless |
| 🔥🔥🔥 | **Amadeus** | live flight/hotel/activity **pricing** | Flight, Hotel, Activity, Fare-Rules | minutes | keyed (free self-service) |
| 🔥🔥🔥 | **GTFS + GTFS-RT** | public transport schedules + realtime | Transport, Route, On-Trip Copilot | static slow / RT seconds | free (per-agency) |
| 🔥🔥🔥 | **Google Places** | current POI, hours, ratings | Local Expert, Food, Experience, Map | daily | keyed; **free monthly quota** (India ~70k events), then paid — premium/fallback over OSM |
| 🔥🔥 | **Government tourism data** | tourism statistics, seasonality, advisories | Seasonality, Safety, Destination | slow | mostly free (open-data) |
| 🔥🔥 | **Historical weather** (Open-Meteo Archive / ERA5) | seasonality — *not* forecast | Seasonality, Weather-context, Packing | slow | free, keyless |
| 🔥🔥 | **Historical prices** | cost prediction | Budget, Flight/Hotel ranking | — | own store (Amadeus snapshots over time) |
| 🔥🔥 | **User feedback** | personalization | Traveler Profile, Negotiator weights | per-trip | own store (Postgres/Vector) |
| 🔥 | **Synthetic datasets** | initial bootstrap + eval golden-trips | eval harness, Profile cold-start | one-time | generated |

### The data-role split *(grounding ≠ fine-tuning)*

**"Data to train the AI" ≠ "fine-tune the LLM on every source."** The frontier LLM is **not**
fine-tuned on travel facts — facts go stale and fine-tuning them invites hallucination (the exact
failure §11 exists to prevent). Each source is used by role:

- **Grounding / retrieval** (live-fetched via the gateway, cited in provenance §11, never
  memorized by the model): OSM, Wikidata, Wikivoyage, Amadeus, GTFS, Google Places, government
  tourism, historical weather. *This is 8 of the 11 — the default.*
- **Prediction** (a small, classic-ML model — not the LLM): historical prices → cost predictor.
- **Personalization** (a preference *vector*, not model weights): user feedback → profile (§14).
- **Train / bootstrap** (the only true "training" bucket, and only for our own small models +
  eval golden-trips — never the frontier LLM): synthetic datasets.

All external calls go through the Tool Gateway (§16); all factual claims carry provenance +
freshness (§11).

---

*Safar is a design for a genuinely agentic travel system — agents that divide the work,
negotiate their disagreements, ground their facts, and hand the final decision to a human.*
