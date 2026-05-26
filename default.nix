{
  openssh,
  git,
  python3,
  stdenvNoCC,
  lib,
  makeBinaryWrapper,
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
    wrapProgram $out/bin/git-mirror-tool \
      --prefix PATH : ${
        lib.makeBinPath [
          openssh
          git
        ]
      }
  '';
  nativeBuildInputs = [ makeBinaryWrapper ];
  meta = {
    description = "A simple tool for mirroring a list of git repositories";
    license = lib.licenses.mit;
    mainProgram = "git-mirror-tool";
  };
})
