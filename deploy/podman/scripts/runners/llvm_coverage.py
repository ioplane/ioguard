"""Collect LLVM source coverage for Clang-instrumented CMake builds."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


def test_environment(build: Path) -> dict[str, str]:
    environment = os.environ.copy()
    environment["LLVM_PROFILE_FILE"] = str(build / "%m.profraw")
    return environment


def collect(build: Path, reports: Path, workspace: Path) -> None:
    profiles = sorted(build.glob("*.profraw"))
    if (
        not profiles
        or not shutil.which("llvm-profdata")
        or not shutil.which("llvm-cov")
    ):
        return
    reports.mkdir(parents=True, exist_ok=True)
    profile = reports / "coverage.profdata"
    subprocess.run(
        [
            "llvm-profdata",
            "merge",
            "-sparse",
            *(str(path) for path in profiles),
            "-o",
            str(profile),
        ],
        cwd=workspace,
        check=False,
    )
    binaries = sorted(
        path
        for path in build.iterdir()
        if path.is_file() and path.stat().st_mode & 0o111
    )
    if not binaries or not profile.is_file():
        return
    objects = [argument for path in binaries for argument in ("-object", str(path))]
    subprocess.run(
        [
            "llvm-cov",
            "show",
            str(binaries[0]),
            "-instr-profile",
            str(profile),
            "-format=html",
            "-output-dir",
            str(reports / "coverage-html"),
            *objects,
        ],
        cwd=workspace,
        check=False,
    )
    subprocess.run(
        [
            "llvm-cov",
            "report",
            str(binaries[0]),
            "-instr-profile",
            str(profile),
            *objects,
        ],
        cwd=workspace,
        check=False,
    )
