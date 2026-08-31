"""Tiny shared helpers (NO llm, NO api). Used by agents + negotiation engine."""


def norm(x: float, lo: float, hi: float, invert: bool = False) -> float:
    """Normalize x into [0,1] given [lo,hi]. invert=True -> higher input scores lower."""
    if hi == lo:
        return 1.0
    v = (x - lo) / (hi - lo)
    v = max(0.0, min(1.0, v))
    return round(1.0 - v if invert else v, 4)
