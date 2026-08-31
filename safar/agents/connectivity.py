"""Connectivity agent — eSIM vs local SIM vs roaming decision (readme §6).

Advises the traveler on the best connectivity option for their destination,
with cost estimates and practical tips.  Deterministic (no LLM).
"""

_CONNECTIVITY = {
    "Japan": {
        "esim": {"available": True, "providers": ["Airalo", "Holafly", "Ubigi"],
                 "cost_est": "₹800–1,500 / 7 days / 3–5 GB",
                 "note": "Best option — activate before departure."},
        "local_sim": {"available": True, "providers": ["IIJmio", "Mobal"],
                      "cost_est": "₹1,000–2,000 / 7 days",
                      "note": "Available at airports; passport required."},
        "roaming": {"cost_est": "₹500–1,500/day (check carrier)",
                    "note": "Expensive; only for short trips."},
        "recommendation": "eSIM",
        "wifi_note": "Free Wi-Fi widely available at stations, convenience stores, hotels.",
    },
    "France": {
        "esim": {"available": True, "providers": ["Airalo", "Holafly"],
                 "cost_est": "₹700–1,200 / 7 days",
                 "note": "EU roaming — one eSIM covers Schengen."},
        "local_sim": {"available": True, "providers": ["Orange", "SFR", "Free"],
                      "cost_est": "€10–20 / prepaid",
                      "note": "Available at tabacs and phone shops."},
        "roaming": {"cost_est": "₹500–1,000/day",
                    "note": "Check if your carrier has EU packs."},
        "recommendation": "eSIM or local SIM",
        "wifi_note": "Good Wi-Fi in cafes; public Wi-Fi in museums.",
    },
    "United Arab Emirates": {
        "esim": {"available": True, "providers": ["Airalo", "du", "etisalat"],
                 "cost_est": "₹800–1,500 / 7 days",
                 "note": "Activate before arrival."},
        "local_sim": {"available": True, "providers": ["du", "etisalat"],
                      "cost_est": "AED 50–100",
                      "note": "Available at the airport; passport scan required."},
        "roaming": {"cost_est": "₹800–2,000/day",
                    "note": "Avoid unless your carrier has a UAE add-on."},
        "recommendation": "eSIM or airport SIM",
        "wifi_note": "Hotels and malls have free Wi-Fi.",
    },
    "Thailand": {
        "esim": {"available": True, "providers": ["Airalo", "Holafly"],
                 "cost_est": "₹500–1,000 / 7 days",
                 "note": "Cheapest option."},
        "local_sim": {"available": True, "providers": ["AIS", "DTAC", "TrueMove"],
                      "cost_est": "₹300–600 / 7 days (tourist SIM)",
                      "note": "Excellent value; available at airports."},
        "roaming": {"cost_est": "₹500–1,500/day",
                    "note": "Poor value for Thailand."},
        "recommendation": "local SIM (cheapest) or eSIM",
        "wifi_note": "Wi-Fi common in hotels, cafes, 7-Elevens.",
    },
    "Singapore": {
        "esim": {"available": True, "providers": ["Airalo", "Holafly"],
                 "cost_est": "₹600–1,200 / 7 days",
                 "note": "Convenient; activate pre-arrival."},
        "local_sim": {"available": True, "providers": ["Singtel", "StarHub", "M1"],
                      "cost_est": "SGD 12–20",
                      "note": "Tourist SIMs at Changi airport."},
        "roaming": {"cost_est": "₹500–1,000/day",
                    "note": "Check carrier packs."},
        "recommendation": "eSIM",
        "wifi_note": "Wireless@SG free public Wi-Fi island-wide.",
    },
}

_DEFAULT = {
    "esim": {"available": True, "providers": ["Airalo", "Holafly"],
             "cost_est": "varies by destination",
             "note": "Check coverage for your destination."},
    "local_sim": {"available": True, "providers": [],
                  "cost_est": "varies",
                  "note": "Usually available at airports; bring passport."},
    "roaming": {"cost_est": "₹500–2,000/day",
                "note": "Usually expensive; use as a backup."},
    "recommendation": "eSIM (safest default)",
    "wifi_note": "Look for hotel and cafe Wi-Fi.",
}


def run(state) -> dict:
    """Return connectivity advice for the destination country."""
    country = (state.grounding or {}).get("country")
    info = _CONNECTIVITY.get(country, _DEFAULT)
    return {
        "country": country,
        **info,
        "sources": ["static:connectivity-guide"],
    }
