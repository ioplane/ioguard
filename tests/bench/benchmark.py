#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14,<3.15"
# dependencies = []
# ///
"""Benchmark one ioguard TLS backend against the local PoC server."""

from __future__ import annotations

import argparse
import atexit
import json
import os
import socket
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path


SERVER_HOST = "127.0.0.1"


class Benchmark:
    def __init__(
        self, backend: str, output: Path, port: int, iterations: int, warmup: int
    ) -> None:
        self.root = Path(__file__).resolve().parents[2]
        self.backend = backend
        self.output = output
        self.port = port
        self.iterations = iterations
        self.warmup = warmup
        self.certificate_dir = self.root / "tests" / "bench" / "certs"
        self.server: subprocess.Popen[bytes] | None = None
        self.server_log = self.root / "server.log"
        atexit.register(self.stop_server)

    def command(self, name: str) -> Path:
        return self.root / f"poc-{name}-{self.backend}"

    def client(
        self, *arguments: str, capture: bool = False
    ) -> subprocess.CompletedProcess[str]:
        command = [
            str(self.command("client")),
            "--backend",
            self.backend,
            "--host",
            SERVER_HOST,
            "--port",
            str(self.port),
            *arguments,
        ]
        return subprocess.run(
            command,
            cwd=self.root,
            check=False,
            text=True,
            stdout=subprocess.PIPE if capture else subprocess.DEVNULL,
            stderr=subprocess.PIPE if capture else subprocess.DEVNULL,
            timeout=5,
        )

    def prerequisites(self) -> None:
        for binary in (self.command("server"), self.command("client")):
            if not binary.is_file():
                raise SystemExit(f"binary not found: {binary}; run make poc-both")
        if (
            not (self.certificate_dir / "server-cert.pem").is_file()
            or not (self.certificate_dir / "server-key.pem").is_file()
        ):
            raise SystemExit(
                f"server certificates not found in {self.certificate_dir}; run generate_certs.py"
            )
        with socket.socket() as probe:
            if probe.connect_ex((SERVER_HOST, self.port)) == 0:
                raise SystemExit(f"port {self.port} is already in use")
        print("Prerequisites check passed")

    def generate_certificates(self) -> None:
        if (self.certificate_dir / "server-cert.pem").is_file():
            return
        subprocess.run(
            [
                "uv",
                "run",
                "--script",
                str(Path(__file__).with_name("generate_certs.py")),
            ],
            cwd=self.root,
            check=True,
        )

    def start_server(self) -> None:
        print(f"Starting TLS server (backend: {self.backend})...")
        log = self.server_log.open("wb")
        self.server = subprocess.Popen(
            [
                str(self.command("server")),
                "--backend",
                self.backend,
                "--port",
                str(self.port),
                "--cert",
                str(self.certificate_dir / "server-cert.pem"),
                "--key",
                str(self.certificate_dir / "server-key.pem"),
            ],
            cwd=self.root,
            stdout=log,
            stderr=subprocess.STDOUT,
            env={
                **os.environ,
                "LD_LIBRARY_PATH": f"/usr/local/lib:{os.environ.get('LD_LIBRARY_PATH', '')}",
            },
        )
        log.close()
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            with socket.socket() as probe:
                if probe.connect_ex((SERVER_HOST, self.port)) == 0:
                    print(f"Server started (PID: {self.server.pid})")
                    return
            time.sleep(0.5)
        log_text = (
            self.server_log.read_text(encoding="utf-8", errors="replace")
            if self.server_log.exists()
            else ""
        )
        raise SystemExit(f"server failed to start\n{log_text}")

    def stop_server(self) -> None:
        if self.server is not None and self.server.poll() is None:
            self.server.terminate()
            try:
                self.server.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.server.kill()
                self.server.wait()
        self.server = None
        self.server_log.unlink(missing_ok=True)

    def warmup_run(self) -> None:
        for _ in range(self.warmup):
            try:
                self.client("--iterations", "1", "--size", "1024")
            except subprocess.TimeoutExpired:
                pass

    def handshake_rate(self) -> dict[str, float | int]:
        start = time.perf_counter()
        successes = 0
        for index in range(1, self.iterations + 1):
            try:
                if self.client("--iterations", "1", "--size", "64").returncode == 0:
                    successes += 1
            except subprocess.TimeoutExpired:
                pass
            if index % 100 == 0:
                print(f"Progress: {index}/{self.iterations}")
        elapsed = time.perf_counter() - start
        return {
            "handshake_rate": successes / elapsed if elapsed else 0.0,
            "total_handshakes": successes,
            "elapsed_seconds": elapsed,
        }

    def throughput(self) -> dict[str, object]:
        result = self.client(
            "--iterations", str(self.iterations), "--json", capture=True
        )
        if result.returncode != 0:
            raise SystemExit(f"throughput benchmark failed: {result.stderr}")
        data = json.loads(result.stdout)
        return data if isinstance(data, dict) else {}

    def process_value(self, field: str) -> float:
        if self.server is None:
            return 0.0
        result = subprocess.run(
            ["ps", "-p", str(self.server.pid), "-o", f"{field}="],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        try:
            return float(result.stdout.strip())
        except ValueError:
            return 0.0

    def resources(self) -> tuple[dict[str, float], dict[str, float]]:
        cpu_before = self.process_value("%cpu")
        try:
            self.client("--iterations", "100", "--size", "65536")
        except subprocess.TimeoutExpired:
            pass
        cpu_after = self.process_value("%cpu")
        memory_kb = self.process_value("rss")
        return {"cpu_before": cpu_before, "cpu_after": cpu_after}, {
            "memory_rss_kb": memory_kb,
            "memory_rss_mb": memory_kb / 1024,
        }

    def latency(self) -> dict[str, float]:
        values: list[float] = []
        for index in range(1, self.iterations + 1):
            start = time.perf_counter()
            try:
                if self.client("--iterations", "1", "--size", "1024").returncode == 0:
                    values.append((time.perf_counter() - start) * 1000)
            except subprocess.TimeoutExpired:
                pass
            if index % 100 == 0:
                print(f"Progress: {index}/{self.iterations}")
        if not values:
            return {"p50_ms": 0.0, "p95_ms": 0.0, "p99_ms": 0.0, "avg_ms": 0.0}
        values.sort()

        def percentile(fraction: float) -> float:
            return values[min(len(values) - 1, max(0, int(len(values) * fraction) - 1))]

        return {
            "p50_ms": percentile(0.50),
            "p95_ms": percentile(0.95),
            "p99_ms": percentile(0.99),
            "avg_ms": sum(values) / len(values),
        }

    def run(self) -> int:
        self.prerequisites()
        self.generate_certificates()
        self.start_server()
        self.warmup_run()
        cpu, memory = self.resources()
        result = {
            "backend": self.backend,
            "timestamp": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "config": {
                "iterations": self.iterations,
                "warmup_iterations": self.warmup,
                "server_port": self.port,
            },
            "handshake": self.handshake_rate(),
            "throughput": self.throughput(),
            "cpu": cpu,
            "memory": memory,
            "latency": self.latency(),
        }
        self.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(f"Benchmark complete; results saved to {self.output}")
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "backend", choices=("gnutls", "wolfssl"), nargs="?", default="gnutls"
    )
    parser.add_argument("output", type=Path, nargs="?")
    parser.add_argument("--port", type=int, default=4433)
    parser.add_argument("--iterations", type=int, default=1000)
    parser.add_argument("--warmup", type=int, default=100)
    args = parser.parse_args()
    if args.iterations < 1 or args.warmup < 0:
        raise SystemExit("iterations must be positive and warmup must be non-negative")
    output = args.output or Path(f"benchmark_{args.backend}.json")
    return Benchmark(
        args.backend, output, args.port, args.iterations, args.warmup
    ).run()


if __name__ == "__main__":
    raise SystemExit(main())
