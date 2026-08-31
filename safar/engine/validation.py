"""Validation engine — constraint checks (readme §9). Owner: sush.

HARD failures -> state.errors (a plan violating one is invalid).
SOFT advisories -> state.warnings (surfaced to the human, never a dead end):
  temporal (opening hours), geo (daily backtracking), weather (rain vs outdoor),
  visa (high-stakes, §11 — always with a "verify official source" disclaimer).

validate() returns the hard errors and also writes state.warnings.
"""
MAX_DAY_KM = 25.0          # per-day transit above this = heavy backtracking
RAINY_DAYS_ALERT = 8       # rainy days in the month that warrant an indoor backup

_CANDS = ("saver", "comfort", "balanced")


def validate(state) -> list[str]:
    errors: list[str] = []
    warnings: list[str] = []
    budget = state.constraints.get("hard", {}).get("budget_inr")

    for name in _CANDS:
        c = state.candidates.get(name)
        if not c:
            continue
        # --- HARD: budget + completeness -------------------------------------
        if budget and c["cost_inr"] > budget:
            errors.append(f"{name}: ₹{c['cost_inr']:,.0f} exceeds hard budget "
                          f"₹{budget:,.0f}")
        if not c.get("flight") or not c.get("hotel"):
            errors.append(f"{name}: incomplete plan (missing flight or hotel)")

        it = c.get("itinerary") or []
        # --- SOFT: temporal (opening hours) ----------------------------------
        late = [i["name"] for day in it for i in day["items"] if not i["within_hours"]]
        if late:
            warnings.append(f"{name}: may not finish before closing — {', '.join(late)}")
        # --- SOFT: geo (daily backtracking) ----------------------------------
        heavy = [day["day"] for day in it if day["total_km"] > MAX_DAY_KM]
        if heavy:
            warnings.append(f"{name}: heavy backtracking on day(s) "
                            f"{', '.join(map(str, heavy))} (> {MAX_DAY_KM:.0f} km)")

    # --- SOFT: weather (plan-level, from historical seasonality) -------------
    seas = state.grounding.get("seasonality") or {}
    if seas.get("rainy_days", 0) >= RAINY_DAYS_ALERT:
        outdoor = _any_outdoor(state)
        if outdoor:
            warnings.append(f"~{seas['rainy_days']} rainy days typical in month "
                            f"{seas['month']} — keep an indoor backup for outdoor stops.")

    # --- SOFT: visa (high-stakes, §11) --------------------------------------
    visa = state.grounding.get("visa") or {}
    dest = visa.get("destination")
    if visa.get("required") is True:
        warnings.append(f"Visa REQUIRED for {dest}: {visa.get('type')}. "
                        f"{visa.get('note')} — {visa.get('disclaimer', '')}")
    elif visa.get("required") is None and dest is not None:
        warnings.append(f"Visa rule unknown for {dest} — {visa.get('disclaimer', '')}")

    state.warnings = warnings
    return errors


def _any_outdoor(state) -> bool:
    for name in _CANDS:
        c = state.candidates.get(name) or {}
        for day in c.get("itinerary", []):
            if any(i.get("outdoor") for i in day["items"]):
                return True
    return False
