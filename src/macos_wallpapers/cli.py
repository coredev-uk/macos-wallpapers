"""macos-wallpaper: Apple's macOS desktop pictures, dynamic ones included, as plain JPEGs.

  macos-wallpaper list           every picture in Apple's catalogue
  macos-wallpaper current        the image to show now for the current picture
  macos-wallpaper next           switch to another picture and print its image
  macos-wallpaper prefetch       download and render every --picture ahead of time

`current` and `next` print the path of a JPEG rendered for the requested size; for dynamic
pictures it is the one matching the sun's position at the given place. A wallpaper setter
runs `current` every few minutes and shows whatever it prints. A picture's first use
downloads and renders it (~20 s); `prefetch` does that in advance so switching is instant.
"""

import argparse
import json
import os
import random
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from . import catalog, heic, sun


def _default_cache() -> Path:
    base = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
    return Path(base) / "macos-wallpapers"


def _slug(picture_id: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", picture_id.lower()).strip("-")


def _write_json(path: Path, data: dict) -> None:
    part = path.with_name(path.name + ".part")
    part.write_text(json.dumps(data))
    part.replace(path)


def _image(directory: Path, index: int, width: int, height: int) -> Path:
    return directory / f"{index}-{width}x{height}.jpg"


def prepare(picture: catalog.Picture, cache: Path, width: int, height: int, profile: str) -> tuple[Path, heic.Metadata]:
    """Download and render every image of picture once; later calls reuse the renders."""
    directory = cache / "pictures" / _slug(picture.id)
    meta_path = directory / "meta.json"
    if meta_path.exists():
        meta = heic.Metadata.from_json(json.loads(meta_path.read_text()))
        if all(_image(directory, i, width, height).exists() for i in meta.indices()):
            return directory, meta

    print(f"Downloading {picture.id} ({picture.size / 1e6:.0f} MB)", file=sys.stderr)
    directory.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=cache) as tmp:
        source = catalog.download(picture, Path(tmp))
        meta = heic.read_metadata(source)
        for index in sorted(meta.indices()):
            heic.render(source, index, _image(directory, index, width, height), width, height, profile)
    _write_json(meta_path, meta.to_json())
    return directory, meta


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="macos-wallpaper", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["list", "current", "next", "prefetch"])
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
    if args.command == "prefetch":
        # Explicit names only: all of Apple's pictures would be ~2.4 GB to download.
        if not args.picture:
            parser.error("prefetch needs the --picture names to prepare")
        for name in allowed:
            prepare(pictures[name], cache, width, height, args.srgb_profile)
        return 0

    state_path = cache / "state.json"
    state = json.loads(state_path.read_text()) if state_path.exists() else {}
    current = state.get("current")
    if args.command == "next" or current not in allowed:
        choices = [name for name in allowed if name != current] or allowed
        current = random.choice(choices)

    directory, meta = prepare(pictures[current], cache, width, height, args.srgb_profile)
    if meta.kind == "static":
        index = 0
    else:
        if args.latitude is None or args.longitude is None:
            parser.error(f"{current} is dynamic: --latitude and --longitude are required")
        altitude, morning = sun.position(datetime.now(timezone.utc), args.latitude, args.longitude)
        index = heic.choose(meta, altitude, morning)

    _write_json(state_path, {"current": current})
    print(_image(directory, index, width, height))
    return 0


if __name__ == "__main__":
    sys.exit(main())
