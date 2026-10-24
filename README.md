# macos-wallpapers

Apple's macOS desktop pictures, including the dynamic ones that follow the sun, as plain
JPEGs for any wallpaper setter.

macOS downloads most of its desktop pictures on demand from Apple's MobileAsset catalogue
(`mesu.apple.com`). `macos-wallpaper` reads the same catalogue, downloads a picture (verified
against the catalogue's SHA-1), and renders its images once, converted from Display P3 to
sRGB and cropped to your screen size.

## Kinds of picture

| Kind | Examples | Shows |
| --- | --- | --- |
| Dynamic | The Lake, The Desert, The Beach, The Cliffs, Big Sur, Catalina, Monterey Graphic, Ventura Graphic, Solar Gradients | One of 5-16 images, by where the sun is |
| Light/dark | Sonoma, Dome, Peak, Valley, Tree, Iridescence, Chroma Blue | Light while the sun is up, dark after sunset |
| Static | Catalina Rock, Big Sur Coastline, iMac Blue, ... | One image |

Dynamic pictures are not on a clock: each image is tagged with a sun altitude and azimuth
(`apple_desktop:solar` in the HEIC's XMP). Those positions are idealised (mornings at
azimuth 70-110, evenings at 250-290), so the tool takes the half of the day from the time
of solar noon and picks the image with the closest altitude. The sun's position comes from
NOAA's solar equations for your latitude and longitude.

## Usage

```sh
macos-wallpaper list                       # every picture name in the catalogue
macos-wallpaper current --latitude 51.5 --longitude -0.13 \
  --picture "The Lake" --picture "The Desert"
macos-wallpaper next ...                   # switch to another of the --picture names
macos-wallpaper prefetch ...               # download and render them all ahead of time
```

`current` and `next` print the path of the JPEG to show now. Run `current` every few
minutes (e.g. a systemd timer) and pass the result to your wallpaper setter. A picture's
first use downloads and renders it (~20 s for a dynamic one); run `prefetch` in the
background (e.g. at login) so switching never waits. The picture in use is remembered
between runs.

| Option | Default |
| --- | --- |
| `--picture NAME` (repeatable) | every picture in the catalogue (`prefetch` needs names) |
| `--latitude`, `--longitude` | required for dynamic pictures |
| `--size WIDTHxHEIGHT` | `3840x2160` |
| `--cache-dir` | `$XDG_CACHE_HOME/macos-wallpapers` |

## Nix

```nix
inputs.macos-wallpapers.url = "github:coredev-uk/macos-wallpapers";
# ...
home.packages = [ inputs.macos-wallpapers.packages.${pkgs.system}.default ];
```

The package brings ImageMagick (with libheif) and an sRGB profile. Elsewhere it needs
Python 3.11+, ImageMagick 7 with HEIC support, and `--srgb-profile` pointing at an sRGB ICC
profile.

## Development

```sh
nix develop
pytest
```
