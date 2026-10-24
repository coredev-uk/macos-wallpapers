"""Apple's desktop-picture catalogue and the archives it points at.

macOS downloads most of its desktop pictures on demand through MobileAsset; the catalogue
lists each one with a zip archive (a single HEIC inside) and the archive's SHA-1.
"""

import hashlib
import os
import plistlib
import shutil
import time
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path

CATALOG_URL = (
    "https://mesu.apple.com/assets/macos/com_apple_MobileAsset_DesktopPicture/"
    "com_apple_MobileAsset_DesktopPicture.xml"
)
CATALOG_MAX_AGE = 7 * 24 * 3600

# Retry every failure (DNS, refused, timeout) for about a minute: at login the network may
# still be coming up.
RETRIES = 6
RETRY_DELAY = 10
TIMEOUT = 30


@dataclass(frozen=True)
class Picture:
    id: str
    url: str
    sha1: bytes
    size: int


def _fetch(url: str, dest: Path) -> None:
    """Download url to dest, atomically."""
    part = dest.with_name(dest.name + ".part")
    for attempt in range(RETRIES):
        try:
            with urllib.request.urlopen(url, timeout=TIMEOUT) as response, open(part, "wb") as out:
                shutil.copyfileobj(response, out, 1 << 20)
            part.replace(dest)
            return
        except (urllib.error.URLError, OSError):
            part.unlink(missing_ok=True)
            if attempt == RETRIES - 1:
                raise
            time.sleep(RETRY_DELAY)


def load(cache: Path) -> dict[str, Picture]:
    """The catalogue by picture ID, refreshed once it's a week old.

    A failed refresh falls back to the cached copy; only a first run without one fails.
    """
    path = cache / "catalog.xml"
    stale = not path.exists() or time.time() - path.stat().st_mtime > CATALOG_MAX_AGE
    if stale:
        try:
            _fetch(CATALOG_URL, path)
        except (urllib.error.URLError, OSError):
            if not path.exists():
                raise

    with open(path, "rb") as f:
        assets = plistlib.load(f)["Assets"]
    return {
        a["DesktopPictureID"]: Picture(
            id=a["DesktopPictureID"],
            url=a["__BaseURL"] + a["__RelativePath"],
            sha1=a["_Measurement"],
            size=a["_DownloadSize"],
        )
        for a in assets
    }


def download(picture: Picture, workdir: Path) -> Path:
    """Download and verify picture's archive into workdir; returns the extracted HEIC."""
    archive = workdir / "picture.zip"
    _fetch(picture.url, archive)

    digest = hashlib.sha1()
    with open(archive, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    if digest.digest() != picture.sha1:
        archive.unlink()
        raise ValueError(f"{picture.id}: archive does not match the catalogue's SHA-1")

    with zipfile.ZipFile(archive) as z:
        member = next(n for n in z.namelist() if n.lower().endswith(".heic") and "/._" not in n)
        heic = workdir / "picture.heic"
        with z.open(member) as src, open(heic, "wb") as out:
            shutil.copyfileobj(src, out, 1 << 20)
    os.remove(archive)
    return heic
