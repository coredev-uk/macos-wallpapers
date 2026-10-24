"""What a desktop-picture HEIC contains, which of its images to show, and rendering one.

Dynamic pictures keep their schedule in the XMP packet as a base64 binary plist:
- apple_desktop:solar  {"si": [{"a": altitude, "z": azimuth, "i": image}, ...], "ap": {"l", "d"}}
- apple_desktop:apr    {"l": light image, "d": dark image}
Anything else is a single static image.
"""

import base64
import mmap
import plistlib
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

_XMP = re.compile(
    rb'apple_desktop:(solar|apr)\s*=\s*"([A-Za-z0-9+/=\s]+)"'
    rb"|<apple_desktop:(solar|apr)>([A-Za-z0-9+/=\s]+)</apple_desktop:\3>"
)


@dataclass(frozen=True)
class SolarImage:
    altitude: float
    azimuth: float
    index: int

    @property
    def morning(self) -> bool:
        return self.azimuth < 180


@dataclass(frozen=True)
class Metadata:
    kind: str  # "static", "appearance" or "solar"
    solar: list[SolarImage] = field(default_factory=list)
    light: int = 0
    dark: int = 0

    def indices(self) -> set[int]:
        """Every image this picture can show."""
        if self.kind == "solar":
            return {s.index for s in self.solar}
        if self.kind == "appearance":
            return {self.light, self.dark}
        return {0}

    def to_json(self) -> dict:
        return {
            "kind": self.kind,
            "solar": [[s.altitude, s.azimuth, s.index] for s in self.solar],
            "light": self.light,
            "dark": self.dark,
        }

    @classmethod
    def from_json(cls, data: dict) -> "Metadata":
        return cls(
            kind=data["kind"],
            solar=[SolarImage(a, z, i) for a, z, i in data["solar"]],
            light=data["light"],
            dark=data["dark"],
        )


def read_metadata(path: Path) -> Metadata:
    with open(path, "rb") as f, mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as data:
        tags = {}
        for m in _XMP.finditer(data):
            name, value = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4))
            tags[name.decode()] = plistlib.loads(base64.b64decode(value))

    if "solar" in tags:
        solar = tags["solar"]
        appearance = solar.get("ap", {})
        return Metadata(
            kind="solar",
            solar=[SolarImage(float(s["a"]), float(s["z"]), int(s["i"])) for s in solar["si"]],
            light=int(appearance.get("l", 0)),
            dark=int(appearance.get("d", 0)),
        )
    if "apr" in tags:
        return Metadata(kind="appearance", light=int(tags["apr"]["l"]), dark=int(tags["apr"]["d"]))
    return Metadata(kind="static")


def choose(meta: Metadata, altitude: float, morning: bool) -> int:
    """The image for a sun at `altitude` degrees, before (morning) or after solar noon.

    Apple tags solar images with idealised positions (azimuth 70-110 for mornings, 250-290 for
    evenings), not where the sun really is at a given place and season. So only the half of
    the day is taken from the azimuth; within it, the closest altitude wins.
    """
    if meta.kind == "solar":
        half = [s for s in meta.solar if s.morning == morning] or meta.solar
        return min(half, key=lambda s: abs(s.altitude - altitude)).index
    if meta.kind == "appearance":
        return meta.light if altitude >= 0 else meta.dark
    return 0


def render(heic: Path, index: int, out: Path, width: int, height: int, srgb_profile: str) -> None:
    """Image `index` of heic, converted to sRGB and cropped to fill width x height, as JPEG.

    Most of Apple's pictures are Display P3; wallpaper setters ignore embedded profiles, so
    the colours are converted rather than just relabelled.
    """
    part = out.with_name(out.name + ".part.jpg")
    subprocess.run(
        [
            "magick",
            f"{heic}[{index}]",
            "-intent", "relative",
            "-profile", srgb_profile,
            "-resize", f"{width}x{height}^",
            "-gravity", "center",
            "-extent", f"{width}x{height}",
            "-quality", "92",
            str(part),
        ],
        check=True,
    )
    part.replace(out)
