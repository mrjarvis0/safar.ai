"""Itinerary builder — day-by-day plan + route order (NO llm). Owner: sush.

Takes the chosen hotel + activity set and lays out each day: activities are
chunked by pace, ordered nearest-neighbour from the hotel (deterministic
haversine, readme §5.1), and time-scheduled against opening hours. Emits
per-item `within_hours` (temporal) and per-day `total_km` (geo) so the
validators (readme §9) have real signals to check.
"""
from ..tools.distance import km_between

CITY_KMH = 18.0                       # avg door-to-door city transit speed
DAY_START_MIN = 9 * 60                # 09:00
BUFFER_MIN = 15                       # gap between activities
PACE_PER_DAY = {"relaxed": 2, "moderate": 3, "packed": 4}


def _mins(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def _hhmm(mins: float) -> str:
    mins = int(mins) % (24 * 60)
    return f"{mins // 60:02d}:{mins % 60:02d}"


def _open_close(hours: str):
    if not hours or hours.strip() == "24h":
        return 0, 24 * 60
    try:
        o, c = hours.split("-")
        return _mins(o), _mins(c)
    except Exception:
        return 0, 24 * 60


def _pt(x: dict):
    lat, lon = x.get("lat"), x.get("lon")
    return (lat, lon) if lat is not None and lon is not None else None


def _travel_min(a, b) -> int:
    if not (a and b):
        return 20                      # unknown coords -> flat estimate
    return max(10, round(km_between(a, b) / CITY_KMH * 60))


def build(hotel: dict, activities: list, days: int, pace: str) -> list:
    """-> [{day, items:[{name, area, arrive, depart, travel_km, within_hours,
    outdoor}], total_km}]  (only days that actually have activities)."""
    per = PACE_PER_DAY.get(pace, 2)
    chunks = [activities[i:i + per] for i in range(0, len(activities), per)]
    chunks = chunks[:max(days, 1)]
    hotel_pt = _pt(hotel)

    out = []
    for d, bucket in enumerate(chunks):
        # nearest-neighbour order, starting from the hotel
        ordered, remaining, cur = [], list(bucket), hotel_pt
        while remaining:
            nxt = min(remaining, key=lambda a: km_between(cur, _pt(a))
                      if (cur and _pt(a)) else 9e9)
            ordered.append(nxt)
            remaining.remove(nxt)
            cur = _pt(nxt) or cur

        t, prev, day_km, items = DAY_START_MIN, hotel_pt, 0.0, []
        for a in ordered:
            pt = _pt(a)
            km = km_between(prev, pt) if (prev and pt) else 0.0
            day_km += km
            arrive = t + _travel_min(prev, pt)
            o, c = _open_close(a.get("hours"))
            if arrive < o:                        # wait for opening
                arrive = o
            dur = a.get("duration_h", 1) * 60
            within = (arrive < c) and (arrive + dur <= c)
            depart = arrive + dur
            items.append({
                "name": a["name"], "area": a.get("area"),
                "arrive": _hhmm(arrive), "depart": _hhmm(depart),
                "travel_km": round(km, 1), "within_hours": within,
                "outdoor": bool(a.get("outdoor", False)),
            })
            t, prev = depart + BUFFER_MIN, pt
        out.append({"day": d + 1, "items": items, "total_km": round(day_km, 1)})
    return out
