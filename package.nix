{
  lib,
  python3Packages,
  imagemagick,
  cacert,
  colord,
  runCommand,
}:
let
  # Just the profile, so the package doesn't depend on all of colord.
  srgbProfile = runCommand "srgb.icc" { } ''
    cp ${colord}/share/color/icc/colord/sRGB.icc $out
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
    # ImageMagick decodes the HEICs (through libheif) and converts their colours.
    "--prefix"
    "PATH"
    ":"
    (lib.makeBinPath [ imagemagick ])
    "--set-default"
    "MACOS_WALLPAPERS_SRGB_PROFILE"
    "${srgbProfile}"
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
