#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14,<3.15"
# dependencies = []
# ///
"""Run the shared ioplane Clang coverage pipeline for ioguard."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    preset = os.environ.get("PRESET", "clang-coverage")
    build_dir = Path(os.environ.get("BUILD_DIR", root / "build" / preset))
    command = [
        "ioplane-build",
        "coverage",
        "--root",
        str(root),
        "--toolchain",
        "clang",
        "--clang-preset",
        preset,
        "--clang-build-dir",
        str(build_dir),
        "--clang-report-dir",
        str(build_dir / "coverage-report"),
        "--profile-dir",
        str(build_dir / "profraw"),
        "--ignore-regex",
        r"tests/|unity",
    ]
    return subprocess.run(command, cwd=root, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
