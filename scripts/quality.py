#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14,<3.15"
# dependencies = []
# ///
"""Run the shared ioplane Python quality pipeline for ioguard."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    command = [
        "ioplane-build",
        "quality",
        "--root",
        str(root),
        "--preset",
        os.environ.get("PRESET", "clang-debug"),
        "--build-dir",
        os.environ.get("BUILD_DIR", str(root / "build" / "clang-debug")),
    ]
    return subprocess.run(command, cwd=root, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
