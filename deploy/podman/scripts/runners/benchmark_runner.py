#!/usr/bin/env python3
"""Run the ioguard PoC benchmark from a mounted workspace."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path)
    parser.add_argument("arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    workspace = args.workspace or Path("/workspace")
    script = workspace / "tests" / "poc" / "benchmark.py"
    if not script.is_file():
        raise SystemExit(f"benchmark script not found: {script}")
    return subprocess.run(
        ["uv", "run", "--script", str(script), *args.arguments],
        cwd=workspace,
        check=False,
    ).returncode


if __name__ == "__main__":
    raise SystemExit(main())
