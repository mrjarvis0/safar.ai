"""Booking & Execution — saga with compensation + idempotency (readme §13).

Two modes, chosen by `config.booking_mode()`:

  • simulate (DEFAULT) — the demo saga: authorize → book steps → capture, with
    reverse-order compensation on partial failure and idempotency keys so a retry
    never double-books. No external calls, no card data.

  • live — books the REAL flight (Amadeus Flight Create Orders → PNR) and creates
    a REAL payment ORDER (Razorpay/Stripe), when Phase-3 keys are set. Even here
    Safar NEVER captures money on its own: it reserves the seat, creates an
    *authorize-only* order, and hands the actual payment (capture) to a human.
    `confirm_payment()` and `refund()` are separate, HUMAN-CONFIRMED steps
    (readme §10/§13). Card data never reaches Safar — the PSP's hosted checkout
    owns PCI scope.

Backwards compatible: `execute(state, pick)` keeps its old signature and, with no
keys, behaves exactly like the original simulated saga.
"""
import uuid

from .. import config, events, store
from ..gateway import gateway, payment


# ============================================================ entry point =====
def execute(state, pick: str = "balanced", fail_at: str | None = None,
            mode: str | None = None, travelers: list | None = None,
            contact: dict | None = None) -> dict:
    """Run the booking saga for a candidate.

    `fail_at` injects a failure to demonstrate compensation (e.g. fail_at='hotel').
    `mode` overrides the configured booking mode ('simulate' | 'live').
    `travelers`/`contact` are required by a real airline order (human-supplied);
    Safar never fabricates passenger identities.
    """
    mode = (mode or config.booking_mode()).lower()
    if mode == "live":
        return _execute_live(state, pick, travelers, contact, fail_at)
    return _execute_simulated(state, pick, fail_at)


# ============================================================ simulate ========
def _execute_simulated(state, pick: str, fail_at: str | None) -> dict:
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
    return {"status": "BOOKED", "amount_inr": total, "log": log, "mode": "simulate"}


# ============================================================ live ============
def _execute_live(state, pick: str, travelers: list | None,
                  contact: dict | None, fail_at: str | None) -> dict:
    cand = state.candidates.get(pick) or {}
    trip_id = state.trip_id
    total = cand.get("cost_inr", 0)
    idem = uuid.uuid4().hex[:8]
    prov = payment.active_provider()
    log = [f"MODE: live · payment provider = {prov}"]
    done: list[dict] = []          # [{type, idem, ref}] booked steps for compensation
    air_order_id = ""              # Amadeus order id, for cancellation/compensation

    # 1. payment ORDER — pending, authorize-only. No money moves; no card data.
    try:
        order = payment.create_order(total, receipt=f"safar-{trip_id}",
                                     notes={"pick": pick, "trip": trip_id})
    except Exception as e:  # noqa: BLE001
        log.append(f"✗ payment order failed: {str(e)[:140]}")
        return {"status": "FAILED", "failed_at": "payment_order", "log": log,
                "mode": "live"}
    order_id = order["order_id"]
    log.append(f"AUTH: payment order {order_id} created "
               f"(authorize only — NOT captured; card data never touches Safar)")

    # 2. flight — real airline order (PNR) when the offer is bookable
    fid = cand.get("flight_id")
    if fail_at == "flight":
        return _compensate(state, trip_id, "flight", order_id, air_order_id, done, log)
    if gateway.has_amadeus() and cand.get("flight_bookable") and fid:
        priced = gateway.amadeus_price_flight(fid)
        if not priced.get("ok"):
            log.append(f"✗ flight re-pricing failed: {priced.get('error')}")
            return _compensate(state, trip_id, "flight", order_id, air_order_id, done, log)
        log.append(f"• flight re-priced live: ₹{priced['price_inr']:,}")
        if not travelers:
            # a real airline order needs passenger identity/documents — human input.
            store.record_booking(trip_id, "flight", "amadeus", "NEEDS_INPUT",
                                 f"{idem}-flight", priced["price_inr"], "")
            _release_order(order_id, log)
            log.append("⏸ paused: traveler details (name/DOB/passport) required — "
                       "Safar never fabricates passenger identities.")
            return {"status": "NEEDS_INPUT", "needs": "traveler_details",
                    "order_id": order_id, "amount_inr": total, "log": log,
                    "mode": "live"}
        booked = gateway.amadeus_book_flight(fid, travelers, contact)
        if not booked.get("ok"):
            log.append(f"✗ flight order failed: {booked.get('error')}")
            return _compensate(state, trip_id, "flight", order_id, air_order_id, done, log)
        air_order_id = booked.get("order_id") or ""
        ref = booked.get("pnr") or air_order_id
        store.record_booking(trip_id, "flight", "amadeus", "BOOKED",
                             f"{idem}-flight", priced["price_inr"], ref)
        done.append({"type": "flight", "idem": f"{idem}-flight", "ref": ref})
        log.append(f"✓ flight booked · PNR {ref or '—'} (order {air_order_id or '—'})")
    else:
        store.record_booking(trip_id, "flight", prov, "HOLD",
                             f"{idem}-flight", round(total * 0.40), "")
        done.append({"type": "flight", "idem": f"{idem}-flight", "ref": ""})
        log.append("• flight HELD (no live air-booking key / mock offer) — "
                   "confirm on payment")

    # 3. hotel / transfer / activity — reserved as HOLDs (no free booking API);
    #    they confirm when the human completes payment.
    for typ, frac in (("hotel", 0.40), ("transfer", 0.10), ("activity", 0.10)):
        if fail_at == typ:
            return _compensate(state, trip_id, typ, order_id, air_order_id, done, log)
        amt = round(total * frac)
        store.record_booking(trip_id, typ, prov, "HOLD", f"{idem}-{typ}", amt, "")
        done.append({"type": typ, "idem": f"{idem}-{typ}", "ref": ""})
        log.append(f"• {typ} HELD (₹{amt:,}) — confirms on payment")

    # 4. STOP before capture. Hand checkout to a human (readme §10/§13).
    log.append("⏸ AWAITING PAYMENT — a human completes checkout; Safar will not "
               "capture money autonomously.")
    events.publish("booking.awaiting_payment",
                   {"trip": trip_id, "order": order_id, "amount": total})
    store.save_trip(state)
    store.append_event(trip_id, "awaiting_payment",
                       {"order_id": order_id, "amount_inr": total, "pick": pick})
    state.status = "AWAITING_PAYMENT"
    return {"status": "AWAITING_PAYMENT", "order_id": order_id, "idem": idem,
            "amount_inr": total, "checkout": order.get("checkout"),
            "client_secret": order.get("client_secret"), "log": log,
            "mode": "live"}


