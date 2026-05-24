{ pkgs, ... }:
{
  projectRootFile = "treefmt.nix";
  imports = [ ];
  programs.nixfmt.enable = true;
  settings.formatter.haskell-json-fmt = {
    command = "${pkgs.haskell-json-fmt}/bin/haskell-json-fmt";
    options = [ "-i" ];
    includes = [ "*.json" ];
    excludes = [ "npins/*" ];
  };
  # programs.ruff-check.enable = true;
  programs.ruff-format.enable = true;
}
