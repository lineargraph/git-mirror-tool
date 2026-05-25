let
  sources = import ./npins;
in
{
  pkgs ? import sources.nixpkgs { },
}:
let
  haskell-json-fmt = pkgs.callPackage (sources.haskell-json-fmt { inherit pkgs; }) { };
  treefmtWrapper = (import (sources.treefmt-nix { inherit pkgs; })).mkWrapper (
    pkgs // { inherit haskell-json-fmt; }
  ) ./treefmt.nix;
  python = pkgs.python3.withPackages (import ./requirements.nix);
  shell = pkgs.mkShell {
    nativeBuildInputs = [
      treefmtWrapper
      pkgs.ruff
      pkgs.ty
      python
    ];
  };
  git-mirror-tool = pkgs.callPackage ./default.nix { };
in
{
  inherit
    python
    shell
    git-mirror-tool
    ;
}
