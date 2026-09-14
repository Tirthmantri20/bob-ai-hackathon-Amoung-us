"""
Haversine great-circle distance utility.

Pure Python — no external dependencies.  Shared by the Risk Engine, Route
Optimizer, and Fleet Matcher.
"""

import math

_EARTH_RADIUS_KM = 6_371.0


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Return the great-circle distance in kilometres between two points on Earth.

    Parameters
    ----------
    lat1, lon1 : float
        Latitude and longitude of the first point in decimal degrees.
    lat2, lon2 : float
        Latitude and longitude of the second point in decimal degrees.

    Returns
    -------
    float
        Distance in kilometres (always ≥ 0).
    """
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    rlat1 = math.radians(lat1)
    rlat2 = math.radians(lat2)

    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(rlat1) * math.cos(rlat2) * math.sin(d_lon / 2) ** 2
    )
    return _EARTH_RADIUS_KM * 2 * math.asin(math.sqrt(a))
