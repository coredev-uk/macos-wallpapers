"""Where the sun is: altitude and which half of the day, from NOAA's general solar position
equations (https://gml.noaa.gov/grad/solcalc/solareqns.PDF); accurate to well under a degree,
plenty for picking a wallpaper."""

import math
from datetime import datetime, timezone


def position(when: datetime, latitude: float, longitude: float) -> tuple[float, bool]:
    """(altitude in degrees, True before solar noon) at `when` for a place (degrees, east +)."""
    utc = when.astimezone(timezone.utc)
    day_of_year = utc.timetuple().tm_yday
    hours = utc.hour + utc.minute / 60 + utc.second / 3600

    # Fractional year in radians.
    g = 2 * math.pi / 365 * (day_of_year - 1 + (hours - 12) / 24)
    equation_of_time = 229.18 * (
        0.000075
        + 0.001868 * math.cos(g)
        - 0.032077 * math.sin(g)
        - 0.014615 * math.cos(2 * g)
        - 0.040849 * math.sin(2 * g)
    )
    declination = (
        0.006918
        - 0.399912 * math.cos(g)
        + 0.070257 * math.sin(g)
        - 0.006758 * math.cos(2 * g)
        + 0.000907 * math.sin(2 * g)
        - 0.002697 * math.cos(3 * g)
        + 0.00148 * math.sin(3 * g)
    )

    true_solar_minutes = hours * 60 + equation_of_time + 4 * longitude
    hour_angle = math.radians(true_solar_minutes / 4 - 180)

    lat = math.radians(latitude)
    cos_zenith = math.sin(lat) * math.sin(declination) + math.cos(lat) * math.cos(declination) * math.cos(hour_angle)
    altitude = 90 - math.degrees(math.acos(max(-1.0, min(1.0, cos_zenith))))

    # Hour angle wrapped to [-180, 180): negative before solar noon.
    morning = math.remainder(math.degrees(hour_angle), 360) < 0
    return altitude, morning
