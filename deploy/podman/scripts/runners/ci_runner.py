#!/usr/bin/env python3
"""Run the complete ioguard CI lane in a mounted workspace."""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

from llvm_coverage import collect, test_environment


def run(
    command: list[str],
    cwd: Path,
    *,
    check: bool = True,
    env: dict[str, str] | None = None,
) -> int:
    return subprocess.run(command, cwd=cwd, check=check, env=env).returncode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path)
    parser.add_argument("--reports", type=Path)
    args = parser.parse_args()
    workspace = args.workspace or Path("/workspace")
    reports = args.reports or workspace / "ci-reports"
    reports.mkdir(parents=True, exist_ok=True)
    run(
        [
            "cmake",
            "--preset",
            "clang-debug",
            "-DBUILD_DOCUMENTATION=OFF",
            "-DUSE_WOLFSSL=ON",
            "-DENABLE_COVERAGE=ON",
        ],
        workspace,
    )
    run(["cmake", "--build", "--preset", "clang-debug", "--parallel"], workspace)
    build = workspace / "build" / "clang-debug"
    test_env = test_environment(build)
    run(
        ["ctest", "--preset", "clang-debug", "--output-on-failure", "--parallel", "4"],
        workspace,
        env=test_env,
    )
    if shutil.which("llvm-profdata"):
        collect(build, reports, workspace)
    elif shutil.which("gcovr"):
        coverage = reports / "coverage.html"
        run(
            [
                "gcovr",
                "--root",
                str(workspace),
                "--object-directory",
                str(build),
                "--html-details",
                str(coverage),
            ],
            workspace,
            check=False,
        )
    cppcheck = shutil.which("cppcheck")
    if cppcheck:
        run(
            [
                cppcheck,
                "--enable=all",
                "--inconclusive",
                "--xml",
                "--xml-version=2",
                "--output-file",
                str(reports / "cppcheck.xml"),
                "src/",
            ],
            workspace,
            check=False,
        )
    print(f"Reports: {reports}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
