"""Currency tool — FX conversion (NO llm). Owner: adi.

Uses the gateway's real FX (Frankfurter, no key) with a static offline fallback.
"""
from ..gateway.gateway import convert_currency

_STATIC = {("INR", "JPY"): 1.75, ("INR", "USD"): 0.012, ("INR", "EUR"): 0.011}


def convert(amount: float, frm: str = "INR", to: str = "JPY") -> float:
    val = convert_currency(amount, frm, to)
    if val == amount and frm != to and (frm, to) in _STATIC:  # gateway fell back
        return round(amount * _STATIC[(frm, to)], 2)
    return val
