{
  python3,
  stdenvNoCC,
  lib,
}:
let
  pythonEnv = python3.withPackages (import ./requirements.nix);
in
stdenvNoCC.mkDerivation (finalAttrs: {
  __structuredAttrs = true;
  strictDeps = true;
  pname = "git-mirror-tool";
  version = "0.0.0";
  src = ./.;
  installPhase = ''
    mkdir -p $out/bin
    substitute $src/__main__.py $out/bin/git-mirror-tool \
      --replace-fail "#!/usr/bin/env python3" "#!${pythonEnv}/bin/python3"
    chmod +x $out/bin/git-mirror-tool
  '';
  meta = {
    description = "A simple tool for mirroring a list of git repositories";
    license = lib.licenses.mit;
  };
})
