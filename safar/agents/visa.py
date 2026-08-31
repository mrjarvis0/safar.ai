"""Visa agent — passport/visa requirement. Owner: sush.

HIGH-STAKES (readme §11): this is a small static demo matrix, NOT ground truth.
Every answer carries a "verify with the official source" disclaimer and is never
acted on autonomously. Unknown pairs return required=None ("unknown"), never a
guess. Production would ground on IATA Timatic.
"""
DISCLAIMER = "Demo data — verify with the official embassy / IATA Timatic source."

# (home_country, destination_country) -> (required?, type, note)
_MATRIX = {
    ("India", "Japan"): (True, "eVisa / consular visa", "Apply before you travel."),
    ("India", "Thailand"): (False, "visa-exempt (short stay)", "Free entry for short tourism."),
    ("India", "United Arab Emirates"): (True, "eVisa", "Quick online pre-approval."),
    ("India", "Singapore"): (True, "eVisa", "Apply online before travel."),
    ("India", "Indonesia"): (False, "visa-on-arrival / VoA", "Available at entry."),
    ("India", "Nepal"): (False, "visa-free", "No visa for Indian nationals."),
    ("India", "France"): (True, "Schengen visa", "Apply at a Schengen consulate."),
    ("India", "United Kingdom"): (True, "Standard Visitor visa", "Apply online in advance."),
    ("India", "United States"): (True, "B1/B2 visa", "Interview + long lead time."),
}


def check(home_country: str, destination_country: str | None) -> dict:
    if not destination_country:
        return {"required": None, "destination": None, "type": None,
                "note": "Destination country unknown.", "disclaimer": DISCLAIMER}
    row = _MATRIX.get((home_country, destination_country))
    if row is None:
        return {"required": None, "destination": destination_country, "type": None,
                "note": f"No rule on file for {home_country} → {destination_country}.",
                "ok": None, "disclaimer": DISCLAIMER}
    required, vtype, note = row
    return {"required": required, "destination": destination_country, "type": vtype,
            "note": note, "ok": True, "disclaimer": DISCLAIMER}
