{
  lib,
  python3Packages,
  imagemagick,
  ffmpeg-headless,
  cacert,
  colord,
  openssl,
  fetchurl,
  runCommand,
}:
let
  # Just the profile, so the package doesn't depend on all of colord.
  srgbProfile = runCommand "srgb.icc" { } ''
    cp ${colord}/share/color/icc/colord/sRGB.icc $out
  '';

  # sylvan.apple.com, which serves the aerial videos, chains to Apple's own root CA rather than
  # one in the system bundle. Pinned by hash, so the download can't be swapped.
  appleRootCa =
    runCommand "apple-root-ca.pem"
      {
        nativeBuildInputs = [ openssl ];
        der = fetchurl {
          url = "https://www.apple.com/appleca/AppleIncRootCertificate.cer";
          hash = "sha256-sLFzDsvH/0UFFCxJ8Slebtpryu1+LGjFvpG1oRAB8CQ=";
        };
      }
      ''
        openssl x509 -inform der -in "$der" -out "$out"
      '';
in
python3Packages.buildPythonApplication {
  pname = "macos-wallpapers";
  version = "0.1.0";
  pyproject = true;

  src = lib.fileset.toSource {
    root = ./.;
    fileset = lib.fileset.unions [
      ./pyproject.toml
      ./README.md
      ./src
      ./tests
    ];
  };

  build-system = [ python3Packages.setuptools ];
  nativeCheckInputs = [ python3Packages.pytestCheckHook ];

  makeWrapperArgs = [
    # ImageMagick decodes the HEICs (through libheif) and converts their colours; ffmpeg grabs
    # the aerial videos' first frames.
    "--prefix"
    "PATH"
    ":"
    (lib.makeBinPath [
      imagemagick
      ffmpeg-headless
    ])
    "--set-default"
    "MACOS_WALLPAPERS_SRGB_PROFILE"
    "${srgbProfile}"
    "--set-default"
    "MACOS_WALLPAPERS_APPLE_CA"
    "${appleRootCa}"
    "--set-default"
    "SSL_CERT_FILE"
    "${cacert}/etc/ssl/certs/ca-bundle.crt"
  ];

  meta = {
    description = "Apple's macOS desktop pictures, dynamic ones included, for any desktop";
    homepage = "https://github.com/coredev-uk/macos-wallpapers";
    mainProgram = "macos-wallpaper";
    platforms = lib.platforms.linux;
  };
}
