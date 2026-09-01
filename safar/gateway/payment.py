"""Payment gateway — PSP-agnostic (Razorpay / Stripe / mock). Owner: mr.jarvis0.

Phase 3 (readme §13). This is the *code-ready* payment layer. The safety line is
drawn inside the code itself, not just in a comment:

  • create_order()  — creates a PENDING payment order/intent server-side. This
    does NOT move money and touches NO card data; it returns an order id + the
    PUBLIC key so a human's checkout can complete the payment. Safe to call.
  • capture()       — captures an authorized payment (money actually moves).
    HUMAN-GATED: refuses unless `human_confirmed=True` is passed. The booking
    saga never calls this automatically (readme §10/§13).
  • refund()        — reverses a captured payment (compensation). Also human-gated.

Safar never sees, stores, or types a card number — PCI scope stays with the PSP's
hosted checkout. Blank keys → the deterministic `mock` provider, so the whole
saga runs end-to-end with no account.

All HTTP is raw REST via `requests` (no SDK dependency); the official razorpay /
stripe SDKs are drop-in if you prefer them.
"""
from __future__ import annotations

import time
import uuid

import requests

from .. import config

_TIMEOUT = 15


class PaymentError(RuntimeError):
    """Raised when a PSP call fails or a human-gated action is attempted unsafely."""


# ---- provider selection ------------------------------------------------------
def active_provider() -> str:
    """The effective PSP. Falls back to 'mock' if the chosen provider lacks keys."""
    p = config.PAYMENT_PROVIDER
    if p == "razorpay" and config.RAZORPAY_KEY_ID and config.RAZORPAY_KEY_SECRET:
        return "razorpay"
    if p == "stripe" and config.STRIPE_SECRET_KEY:
        return "stripe"
    return "mock"


def public_config() -> dict:
    """Non-secret config a front-end checkout needs (publishable/key id only).

    NEVER returns a secret. Safe to send to a browser.
    """
    prov = active_provider()
    if prov == "razorpay":
        return {"provider": "razorpay", "key_id": config.RAZORPAY_KEY_ID}
    if prov == "stripe":
        return {"provider": "stripe", "publishable_key": config.STRIPE_PUBLISHABLE_KEY}
    return {"provider": "mock", "key_id": "mock_public_key"}


def _minor_units(amount_inr: float) -> int:
    """INR rupees -> paise (both Razorpay and Stripe-India bill in the minor unit)."""
    return int(round(float(amount_inr) * 100))


# ---- create order (SAFE — no money moves) ------------------------------------
def create_order(amount_inr: float, receipt: str, notes: dict | None = None) -> dict:
    """Create a PENDING payment order/intent. Does NOT charge anyone.

    Returns {provider, order_id, amount_inr, currency, status:'created',
             checkout:{...public config...}}. The human completes payment against
    this order in the PSP's hosted checkout; capture happens only after that.
    """
    prov = active_provider()
    notes = notes or {}
    if prov == "razorpay":
        data = _razorpay("POST", "/v1/orders", {
            "amount": _minor_units(amount_inr), "currency": "INR",
            "receipt": receipt[:40], "notes": notes,
            "payment_capture": 0,          # 0 = authorize only; capture is explicit
        })
        return {"provider": "razorpay", "order_id": data["id"],
                "amount_inr": amount_inr, "currency": "INR", "status": "created",
                "checkout": public_config()}
    if prov == "stripe":
        # capture_method=manual → authorize now, capture later (human-gated).
        data = _stripe("POST", "/v1/payment_intents", {
            "amount": _minor_units(amount_inr), "currency": "inr",
            "capture_method": "manual", "description": receipt[:200],
            **{f"metadata[{k}]": str(v) for k, v in notes.items()}})
        return {"provider": "stripe", "order_id": data["id"],
                "client_secret": data.get("client_secret"),
                "amount_inr": amount_inr, "currency": "INR", "status": "created",
                "checkout": public_config()}
    # mock
    return {"provider": "mock", "order_id": "order_mock_" + uuid.uuid4().hex[:12],
            "amount_inr": amount_inr, "currency": "INR", "status": "created",
            "checkout": public_config(),
            "note": "MOCK — no real order created; set PAYMENT_PROVIDER to go live."}


