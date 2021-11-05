with import <nixpkgs> {};

let
  pythonPackages = python38Packages;
in mkShell rec {
  venvDir = "./.venv";
  buildInputs = [
    # Python
    pythonPackages.python

    # This execute some shell code to initialize a venv in $venvDir before
    # dropping into the shell
    pythonPackages.venvShellHook
    # Linting + development
    nodePackages.pyright
    bashInteractive
  ];

  # Run this command, only after creating the virtual environment
  postVenvCreation = ''
    unset SOURCE_DATE_EPOCH
    for requirements_file in requirements*.txt; do
      pip install -r $requirements_file
    done
  '';

  postShellHook = ''
    # allow pip to install wheels
    unset SOURCE_DATE_EPOCH
  '';

}
# let

  #pkgs = import sources.nixpkgs { };
  #inherit (pkgs.lib) optional optionals;

  # inherit (pkgs.lib) optional optionals;

  # web3 = pkgs.python39.pkgs.buildPythonPackage rec {
  #   pname = "web3";
  #   version = "5.20.0";

  #   src = pkgs.fetchPypi {
  #     inherit pname version;
  #     sha256 = "0000000000000000000000000000000000000000000000000000";
  #     #sha256 = "1nrmn6jx93glbb6gsx333n0rp7d2x8dpw5shp97y5yv147ff1y6h";
  #     #url = "https://github.com/ramonhagenaars/typish/archive/refs/tags/v1.9.1.tar.gz";
  #   };

  #   doCheck = false;

  #   meta = {
  #     homepage = "https://pypi.org/project/web3";
  #     description = "A Python library for interacting with Ethereum";
  #   };
  # };

#   pythonPackages = ps:

#     with ps; [
#       # Linting
#       #black
#       #pylint
#       virtualenvwrapper

#       # libs
#       #web3
#     ];
# in
# pkgs.mkShell {
#   buildInputs = [
#     pkgs.hello
#     pkgs.black

#     # keep this line if you use bash
#     pkgs.bashInteractive

#     (pkgs.python39.withPackages pythonPackages)
#   ];
# }
