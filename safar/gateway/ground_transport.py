"""Ground transport inventory — intercity bus + train. Owner: adi.

Phase 3b (readme §6 Transport, §16). Buses and trains in India come from
partner/paid aggregators (RedBus-class bus API; IRCTC-class rail aggregator) —
there is no free, keyless price source, so this mirrors the flight/hotel pattern:
a real adapter that activates when a base URL + key are configured, and a
deterministic MOCK inventory otherwise so the demo never breaks.

Everything is wrapped in try/except + a short timeout; any failure falls back to
mock. These are grounding/pricing sources (readme §11), never fine-tuned in.
"""
from __future__ import annotations

import datetime
import hashlib

import requests

from .. import config

_TIMEOUT = 10
_CACHE: dict = {}


# ---- public API --------------------------------------------------------------
def search_ground(origin: str, dest: str, date: str | None = None) -> dict:
    """Intercity options between two cities. Returns {buses, trains, source}."""
    date = date or _default_date()
    buses = search_buses(origin, dest, date)
    trains = search_trains(origin, dest, date)
    live = bool(config.REDBUS_BASE_URL or config.RAIL_BASE_URL)
    return {"origin": origin, "destination": dest, "date": date,
            "buses": buses, "trains": trains,
            "source": "live" if live else "mock"}


def search_buses(origin: str, dest: str, date: str | None = None) -> list[dict]:
    """Bus inventory. Live RedBus-class API when configured, else mock."""
    date = date or _default_date()
    if config.REDBUS_BASE_URL and config.REDBUS_API_KEY:
        try:
            live = _redbus(origin, dest, date)
            if live:
                return live
        except Exception:
            pass
    return _mock_buses(origin, dest, date)


def search_trains(origin: str, dest: str, date: str | None = None) -> list[dict]:
    """Train inventory. Live rail-aggregator API when configured, else mock."""
    date = date or _default_date()
    if config.RAIL_BASE_URL and config.RAIL_API_KEY:
        try:
            live = _rail(origin, dest, date)
            if live:
                return live
        except Exception:
            pass
    return _mock_trains(origin, dest, date)


def status() -> dict:
    """Config summary for the dashboard (no secrets)."""
    return {"bus_api": "live" if config.REDBUS_BASE_URL else "mock",
            "rail_api": "live" if config.RAIL_BASE_URL else "mock"}


# ---- live adapters (partner/paid; shapes vary by provider) -------------------
# Providers differ in payload shape, so these map a generic response into our
# schema. Adjust the field paths to match your specific aggregator's contract.
def _redbus(origin: str, dest: str, date: str) -> list[dict]:
    r = requests.get(f"{config.REDBUS_BASE_URL.rstrip('/')}/search",
                     params={"source": origin, "destination": dest,
                             "date": date},
                     headers={"Authorization": f"Bearer {config.REDBUS_API_KEY}"},
                     timeout=_TIMEOUT)
    r.raise_for_status()
    rows = r.json().get("services") or r.json().get("data") or []
    out = []
    for i, s in enumerate(rows[:12]):
        out.append({
            "id": f"BUS{i + 1}",
            "operator": s.get("travels") or s.get("operator") or "Operator",
            "type": s.get("busType") or s.get("type") or "AC Seater",
            "depart": _hhmm(s.get("departureTime") or s.get("depart")),
            "arrive": _hhmm(s.get("arrivalTime") or s.get("arrive")),
            "duration_h": _to_hours(s.get("duration")),
            "price_inr": _to_inr(s.get("fare") or s.get("price")),
            "seats_available": int(s.get("availableSeats") or s.get("seats") or 0),
            "rating": float(s.get("rating") or 4.0),
            "cancellable": bool(s.get("cancellable", True)),
        })
    return out


def _rail(origin: str, dest: str, date: str) -> list[dict]:
    r = requests.get(f"{config.RAIL_BASE_URL.rstrip('/')}/trains/between",
                     params={"from": origin, "to": dest, "date": date},
                     headers={"Authorization": f"Bearer {config.RAIL_API_KEY}"},
                     timeout=_TIMEOUT)
    r.raise_for_status()
    rows = r.json().get("trains") or r.json().get("data") or []
    out = []
    for i, t in enumerate(rows[:12]):
        out.append({
            "id": f"TRN{i + 1}",
            "train_no": str(t.get("trainNumber") or t.get("number") or ""),
            "name": t.get("trainName") or t.get("name") or "Express",
            "class": t.get("class") or "3A",
            "depart": _hhmm(t.get("departureTime") or t.get("depart")),
            "arrive": _hhmm(t.get("arrivalTime") or t.get("arrive")),
            "duration_h": _to_hours(t.get("duration")),
            "price_inr": _to_inr(t.get("fare") or t.get("price")),
            "seats_available": int(t.get("availableSeats") or t.get("avail") or 0),
            "refundable": bool(t.get("refundable", True)),
        })
    return out


