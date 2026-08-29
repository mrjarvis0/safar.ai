"""Negotiation engine — the differentiator. Owner: sush.

conflicts -> weighted utility -> 3 candidates (Saver / Comfort / Balanced).
See readme.md section 8 (and the 8.6 pseudocode).
"""


def negotiate(state) -> dict:
    # TODO(sush): detect conflicts (cheap vs comfort, time vs experience)
    # TODO(sush): score each combo with a weighted utility (state.weights)
    # TODO(sush): return {"saver": {...}, "comfort": {...}, "balanced": {...}}
    return {}
