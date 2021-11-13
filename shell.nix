with import <nixpkgs> {};
let
  myipfshttpclient = python38.pkgs.buildPythonPackage rec {
    pname = "ipfshttpclient";
    version = "0.8.0a2";

    src = pkgs.python38.pkgs.fetchPypi {
      inherit pname version;
      sha256 = "0d80e95ee60b02c7d414e79bf81a36fc3c8fbab74265475c52f70b2620812135";
    };

    doCheck = false;
    propagatedBuildInputs = [
      pkgs.python38Packages.py-multiaddr
      pkgs.python38Packages.requests
    ];
  };
  eth-keyfile = python38.pkgs.buildPythonPackage rec {
    pname = "eth-keyfile";
    version = "0.5.1";

    src = pkgs.python38.pkgs.fetchPypi {
      inherit pname version;
      sha256 = "939540efb503380bc30d926833e6a12b22c6750de80feef3720d79e5a79de47d";
    };

    doCheck = false;
    propagatedBuildInputs = [
      setuptools-markdown
      eth-keys
    ];
  };
  setuptools-markdown = python38.pkgs.buildPythonPackage rec {
    pname = "setuptools-markdown";
    version = "0.4.1";

    src = pkgs.python38.pkgs.fetchPypi {
      inherit pname version;
      sha256 = "e8da0784a730eb8aa8f686d34e0f5c02bb236ae4d7f07ee36006f103b24f0c29";
    };

    doCheck = false;
    propagatedBuildInputs = [
      pkgs.python38Packages.pypandoc
    ];
  };
  eth-keys = python38.pkgs.buildPythonPackage rec {
    pname = "eth-keys";
    version = "0.3.3";

    src = pkgs.python38.pkgs.fetchPypi {
      inherit pname version;
      sha256 = "a9a1e83e443bd369265b1a1b66dc30f6841bdbb3577ecd042e037b7b405b6cb0";
    };

    doCheck = false;
    propagatedBuildInputs = [
      setuptools-markdown
      pkgs.python38Packages.eth-typing
      pkgs.python38Packages.eth-utils
    ];
  };
  mybitarray = python38.pkgs.buildPythonPackage rec {
    pname = "bitarray";
    version = "1.2.2";

    src = pkgs.python38.pkgs.fetchPypi {
      inherit pname version;
      sha256 = "27a69ffcee3b868abab3ce8b17c69e02b63e722d4d64ffd91d659f81e9984954";
    };

    doCheck = false;
  };
  eth-rlp = python38.pkgs.buildPythonPackage rec {
    pname = "eth-rlp";
    version = "0.2.1";

    src = pkgs.python38.pkgs.fetchPypi {
      inherit pname version;
      sha256 = "f016f980b0ed42ee7650ba6e4e4d3c4e9aa06d8b9c6825a36d3afe5aa0187a8b";
    };

    doCheck = false;
    propagatedBuildInputs = [
      hexbytes
      pkgs.python38Packages.eth-utils
      pkgs.python38Packages.rlp
    ];
  };
  eth-account = python38.pkgs.buildPythonPackage rec {
    pname = "eth-account";
    version = "0.5.6";

    src = pkgs.python38.pkgs.fetchPypi {
      inherit pname version;
      sha256 = "baef80956e88af5643f8602e72aab6bcd91d8a9f71dd03c7a7f1145f5e6fd694";
    };

    doCheck = false;
    propagatedBuildInputs = [
      hexbytes
      eth-abi
      eth-rlp
      eth-keys
      eth-keyfile
      mybitarray
      pkgs.python38Packages.rlp
    ];
  };
  eth-abi = python38.pkgs.buildPythonPackage rec {
    pname = "eth_abi";
    version = "2.1.1";

    src = pkgs.python38.pkgs.fetchPypi {
      inherit pname version;
      sha256 = "4bb1d87bb6605823379b07f6c02c8af45df01a27cc85bd6abb7cf1446ce7d188";
    };

    doCheck = false;
    propagatedBuildInputs = [
      pkgs.python38Packages.parsimonious
      pkgs.python38Packages.eth-utils
      pkgs.python38Packages.eth-typing
    ];
  };
  mywebsockets = python38.pkgs.buildPythonPackage rec {
    pname = "websockets";
    version = "9.1";

    src = pkgs.python38.pkgs.fetchPypi {
      inherit pname version;
      sha256 = "276d2339ebf0df4f45df453923ebd2270b87900eda5dfd4a6b0cfa15f82111c3";
    };

    doCheck = false;
  };

  lru-dict = python38.pkgs.buildPythonPackage rec {
    pname = "lru-dict";
    version = "1.1.7";

    src = pkgs.python38.pkgs.fetchPypi {
      inherit pname version;
      sha256 = "45b81f67d75341d4433abade799a47e9c42a9e22a118531dcb5e549864032d7c";
    };

    doCheck = false;
  };

  hexbytes = python38.pkgs.buildPythonPackage rec {
    pname = "hexbytes";
    version = "0.2.2";

    src = pkgs.python38.pkgs.fetchPypi {
      inherit pname version;
      sha256 = "a5881304d186e87578fb263a85317c808cf130e1d4b3d37d30142ab0f7898d03";
    };

    doCheck = false;
  };

  web3 = python38.pkgs.buildPythonPackage rec {
    pname = "web3";
    version = "5.24.0";

    src = pkgs.python38.pkgs.fetchPypi {
      inherit pname version;
      sha256 = "6535618b07a8d3d7496374a3b7714cfade4f94e6dc085a518718d4c6f776ac3f";
    };

    doCheck = false;

    propagatedBuildInputs = [
      hexbytes
      lru-dict
      mywebsockets
      eth-abi
      eth-account
      myipfshttpclient
      pkgs.python38Packages.eth-hash
      pkgs.python38Packages.protobuf
      pkgs.python38Packages.aiohttp
      pkgs.python38Packages.jsonschema
      pkgs.python38Packages.eth-typing
      pkgs.python38Packages.requests
    ];
  };
  pythonPackages = ps:
    with ps; [
      setuptools

      # Linting
      black
      pylint

      pandas
      web3
    ];
in mkShell rec {
  venvDir = "./.venv";
  buildInputs = [
    python

    # Linting + development
    nodePackages.pyright
    hello
    bashInteractive

    # Python development
    (python38.withPackages pythonPackages)
    pipreqs
  ];
}
