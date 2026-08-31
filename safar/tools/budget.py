"""Budget tool — deterministic cost math (NO llm). Owner: adi."""

LOCAL_PER_DAY = 3000  # ₹/day buffer: local transport + food + incidentals


def total_cost(plan: dict) -> float:
    """Flight + hotel*nights + activities + daily buffer. `plan` uses agent envelopes."""
    days = plan.get("days", 1)
    nights = plan.get("nights", max(days - 1, 1))
    flight = plan["flight"]["raw"]["price_inr"]
    hotel = plan["hotel"]["raw"]["price_inr_night"] * nights
    acts = sum(a["raw"].get("price_inr", 0) for a in plan.get("activities", []))
    buffer = days * LOCAL_PER_DAY
    return round(flight + hotel + acts + buffer, 2)
