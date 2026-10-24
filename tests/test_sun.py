from datetime import datetime, timezone

import pytest

from macos_wallpapers.sun import position

LONDON = (51.5074, -0.1278)


def at(*args):
    return datetime(*args, tzinfo=timezone.utc)


def test_summer_solstice_noon_altitude():
    # Maximum altitude at 51.5 N: 90 - 51.5 + 23.44 = 61.9 degrees.
    altitude, _ = position(at(2026, 6, 21, 12, 2), *LONDON)
    assert altitude == pytest.approx(61.9, abs=0.5)


def test_winter_solstice_noon_altitude():
    # 90 - 51.5 - 23.44 = 15.1 degrees.
    altitude, _ = position(at(2026, 12, 21, 11, 58), *LONDON)
    assert altitude == pytest.approx(15.1, abs=0.5)


def test_midnight_is_well_below_the_horizon():
    altitude, _ = position(at(2026, 12, 21, 0, 0), *LONDON)
    assert altitude < -50


def test_morning_and_evening_split_at_solar_noon():
    assert position(at(2026, 6, 21, 8, 0), *LONDON)[1] is True
    assert position(at(2026, 6, 21, 16, 0), *LONDON)[1] is False


def test_longitude_shifts_solar_noon():
    # Solar noon at 90 E is ~6 hours earlier than at Greenwich, so 09:00 UTC is afternoon there.
    assert position(at(2026, 6, 21, 9, 0), 30.0, 90.0)[1] is False
    assert position(at(2026, 6, 21, 9, 0), 30.0, 0.0)[1] is True


def test_equinox_noon_altitude_is_the_colatitude():
    # Declination ~0 at the March equinox: 90 - 51.5 = 38.5 degrees at solar noon (~12:08 UTC).
    altitude, _ = position(at(2026, 3, 20, 12, 8), *LONDON)
    assert altitude == pytest.approx(38.5, abs=0.5)
