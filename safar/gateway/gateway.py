"""Tool Gateway — all external API calls go through here. Owner: adi.

Real FREE, keyless grounding sources (priority order): OpenStreetMap (Nominatim
geocode + Overpass POI), Wikidata (knowledge graph), Wikivoyage (human travel
knowledge), Open-Meteo (forecast) + Open-Meteo Archive (historical/seasonality),
Frankfurter (FX). Mock JSON stays as fallback for flights/hotels/activities (no
free priced source — Amadeus is keyed, added later). Every call is wrapped in
try/except + a short timeout + an in-memory cache so the live demo can never
crash. These are GROUNDING sources: fetched live and cited (readme §11) — never
fine-tuned into the LLM. Keyed APIs read from safar.config (from .env).
"""
import calendar
import datetime
import json
import pathlib
import re
import time
import requests

from .. import config

_DATA = pathlib.Path(__file__).resolve().parents[2] / "data" / "tokyo.json"
_CACHE: dict = {}
_TIMEOUT = 10
# Nominatim/Wikidata usage policies require a real User-Agent identifying the app.
_UA = "Safar/0.1 (travel-os; contact: rustymission@gmail.com)"
_HEADERS = {"User-Agent": _UA}


def _mock(kind: str) -> list:
    data = json.loads(_DATA.read_text(encoding="utf-8"))
    return data.get(kind, [])


def _get(url: str, params: dict | None = None, headers: dict | None = None):
    key = url + json.dumps(params or {}, sort_keys=True)
    if key in _CACHE:
        return _CACHE[key]
    r = requests.get(url, params=params, headers=headers or _HEADERS,
                     timeout=_TIMEOUT)
    r.raise_for_status()
    _CACHE[key] = r.json()
    return _CACHE[key]


def _overpass(query: str) -> dict:
    """POST an Overpass QL query (form-encoded `data=`). Cached, keyless."""
    key = "OVERPASS" + query
    if key in _CACHE:
        return _CACHE[key]
    r = requests.post("https://overpass-api.de/api/interpreter",
                      data={"data": query}, headers=_HEADERS, timeout=_TIMEOUT)
    r.raise_for_status()
    _CACHE[key] = r.json()
    return _CACHE[key]


def _post(url: str, body: dict):
    key = "POST" + url + json.dumps(body, sort_keys=True)
    if key in _CACHE:
        return _CACHE[key]
    r = requests.post(url, json=body, timeout=_TIMEOUT)
    r.raise_for_status()
    _CACHE[key] = r.json()
    return _CACHE[key]


# ---- Flights / hotels / activities -------------------------------------------
# Amadeus (keyed) when creds are set; otherwise mock JSON so the demo never breaks.
def get_flights(trip: dict) -> list:
    if config.AMADEUS_CLIENT_ID and config.AMADEUS_CLIENT_SECRET:
        try:
            live = amadeus_flights(trip)
            if live:
                return live
        except Exception:
            pass
    return _mock("flights")


def get_hotels(trip: dict) -> list:
    if config.AMADEUS_CLIENT_ID and config.AMADEUS_CLIENT_SECRET:
        try:
            live = amadeus_hotels(trip)
            if live:
                return live
        except Exception:
            pass
    return _mock("hotels")


def get_activities(trip: dict) -> list:
    return _mock("activities")   # Amadeus Tours & Activities: Phase 2


# ---- Real, keyless enrichment APIs ------------------------------------------
def geocode(city: str) -> dict:
    """City -> {lat, lon, country}. Open-Meteo geocoding (no key)."""
    try:
        d = _get("https://geocoding-api.open-meteo.com/v1/search",
                 {"name": city, "count": 1})
        r = (d.get("results") or [{}])[0]
        return {"lat": r.get("latitude"), "lon": r.get("longitude"),
                "country": r.get("country")}
    except Exception:
        return {"lat": 35.68, "lon": 139.65, "country": "Japan"}  # Tokyo fallback


def get_weather(lat: float, lon: float) -> dict:
    """7-day daily forecast. Open-Meteo (no key)."""
    try:
        return _get("https://api.open-meteo.com/v1/forecast", {
            "latitude": lat, "longitude": lon,
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
            "forecast_days": 7, "timezone": "auto"})
    except Exception:
        return {}


def convert_currency(amount: float, frm: str = "INR", to: str = "JPY") -> float:
    """Real FX via Frankfurter (no key). Returns the input amount on failure."""
    try:
        d = _get("https://api.frankfurter.app/latest", {"from": frm, "to": to})
        return round(amount * d["rates"][to], 2)
    except Exception:
        return amount


