"""Discovery team — destination, local expert, food, events. Owner: adi.

Grounded on the free/keyless sources already wired in the gateway (Wikidata,
Wikivoyage, OpenStreetMap). Every output carries its sources for observability.
"""
from ..gateway import gateway


def destination(state) -> dict:
    dest = state.trip["destination"]
    wd = gateway.wikidata_entity(dest)
    wv = gateway.wikivoyage(dest)
    return {
        "name": dest, "country": wd.get("country"), "label": wd.get("label"),
        "description": wd.get("description"),
        "summary": (wv.get("summary") or "")[:300], "url": wv.get("url"),
        "sources": [f"wikidata:{wd.get('qid')}", "wikivoyage"],
    }


def local_expert(state) -> dict:
    dest = state.trip["destination"]
    geo = gateway.osm_geocode(dest)
    picks = []
    if geo.get("lat"):
        picks = [p["name"] for p in
                 gateway.osm_pois(geo["lat"], geo["lon"], "attraction", 4000, 8)][:6]
    return {"neighbourhood_picks": picks, "sources": ["osm:overpass#attraction"]}


def food(state) -> dict:
    dest = state.trip["destination"]
    geo = gateway.osm_geocode(dest)
    spots = []
    if geo.get("lat"):
        spots = [p["name"] for p in
                 gateway.osm_pois(geo["lat"], geo["lon"], "food", 2500, 8)][:6]
    return {"food_spots": spots, "diet_note": "filter by cuisine/diet at booking",
            "sources": ["osm:overpass#food"]}


def events(state) -> dict:
    # Honest gap: no free events feed wired yet (Ticketmaster/PredictHQ need keys).
    return {"status": "unavailable", "items": [],
            "note": "No free events source wired (Phase 2: keyed Events API)."}


def run(state) -> dict:
    return {"destination": destination(state), "local_expert": local_expert(state),
            "food": food(state), "events": events(state)}
