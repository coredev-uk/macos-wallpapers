import json

import pytest

from macos_wallpapers import aerial
from macos_wallpapers.heic import choose

URL = "https://sylvan.apple.com/itunes-assets/x/{}.mov"


def asset(label: str, subcategory: str, order: int, file: str = "video") -> dict:
    return {"accessibilityLabel": label, "subcategories": [subcategory], "preferredOrder": order, "url-4K-SDR-240FPS": URL.format(file)}


# Shaped like the macOS 27 manifest: Golden Gate's day and evening videos have no proper label.
MANIFEST = {
    "categories": [
        {
            "id": "landscapes",
            "localizedNameKey": "AerialCategoryLandscapes",
            "subcategories": [
                {"id": "gg", "localizedNameKey": "AerialSubcategoryGoldenGate"},
                {"id": "tahoe", "localizedNameKey": "AerialSubcategoryTahoe"},
                {"id": "sequoia", "localizedNameKey": "AerialSubcategorySequoia"},
                {"id": "sonoma", "localizedNameKey": "AerialSubcategorySonoma"},
                {"id": "iceland", "localizedNameKey": "AerialSubcategoryIceland"},
            ],
        }
    ],
    "assets": [
        asset("Golden Gate Sunset", "gg", 0),
        asset("GG_A_DAY_BLUFFS_C35_V25_HFR_HEVC", "gg", 5, "GG_A_DAY_BLUFFS"),
        asset("GG_A_EVENING_TORPEDOWHARF_C35_V22_HFR_HEVC", "gg", 6),
        asset("Golden Gate Night", "gg", 39),
        asset("Tahoe Day", "tahoe", 1),
        asset("Tahoe Morning", "tahoe", 15),
        asset("Tahoe Evening", "tahoe", 22),
        asset("Tahoe Night", "tahoe", 40),
        asset("Sequoia Sunrise", "sequoia", 2),
        asset("Sequoia Morning", "sequoia", 16),
        asset("Sequoia Night", "sequoia", 23),
        # Not a time-of-day set: one video names a time of day, the others don't.
        asset("Sonoma Evening", "sonoma", 18),
        asset("Cazadero", "sonoma", 3),
        asset("Iceland", "iceland", 11),
        asset("Iceland", "iceland", 24),
    ],
}


@pytest.fixture
def places(tmp_path):
    # A fresh cached manifest, so nothing is fetched.
    (tmp_path / "aerials.json").write_text(json.dumps(MANIFEST))
    return aerial.load(tmp_path, apple_ca="unused")


def test_only_time_of_day_sets_become_pictures(places):
    assert sorted(places) == ["Golden Gate", "Sequoia", "Tahoe"]


def test_frames_follow_apples_order_and_name_their_phase(places):
    assert [f.phase for f in places["Tahoe"].frames] == ["day", "morning", "evening", "night"]
    assert [f.phase for f in places["Golden Gate"].frames] == ["sunset", "day", "evening", "night"]


def frame_for(picture, altitude, morning):
    return picture.frames[choose(aerial.metadata(picture), altitude, morning)].phase


@pytest.mark.parametrize(
    ("altitude", "morning", "phase"),
    [
        (-40, True, "night"),
        (5, True, "morning"),
        (50, False, "day"),
        (10, False, "evening"),  # low evening sun: no sunset video, so evening
        (-40, False, "night"),
    ],
)
def test_tahoe_through_the_day(places, altitude, morning, phase):
    assert frame_for(places["Tahoe"], altitude, morning) == phase


@pytest.mark.parametrize(
    ("altitude", "morning", "phase"),
    [
        (0, True, "sunrise"),
        (20, True, "morning"),
        # No afternoon or evening video: the nearest morning one stands in, not night.
        (30, False, "morning"),
        (-40, False, "night"),
    ],
)
def test_sequoia_falls_back_without_evening_videos(places, altitude, morning, phase):
    assert frame_for(places["Sequoia"], altitude, morning) == phase


def test_golden_gate_sunset_then_evening(places):
    assert frame_for(places["Golden Gate"], 4, False) == "sunset"
    assert frame_for(places["Golden Gate"], -6, False) == "evening"
