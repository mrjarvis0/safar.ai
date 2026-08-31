"""Date arithmetic tool — deterministic (NO llm, NO api). Owner: mr.jarvis0.

Trip day calculations, date ranges, day-of-week, and public holiday detection.
Uses Python stdlib `datetime` — no external dependency.
"""
import datetime

# Major public holidays (month, day) → name.  Not exhaustive — just common ones
# that affect travel (closures, crowds).
_HOLIDAYS = {
    "Japan": {
        (1, 1): "New Year's Day", (1, 2): "New Year holiday",
        (1, 3): "New Year holiday",
        (2, 11): "National Foundation Day",
        (4, 29): "Showa Day (Golden Week start)",
        (5, 3): "Constitution Day", (5, 4): "Greenery Day",
        (5, 5): "Children's Day (Golden Week end)",
        (8, 11): "Mountain Day",
        (11, 3): "Culture Day", (11, 23): "Labor Thanksgiving",
    },
    "France": {
        (1, 1): "New Year's Day", (5, 1): "Labour Day",
        (5, 8): "Victory in Europe Day", (7, 14): "Bastille Day",
        (8, 15): "Assumption of Mary", (11, 1): "All Saints' Day",
        (11, 11): "Armistice Day", (12, 25): "Christmas Day",
    },
    "United Arab Emirates": {
        (1, 1): "New Year's Day", (12, 2): "National Day",
        (12, 3): "National Day holiday",
    },
    "Thailand": {
        (1, 1): "New Year's Day", (4, 13): "Songkran",
        (4, 14): "Songkran", (4, 15): "Songkran",
        (5, 1): "Labour Day", (12, 5): "King's Birthday",
        (12, 10): "Constitution Day",
    },
    "India": {
        (1, 26): "Republic Day", (8, 15): "Independence Day",
        (10, 2): "Gandhi Jayanti", (12, 25): "Christmas",
    },
}


def trip_dates(start: str | datetime.date, days: int) -> list[datetime.date]:
    """Generate a list of dates for a trip starting on `start` for `days` days."""
    if isinstance(start, str):
        start = datetime.date.fromisoformat(start)
    return [start + datetime.timedelta(days=d) for d in range(days)]


def day_of_week(date: str | datetime.date) -> str:
    """Return day-of-week name (e.g. 'Monday')."""
    if isinstance(date, str):
        date = datetime.date.fromisoformat(date)
    return date.strftime("%A")


def days_between(a: str | datetime.date, b: str | datetime.date) -> int:
    """Number of days between two dates."""
    if isinstance(a, str):
        a = datetime.date.fromisoformat(a)
    if isinstance(b, str):
        b = datetime.date.fromisoformat(b)
    return abs((b - a).days)


def holidays_in_range(country: str, start: str | datetime.date,
                      days: int) -> list[dict]:
    """Find public holidays falling within a date range."""
    dates = trip_dates(start, days)
    hols = _HOLIDAYS.get(country, {})
    found = []
    for d in dates:
        name = hols.get((d.month, d.day))
        if name:
            found.append({"date": d.isoformat(), "day": day_of_week(d),
                          "holiday": name})
    return found


def is_weekend(date: str | datetime.date) -> bool:
    """Check if a date falls on Saturday or Sunday."""
    if isinstance(date, str):
        date = datetime.date.fromisoformat(date)
    return date.weekday() >= 5


def next_occurrence(month: int, day: int = 15) -> datetime.date:
    """Next future occurrence of a given month/day."""
    today = datetime.date.today()
    candidate = datetime.date(today.year, month, min(day, 28))
    if candidate <= today:
        candidate = datetime.date(today.year + 1, month, min(day, 28))
    return candidate
