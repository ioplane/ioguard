#!/usr/bin/env python3
"""Run the fast ioguard CMake build and CTest lane."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path)
    args = parser.parse_args()
    workspace = args.workspace or Path("/workspace")
    subprocess.run(
        [
            "cmake",
            "--preset",
            "clang-debug",
            "-DBUILD_DOCUMENTATION=OFF",
            "-DUSE_WOLFSSL=ON",
        ],
        cwd=workspace,
        check=True,
    )
    subprocess.run(
        ["cmake", "--build", "--preset", "clang-debug", "--parallel"],
        cwd=workspace,
        check=True,
    )
    return subprocess.run(
        ["ctest", "--preset", "clang-debug", "--output-on-failure", "--parallel", "4"],
        cwd=workspace,
        check=False,
    ).returncode


if __name__ == "__main__":
    raise SystemExit(main())
