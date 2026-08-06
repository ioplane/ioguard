#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14,<3.15"
# dependencies = []
# ///
"""Run the reusable TLS benchmark for one or both PoC backends."""

from __future__ import annotations

import argparse
import subprocess
from datetime import datetime
from pathlib import Path


BACKENDS = ("gnutls", "wolfssl")


def run_backend(
    benchmark_script: Path,
    backend: str,
    output: Path,
    cert_dir: Path,
    port: int,
    iterations: int,
    warmup: int,
) -> bool:
    command = [
        "uv",
        "run",
        "--script",
        str(benchmark_script),
        backend,
        str(output),
        "--port",
        str(port),
        "--iterations",
        str(iterations),
        "--warmup",
        str(warmup),
        "--cert-dir",
        str(cert_dir),
    ]
    print(f"=== Testing backend: {backend} ===")
    result = subprocess.run(command, check=False)
    if result.returncode != 0:
        print(f"[FAIL] Benchmark failed for {backend}")
        return False
    print(f"[PASS] Results saved to {output}")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-b", "--backend", choices=BACKENDS, action="append")
    parser.add_argument("-n", "--iterations", type=int, default=1000)
    parser.add_argument("-w", "--warmup", type=int, default=10)
    parser.add_argument("-p", "--port", type=int, default=4433)
    parser.add_argument("-o", "--output", type=Path)
    parser.add_argument("--cert-dir", type=Path)
    args = parser.parse_args()
    if args.iterations < 1 or args.warmup < 0:
        raise SystemExit("iterations must be positive and warmup must be non-negative")
    if not 1 <= args.port <= 65535:
        raise SystemExit("port must be between 1 and 65535")

    script_dir = Path(__file__).resolve().parent
    root = script_dir.parents[1]
    output_dir = args.output or script_dir / "results"
    cert_dir = args.cert_dir or root / "tests" / "certs"
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    benchmark_script = root / "tests" / "bench" / "benchmark.py"
    backends = tuple(args.backend or BACKENDS)

    print("=== TLS Performance Benchmark ===")
    print(f"Iterations: {args.iterations}")
    print(f"Port: {args.port}")
    print(f"Backends: {' '.join(backends)}")
    print(f"Output directory: {output_dir}")
    print(f"Certificate directory: {cert_dir}")

    passed = 0
    for backend in backends:
        output = output_dir / f"results_{backend}_{timestamp}.json"
        if run_backend(
            benchmark_script,
            backend,
            output,
            cert_dir,
            args.port,
            args.iterations,
            args.warmup,
        ):
            passed += 1
    print(f"Benchmark complete: {passed}/{len(backends)} backends passed")
    print(
        f"Compare results with: uv run --script {script_dir / 'compare.py'} {output_dir}"
    )
    return 0 if passed == len(backends) else 1


if __name__ == "__main__":
    raise SystemExit(main())
