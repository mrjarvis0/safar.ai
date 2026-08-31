"""Document agent — travel wallet + required docs (readme §6).

Tracks passport validity, required documents per destination, booking
confirmation checklist, and document readiness.  Phase 2 scope: ingesting
booking emails/PDFs is roadmapped but not yet built (needs OCR/parsing).

Deterministic for the checklist; the \"ingestion\" path is a stub.
"""

_DOCS_BY_COUNTRY = {
    "Japan": ["passport (6+ months validity)", "visa / eVisa printout",
              "return flight proof", "hotel booking confirmation",
              "travel insurance certificate"],
    "France": ["passport (6+ months validity)", "Schengen visa",
               "hotel booking", "travel insurance (€30k medical min)",
               "return ticket"],
    "United Arab Emirates": ["passport (6+ months validity)", "eVisa / visa stamp",
                             "hotel booking", "return ticket"],
    "Thailand": ["passport (6+ months validity)", "hotel booking",
                 "return ticket", "cash / proof of funds (₹30k THB equiv.)"],
    "Singapore": ["passport (6+ months validity)", "eVisa / SG Arrival Card",
                  "hotel booking", "return ticket"],
    "Indonesia": ["passport (6+ months validity)", "hotel booking",
                  "return ticket", "cash for visa-on-arrival fee"],
}

_UNIVERSAL = [
    "passport + 2 photocopies (separate from original)",
    "visa document (if required)",
    "flight booking confirmation",
    "hotel booking confirmation",
    "travel insurance policy",
    "emergency contact card",
    "digital copies in email / cloud",
]


def run(state) -> dict:
    """Build a document checklist for the trip."""
    country = (state.grounding or {}).get("country")
    visa = (state.grounding or {}).get("visa", {})

    # Country-specific docs
    specific = _DOCS_BY_COUNTRY.get(country, [])

    # Merge with universal checklist (deduplicate)
    all_docs = list(dict.fromkeys(specific + _UNIVERSAL))

    # Readiness assessment
    ready_count = 0
    items: list[dict] = []
    for doc in all_docs:
        # In a real system, the user would mark these; here we flag what's
        # derivable from the plan.
        status = "check"
        if "visa" in doc.lower() and visa.get("required") is False:
            status = "not_needed"
        elif "visa" in doc.lower() and visa.get("required"):
            status = "action_required"
        items.append({"document": doc, "status": status})
        if status != "action_required":
            ready_count += 1

    return {
        "country": country,
        "checklist": items,
        "total": len(items),
        "ready": ready_count,
        "action_required": len(items) - ready_count,
        "ingestion_note": "Email/PDF ingestion is Phase 3 — upload manually for now.",
        "sources": ["static:document-checklist"],
    }
