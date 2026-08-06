#!/usr/bin/env python3
"""Run formatting and static-analysis checks for ioguard."""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path)
    args = parser.parse_args()
    workspace = args.workspace or Path("/workspace")
    failures = 0
    formatter = shutil.which("clang-format")
    if formatter:
        for path in sorted(
            (
                *workspace.glob("src/**/*.c"),
                *workspace.glob("src/**/*.h"),
                *workspace.glob("tests/**/*.c"),
                *workspace.glob("tests/**/*.h"),
            )
        ):
            result = subprocess.run(
                [formatter, "--dry-run", "--Werror", str(path)],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            failures += result.returncode != 0
    cppcheck = shutil.which("cppcheck")
    if cppcheck:
        result = subprocess.run(
            [
                cppcheck,
                "--enable=warning,style,performance,portability",
                "--error-exitcode=1",
                "--inline-suppr",
                "src/",
                "tests/",
            ],
            cwd=workspace,
            check=False,
        )
        failures += result.returncode != 0
    return int(failures > 0)


if __name__ == "__main__":
    raise SystemExit(main())
