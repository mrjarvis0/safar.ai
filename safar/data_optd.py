"""OpenTravelData (OPTD) loader — offline airports/cities/airlines. Owner: adi.

Free, keyless, offline reference data from https://github.com/opentraveldata/
opentraveldata (CC-BY 4.0 — see data/optd/NOTICE). Gives the gateway a real
city/airport -> IATA resolver (thousands of places, no API), airline code ->
name, and an offline geo/country/timezone fallback.

Files (^-separated, curated subset committed under data/optd/):
  optd_por_min.csv  — iata,name,lat,lon,country_code,country,timezone,page_rank,loc_type
  optd_airlines.csv — full OPTD airlines table
"""
import csv
import pathlib

_DIR = pathlib.Path(__file__).resolve().parents[1] / "data" / "optd"
_POR = _DIR / "optd_por_min.csv"
_AIRLINES = _DIR / "optd_airlines.csv"

_por_by_name: dict | None = None
_por_by_iata: dict | None = None
_airlines: dict | None = None


def _load_por() -> None:
    global _por_by_name, _por_by_iata
    if _por_by_name is not None:
        return
    _por_by_name, _por_by_iata = {}, {}
    if not _POR.exists():
        return
    # File is pre-sorted by page_rank desc, so the first row per name/IATA wins.
    with open(_POR, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            name_key = (row.get("name") or "").strip().lower()
            if name_key and name_key not in _por_by_name:
                _por_by_name[name_key] = row
            iata = (row.get("iata") or "").strip().upper()
            if iata and iata not in _por_by_iata:
                _por_by_iata[iata] = row


def _pack(row: dict) -> dict:
    return {
        "iata": row["iata"], "name": row["name"],
        "lat": float(row["lat"]) if row.get("lat") else None,
        "lon": float(row["lon"]) if row.get("lon") else None,
        "country_code": row.get("country_code"), "country": row.get("country"),
        "timezone": row.get("timezone"),
    }


def resolve_city(name: str) -> dict | None:
    """City/airport name -> {iata, name, lat, lon, country_code, country, timezone}."""
    _load_por()
    if not name or not _por_by_name:
        return None
    q = name.strip().lower()
    row = _por_by_name.get(q)
    if not row:                                   # highest-rank name that starts with q
        for k, r in _por_by_name.items():
            if k.startswith(q):
                row = r
                break
    return _pack(row) if row else None


def airport(iata: str) -> dict | None:
    _load_por()
    row = (_por_by_iata or {}).get((iata or "").strip().upper())
    return _pack(row) if row else None


def _load_airlines() -> None:
    global _airlines
    if _airlines is not None:
        return
    _airlines = {}
    if not _AIRLINES.exists():
        return
    with open(_AIRLINES, encoding="utf-8") as f:
        r = csv.reader(f, delimiter="^")
        next(r, None)
        for row in r:
            if len(row) < 8:
                continue
            validity_to, three, two, name = row[3], row[4], row[5], row[7]
            if not name:
                continue
            for code in (two.strip(), three.strip()):
                # prefer currently-active carriers (empty validity_to)
                if code and (code not in _airlines or not validity_to):
                    _airlines[code] = name


def airline_name(code: str) -> str | None:
    """IATA (2-char) or ICAO (3-char) airline code -> carrier name."""
    _load_airlines()
    return (_airlines or {}).get((code or "").strip().upper())
