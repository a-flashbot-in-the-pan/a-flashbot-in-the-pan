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
    pythonPackages.pandas

    pipreqs
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
