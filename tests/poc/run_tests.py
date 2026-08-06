#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14,<3.15"
# dependencies = []
# ///
"""Run the four GnuTLS/wolfSSL PoC server/client compatibility tests."""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path


BACKENDS = ("gnutls", "wolfssl")


@dataclass(frozen=True)
class TestCase:
    name: str
    server_backend: str
    client_backend: str


CASES = (
    TestCase("GnuTLS-to-GnuTLS", "gnutls", "gnutls"),
    TestCase("wolfSSL-to-wolfSSL", "wolfssl", "wolfssl"),
    TestCase("GnuTLS-server-wolfSSL-client", "gnutls", "wolfssl"),
    TestCase("wolfSSL-server-GnuTLS-client", "wolfssl", "gnutls"),
)


def project_root() -> Path:
    workspace = Path("/workspace")
    return (
        workspace
        if (workspace / "Makefile").is_file()
        else Path(__file__).resolve().parents[2]
    )


def binary(root: Path, role: str, backend: str) -> Path:
    return root / f"poc-{role}-{backend}"


def build_if_requested(root: Path, build: bool) -> None:
    if not build:
        return
    subprocess.run(["make", "poc-both"], cwd=root, check=True)


def wait_for_server(host: str, port: int, timeout: float = 10.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with socket.socket() as probe:
            probe.settimeout(0.5)
            if probe.connect_ex((host, port)) == 0:
                return True
        time.sleep(0.5)
    return False


def stop_server(server: subprocess.Popen[bytes]) -> None:
    if server.poll() is not None:
        return
    server.terminate()
    try:
        server.wait(timeout=2)
    except subprocess.TimeoutExpired:
        server.kill()
        server.wait()


def run_case(
    root: Path,
    logs: Path,
    case: TestCase,
    host: str,
    port: int,
    iterations: int,
    certificate: Path,
    key: Path,
) -> bool:
    prefix = f"{case.server_backend}_{case.client_backend}"
    server_log = logs / f"server_{prefix}.log"
    client_log = logs / f"client_{prefix}.log"
    client_json = logs / f"client_{prefix}.json"
    server_command = [
        str(binary(root, "server", case.server_backend)),
        "--backend",
        case.server_backend,
        "--port",
        str(port),
        "--cert",
        str(certificate),
        "--key",
        str(key),
        "--verbose",
    ]
    client_command = [
        str(binary(root, "client", case.client_backend)),
        "--backend",
        case.client_backend,
        "--host",
        host,
        "--port",
        str(port),
        "--iterations",
        str(iterations),
        "--verbose",
    ]
    environment = {
        **os.environ,
        "LD_LIBRARY_PATH": f"/usr/local/lib:/usr/local/lib64:{os.environ.get('LD_LIBRARY_PATH', '')}",
    }
    print(
        f"[INFO] {case.name}: server={case.server_backend}, client={case.client_backend}"
    )
    with server_log.open("wb") as stream:
        server = subprocess.Popen(
            server_command,
            cwd=root,
            env=environment,
            stdout=stream,
            stderr=subprocess.STDOUT,
        )
    try:
        if not wait_for_server(host, port):
            print(f"[FAIL] {case.name}: server startup timeout")
            return False
        with client_log.open("w", encoding="utf-8") as stream:
            client_result = subprocess.run(
                client_command,
                cwd=root,
                env=environment,
                check=False,
                text=True,
                stdout=stream,
                stderr=subprocess.STDOUT,
            )
        json_result = subprocess.run(
            [*client_command[:-1], "--json"],
            cwd=root,
            env=environment,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        client_json.write_text(json_result.stdout, encoding="utf-8")
        if client_result.returncode != 0:
            print(f"[FAIL] {case.name}: client returned {client_result.returncode}")
            print(f"       logs: {server_log}, {client_log}")
            return False
        try:
            report = json.loads(json_result.stdout)
        except json.JSONDecodeError:
            report = None
        if isinstance(report, dict):
            print(
                f"[PASS] {case.name}: handshake={report.get('handshake_time_ms', 'n/a')} ms"
            )
        else:
            print(f"[PASS] {case.name}")
        return True
    finally:
        stop_server(server)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=4433)
    parser.add_argument("--iterations", type=int, default=10)
    parser.add_argument("--log-dir", type=Path)
    parser.add_argument(
        "--build", action="store_true", help="build both PoC variants before testing"
    )
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        raise SystemExit("port must be between 1 and 65535")
    if args.iterations < 1:
        raise SystemExit("iterations must be positive")
    root = args.project_root or project_root()
    logs = args.log_dir or root / "tests" / "poc" / "logs"
    certificate_dir = root / "tests" / "certs"
    certificate = certificate_dir / "server-cert.pem"
    key = certificate_dir / "server-key.pem"
    logs.mkdir(parents=True, exist_ok=True)
    build_if_requested(root, args.build)
    missing = [
        path
        for backend in BACKENDS
        for path in (binary(root, "server", backend), binary(root, "client", backend))
        if not path.is_file()
    ]
    if missing:
        raise SystemExit("PoC binaries not found; run `make poc-both` or pass --build")
    if not certificate.is_file() or not key.is_file():
        raise SystemExit(
            f"certificates not found in {certificate_dir}; run generate_certs.py"
        )

    passed = sum(
        run_case(
            root,
            logs,
            case,
            args.host,
            args.port,
            args.iterations,
            certificate,
            key,
        )
        for case in CASES
    )
    print(f"Test summary: {passed}/{len(CASES)} passed; logs: {logs}")
    return 0 if passed == len(CASES) else 1


if __name__ == "__main__":
    raise SystemExit(main())