def country_info(name: str) -> dict:
    """Currency + capital for a country. countriesnow.space (no key)."""
    out: dict = {"name": name}
    base = "https://countriesnow.space/api/v0.1/countries"
    try:
        d = _post(f"{base}/currency", {"country": name}).get("data", {})
        out["currency"] = d.get("currency")
        out["iso2"] = d.get("iso2")
    except Exception:
        pass
    try:
        d = _post(f"{base}/capital", {"country": name}).get("data", {})
        out["capital"] = d.get("capital")
    except Exception:
        pass
    return out


# ---- OpenStreetMap: places + geography (priority #1, free/keyless) -----------
def osm_geocode(city: str) -> dict:
    """City -> {lat, lon, display_name, osm_id}. Nominatim (no key).

    Falls back to the Open-Meteo geocoder (`geocode`) if Nominatim is down.
    """
    try:
        d = _get("https://nominatim.openstreetmap.org/search",
                 {"q": city, "format": "jsonv2", "limit": 1})
        r = (d or [{}])[0]
        if r.get("lat"):
            return {"lat": float(r["lat"]), "lon": float(r["lon"]),
                    "display_name": r.get("display_name"),
                    "osm_id": r.get("osm_id")}
    except Exception:
        pass
    g = geocode(city)  # Open-Meteo fallback
    return {"lat": g.get("lat"), "lon": g.get("lon"),
            "display_name": g.get("country"), "osm_id": None}


# Overpass tag filters per POI category.
_OSM_KINDS = {
    "attraction": '["tourism"~"attraction|museum|gallery|viewpoint|artwork|zoo"]',
    "food":       '["amenity"~"restaurant|cafe|fast_food|food_court"]',
    "hotel":      '["tourism"~"hotel|hostel|guest_house|apartment"]',
    "transit":    '["public_transport"="station"]',
}


def osm_pois(lat: float, lon: float, kind: str = "attraction",
             radius: int = 2000, limit: int = 20) -> list:
    """POIs near a point. Overpass/OSM (no key). Returns [{name, lat, lon, tags}]."""
    tag = _OSM_KINDS.get(kind, _OSM_KINDS["attraction"])
    q = (f"[out:json][timeout:20];"
         f"node{tag}(around:{radius},{lat},{lon});"
         f"out body {limit};")
    try:
        els = _overpass(q).get("elements", [])
    except Exception:
        return []
    out = []
    for e in els:
        t = e.get("tags", {})
        name = t.get("name")
        if not name:
            continue
        out.append({"name": name, "lat": e.get("lat"), "lon": e.get("lon"),
                    "tags": {k: v for k, v in t.items()
                             if k in ("cuisine", "tourism", "amenity", "stars",
                                      "opening_hours", "website")}})
    return out[:limit]


# ---- Wikidata: world knowledge graph (priority #2, free/keyless) -------------
def wikidata_entity(name: str) -> dict:
    """Name -> {qid, label, description, lat, lon, country}. Wikidata (no key).

    Search resolves a stable QID; SPARQL by QID adds coordinates + country label.
    """
    out: dict = {"name": name}
    try:
        s = _get("https://www.wikidata.org/w/api.php", {
            "action": "wbsearchentities", "search": name, "language": "en",
            "format": "json", "limit": 1}).get("search", [])
        if not s:
            return out
        top = s[0]
        out.update({"qid": top.get("id"), "label": top.get("label"),
                    "description": top.get("description")})
    except Exception:
        return out
    try:
        q = (f'SELECT ?coord ?countryLabel WHERE {{'
             f'  OPTIONAL {{ wd:{out["qid"]} wdt:P625 ?coord. }}'
             f'  OPTIONAL {{ wd:{out["qid"]} wdt:P17 ?country. }}'
             f'  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}'
             f'}} LIMIT 1')
        b = _get("https://query.wikidata.org/sparql",
                 {"query": q, "format": "json"},
                 headers={**_HEADERS, "Accept": "application/sparql-results+json"})
        rows = b.get("results", {}).get("bindings", [])
        if rows:
            row = rows[0]
            out["country"] = row.get("countryLabel", {}).get("value")
            coord = row.get("coord", {}).get("value", "")  # "Point(lon lat)"
            if coord.startswith("Point("):
                lon, lat = coord[6:-1].split()
                out["lat"], out["lon"] = float(lat), float(lon)
    except Exception:
        pass
    return out


# ---- Wikivoyage: human travel knowledge (priority #3, free/keyless) ----------
def wikivoyage(city: str, max_chars: int = 1500) -> dict:
    """City -> {title, summary, url}. Wikivoyage article intro (MediaWiki API, no key)."""
    try:
        d = _get("https://en.wikivoyage.org/w/api.php", {
            "action": "query", "prop": "extracts", "exintro": 1,
            "explaintext": 1, "redirects": 1, "titles": city, "format": "json"})
        pages = d.get("query", {}).get("pages", {})
        page = next(iter(pages.values()), {})
        extract = (page.get("extract") or "").strip()
        if not extract:
            return {"title": city, "summary": "", "url": None}
        title = page.get("title", city)
        return {"title": title, "summary": extract[:max_chars],
                "url": f"https://en.wikivoyage.org/wiki/{title.replace(' ', '_')}"}
    except Exception:
        return {"title": city, "summary": "", "url": None}


