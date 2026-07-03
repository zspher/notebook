{
  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";

    pyproject-nix = {
      url = "github:pyproject-nix/pyproject.nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    uv2nix = {
      url = "github:pyproject-nix/uv2nix";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    pyproject-build-systems = {
      url = "github:pyproject-nix/build-system-pkgs";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.uv2nix.follows = "uv2nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs =
    {
      nixpkgs,
      pyproject-nix,
      uv2nix,
      pyproject-build-systems,
      ...
    }:
    let
      inherit (nixpkgs) lib;
      perSystem = lib.genAttrs [
        "x86_64-linux"
        "aarch64-linux"
        "x86_64-darwin"
        "aarch64-darwin"
      ];

      workspace = uv2nix.lib.workspace.loadWorkspace { workspaceRoot = ./.; };

      overlay = workspace.mkPyprojectOverlay {
        sourcePreference = "wheel";
      };

      editableOverlay = workspace.mkEditablePyprojectOverlay {
        root = "$REPO_ROOT";
      };

      pythonSets = perSystem (
        system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
          python = pkgs.python3;
          hacks = pkgs.callPackage pyproject-nix.build.hacks { };
          baseSet = pkgs.callPackage pyproject-nix.build.packages {
            inherit python;
          };
        in
        baseSet.overrideScope (
          lib.composeManyExtensions [
            pyproject-build-systems.overlays.wheel
            overlay
            (final: prev: {
              ratelimit = hacks.nixpkgsPrebuilt {
                from = pkgs.python3Packages.ratelimit;
                prev = prev.ratelimit;
              };
            })
          ]
        )
      );

    in
    {
      devShells = perSystem (
        system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
          pythonSet = pythonSets.${system}.overrideScope editableOverlay;
          pythonEnv = pythonSet.mkVirtualEnv "dev-env" workspace.deps.all;
        in
        {
          default = pkgs.mkShellNoCC {
            packages = with pkgs; [
              pythonEnv
              uv
              sqlite
            ];
            env = {
              UV_NO_SYNC = "1";
              UV_PYTHON = pythonSet.python.interpreter;
              UV_PYTHON_DOWNLOADS = "never";
              UV_PROJECT_ENVIRONMENT = pythonEnv; # prevent creating .venv
            };
            shellHook = ''
              unset PYTHONPATH
              export REPO_ROOT=$(git rev-parse --show-toplevel)
              ln -s ${pythonEnv} .venv
            '';
            venv = pythonEnv;
          };
        }
      );

      packages = perSystem (system: {
        default = pythonSets.${system}.mkVirtualEnv "scripts-env" workspace.deps.default;
      });
    };
}