# ============================== human-confirmed capture (money moves) =========
def confirm_payment(state, idem: str, payment_id: str, order_id: str = "",
                    signature: str = "", human_confirmed: bool = False) -> dict:
    """Finalize a live booking AFTER a human has paid in the hosted checkout.

    HUMAN-GATED: `human_confirmed` must be True (the user clicked confirm). This
    verifies the payment (Razorpay signature when provided), captures the
    authorized amount via the PSP, and flips the HOLD/BOOKED rows to CAPTURED.
    Safar itself never initiates capture without this explicit human step.
    """
    trip_id = state.trip_id
    total = (state.candidates.get(state.approval.get("pick", "balanced")) or {}).get("cost_inr", 0)
    log = []
    if payment.active_provider() == "razorpay" and signature:
        if not payment.verify_razorpay_signature(order_id, payment_id, signature):
            return {"status": "REJECTED", "reason": "signature verification failed",
                    "log": ["✗ payment signature invalid — not capturing"]}
        log.append("✓ payment signature verified")
    try:
        cap = payment.capture(payment_id, total, human_confirmed=human_confirmed)
    except payment.PaymentError as e:
        return {"status": "BLOCKED", "reason": str(e), "log": [f"✗ {e}"]}
    # flip this saga's rows to CAPTURED
    for b in store.bookings(trip_id):
        if b["idempotency_key"].startswith(idem) and b["status"] in ("HOLD", "BOOKED"):
            store.update_booking_status(trip_id, b["idempotency_key"], "CAPTURED")
    events.publish("booking.captured", {"trip": trip_id, "amount": total})
    store.append_event(trip_id, "captured", {"payment_id": payment_id, "amount_inr": total})
    state.status = "BOOKED"
    store.save_trip(state)
    log.append(f"✓ CAPTURED ₹{total:,.0f} via {cap.get('provider')} — booking confirmed")
    return {"status": "BOOKED", "amount_inr": total, "capture": cap, "log": log}


# ============================== refund (human-confirmed compensation) =========
def refund(state, idem: str, payment_id: str, amount_inr: float | None = None,
           human_confirmed: bool = False) -> dict:
    """Refund a captured booking (cancellation / compensation). HUMAN-GATED."""
    trip_id = state.trip_id
    try:
        r = payment.refund(payment_id, amount_inr, human_confirmed=human_confirmed)
    except payment.PaymentError as e:
        return {"status": "BLOCKED", "reason": str(e), "log": [f"✗ {e}"]}
    for b in store.bookings(trip_id):
        if b["idempotency_key"].startswith(idem):
            store.update_booking_status(trip_id, b["idempotency_key"], "REFUNDED")
    store.append_event(trip_id, "refunded", {"payment_id": payment_id, "refund": r})
    return {"status": "REFUNDED", "refund": r,
            "log": [f"↩ refund {r.get('status')} via {r.get('provider')}"]}


# ============================================================ helpers ==========
def _compensate(state, trip_id: str, failed_at: str, order_id: str,
                air_order_id: str, done: list[dict], log: list) -> dict:
    """Reverse-order compensation for a live saga (readme §13)."""
    log.append(f"✗ {failed_at} FAILED — compensating in reverse")
    for step in reversed(done):
        if step["type"] == "flight" and air_order_id:
            res = gateway.amadeus_cancel_flight(air_order_id)
            ok = "cancelled" if res.get("ok") else f"cancel-attempted ({res.get('error', '')[:40]})"
            log.append(f"↩ flight order {air_order_id} {ok}")
        store.update_booking_status(trip_id, step["idem"], "COMPENSATED")
        log.append(f"↩ compensated {step['type']}")
    _release_order(order_id, log)
    events.publish("booking.failed", {"trip": trip_id, "failed_at": failed_at})
    return {"status": "FAILED", "failed_at": failed_at, "order_id": order_id,
            "log": log, "mode": "live"}


def _release_order(order_id: str, log: list) -> None:
    """Release an uncaptured payment order. Nothing was captured → nothing to refund."""
    log.append(f"✗ payment order {order_id} released — authorize-only, "
               f"never captured (₹0 moved)")
