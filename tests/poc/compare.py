#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14,<3.15"
# dependencies = []
# ///
"""Compare the latest GnuTLS and wolfSSL PoC benchmark reports."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def latest(results_dir: Path, backend: str) -> Path:
    files = sorted(
        results_dir.glob(f"results_{backend}_*.json"),
        key=lambda path: path.stat().st_mtime,
    )
    if not files:
        raise SystemExit(f"No {backend} results found in {results_dir}")
    return files[-1]


def percent(baseline: float, candidate: float) -> float:
    return ((candidate - baseline) / baseline) * 100 if baseline else 0.0


def number(data: dict[str, Any], key: str) -> float:
    value = data.get(key, 0.0)
    return float(value) if isinstance(value, int | float) else 0.0


def print_report(label: str, data: dict[str, Any]) -> None:
    print(f"--- {label} Results ---")
    print(f"Backend: {data.get('backend', 'unknown')}")
    print(f"Handshake time: {number(data, 'handshake_time_ms'):.3f} ms\n")
    print(f"{'Size':<15} {'Iterations':<12} {'Throughput':<15} {'Latency':<15}")
    print(f"{'(bytes)':<15} {'':12} {'(MB/s)':<15} {'(ms)':<15}")
    print("-" * 60)
    tests = data.get("tests", [])
    if not isinstance(tests, list):
        return
    for test in tests:
        if not isinstance(test, dict):
            continue
        print(
            f"{test.get('size', 0):<15} {test.get('iterations', 0):<12} "
            f"{number(test, 'throughput_mbps'):<15.2f} {number(test, 'latency_ms'):<15.3f}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results_dir", type=Path)
    args = parser.parse_args()
    if not args.results_dir.is_dir():
        raise SystemExit(f"Results directory not found: {args.results_dir}")
    gnutls_file = latest(args.results_dir, "gnutls")
    wolfssl_file = latest(args.results_dir, "wolfssl")
    gnutls = json.loads(gnutls_file.read_text(encoding="utf-8"))
    wolfssl = json.loads(wolfssl_file.read_text(encoding="utf-8"))
    if not isinstance(gnutls, dict) or not isinstance(wolfssl, dict):
        raise SystemExit("benchmark JSON roots must be objects")
    print("=== TLS Performance Comparison ===\n")
    print(f"GnuTLS results: {gnutls_file.name}")
    print(f"wolfSSL results: {wolfssl_file.name}\n")
    print_report("GnuTLS", gnutls)
    print()
    print_report("wolfSSL", wolfssl)
    print("\n--- Performance Comparison ---")
    handshake_delta = percent(
        number(gnutls, "handshake_time_ms"), number(wolfssl, "handshake_time_ms")
    )
    print(
        f"Handshake Time: GnuTLS {number(gnutls, 'handshake_time_ms'):.3f} ms; wolfSSL {number(wolfssl, 'handshake_time_ms'):.3f} ms; Delta {handshake_delta:+.2f}%"
    )
    gnutls_tests = gnutls.get("tests", [])
    wolfssl_tests = wolfssl.get("tests", [])
    if not isinstance(gnutls_tests, list) or not isinstance(wolfssl_tests, list):
        gnutls_tests, wolfssl_tests = [], []
    print(f"{'Size':<15} {'Metric':<15} {'GnuTLS':<15} {'wolfSSL':<15} {'Delta':<15}")
    print("-" * 75)
    throughput_deltas: list[float] = []
    latency_deltas: list[float] = []
    for gnutls_test, wolfssl_test in zip(gnutls_tests, wolfssl_tests, strict=False):
        if not isinstance(gnutls_test, dict) or not isinstance(wolfssl_test, dict):
            continue
        size = gnutls_test.get("size", 0)
        gnutls_throughput = number(gnutls_test, "throughput_mbps")
        wolfssl_throughput = number(wolfssl_test, "throughput_mbps")
        gnutls_latency = number(gnutls_test, "latency_ms")
        wolfssl_latency = number(wolfssl_test, "latency_ms")
        throughput_delta = percent(gnutls_throughput, wolfssl_throughput)
        latency_delta = percent(gnutls_latency, wolfssl_latency)
        throughput_deltas.append(throughput_delta)
        latency_deltas.append(latency_delta)
        print(
            f"{size:<15} {'Throughput':<15} {gnutls_throughput:<15.2f} {wolfssl_throughput:<15.2f} {throughput_delta:+14.2f}%"
        )
        print(
            f"{'':<15} {'Latency':<15} {gnutls_latency:<15.3f} {wolfssl_latency:<15.3f} {latency_delta:+14.2f}%\n"
        )
    average_throughput = (
        sum(throughput_deltas) / len(throughput_deltas) if throughput_deltas else 0.0
    )
    average_latency = (
        sum(latency_deltas) / len(latency_deltas) if latency_deltas else 0.0
    )
    print(
        f"Average Performance Delta: Handshake {handshake_delta:+.2f}%; Throughput {average_throughput:+.2f}%; Latency {average_latency:+.2f}%"
    )
    threshold = 10.0
    regressions = (
        abs(handshake_delta) > threshold
        or abs(average_throughput) > threshold
        or abs(average_latency) > threshold
    )
    verdict = "NO-GO" if regressions else "GO"
    print(f"\nGO/NO-GO Decision Criteria: Performance within ±{threshold:.0f}%")
    print(f"VERDICT: {verdict}")
    return 1 if regressions else 0


if __name__ == "__main__":
    raise SystemExit(main())
