#!/usr/bin/env python3
"""Run the complete ioguard CI lane in a mounted workspace."""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path


def run(command: list[str], cwd: Path, *, check: bool = True) -> int:
    return subprocess.run(command, cwd=cwd, check=check).returncode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path)
    parser.add_argument("--reports", type=Path)
    args = parser.parse_args()
    workspace = args.workspace or Path("/workspace")
    reports = args.reports or workspace / "ci-reports"
    build = workspace / "build"
    reports.mkdir(parents=True, exist_ok=True)
    run(
        [
            "meson",
            "setup",
            str(build),
            "--buildtype=release",
            "--werror",
            "-Db_coverage=true",
            "-Db_lto=true",
        ],
        workspace,
    )
    run(["meson", "compile", "-C", str(build)], workspace)
    run(
        [
            "meson",
            "test",
            "-C",
            str(build),
            "--verbose",
            "--timeout-multiplier=2",
            "--print-errorlogs",
        ],
        workspace,
    )
    run(["ninja", "-C", str(build), "coverage-html"], workspace, check=False)
    coverage = build / "meson-logs" / "coveragereport"
    if coverage.is_dir():
        shutil.copytree(coverage, reports / coverage.name, dirs_exist_ok=True)
    cppcheck = shutil.which("cppcheck")
    if cppcheck:
        run(
            [
                cppcheck,
                "--enable=all",
                "--inconclusive",
                "--xml",
                "--xml-version=2",
                "src/",
            ],
            workspace,
            check=False,
        )
    print(f"Reports: {reports}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
