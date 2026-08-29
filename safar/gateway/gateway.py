"""Tool Gateway — all external API calls go through here. Owner: adi.

Adds caching + a mock fallback so the live demo can't crash (readme.md section 16).
Reads keys via safar.config (from .env — never hard-coded, never committed).
"""
import json
import pathlib

_DATA = pathlib.Path(__file__).resolve().parents[2] / "data" / "tokyo.json"


def _mock(kind: str) -> list:
    data = json.loads(_DATA.read_text(encoding="utf-8"))
    return data.get(kind, [])


def get_flights(trip: dict) -> list:
    # TODO(adi): call the real API; on error/timeout -> return _mock("flights")
    return _mock("flights")


def get_hotels(trip: dict) -> list:
    return _mock("hotels")


def get_activities(trip: dict) -> list:
    return _mock("activities")
