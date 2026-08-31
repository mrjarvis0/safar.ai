"""Provenance & grounding helpers (readme §11).

Every factual claim should carry provenance: what was claimed, where it came
from, when it was fetched, and when it expires.  This module provides helpers
to attach structured provenance records to TripState.
"""
import datetime


def add_claim(state, claim: str, source: str,
              confidence: float = 0.9, ttl_hours: float = 24.0) -> dict:
    """Append a structured provenance record to state.provenance.

    Returns the record dict.
    """
    now = datetime.datetime.utcnow()
    record = {
        "claim": claim,
        "source": source,
        "retrieved_at": now.isoformat() + "Z",
        "expires_at": (now + datetime.timedelta(hours=ttl_hours)).isoformat() + "Z",
        "confidence": round(confidence, 3),
    }

    if not hasattr(state, "provenance") or state.provenance is None:
        state.provenance = []
    state.provenance.append(record)
    return record


def add_claims_from_grounding(state) -> int:
    """Extract provenance entries from state.grounding and add them.

    Returns the count of records added.
    """
    g = getattr(state, "grounding", None) or {}
    count = 0

    # Geo (from OSM / Open-Meteo)
    geo = g.get("geo") or {}
    if geo.get("lat"):
        add_claim(state, f"Geocode: {geo.get('display_name', '?')}",
                  "osm:nominatim", confidence=0.95, ttl_hours=720)
        count += 1

    # Seasonality (from Open-Meteo Archive)
    seas = g.get("seasonality") or {}
    if seas.get("avg_high_c"):
        add_claim(state,
                  f"Seasonality mo {seas['month']}: "
                  f"{seas['avg_high_c']}°/{seas['avg_low_c']}°C, "
                  f"{seas.get('rainy_days', 0)} rainy days",
                  "open-meteo:archive", confidence=0.9, ttl_hours=720)
        count += 1

    # Wikivoyage
    wv = g.get("wikivoyage")
    if wv:
        add_claim(state, f"Wikivoyage: {wv[:120]}…",
                  g.get("wikivoyage_url") or "wikivoyage", confidence=0.85,
                  ttl_hours=168)
        count += 1

    # Visa (high-stakes — short TTL, always re-verify)
    visa = g.get("visa") or {}
    if visa.get("destination"):
        req = visa.get("required")
        status = "required" if req else ("not required" if req is False else "unknown")
        add_claim(state,
                  f"Visa for {visa['destination']}: {status} — {visa.get('type', '?')}",
                  "static:visa-matrix", confidence=0.7, ttl_hours=72)
        count += 1

    # OPTD (offline — very long TTL)
    optd = g.get("optd") or {}
    if optd.get("iata"):
        add_claim(state,
                  f"OPTD: IATA {optd['iata']}, {optd.get('timezone')}, "
                  f"{optd.get('country')}",
                  "optd:offline", confidence=0.95, ttl_hours=8760)
        count += 1

    # Country
    country = g.get("country")
    if country:
        add_claim(state, f"Destination country: {country}",
                  "wikidata:sparql", confidence=0.92, ttl_hours=720)
        count += 1

    return count


def expired(record: dict) -> bool:
    """Check if a provenance record has expired."""
    try:
        exp = datetime.datetime.fromisoformat(record["expires_at"].rstrip("Z"))
        return datetime.datetime.utcnow() > exp
    except Exception:
        return False


def summary(state) -> dict:
    """Return a summary of provenance records on the state."""
    records = getattr(state, "provenance", []) or []
    return {
        "total_claims": len(records),
        "expired": sum(1 for r in records if expired(r)),
        "avg_confidence": (round(sum(r.get("confidence", 0) for r in records)
                                 / max(len(records), 1), 3)),
        "sources": list({r.get("source", "?") for r in records}),
    }
