"""Support team — transport, packing, culture. Owner: rishu.

Transport is GTFS-ready (gateway.gtfs_status). Packing derives from the historical
seasonality already grounded on the plan. Culture is static demo etiquette with a
"verify locally" disclaimer.
"""
from ..gateway import gateway

_CULTURE = {
    "Japan": ["Remove shoes indoors", "Keep quiet on trains", "No tipping",
              "Carry cash; many places are cash-only"],
    "France": ["Greet with 'Bonjour' in shops", "Lunch 12–14h", "Tipping optional"],
    "United Arab Emirates": ["Dress modestly", "No public alcohol", "Respect Ramadan hours"],
    "Thailand": ["Dress modestly at temples", "Don't touch heads", "Remove shoes in temples"],
}


def transport(state) -> dict:
    return {
        "airport_transfer": "~45–75 min by airport express / taxi",
        "intra_city": "metro + walking; buy a stored-value transit card",
        "gtfs": gateway.gtfs_status(),
    }


def packing(state) -> dict:
    seas = state.grounding.get("seasonality") or {}
    items = ["passport + copies", "universal power adapter", "meds + basics"]
    low = seas.get("avg_low_c")
    if low is not None and low < 12:
        items.append("warm layers / light jacket")
    if seas.get("rainy_days", 0) >= 6:
        items.append("compact umbrella / rain shell")
    interests = state.trip.get("interests", [])
    if "culture" in interests or "city" in interests:
        items.append("comfortable walking shoes")
    return {"items": items, "driver": "season + activities"}


def culture(state) -> dict:
    country = state.grounding.get("country")
    return {"country": country,
            "etiquette": _CULTURE.get(country, ["Research local customs before you go"]),
            "disclaimer": "Demo etiquette — verify local norms on the ground."}


def run(state) -> dict:
    return {"transport": transport(state), "packing": packing(state),
            "culture": culture(state)}
