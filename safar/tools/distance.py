"""Distance tool — deterministic haversine (NO llm, NO api). Owner: adi."""
import math


def km_between(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Great-circle distance in km between (lat, lon) points a and b."""
    lat1, lon1 = a
    lat2, lon2 = b
    R = 6371.0  # Earth radius, km
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    h = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return round(2 * R * math.asin(math.sqrt(h)), 2)
