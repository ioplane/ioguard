#!/usr/bin/env python3
"""Run the fast ioguard build and smoke-test lane."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path)
    args = parser.parse_args()
    workspace = args.workspace or Path("/workspace")
    build = workspace / "build-quick"
    subprocess.run(
        ["meson", "setup", str(build), "--buildtype=debug"], cwd=workspace, check=True
    )
    subprocess.run(["meson", "compile", "-C", str(build)], cwd=workspace, check=True)
    return subprocess.run(
        ["meson", "test", "-C", str(build), "--suite=smoke", "--timeout-multiplier=1"],
        cwd=workspace,
        check=False,
    ).returncode


if __name__ == "__main__":
    raise SystemExit(main())