# ---- deterministic mock inventory (stable per origin/dest/date) --------------
_BUS_OPS = ["VRL Travels", "SRS Travels", "Orange Tours", "IntrCity SmartBus",
            "Zingbus", "APSRTC"]
_BUS_TYPES = ["AC Sleeper (2+1)", "AC Seater", "Non-AC Sleeper", "Volvo Multi-Axle"]
_TRAIN_NAMES = [("12951", "Rajdhani Express", "2A"), ("12009", "Shatabdi Express", "CC"),
                ("12627", "Karnataka Express", "3A"), ("11013", "Coimbatore Express", "SL")]


def _rng(origin: str, dest: str, date: str, salt: str) -> int:
    h = hashlib.md5(f"{origin}|{dest}|{date}|{salt}".encode()).hexdigest()
    return int(h[:8], 16)


def _mock_buses(origin: str, dest: str, date: str) -> list[dict]:
    key = ("BUS", origin, dest, date)
    if key in _CACHE:
        return _CACHE[key]
    base_price = 600 + _rng(origin, dest, date, "p") % 1400        # ₹600–2000
    out = []
    for i in range(4):
        seed = _rng(origin, dest, date, f"b{i}")
        dep_h = 18 + i                                            # evening departures
        dur = 6 + seed % 8
        out.append({
            "id": f"BUS{i + 1}",
            "operator": _BUS_OPS[seed % len(_BUS_OPS)],
            "type": _BUS_TYPES[(seed >> 3) % len(_BUS_TYPES)],
            "depart": f"{dep_h % 24:02d}:{(seed % 4) * 15:02d}",
            "arrive": f"{(dep_h + dur) % 24:02d}:{(seed % 4) * 15:02d}",
            "duration_h": float(dur),
            "price_inr": base_price + i * 120,
            "seats_available": 3 + seed % 34,
            "rating": round(3.6 + (seed % 13) / 10, 1),
            "cancellable": seed % 5 != 0,
        })
    _CACHE[key] = out
    return out


def _mock_trains(origin: str, dest: str, date: str) -> list[dict]:
    key = ("TRN", origin, dest, date)
    if key in _CACHE:
        return _CACHE[key]
    base_price = 450 + _rng(origin, dest, date, "tp") % 1600
    out = []
    for i, (no, name, cls) in enumerate(_TRAIN_NAMES):
        seed = _rng(origin, dest, date, f"t{i}")
        dep_h = 6 + (seed % 16)
        dur = 7 + seed % 12
        out.append({
            "id": f"TRN{i + 1}",
            "train_no": no,
            "name": name,
            "class": cls,
            "depart": f"{dep_h % 24:02d}:{(seed % 6) * 10:02d}",
            "arrive": f"{(dep_h + dur) % 24:02d}:{(seed % 6) * 10:02d}",
            "duration_h": float(dur),
            "price_inr": base_price + i * 200,
            "seats_available": seed % 60,          # 0 => waitlist, realistic
            "refundable": True,
        })
    _CACHE[key] = out
    return out


# ---- small parsers (tolerant of provider quirks) -----------------------------
def _default_date() -> str:
    return (datetime.date.today() + datetime.timedelta(days=30)).isoformat()


def _hhmm(v) -> str:
    s = str(v or "")
    if "T" in s and len(s) >= 16:      # ISO datetime
        return s[11:16]
    return s[:5] if ":" in s else s


def _to_hours(v) -> float:
    """'6h 30m' / '06:30' / 390 (minutes) -> hours as float."""
    if v is None:
        return 0.0
    if isinstance(v, (int, float)):
        return round(float(v) / 60, 2) if v > 24 else float(v)
    s = str(v)
    if ":" in s:
        h, m = (s.split(":") + ["0"])[:2]
        return round(int(h) + int(m) / 60, 2)
    import re
    hh = re.search(r"(\d+)\s*h", s)
    mm = re.search(r"(\d+)\s*m", s)
    return round((int(hh.group(1)) if hh else 0) + (int(mm.group(1)) if mm else 0) / 60, 2)


def _to_inr(v) -> int:
    try:
        return int(round(float(str(v).replace("₹", "").replace(",", "").strip())))
    except Exception:
        return 0
