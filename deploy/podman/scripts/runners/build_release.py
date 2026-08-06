#!/usr/bin/env python3
"""Build release artifacts inside the ioguard build image."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import tarfile
from datetime import UTC, datetime
from pathlib import Path


def run(command: list[str], cwd: Path) -> None:
    subprocess.run(command, cwd=cwd, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path)
    parser.add_argument("--artifacts", type=Path)
    args = parser.parse_args()
    workspace = args.workspace or Path("/workspace")
    artifacts = args.artifacts or Path("/artifacts")
    build = workspace / "build"
    run(
        [
            "meson",
            "setup",
            str(build),
            "--buildtype=release",
            "--strip",
            "--werror",
            "-Db_lto=true",
            "-Db_pie=true",
            "-Db_ndebug=true",
        ],
        workspace,
    )
    run(["meson", "compile", "-C", str(build)], workspace)
    for directory in ("bin", "lib", "share"):
        (artifacts / directory).mkdir(parents=True, exist_ok=True)
    source = build / "src"
    if source.is_dir():
        for path in source.rglob("*"):
            if path.is_file() and path.stat().st_mode & 0o111:
                shutil.copy2(path, artifacts / "bin" / path.name)
            if path.is_file() and ".so" in path.name:
                shutil.copy2(path, artifacts / "lib" / path.name)
    name = f"ioguard-{datetime.now(UTC).strftime('%Y%m%d')}.tar.gz"
    with tarfile.open(artifacts / name, "w:gz") as archive:
        for directory in ("bin", "lib", "share"):
            archive.add(artifacts / directory, arcname=directory)
    print(f"Artifacts: {artifacts}")
    print(f"Archive: {artifacts / name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
