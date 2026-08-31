"""Booking & Execution — saga with compensation + idempotency (readme §13).

SIMULATED ONLY. No real payment is made and NO card data is touched — capturing
money and entering payment details stay human actions (readme §10/§13). This
demonstrates the saga: authorize → book steps → capture, with reverse-order
compensation on partial failure, and idempotency keys so a retry never
double-books.
"""
import uuid

from .. import store, events


def execute(state, pick: str = "balanced", fail_at: str | None = None) -> dict:
    """Run the booking saga for a candidate. `fail_at` injects a failure to show
    compensation (e.g. fail_at='hotel')."""
    cand = state.candidates.get(pick) or {}
    trip_id = state.trip_id
    total = cand.get("cost_inr", 0)
    idem = uuid.uuid4().hex[:8]
    steps = [
        ("flight", cand.get("flight", "flight"), 0.40),
        ("hotel", cand.get("hotel", "hotel"), 0.40),
        ("transfer", "airport transfer", 0.10),
        ("activity", ", ".join(cand.get("activities", []))[:40] or "activities", 0.10),
    ]
    log = ["AUTH: payment hold placed (authorize, not capture) — no card data stored"]
    done: list[str] = []

    for typ, desc, frac in steps:
        if fail_at == typ:
            log.append(f"✗ {typ} booking FAILED")
            for d in reversed(done):
                store.record_booking(trip_id, d, "mock", "COMPENSATED", f"{idem}-{d}", 0)
                log.append(f"↩ compensated {d} (cancelled within free window)")
            log.append("✗ auth released — nothing captured")
            events.publish("booking.failed", {"trip": trip_id, "failed_at": typ})
            return {"status": "FAILED", "failed_at": typ, "log": log}
        amt = round(total * frac)
        store.record_booking(trip_id, typ, "mock", "BOOKED", f"{idem}-{typ}", amt)
        done.append(typ)
        log.append(f"✓ booked {typ}: {desc}  (₹{amt:,}, idem {idem}-{typ})")

    log.append(f"✓ CAPTURE payment ₹{total:,.0f} — saga complete")
    events.publish("booking.captured", {"trip": trip_id, "amount": total})
    state.status = "BOOKED"
    store.append_event(trip_id, "booked", {"amount_inr": total, "pick": pick})
    return {"status": "BOOKED", "amount_inr": total, "log": log}
