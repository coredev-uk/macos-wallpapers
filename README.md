# macos-wallpapers

Apple's macOS desktop pictures, including the dynamic ones that follow the sun, as plain
JPEGs for any wallpaper setter.

macOS downloads most of its desktop pictures on demand from Apple's MobileAsset catalogue
(`mesu.apple.com`). `macos-wallpaper` reads the same catalogue, downloads a picture (verified
against the catalogue's SHA-1), and renders its images once, converted from Display P3 to
sRGB and cropped to your screen size.

Since Sonoma, each release's own landscapes are aerial videos instead, one per time of day
(Tahoe Morning, Tahoe Night, ...); macOS shows a video's first frame on the desktop. The tool
reads the aerial manifest of the newest macOS release and turns every place with a video for
each time of day into a dynamic picture made of those first frames.

## Kinds of picture

| Kind | Examples | Shows |
| --- | --- | --- |
| Dynamic | The Lake, The Desert, The Beach, The Cliffs, Big Sur, Catalina, Monterey Graphic, Ventura Graphic, Solar Gradients | One of 5-16 images, by where the sun is |
| Aerial place | Golden Gate (macOS 27), Tahoe (26), Sequoia (15) | One of 3-4 video frames (sunrise, morning, day, sunset, evening, night), by where the sun is |
| Light/dark | Sonoma, Dome, Peak, Valley, Tree, Iridescence, Chroma Blue | Light while the sun is up, dark after sunset |
| Static | Catalina Rock, Big Sur Coastline, iMac Blue, ... | One image |

The default graphic wallpapers of Monterey, Ventura, Sequoia and Tahoe ship inside macOS and
aren't in either catalogue, so they aren't available.

Dynamic pictures are not on a clock: each image is tagged with a sun altitude and azimuth
(`apple_desktop:solar` in the HEIC's XMP; aerial frames get the same from their time of day).
Those positions are idealised (mornings at azimuth 70-110, evenings at 250-290), so the tool
takes the half of the day from the time of solar noon and picks the image with the closest
altitude, favouring that half. The sun's position comes from NOAA's solar equations for your
latitude and longitude.

## Usage

```sh
macos-wallpaper list                       # every picture name in the catalogue
macos-wallpaper current --latitude 51.5 --longitude -0.13 \
  --picture "The Lake" --picture "The Desert"
macos-wallpaper set "The Desert" ...       # switch to a picture
macos-wallpaper previews ...               # low-res images for now of every --picture, as JSON
```

`current` and `set` print the path of the JPEG to show now. Run `current` every few
minutes (e.g. a systemd timer) and pass the result to your wallpaper setter. The picture
in use stays until `set` changes it; the very first run picks one of the `--picture` names.

Only the picture in use is kept at full size. `set` downloads the picture's HEIC (65-140 MB
for a dynamic one) or its videos' first frames (a few MB each), about 4 s either way, and
renders just the image for now; the others are rendered, a few seconds each, when the sun
reaches them.

`previews` is for a wallpaper picker. It keeps a 960x540 copy of every image of every
`--picture` (about 200 KB each; each picture is downloaded once to make them) and prints
`{"current": NAME, "pictures": [{"id": NAME, "image": PATH}, ...]}` with each picture's
image for now.

| Option | Default |
| --- | --- |
| `--picture NAME` (repeatable) | every picture available |
| `--latitude`, `--longitude` | required for dynamic pictures |
| `--size WIDTHxHEIGHT` | `3840x2160` |
| `--cache-dir` | `$XDG_CACHE_HOME/macos-wallpapers` |

## Nix

```nix
inputs.macos-wallpapers.url = "github:coredev-uk/macos-wallpapers";
# ...
home.packages = [ inputs.macos-wallpapers.packages.${pkgs.system}.default ];
```

The package brings ImageMagick (with libheif), ffmpeg, an sRGB profile and Apple's root CA
(the aerial videos' server chains to it). Elsewhere it needs Python 3.11+, ImageMagick 7 with
HEIC support, ffmpeg, `--srgb-profile` pointing at an sRGB ICC profile and `--apple-ca` at
Apple's root CA; without the CA only desktop pictures are offered.

## Development

```sh
nix develop
pytest
```
