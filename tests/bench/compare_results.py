#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14,<3.15"
# dependencies = []
# ///
"""Compare GnuTLS and wolfSSL benchmark JSON reports."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def value(data: dict[str, Any], *path: str, default: float = 0.0) -> float:
    current: Any = data
    for key in path:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
    return float(current) if isinstance(current, int | float) else default


def delta(baseline: float, candidate: float) -> float:
    return ((candidate - baseline) / baseline) * 100 if baseline else 0.0


def metric_rows(
    gnutls: dict[str, Any], wolfssl: dict[str, Any]
) -> list[tuple[str, float, float, float, bool]]:
    return [
        (
            "Handshake rate",
            value(gnutls, "handshake", "handshake_rate"),
            value(wolfssl, "handshake", "handshake_rate"),
            delta(
                value(gnutls, "handshake", "handshake_rate"),
                value(wolfssl, "handshake", "handshake_rate"),
            ),
            True,
        ),
        (
            "Latency p95",
            value(gnutls, "latency", "p95_ms"),
            value(wolfssl, "latency", "p95_ms"),
            delta(
                value(gnutls, "latency", "p95_ms"), value(wolfssl, "latency", "p95_ms")
            ),
            False,
        ),
        (
            "Latency p99",
            value(gnutls, "latency", "p99_ms"),
            value(wolfssl, "latency", "p99_ms"),
            delta(
                value(gnutls, "latency", "p99_ms"), value(wolfssl, "latency", "p99_ms")
            ),
            False,
        ),
        (
            "Throughput",
            value(gnutls, "throughput", "tests", default=0.0),
            value(wolfssl, "throughput", "tests", default=0.0),
            0.0,
            True,
        ),
        (
            "Memory RSS",
            value(gnutls, "memory", "memory_rss_mb"),
            value(wolfssl, "memory", "memory_rss_mb"),
            delta(
                value(gnutls, "memory", "memory_rss_mb"),
                value(wolfssl, "memory", "memory_rss_mb"),
            ),
            False,
        ),
    ]


def throughput_value(data: dict[str, Any]) -> float:
    tests = data.get("throughput", {}).get("tests", [])
    if isinstance(tests, list) and len(tests) > 5 and isinstance(tests[5], dict):
        raw = tests[5].get("throughput_mbps", 0.0)
        return float(raw) if isinstance(raw, int | float) else 0.0
    return 0.0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("gnutls_file", type=Path)
    parser.add_argument("wolfssl_file", type=Path)
    parser.add_argument("--output", type=Path, default=Path("comparison.md"))
    parser.add_argument("--threshold", type=float, default=10.0)
    args = parser.parse_args()
    if not args.gnutls_file.is_file() or not args.wolfssl_file.is_file():
        raise SystemExit("both benchmark JSON files must exist")
    gnutls = json.loads(args.gnutls_file.read_text(encoding="utf-8"))
    wolfssl = json.loads(args.wolfssl_file.read_text(encoding="utf-8"))
    if not isinstance(gnutls, dict) or not isinstance(wolfssl, dict):
        raise SystemExit("benchmark JSON roots must be objects")
    handshake_base = value(gnutls, "handshake", "handshake_rate")
    handshake_candidate = value(wolfssl, "handshake", "handshake_rate")
    latency_p95_base = value(gnutls, "latency", "p95_ms")
    latency_p95_candidate = value(wolfssl, "latency", "p95_ms")
    latency_p99_base = value(gnutls, "latency", "p99_ms")
    latency_p99_candidate = value(wolfssl, "latency", "p99_ms")
    throughput_base = throughput_value(gnutls)
    throughput_candidate = throughput_value(wolfssl)
    memory_base = value(gnutls, "memory", "memory_rss_mb")
    memory_candidate = value(wolfssl, "memory", "memory_rss_mb")
    metrics = [
        (
            "Handshake rate",
            handshake_base,
            handshake_candidate,
            delta(handshake_base, handshake_candidate),
            True,
        ),
        (
            "Latency p95",
            latency_p95_base,
            latency_p95_candidate,
            delta(latency_p95_base, latency_p95_candidate),
            False,
        ),
        (
            "Latency p99",
            latency_p99_base,
            latency_p99_candidate,
            delta(latency_p99_base, latency_p99_candidate),
            False,
        ),
        (
            "Throughput (64KB)",
            throughput_base,
            throughput_candidate,
            delta(throughput_base, throughput_candidate),
            True,
        ),
        (
            "Memory RSS",
            memory_base,
            memory_candidate,
            delta(memory_base, memory_candidate),
            False,
        ),
    ]
    regressions = [
        (name, difference)
        for name, _, _, difference, higher_is_better in metrics
        if abs(difference) > args.threshold
        and (
            (higher_is_better and difference < 0)
            or (not higher_is_better and difference > 0)
        )
    ]
    decision = "NO-GO" if regressions else "GO"
    report = [
        "# TLS Backend Performance Comparison",
        "",
        f"**Generated**: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}",
        "",
        "**Baseline**: GnuTLS  ",
        "**Candidate**: wolfSSL",
        "",
        f"## Decision: **{decision}**",
        "",
        f"Regression threshold: {args.threshold:.2f}%",
        "",
        "| Metric | GnuTLS | wolfSSL | Difference |",
        "|---|---:|---:|---:|",
    ]
    report.extend(
        f"| {name} | {baseline:.3f} | {candidate:.3f} | {difference:+.2f}% |"
        for name, baseline, candidate, difference, _ in metrics
    )
    report.extend(
        [
            "",
            "## Raw Data",
            "",
            "### GnuTLS Results",
            "",
            "```json",
            json.dumps(gnutls, indent=2),
            "```",
            "",
            "### wolfSSL Results",
            "",
            "```json",
            json.dumps(wolfssl, indent=2),
            "```",
            "",
        ]
    )
    if regressions:
        report.extend(
            [
                "## Reasons for NO-GO",
                "",
                *[
                    f"- {name}: {difference:+.2f}% exceeds the threshold"
                    for name, difference in regressions
                ],
                "",
            ]
        )
    else:
        report.extend(["All key metrics are within the configured threshold.", ""])
    args.output.write_text("\n".join(report), encoding="utf-8")
    print(f"Decision: {decision}")
    print(f"Full report: {args.output}")
    return 1 if regressions else 0


if __name__ == "__main__":
    raise SystemExit(main())
