#!/usr/bin/env python3
"""Run ioguard tests and collect coverage artifacts."""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path)
    parser.add_argument("--coverage-reports", type=Path)
    args = parser.parse_args()
    workspace = args.workspace or Path("/workspace")
    reports = args.coverage_reports or workspace / "coverage-reports"
    build = workspace / "build"
    if not build.is_dir():
        raise SystemExit(f"build directory not found: {build}")
    subprocess.run(
        [
            "meson",
            "test",
            "-C",
            str(build),
            "--verbose",
            "--timeout-multiplier=2",
            "--print-errorlogs",
        ],
        cwd=workspace,
        check=True,
    )
    coverage = build / "meson-logs" / "coveragereport"
    if coverage.is_dir():
        reports.mkdir(parents=True, exist_ok=True)
        target = reports / coverage.name
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(coverage, target)
    integration = workspace / "tests" / "integration"
    if integration.is_dir():
        print(
            f"Integration tests are available at {integration}; run their native test target"
        )
    print(f"Test results: {workspace / 'test-results'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
