"""Dynamic wallpapers made from Apple's aerial videos (Golden Gate, Tahoe, Sequoia, ...).

Since macOS Sonoma, a release's own landscapes ship as aerial videos, one per time of day
(e.g. "Tahoe Morning", "Tahoe Night"); the desktop shows the video's first frame. Places whose
videos all name a time of day become one picture here, with a sun schedule like the HEIC
pictures' so the same choice applies.
"""

import io
import json
import plistlib
import re
import ssl
import subprocess
import tarfile
import time
import urllib.error
import urllib.request
from pathlib import Path

from . import catalog
from .heic import Metadata, SolarImage

CONFIG_BASE = "https://configuration.apple.com/configurations/internetservices/aerials"
# Each macOS release has resources-config-<major>-0.plist; probe upward from here.
CONFIG_MIN_MAJOR = 27
MANIFEST_MAX_AGE = 7 * 24 * 3600

# Idealised sun positions per time of day: (altitude, before solar noon). "Day" and "Night"
# stand for both halves.
PHASES = {
    "dawn": [(-8, True)],
    "sunrise": [(0, True)],
    "morning": [(15, True)],
    "day": [(45, True), (45, False)],
    "afternoon": [(25, False)],
    "sunset": [(3, False)],
    "evening": [(-5, False)],
    "dusk": [(-8, False)],
    "night": [(-25, True), (-25, False)],
}


def _context(apple_ca: str) -> ssl.SSLContext:
    """sylvan.apple.com chains to Apple's own root CA, which isn't in the system bundle."""
    context = ssl.create_default_context()
    context.load_verify_locations(apple_ca)
    return context


def _get(url: str, context: ssl.SSLContext | None = None) -> bytes:
    with urllib.request.urlopen(url, timeout=catalog.TIMEOUT, context=context) as response:
        return response.read()


def _newest_config() -> str:
    major = CONFIG_MIN_MAJOR
    while True:
        try:
            _get(f"{CONFIG_BASE}/resources-config-{major + 1}-0.plist")
            major += 1
        except urllib.error.HTTPError:
            return f"{CONFIG_BASE}/resources-config-{major}-0.plist"


def _manifest(cache: Path, apple_ca: str) -> dict:
    """entries.json of the newest release, refreshed once it's a week old."""
    path = cache / "aerials.json"
    if not path.exists() or time.time() - path.stat().st_mtime > MANIFEST_MAX_AGE:
        try:
            config = plistlib.loads(_get(_newest_config()))
            archive = _get(config["resources-url"], _context(apple_ca))
            with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
                entries = tar.extractfile("entries.json").read()
            json.loads(entries)
            part = path.with_name(path.name + ".part")
            part.write_bytes(entries)
            part.replace(path)
        except (urllib.error.URLError, OSError, KeyError, ValueError, tarfile.TarError):
            if not path.exists():
                raise
    return json.loads(path.read_text())


def _phase(asset: dict) -> str | None:
    """The time of day an asset shows, from its label or, for unlabelled ones, its file name."""
    text = f"{asset.get('accessibilityLabel', '')} {asset.get('url-4K-SDR-240FPS', '').rsplit('/', 1)[-1]}"
    for word in re.findall(r"[a-z]+", text.lower()):
        if word in PHASES:
            return word
    return None


def _place_name(subcategory_key: str) -> str:
    # "AerialSubcategoryGoldenGate" -> "Golden Gate"
    return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", subcategory_key.removeprefix("AerialSubcategory"))


def load(cache: Path, apple_ca: str) -> dict[str, catalog.Picture]:
    """Every place whose videos each show a time of day (two at least), by place name."""
    manifest = _manifest(cache, apple_ca)
    subcategories = {s["id"]: s["localizedNameKey"] for c in manifest["categories"] for s in c.get("subcategories", [])}

    places: dict[str, list[dict]] = {}
    for asset in manifest["assets"]:
        if not asset.get("url-4K-SDR-240FPS"):
            continue
        for subcategory in asset.get("subcategories", []):
            if subcategories.get(subcategory, "").startswith("AerialSubcategory"):
                places.setdefault(subcategories[subcategory], []).append(asset)

    pictures = {}
    for key, assets in places.items():
        phases = [_phase(a) for a in assets]
        if None in phases or len(set(phases)) < 2:
            continue
        frames = tuple(
            catalog.Frame(label=a["accessibilityLabel"], url=a["url-4K-SDR-240FPS"], phase=phase)
            for a, phase in sorted(zip(assets, phases), key=lambda pair: pair[0].get("preferredOrder", 0))
        )
        name = _place_name(key)
        pictures[name] = catalog.Picture(id=name, url="", sha1=b"", size=0, frames=frames)
    return pictures


def metadata(picture: catalog.Picture) -> Metadata:
    """The place's sun schedule; image i is frame i."""
    return Metadata(
        kind="solar",
        solar=[
            SolarImage(altitude, 90 if morning else 270, index)
            for index, frame in enumerate(picture.frames)
            for altitude, morning in PHASES[frame.phase]
        ],
    )


def grab_frames(picture: catalog.Picture, directory: Path, apple_ca: str) -> list[Path]:
    """The first frame of each of the place's videos, as frame-<i>.png in directory.

    ffmpeg range-requests the video's index and its first frame, a few MB of each ~500 MB file;
    the videos are fetched in parallel, as each is mostly round trips.
    """
    paths = [directory / f"frame-{index}.png" for index in range(len(picture.frames))]
    grabs = [
        subprocess.Popen(
            ["ffmpeg", "-v", "error", "-tls_verify", "1", "-ca_file", apple_ca, "-rw_timeout", "30000000",
             "-i", frame.url, "-frames:v", "1", "-y", str(path)],
            stdin=subprocess.DEVNULL,
        )
        for frame, path in zip(picture.frames, paths)
    ]
    failed = [frame.label for frame, grab in zip(picture.frames, grabs) if grab.wait() != 0]
    if failed:
        raise OSError(f"{picture.id}: couldn't grab {', '.join(failed)}")
    return paths
