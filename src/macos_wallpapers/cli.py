"""macos-wallpaper: Apple's macOS desktop pictures, dynamic ones included, as plain JPEGs.

  macos-wallpaper list           every picture available
  macos-wallpaper current        the image to show now for the picture in use
  macos-wallpaper set NAME       switch to picture NAME and print its image for now
  macos-wallpaper previews       low-res images for now of every --picture, as JSON

Pictures are Apple's desktop pictures (one HEIC each, e.g. "The Lake") and, since macOS
Sonoma, the releases' aerial landscapes (e.g. "Tahoe": one video per time of day, of which the
first frame is used).

`current` and `set` print the path of a JPEG rendered for the requested size; for dynamic
pictures it is the one matching the sun's position at the given place. A wallpaper setter
runs `current` every few minutes and shows whatever it prints. The picture in use stays
until `set` changes it (the first run picks one of the --picture names at random).

Only the picture in use is kept at full size. Switching downloads its HEIC (65-140 MB) or
its videos' first frames (a few MB each); images are rendered only when the sun reaches
them, a few seconds each.

`previews` is for a wallpaper picker: it keeps a 960x540 copy of every image of every
--picture (downloading each picture once to make them) and prints
{"current": NAME, "pictures": [{"id": NAME, "image": PATH}, ...]}, with each picture's
image for now.
"""

import argparse
import json
import os
import random
import re
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from . import aerial, catalog, heic, sun

PREVIEW_SIZE = (960, 540)


def _default_cache() -> Path:
    base = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
    return Path(base) / "macos-wallpapers"


