"""Emergency agent — crisis playbooks (readme §6).

Returns immediate action steps for common travel emergencies: lost passport,
missed flight, medical, natural disaster, theft.  Each playbook includes nearest
relevant service type, local emergency numbers, embassy/consular guidance, and
safe next steps.

HIGH-STAKES (readme §11): this is static demo guidance.  Every answer carries a
disclaimer.  Production would ground on official government + embassy feeds.
"""

_DISCLAIMER = ("Demo emergency guidance — verify with local authorities, your "
               "embassy, and emergency services on the ground.")

_NUMBERS = {
    "Japan": {"police": "110", "ambulance": "119", "fire": "119",
              "tourist_helpline": "03-5321-3077 (JNTO)"},
    "France": {"police": "17", "ambulance": "15", "fire": "18",
               "eu_emergency": "112"},
    "United Arab Emirates": {"police": "999", "ambulance": "998",
                             "tourist_police": "901"},
    "Thailand": {"police": "191", "ambulance": "1669",
                 "tourist_police": "1155"},
    "Singapore": {"police": "999", "ambulance": "995"},
    "Indonesia": {"police": "110", "ambulance": "118"},
    "United Kingdom": {"police": "999", "ambulance": "999",
                       "non_emergency": "101"},
    "United States": {"emergency": "911"},
}

_INDIA_EMBASSIES = {
    "Japan": "Embassy of India, Tokyo: +81-3-3262-2391",
    "France": "Embassy of India, Paris: +33-1-40-50-70-70",
    "United Arab Emirates": "Embassy of India, Abu Dhabi: +971-2-449-2700; "
                            "Consulate, Dubai: +971-4-397-1222",
    "Thailand": "Embassy of India, Bangkok: +66-2-258-0300",
    "Singapore": "High Commission of India: +65-6737-6777",
    "Indonesia": "Embassy of India, Jakarta: +62-21-5204-150",
    "United Kingdom": "High Commission of India, London: +44-20-7836-8484",
    "United States": "Embassy of India, Washington DC: +1-202-939-7000",
}


def _playbook_lost_passport(country: str) -> dict:
    return {
        "title": "Lost Passport",
        "severity": "high",
        "steps": [
            "1. File a police report (get the report number)",
            "2. Contact your embassy/consulate immediately",
            "3. Get emergency travel document (Emergency Certificate)",
            "4. Keep digital copies of your passport in email/cloud",
            "5. Carry 2 passport-size photos for the emergency document",
        ],
        "embassy": _INDIA_EMBASSIES.get(country, "Contact Indian embassy abroad"),
        "prevention": "Keep a photocopy separate from the original; "
                      "store digital scan in email.",
    }


def _playbook_missed_flight(country: str) -> dict:
    return {
        "title": "Missed Flight",
        "severity": "medium",
        "steps": [
            "1. Go to the airline counter immediately",
            "2. Ask about the next available flight (rebooking)",
            "3. Check your ticket's rebooking/change policy",
            "4. If refundable: rebook free. If not: ask about standby",
            "5. Contact travel insurance if delay causes losses",
        ],
        "tip": "Airlines are more helpful at the counter than on the phone.",
    }


def _playbook_medical(country: str) -> dict:
    numbers = _NUMBERS.get(country, {})
    return {
        "title": "Medical Emergency",
        "severity": "critical",
        "steps": [
            f"1. Call ambulance: {numbers.get('ambulance', 'local emergency number')}",
            "2. Go to the nearest hospital (ask hotel reception)",
            "3. Contact travel insurance helpline (policy card)",
            "4. Keep all receipts and medical reports for claims",
            "5. Contact embassy if hospitalization is needed",
        ],
        "embassy": _INDIA_EMBASSIES.get(country, "Contact Indian embassy abroad"),
        "insurance_note": "Travel insurance with medical + evacuation is essential.",
    }


def _playbook_theft(country: str) -> dict:
    numbers = _NUMBERS.get(country, {})
    return {
        "title": "Theft / Robbery",
        "severity": "high",
        "steps": [
            f"1. Call police: {numbers.get('police', 'local police number')}",
            "2. File a police report (needed for insurance claim)",
            "3. Cancel stolen credit/debit cards immediately",
            "4. If passport stolen → follow Lost Passport playbook",
            "5. Contact travel insurance with the police report",
        ],
        "prevention": "Use hotel safe; carry only what you need for the day; "
                      "keep copies of everything.",
    }


def _playbook_natural_disaster(country: str) -> dict:
    numbers = _NUMBERS.get(country, {})
    return {
        "title": "Natural Disaster / Severe Weather",
        "severity": "critical",
        "steps": [
            "1. Follow local authority instructions (TV, radio, alerts)",
            f"2. Call emergency: {numbers.get('police', 'local emergency number')}",
            "3. Move to the nearest safe shelter / high ground",
            "4. Contact your embassy for assistance / evacuation",
            "5. Register with your government's traveler program if not done",
        ],
        "embassy": _INDIA_EMBASSIES.get(country, "Contact Indian embassy abroad"),
    }


def run(state) -> dict:
    """Return all emergency playbooks for the destination country."""
    country = (state.grounding or {}).get("country")
    numbers = _NUMBERS.get(country, {"note": "Look up local emergency numbers"})

    playbooks = [
        _playbook_lost_passport(country),
        _playbook_missed_flight(country),
        _playbook_medical(country),
        _playbook_theft(country),
        _playbook_natural_disaster(country),
    ]

    return {
        "country": country,
        "emergency_numbers": numbers,
        "playbooks": playbooks,
        "embassy": _INDIA_EMBASSIES.get(country, "Contact Indian embassy abroad"),
        "disclaimer": _DISCLAIMER,
        "sources": ["static:emergency-playbooks"],
    }
