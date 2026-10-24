"""macos-wallpaper: Apple's macOS desktop pictures, dynamic ones included, as plain JPEGs.

  macos-wallpaper list           every picture in Apple's catalogue
  macos-wallpaper current        the image to show now for the current picture
  macos-wallpaper next           switch to another picture and print its image

`current` and `next` print the path of a JPEG rendered for the requested size; for dynamic
pictures it is the one matching the sun's position at the given place. A wallpaper setter
runs `current` every few minutes and shows whatever it prints.

Only the picture in use is kept. Apple ships each picture as one HEIC holding all of its
images, so switching downloads that file (65-140 MB); images are rendered only when the sun
reaches them, a few seconds each.
"""

import argparse
import json
import os
import random
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import catalog, heic, sun


def _default_cache() -> Path:
    base = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
    return Path(base) / "macos-wallpapers"


def _write_json(path: Path, data: dict) -> None:
    part = path.with_name(path.name + ".part")
    part.write_text(json.dumps(data))
    part.replace(path)


class Current:
    """The picture in use: its source HEIC, schedule and the images rendered from it so far."""

    def __init__(self, cache: Path):
        self.directory = cache / "picture"
        self.meta_path = self.directory / "meta.json"
        self.source = self.directory / "source.heic"

    def id(self) -> str | None:
        if not (self.meta_path.exists() and self.source.exists()):
            return None
        return json.loads(self.meta_path.read_text())["id"]

    def metadata(self) -> heic.Metadata:
        return heic.Metadata.from_json(json.loads(self.meta_path.read_text()))

    def replace(self, picture: catalog.Picture) -> None:
        """Download picture in place of the current one."""
        print(f"Downloading {picture.id} ({picture.size / 1e6:.0f} MB)", file=sys.stderr)
        staging = self.directory.with_name(self.directory.name + ".new")
        shutil.rmtree(staging, ignore_errors=True)
        staging.mkdir(parents=True)
        source = catalog.download(picture, staging)
        source.rename(staging / self.source.name)
        meta = heic.read_metadata(staging / self.source.name)
        _write_json(staging / self.meta_path.name, {"id": picture.id, **meta.to_json()})
        shutil.rmtree(self.directory, ignore_errors=True)
        staging.rename(self.directory)

    def image(self, index: int, width: int, height: int, profile: str) -> Path:
        """Image `index`, rendered the first time it's needed. Named after the picture, so the
        path changes on every switch and setters that compare paths notice it."""
        slug = re.sub(r"[^a-z0-9]+", "-", (self.id() or "").lower()).strip("-")
        path = self.directory / f"{slug}-{index}-{width}x{height}.jpg"
        if not path.exists():
            heic.render(self.source, index, path, width, height, profile)
        return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="macos-wallpaper", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["list", "current", "next"])
    parser.add_argument("--picture", action="append", default=[], metavar="NAME", help="picture to choose from (repeatable; default: all)")
    parser.add_argument("--latitude", type=float, help="degrees north, for dynamic pictures")
    parser.add_argument("--longitude", type=float, help="degrees east, for dynamic pictures")
    parser.add_argument("--size", default="3840x2160", help="rendered size, WIDTHxHEIGHT (default: %(default)s)")
    parser.add_argument("--cache-dir", type=Path, default=_default_cache())
    parser.add_argument(
        "--srgb-profile",
        default=os.environ.get("MACOS_WALLPAPERS_SRGB_PROFILE"),
        help="sRGB ICC profile the images are converted to",
    )
    args = parser.parse_args(argv)

    cache: Path = args.cache_dir
    cache.mkdir(parents=True, exist_ok=True)
    pictures = catalog.load(cache)

    if args.command == "list":
        for picture_id in sorted(pictures, key=str.casefold):
            print(picture_id)
        return 0

    if not args.srgb_profile:
        parser.error("--srgb-profile (or MACOS_WALLPAPERS_SRGB_PROFILE) is required")
    width, height = (int(n) for n in args.size.lower().split("x"))

    unknown = [name for name in args.picture if name not in pictures]
    for name in unknown:
        print(f"warning: no picture named {name!r} in Apple's catalogue", file=sys.stderr)
    allowed = [name for name in args.picture if name in pictures] or (sorted(pictures) if not args.picture else [])
    if not allowed:
        parser.error("none of the --picture names are in Apple's catalogue (see `macos-wallpaper list`)")

    current = Current(cache)
    in_use = current.id()
    if args.command == "next" or in_use not in allowed:
        choices = [name for name in allowed if name != in_use] or allowed
        current.replace(pictures[random.choice(choices)])

    meta = current.metadata()
    if meta.kind == "static":
        index = 0
    else:
        if args.latitude is None or args.longitude is None:
            parser.error(f"{current.id()} is dynamic: --latitude and --longitude are required")
        altitude, morning = sun.position(datetime.now(timezone.utc), args.latitude, args.longitude)
        index = heic.choose(meta, altitude, morning)

    print(current.image(index, width, height, args.srgb_profile))
    return 0


if __name__ == "__main__":
    sys.exit(main())