# ---- Historical weather: seasonality (priority #8, free/keyless) -------------
def seasonality(lat: float, lon: float, month: int, year: int | None = None) -> dict:
    """Typical weather for a month from the historical archive (Open-Meteo, no key).

    NOT a forecast — this is seasonality grounding: avg high/low, mean daily rain,
    and rainy-day count for `month` over the last completed year by default.
    """
    if year is None:
        year = datetime.date.today().year - 1
    days = calendar.monthrange(year, month)[1]
    start, end = f"{year}-{month:02d}-01", f"{year}-{month:02d}-{days:02d}"
    try:
        d = _get("https://archive-api.open-meteo.com/v1/archive", {
            "latitude": lat, "longitude": lon, "start_date": start,
            "end_date": end, "timezone": "auto",
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum"})
        daily = d.get("daily", {})
        tmax = [x for x in daily.get("temperature_2m_max", []) if x is not None]
        tmin = [x for x in daily.get("temperature_2m_min", []) if x is not None]
        prcp = [x for x in daily.get("precipitation_sum", []) if x is not None]
        if not tmax:
            return {}
        n = len(prcp) or 1
        return {
            "month": month, "year": year,
            "avg_high_c": round(sum(tmax) / len(tmax), 1),
            "avg_low_c": round(sum(tmin) / len(tmin), 1),
            "mean_daily_rain_mm": round(sum(prcp) / n, 1),
            "rainy_days": sum(1 for p in prcp if p >= 1.0),
        }
    except Exception:
        return {}


# ---- Amadeus: live flight/hotel prices (priority #4, keyed, free test tier) ---
# Set AMADEUS_CLIENT_ID / AMADEUS_CLIENT_SECRET in .env to activate. Everything
# below falls back to mock via get_flights/get_hotels on any failure.
_AMADEUS = {"token": None, "exp": 0.0}
# Common destination -> Amadeus city code (flights + hotels). Unknown cities fall
# back to the reference-data locations API.
_CITY_CODE = {"tokyo": "TYO", "kyoto": "OSA", "osaka": "OSA", "paris": "PAR",
              "london": "LON", "dubai": "DXB", "singapore": "SIN",
              "bangkok": "BKK", "new york": "NYC", "bali": "DPS"}


def _amadeus_token() -> str:
    now = time.time()
    if _AMADEUS["token"] and _AMADEUS["exp"] - 30 > now:
        return _AMADEUS["token"]
    r = requests.post(
        f"{config.AMADEUS_BASE_URL}/v1/security/oauth2/token",
        data={"grant_type": "client_credentials",
              "client_id": config.AMADEUS_CLIENT_ID,
              "client_secret": config.AMADEUS_CLIENT_SECRET},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=_TIMEOUT)
    r.raise_for_status()
    j = r.json()
    _AMADEUS["token"] = j["access_token"]
    _AMADEUS["exp"] = now + j.get("expires_in", 1799)
    return _AMADEUS["token"]


def _amadeus_get(path: str, params: dict) -> dict:
    r = requests.get(f"{config.AMADEUS_BASE_URL}{path}", params=params,
                     headers={"Authorization": f"Bearer {_amadeus_token()}"},
                     timeout=_TIMEOUT)
    r.raise_for_status()
    return r.json()


def _iso_hours(iso: str) -> float:
    """ISO-8601 duration 'PT13H30M' -> hours as float."""
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?", iso or "")
    if not m:
        return 0.0
    h = int(m.group(1) or 0)
    mi = int(m.group(2) or 0)
    return round(h + mi / 60, 2)


def _city_code(city: str) -> str | None:
    key = (city or "").strip().lower()
    if key in _CITY_CODE:
        return _CITY_CODE[key]
    try:
        d = _amadeus_get("/v1/reference-data/locations",
                         {"keyword": city, "subType": "CITY", "page[limit]": 1})
        return (d.get("data") or [{}])[0].get("iataCode")
    except Exception:
        return None


def _trip_dates(trip: dict):
    """(departure, return, nights) — 15th of the travel month, next occurrence."""
    month = int(trip.get("travel_month", 11))
    days = int(trip.get("days", 5))
    today = datetime.date.today()
    dep = datetime.date(today.year, month, 15)
    if dep <= today:
        dep = datetime.date(today.year + 1, month, 15)
    nights = max(days - 1, 1)
    return dep, dep + datetime.timedelta(days=days), nights


def _map_flight_offer(o: dict, idx: int) -> dict:
    """Amadeus flight-offer -> our flight schema (pure; no network)."""
    price = o.get("price", {})
    total = float(price.get("total", 0))
    cur = price.get("currency", "INR")
    price_inr = total if cur == "INR" else convert_currency(total, cur, "INR")
    itin = (o.get("itineraries") or [{}])[0]
    segs = itin.get("segments") or [{}]
    first, last = segs[0], segs[-1]
    airline = (o.get("validatingAirlineCodes")
               or [first.get("carrierCode", "")])[0]
    return {
        "id": f"AMF{idx + 1}",
        "airline": airline,
        "price_inr": round(price_inr),
        "stops": max(len(segs) - 1, 0),
        "depart": first.get("departure", {}).get("at", "T")[11:16],
        "arrive": last.get("arrival", {}).get("at", "T")[11:16],
        "duration_h": _iso_hours(itin.get("duration", "PT0H")),
        "refundable": bool(o.get("pricingOptions", {}).get("refundableFare", False)),
    }


def _map_hotel_offer(x: dict, idx: int, nights: int) -> dict | None:
    """Amadeus hotel-offer -> our hotel schema (pure; no network)."""
    offers = x.get("offers") or []
    if not offers:
        return None
    hotel = x.get("hotel", {})
    price = offers[0].get("price", {})
    total = float(price.get("total", 0))
    cur = price.get("currency", "INR")
    per_night = total / max(nights, 1)
    per_night_inr = per_night if cur == "INR" else convert_currency(per_night, cur, "INR")
    rating = hotel.get("rating")
    stars = int(round(float(rating))) if rating else 3
    return {
        "id": f"AMH{idx + 1}",
        "name": hotel.get("name", "Hotel"),
        "stars": stars,
        "price_inr_night": round(per_night_inr),
        "area": hotel.get("cityCode", ""),
        "transit_min": 8,                       # not in offer; sensible default
        "rating": round(min(5.0, stars + 0.3), 1),
    }


def amadeus_flights(trip: dict) -> list:
    dest = _city_code(trip.get("destination", ""))
    if not dest:
        return []
    dep, ret, _ = _trip_dates(trip)
    d = _amadeus_get("/v2/shopping/flight-offers", {
        "originLocationCode": config.ORIGIN_IATA,
        "destinationLocationCode": dest,
        "departureDate": dep.isoformat(),
        "returnDate": ret.isoformat(),
        "adults": 1, "currencyCode": "INR", "max": 6})
    return [_map_flight_offer(o, i) for i, o in enumerate(d.get("data", []))]


def amadeus_hotels(trip: dict) -> list:
    city = _city_code(trip.get("destination", ""))
    if not city:
        return []
    dep, _, nights = _trip_dates(trip)
    ids = [h.get("hotelId") for h in _amadeus_get(
        "/v1/reference-data/locations/hotels/by-city",
        {"cityCode": city}).get("data", [])[:20] if h.get("hotelId")]
    if not ids:
        return []
    d = _amadeus_get("/v3/shopping/hotel-offers", {
        "hotelIds": ",".join(ids), "adults": 1,
        "checkInDate": dep.isoformat(),
        "checkOutDate": (dep + datetime.timedelta(days=nights)).isoformat(),
        "currency": "INR", "bestRateOnly": "true"})
    out = []
    for i, x in enumerate(d.get("data", [])):
        h = _map_hotel_offer(x, i, nights)
        if h:
            out.append(h)
    return out


# ---- GTFS: public transport (priority #5, free per-agency feeds) --------------
def gtfs_status() -> dict:
    """Report whether a GTFS feed is wired. Set GTFS_FEED_URL in .env to activate."""
    return {"configured": bool(config.GTFS_FEED_URL),
            "feed": config.GTFS_FEED_URL or None}


def gtfs_routes(limit: int = 20) -> list:
    """Load route short/long names from a static GTFS .zip feed (stdlib only).

    Returns [] when no feed is configured — the Transport agent then falls back
    to time/distance estimates.
    """
    if not config.GTFS_FEED_URL:
        return []
    import csv
    import io
    import zipfile
    try:
        r = requests.get(config.GTFS_FEED_URL, timeout=_TIMEOUT)
        r.raise_for_status()
        zf = zipfile.ZipFile(io.BytesIO(r.content))
        with zf.open("routes.txt") as f:
            rows = list(csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig")))
        return [{"route": (row.get("route_short_name") or row.get("route_long_name")),
                 "type": row.get("route_type")} for row in rows[:limit]]
    except Exception:
        return []