def _slug(picture_id: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", picture_id.lower()).strip("-")


def _write_json(path: Path, data: dict) -> None:
    part = path.with_name(path.name + ".part")
    part.write_text(json.dumps(data))
    part.replace(path)


def fetch(picture: catalog.Picture, directory: Path, apple_ca: str | None) -> heic.Metadata:
    """Download picture's images into directory (source.heic, or frame-<i>.png for an aerial
    place) and return its schedule."""
    if picture.frames:
        print(f"Downloading {picture.id} ({len(picture.frames)} aerial frames)", file=sys.stderr)
        aerial.grab_frames(picture, directory, apple_ca)
        return aerial.metadata(picture)
    print(f"Downloading {picture.id} ({picture.size / 1e6:.0f} MB)", file=sys.stderr)
    source = catalog.download(picture, directory).rename(directory / "source.heic")
    return heic.read_metadata(source)


def source(directory: Path, index: int) -> str:
    """What to render image `index` from, as fetch() left it in directory."""
    frame = directory / f"frame-{index}.png"
    return str(frame) if frame.exists() else f"{directory / 'source.heic'}[{index}]"


class Current:
    """The picture in use: its source images, schedule and the images rendered from it so far."""

    def __init__(self, cache: Path):
        self.directory = cache / "picture"
        self.meta_path = self.directory / "meta.json"

    def id(self) -> str | None:
        if not self.meta_path.exists():
            return None
        return json.loads(self.meta_path.read_text())["id"]

    def metadata(self) -> heic.Metadata:
        return heic.Metadata.from_json(json.loads(self.meta_path.read_text()))

    def replace(self, picture: catalog.Picture, apple_ca: str | None) -> None:
        """Download picture in place of the current one."""
        staging = self.directory.with_name(self.directory.name + ".new")
        shutil.rmtree(staging, ignore_errors=True)
        staging.mkdir(parents=True)
        meta = fetch(picture, staging, apple_ca)
        _write_json(staging / self.meta_path.name, {"id": picture.id, **meta.to_json()})
        shutil.rmtree(self.directory, ignore_errors=True)
        staging.rename(self.directory)

    def image(self, index: int, width: int, height: int, profile: str) -> Path:
        """Image `index`, rendered the first time it's needed. Named after the picture, so the
        path changes on every switch and setters that compare paths notice it."""
        path = self.directory / f"{_slug(self.id() or '')}-{index}-{width}x{height}.jpg"
        if not path.exists():
            heic.render(source(self.directory, index), path, width, height, profile)
        return path


def previews(picture: catalog.Picture, cache: Path, current: Current, profile: str, apple_ca: str | None) -> tuple[Path, heic.Metadata]:
    """Low-res copies of every image of picture, made once (from the picture in use if it's
    this one, otherwise from a download that's discarded afterwards)."""
    directory = cache / "previews" / _slug(picture.id)
    meta_path = directory / "meta.json"
    width, height = PREVIEW_SIZE

    def image(index: int) -> Path:
        return directory / f"{index}.jpg"

    if meta_path.exists():
        meta = heic.Metadata.from_json(json.loads(meta_path.read_text()))
        if all(image(i).exists() for i in meta.indices()):
            return directory, meta

    directory.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=cache) as tmp:
        if current.id() == picture.id:
            sources, meta = current.directory, current.metadata()
        else:
            sources = Path(tmp)
            meta = fetch(picture, sources, apple_ca)
        for index in sorted(meta.indices()):
            heic.render(source(sources, index), image(index), width, height, profile)
    _write_json(meta_path, meta.to_json())
    return directory, meta


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="macos-wallpaper", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["list", "current", "set", "previews"])
    parser.add_argument("name", nargs="?", help="picture for `set`")
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
    parser.add_argument(
        "--apple-ca",
        default=os.environ.get("MACOS_WALLPAPERS_APPLE_CA"),
        help="Apple Root CA (PEM), for the aerial places' videos; without it only desktop pictures are offered",
    )
    args = parser.parse_args(argv)
    if (args.command == "set") != (args.name is not None):
        parser.error("NAME is required for `set` and only for `set`")

    cache: Path = args.cache_dir
    cache.mkdir(parents=True, exist_ok=True)
    pictures = catalog.load(cache)
    if args.apple_ca:
        try:
            pictures.update(aerial.load(cache, args.apple_ca))
        except (OSError, ValueError, KeyError) as e:
            print(f"warning: aerial places unavailable: {e}", file=sys.stderr)

    if args.command == "list":
        for picture_id in sorted(pictures, key=str.casefold):
            print(picture_id)
        return 0

    if not args.srgb_profile:
        parser.error("--srgb-profile (or MACOS_WALLPAPERS_SRGB_PROFILE) is required")
    width, height = (int(n) for n in args.size.lower().split("x"))

    def index_for_now(meta: heic.Metadata, picture_id: str) -> int:
        if meta.kind == "static":
            return 0
        if args.latitude is None or args.longitude is None:
            parser.error(f"{picture_id} is dynamic: --latitude and --longitude are required")
        altitude, morning = sun.position(datetime.now(timezone.utc), args.latitude, args.longitude)
        return heic.choose(meta, altitude, morning)

    current = Current(cache)

    if args.command == "set":
        if args.name not in pictures:
            parser.error(f"no picture named {args.name!r} (see `macos-wallpaper list`)")
        if current.id() != args.name:
            current.replace(pictures[args.name], args.apple_ca)
        print(current.image(index_for_now(current.metadata(), args.name), width, height, args.srgb_profile))
        return 0

    unknown = [name for name in args.picture if name not in pictures]
    for name in unknown:
        print(f"warning: no picture named {name!r}", file=sys.stderr)
    allowed = [name for name in args.picture if name in pictures] or (sorted(pictures) if not args.picture else [])
    if not allowed:
        parser.error("none of the --picture names exist (see `macos-wallpaper list`)")

    if args.command == "previews":
        entries = []
        for name in allowed:
            directory, meta = previews(pictures[name], cache, current, args.srgb_profile, args.apple_ca)
            entries.append({"id": name, "image": str(directory / f"{index_for_now(meta, name)}.jpg")})
        print(json.dumps({"current": current.id(), "pictures": entries}))
        return 0

    # current: the picture in use stays until `set` changes it; the first run picks one.
    in_use = current.id()
    if in_use is None:
        current.replace(pictures[random.choice(allowed)], args.apple_ca)
    print(current.image(index_for_now(current.metadata(), current.id()), width, height, args.srgb_profile))
    return 0


if __name__ == "__main__":
    sys.exit(main())
