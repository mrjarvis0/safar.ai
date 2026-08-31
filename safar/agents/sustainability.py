"""Sustainability agent — carbon footprint, rail alternatives, eco tips (readme §6).

Estimates CO₂ emissions for the trip (flights dominate), suggests lower-carbon
alternatives where available, and provides destination-specific eco tips.
Deterministic (no LLM).
"""

# Approximate CO₂ per passenger-km for different transport modes (kg CO₂/km).
_EMISSION_FACTOR = {
    "flight_short": 0.255,    # short-haul (<1500 km)
    "flight_long": 0.195,     # long-haul (>1500 km) — more efficient per km
    "train": 0.041,
    "bus": 0.089,
    "car_shared": 0.120,
}

# Rail alternatives for common city pairs (demo data).
_RAIL_ALTERNATIVES = {
    ("Tokyo", "Kyoto"): {"mode": "Shinkansen", "duration": "2h15m",
                         "note": "Faster and greener than domestic flight."},
    ("Paris", "London"): {"mode": "Eurostar", "duration": "2h16m",
                          "note": "Significantly lower carbon than flying."},
    ("Paris", "Brussels"): {"mode": "Thalys/Eurostar", "duration": "1h22m",
                            "note": "Train is faster door-to-door."},
    ("Tokyo", "Osaka"): {"mode": "Shinkansen", "duration": "2h30m",
                         "note": "Bullet train — no contest vs flight."},
}

_ECO_TIPS = {
    "Japan": ["Carry a reusable bottle (refill stations everywhere)",
              "Use trains over taxis (excellent rail network)",
              "Bring a furoshiki — Japan's reusable wrapping cloth"],
    "France": ["Use the vélo (bike-share) in Paris and Lyon",
               "Bring a tote bag — plastic bags are banned",
               "Refill water from fontaines Wallace (free, safe)"],
    "Thailand": ["Carry a refillable water bottle (avoid single-use plastic)",
                 "Support local eco-tour operators",
                 "Avoid elephant-riding attractions"],
    "United Arab Emirates": ["Use the Dubai Metro — efficient and cheap",
                             "Carry a refillable bottle (water stations in malls)",
                             "Choose hotels with sustainability certifications"],
}


def run(state) -> dict:
    """Estimate trip carbon footprint and suggest greener alternatives."""
    dest = state.trip["destination"]
    country = (state.grounding or {}).get("country")
    days = state.trip.get("days", 5)

    # Estimate flight distance from duration (rough: 800 km/h × hours)
    flights = state.options.get("flights", [])
    best_flight = min(flights, key=lambda f: f["raw"]["price_inr"]) if flights else None
    flight_h = best_flight["raw"]["duration_h"] if best_flight else 9.0
    distance_km = flight_h * 800  # rough great-circle estimate
    factor = "flight_long" if distance_km > 1500 else "flight_short"

    flight_co2 = round(distance_km * _EMISSION_FACTOR[factor] * 2, 1)  # round trip
    local_co2 = round(days * 15 * _EMISSION_FACTOR["train"], 1)  # ~15 km/day local transit
    total_co2 = round(flight_co2 + local_co2, 1)

    # Rail alternatives
    home = state.trip.get("home_country", "India")
    rail_alt = _RAIL_ALTERNATIVES.get((home, dest))  # inter-city
    intra_rail = _RAIL_ALTERNATIVES.get((dest, dest))  # will be None typically

    # Eco tips
    tips = _ECO_TIPS.get(country, ["Carry a reusable water bottle",
                                    "Use public transport where possible",
                                    "Support local businesses over chains"])

    return {
        "carbon_footprint": {
            "flight_kg_co2": flight_co2,
            "local_transit_kg_co2": local_co2,
            "total_kg_co2": total_co2,
            "equivalent": f"~{int(total_co2 / 21)} trees needed to offset (annual absorption)",
        },
        "rail_alternative": rail_alt,
        "eco_tips": tips,
        "note": ("Flight is ~90%+ of trip emissions. Consider trains for "
                 "shorter segments where available."),
        "sources": ["static:emission-factors", "derived:flight-duration"],
    }
