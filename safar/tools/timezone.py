"""Timezone / DST tool — deterministic (NO llm, NO api). Owner: mr.jarvis0.

Convert times between zones, compute jet-lag offset, check DST crossings.
Uses Python stdlib `zoneinfo` (Python 3.9+) — no external dependency.
"""
import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

# Common city → IANA timezone mapping (offline fallback for OPTD data).
_CITY_TZ = {
    "tokyo": "Asia/Tokyo", "kyoto": "Asia/Tokyo", "osaka": "Asia/Tokyo",
    "paris": "Europe/Paris", "london": "Europe/London",
    "dubai": "Asia/Dubai", "abu dhabi": "Asia/Dubai",
    "bangkok": "Asia/Bangkok", "singapore": "Asia/Singapore",
    "bali": "Asia/Makassar", "jakarta": "Asia/Jakarta",
    "new york": "America/New_York", "los angeles": "America/Los_Angeles",
    "delhi": "Asia/Kolkata", "mumbai": "Asia/Kolkata",
    "kathmandu": "Asia/Kathmandu", "colombo": "Asia/Colombo",
}


def city_timezone(city: str) -> str | None:
    """City name → IANA timezone string (e.g. 'Asia/Tokyo')."""
    return _CITY_TZ.get((city or "").strip().lower())


def utc_offset(tz_name: str, when: datetime.datetime | None = None) -> float:
    """UTC offset in hours for a timezone at a given moment (default: now)."""
    try:
        tz = ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, KeyError):
        return 0.0
    dt = when or datetime.datetime.now(tz)
    offset = dt.utcoffset()
    return offset.total_seconds() / 3600 if offset else 0.0


def jet_lag_hours(home_tz: str, dest_tz: str) -> float:
    """Absolute time difference (hours) — a proxy for jet-lag severity."""
    try:
        return abs(utc_offset(home_tz) - utc_offset(dest_tz))
    except Exception:
        return 0.0


def convert_time(time_str: str, from_tz: str, to_tz: str,
                 date: datetime.date | None = None) -> str:
    """Convert 'HH:MM' from one timezone to another. Returns 'HH:MM'."""
    try:
        h, m = map(int, time_str.split(":"))
        d = date or datetime.date.today()
        dt = datetime.datetime(d.year, d.month, d.day, h, m,
                               tzinfo=ZoneInfo(from_tz))
        converted = dt.astimezone(ZoneInfo(to_tz))
        return converted.strftime("%H:%M")
    except Exception:
        return time_str  # fallback: return as-is


def is_dst(tz_name: str, when: datetime.datetime | None = None) -> bool:
    """Check if DST is in effect for a timezone at a given moment."""
    try:
        tz = ZoneInfo(tz_name)
        dt = when or datetime.datetime.now(tz)
        return bool(dt.dst())
    except Exception:
        return False