# ---- capture (HUMAN-GATED — money moves) -------------------------------------
def capture(payment_id: str, amount_inr: float, human_confirmed: bool = False) -> dict:
    """Capture an AUTHORIZED payment. Money actually moves — HUMAN-GATED.

    Refuses unless `human_confirmed=True`. The booking saga never sets this; a
    human must explicitly confirm capture in the UI after they have paid. This
    guard encodes readme §10/§13 in code, not just prose.
    """
    if not human_confirmed:
        raise PaymentError(
            "capture blocked: needs explicit human confirmation "
            "(human_confirmed=True). Safar never captures payment autonomously.")
    prov = active_provider()
    if prov == "razorpay":
        d = _razorpay("POST", f"/v1/payments/{payment_id}/capture",
                      {"amount": _minor_units(amount_inr), "currency": "INR"})
        return {"provider": "razorpay", "payment_id": payment_id,
                "status": d.get("status", "captured"), "amount_inr": amount_inr}
    if prov == "stripe":
        d = _stripe("POST", f"/v1/payment_intents/{payment_id}/capture",
                    {"amount_to_capture": _minor_units(amount_inr)})
        return {"provider": "stripe", "payment_id": payment_id,
                "status": d.get("status", "succeeded"), "amount_inr": amount_inr}
    return {"provider": "mock", "payment_id": payment_id, "status": "captured",
            "amount_inr": amount_inr, "note": "MOCK capture — no money moved."}


# ---- refund (HUMAN-GATED — compensation) -------------------------------------
def refund(payment_id: str, amount_inr: float | None = None,
           human_confirmed: bool = False) -> dict:
    """Refund a captured payment (saga compensation). HUMAN-GATED.

    `amount_inr=None` → full refund. Refuses unless `human_confirmed=True`.
    """
    if not human_confirmed:
        raise PaymentError(
            "refund blocked: needs explicit human confirmation "
            "(human_confirmed=True).")
    prov = active_provider()
    body: dict = {}
    if amount_inr is not None:
        body["amount"] = _minor_units(amount_inr)
    if prov == "razorpay":
        d = _razorpay("POST", f"/v1/payments/{payment_id}/refund", body)
        return {"provider": "razorpay", "refund_id": d.get("id"),
                "status": d.get("status", "processed")}
    if prov == "stripe":
        d = _stripe("POST", "/v1/refunds", {"payment_intent": payment_id, **body})
        return {"provider": "stripe", "refund_id": d.get("id"),
                "status": d.get("status", "succeeded")}
    return {"provider": "mock", "refund_id": "rfnd_mock_" + uuid.uuid4().hex[:10],
            "status": "processed", "note": "MOCK refund — no money moved."}


# ---- verify (SAFE — crypto check that the human actually paid) ----------------
def verify_razorpay_signature(order_id: str, payment_id: str, signature: str) -> bool:
    """Verify a Razorpay checkout callback signature (HMAC-SHA256). No money moves.

    Confirms the browser payment really happened before the saga treats it as paid.
    """
    import hashlib
    import hmac
    if not config.RAZORPAY_KEY_SECRET:
        return False
    expected = hmac.new(config.RAZORPAY_KEY_SECRET.encode(),
                        f"{order_id}|{payment_id}".encode(),
                        hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature or "")


def order_status(order_id: str) -> dict:
    """Read-only status of an order/intent (no money moves)."""
    prov = active_provider()
    try:
        if prov == "razorpay":
            d = _razorpay("GET", f"/v1/orders/{order_id}", None)
            return {"provider": "razorpay", "status": d.get("status"),
                    "amount_paid": d.get("amount_paid")}
        if prov == "stripe":
            d = _stripe("GET", f"/v1/payment_intents/{order_id}", None)
            return {"provider": "stripe", "status": d.get("status")}
    except Exception as e:  # noqa: BLE001 — status is best-effort
        return {"provider": prov, "status": "unknown", "error": str(e)[:120]}
    return {"provider": "mock", "status": "created"}


# ---- raw REST helpers --------------------------------------------------------
def _razorpay(method: str, path: str, body: dict | None) -> dict:
    auth = (config.RAZORPAY_KEY_ID, config.RAZORPAY_KEY_SECRET)
    url = "https://api.razorpay.com" + path
    r = requests.request(method, url, auth=auth, json=body, timeout=_TIMEOUT)
    if r.status_code >= 400:
        raise PaymentError(f"razorpay {path} -> {r.status_code}: {r.text[:200]}")
    return r.json()


def _stripe(method: str, path: str, body: dict | None) -> dict:
    # Stripe wants application/x-www-form-urlencoded, not JSON.
    headers = {"Authorization": f"Bearer {config.STRIPE_SECRET_KEY}"}
    url = "https://api.stripe.com" + path
    r = requests.request(method, url, headers=headers, data=body or {},
                         timeout=_TIMEOUT)
    if r.status_code >= 400:
        raise PaymentError(f"stripe {path} -> {r.status_code}: {r.text[:200]}")
    return r.json()


def status() -> dict:
    """One-line health/config summary for the dashboard (no secrets)."""
    prov = active_provider()
    return {"provider": prov, "live": prov != "mock",
            "capture_policy": "human-confirmed only (never autonomous)",
            "card_data": "never touches Safar (PSP hosted checkout)",
            "ts": time.time()}
