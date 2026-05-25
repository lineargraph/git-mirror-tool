let
  sources = import ./npins;
  pkgs = import sources.nixpkgs { };
  haskell-json-fmt = pkgs.callPackage (sources.haskell-json-fmt { inherit pkgs; }) { };
  treefmtWrapper = (import (sources.treefmt-nix { inherit pkgs; })).mkWrapper (
    pkgs // { inherit haskell-json-fmt; }
  ) ./treefmt.nix;
  python = pkgs.python3.withPackages (pp: [
    pp.requests
    pp.msgspec
  ]);
in
pkgs.mkShell {
  nativeBuildInputs = [
    treefmtWrapper
    pkgs.ruff
    python
  ];
}
