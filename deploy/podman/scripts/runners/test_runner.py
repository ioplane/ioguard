#!/usr/bin/env python3
"""Run ioguard tests and collect coverage artifacts."""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

from llvm_coverage import collect, test_environment


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path)
    parser.add_argument("--coverage-reports", type=Path)
    args = parser.parse_args()
    workspace = args.workspace or Path("/workspace")
    reports = args.coverage_reports or workspace / "coverage-reports"
    subprocess.run(
        [
            "cmake",
            "--preset",
            "clang-debug",
            "-DBUILD_DOCUMENTATION=OFF",
            "-DENABLE_COVERAGE=ON",
        ],
        cwd=workspace,
        check=True,
    )
    subprocess.run(
        ["cmake", "--build", "--preset", "clang-debug", "--parallel"],
        cwd=workspace,
        check=True,
    )
    build = workspace / "build" / "clang-debug"
    subprocess.run(
        ["ctest", "--preset", "clang-debug", "--output-on-failure", "--parallel", "4"],
        cwd=workspace,
        check=True,
        env=test_environment(build),
    )
    reports.mkdir(parents=True, exist_ok=True)
    if shutil.which("llvm-profdata"):
        collect(build, reports, workspace)
    elif shutil.which("gcovr"):
        coverage = reports / "coverage.html"
        subprocess.run(
            [
                "gcovr",
                "--root",
                str(workspace),
                "--object-directory",
                str(build),
                "--html-details",
                str(coverage),
            ],
            cwd=workspace,
            check=False,
        )
    integration = workspace / "tests" / "integration"
    if integration.is_dir():
        print(
            f"Integration tests are available at {integration}; run their native test target"
        )
    print(f"Test results: {workspace / 'test-results'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
