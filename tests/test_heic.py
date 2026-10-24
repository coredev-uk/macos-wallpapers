import base64
import plistlib

import pytest

from macos_wallpapers.heic import Metadata, SolarImage, choose, read_metadata

# The schedule of "The Lake" (also The Beach, The Cliffs, The Desert, Big Sur): 1 night,
# 2 dawn, 3 sunrise, 0 morning, 4 day, 5 afternoon, 6 sunset, 7 dusk.
LAKE = Metadata(
    kind="solar",
    solar=[
        SolarImage(10, 100, 0),
        SolarImage(-25, 70, 1),
        SolarImage(-9, 80, 2),
        SolarImage(0, 90, 3),
        SolarImage(25, 110, 4),
        SolarImage(25, 250, 4),
        SolarImage(10, 260, 5),
        SolarImage(0, 270, 6),
        SolarImage(-9, 280, 7),
        SolarImage(-25, 290, 1),
    ],
    light=0,
    dark=1,
)


@pytest.mark.parametrize(
    ("altitude", "morning", "image"),
    [
        (-60, True, 1),  # night, before sunrise
        (-60, False, 1),  # night, after sunset
        (-10, True, 2),  # dawn
        (1, True, 3),  # sunrise
        (8, True, 0),  # morning
        (62, True, 4),  # high summer sun
        (62, False, 4),
        (12, False, 5),  # afternoon
        (-1, False, 6),  # sunset
        (-8, False, 7),  # dusk, not dawn: same altitude, other half of the day
    ],
)
def test_solar_choice(altitude, morning, image):
    assert choose(LAKE, altitude, morning) == image


def test_appearance_choice_follows_the_horizon():
    meta = Metadata(kind="appearance", light=0, dark=1)
    assert choose(meta, 30, True) == 0
    assert choose(meta, -3, False) == 1


def test_static_always_shows_the_only_image():
    assert choose(Metadata(kind="static"), -40, False) == 0


def _xmp(name: str, value: dict, element: bool) -> bytes:
    encoded = base64.b64encode(plistlib.dumps(value, fmt=plistlib.FMT_BINARY))
    if element:
        return b"<apple_desktop:" + name + b">" + encoded + b"</apple_desktop:" + name + b">"
    return b'apple_desktop:' + name + b'="' + encoded + b'"'


@pytest.mark.parametrize("element", [False, True])
def test_reads_solar_schedule(tmp_path, element):
    schedule = {"ap": {"l": 0, "d": 1}, "si": [{"a": -25.0, "z": 70.0, "i": 1}, {"a": 25.0, "z": 110.0, "i": 4}]}
    path = tmp_path / "x.heic"
    path.write_bytes(b"\x00ftypheic...<x:xmpmeta " + _xmp(b"solar", schedule, element) + b"/>...mdat")

    meta = read_metadata(path)

    assert meta.kind == "solar"
    assert meta.solar == [SolarImage(-25.0, 70.0, 1), SolarImage(25.0, 110.0, 4)]
    assert meta.indices() == {1, 4}


def test_reads_light_dark_pair(tmp_path):
    path = tmp_path / "x.heic"
    path.write_bytes(b"...<rdf:Description " + _xmp(b"apr", {"l": 0, "d": 1}, False) + b"/>...")

    meta = read_metadata(path)

    assert meta.kind == "appearance"
    assert meta.indices() == {0, 1}


def test_no_schedule_means_static(tmp_path):
    path = tmp_path / "x.heic"
    path.write_bytes(b"\x00ftypheic plain image")

    assert read_metadata(path).kind == "static"


def test_metadata_survives_the_json_cache():
    assert Metadata.from_json(LAKE.to_json()) == LAKE
