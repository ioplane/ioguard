#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14,<3.15"
# dependencies = []
# ///
"""Build and run one ioguard LibFuzzer target with a temporary corpus."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

TARGETS = ("cstp", "http", "ipc", "session_key", "toml")


def run(command: list[str], *, root: Path) -> None:
    subprocess.run(command, cwd=root, check=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", choices=TARGETS)
    parser.add_argument(
        "--runs",
        type=int,
        default=int(os.environ.get("RUNS", "256")),
        help="LibFuzzer run budget (default: RUNS or 256)",
    )
    parser.add_argument(
        "--preset",
        default=os.environ.get("PRESET", "clang-fuzz"),
        help="CMake preset (default: PRESET or clang-fuzz)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.runs < 1:
        raise SystemExit("--runs must be positive")
    root = Path(__file__).resolve().parents[1]
    build_dir = root / "build" / args.preset
    corpus_dir = root / "tests" / "fuzz" / "corpus" / args.target
    executable = build_dir / f"fuzz_{args.target}"

    print(f"=== Building fuzz target: {args.target} ===")
    run(["cmake", "--preset", args.preset], root=root)
    run(
        [
            "cmake",
            "--build",
            "--preset",
            args.preset,
            "--target",
            f"fuzz_{args.target}",
            "-j",
            str(os.cpu_count() or 1),
        ],
        root=root,
    )
    if not executable.is_file():
        raise SystemExit(f"fuzz executable not found: {executable}")

    with tempfile.TemporaryDirectory(prefix="ioguard-fuzz-") as temporary:
        temporary_corpus = Path(temporary)
        if corpus_dir.is_dir():
            for source in corpus_dir.iterdir():
                if source.is_file():
                    shutil.copy2(source, temporary_corpus / source.name)
        print(f"=== Running {args.target} fuzzer ({args.runs} runs) ===")
        run(
            [
                str(executable),
                str(temporary_corpus),
                f"-runs={args.runs}",
                "-max_len=65536",
            ],
            root=root,
        )
    print(f"=== PASSED: {args.target} ({args.runs} runs, no crashes) ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
