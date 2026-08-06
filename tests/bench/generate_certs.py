#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14,<3.15"
# dependencies = []
# ///
"""Generate the benchmark CA and localhost server certificates."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


def run(command: list[str]) -> None:
    subprocess.run(
        command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cert-dir",
        type=Path,
        default=Path(__file__).resolve().parent / "certs",
    )
    args = parser.parse_args()
    cert_dir = args.cert_dir
    cert_dir.mkdir(parents=True, exist_ok=True)
    ca_key = cert_dir / "ca-key.pem"
    ca_cert = cert_dir / "ca-cert.pem"
    server_key = cert_dir / "server-key.pem"
    server_csr = cert_dir / "server-csr.pem"
    server_cert = cert_dir / "server-cert.pem"

    print(f"Generating test certificates in {cert_dir}...")
    print("  [1/5] Generating CA private key (4096 bits)...")
    run(["openssl", "genrsa", "-out", str(ca_key), "4096"])
    print("  [2/5] Generating CA certificate (10 year validity)...")
    run(
        [
            "openssl",
            "req",
            "-new",
            "-x509",
            "-days",
            "3650",
            "-key",
            str(ca_key),
            "-out",
            str(ca_cert),
            "-subj",
            "/C=US/ST=Test/L=Test/O=ioguard/OU=Testing/CN=Test CA",
        ]
    )
    print("  [3/5] Generating server private key (2048 bits)...")
    run(["openssl", "genrsa", "-out", str(server_key), "2048"])
    print("  [4/5] Generating server certificate signing request...")
    run(
        [
            "openssl",
            "req",
            "-new",
            "-key",
            str(server_key),
            "-out",
            str(server_csr),
            "-subj",
            "/C=US/ST=Test/L=Test/O=ioguard/OU=Testing/CN=localhost",
        ]
    )
    san_config = cert_dir / "san.cnf"
    san_config.write_text(
        """[req]
distinguished_name = req_distinguished_name
req_extensions = v3_req
x509_extensions = v3_ca

[req_distinguished_name]

[v3_req]
basicConstraints = CA:FALSE
keyUsage = digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth
subjectAltName = @alt_names

[v3_ca]
basicConstraints = CA:FALSE
keyUsage = digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth
subjectAltName = @alt_names

[alt_names]
DNS.1 = localhost
DNS.2 = *.localhost
IP.1 = 127.0.0.1
IP.2 = ::1
""",
        encoding="utf-8",
    )
    print("  [5/5] Signing server certificate...")
    run(
        [
            "openssl",
            "x509",
            "-req",
            "-days",
            "365",
            "-in",
            str(server_csr),
            "-CA",
            str(ca_cert),
            "-CAkey",
            str(ca_key),
            "-CAcreateserial",
            "-out",
            str(server_cert),
            "-extensions",
            "v3_ca",
            "-extfile",
            str(san_config),
        ]
    )
    for path in cert_dir.glob("*.pem"):
        path.chmod(0o600)
    for path in (ca_cert, server_cert):
        path.chmod(0o644)
    print("\nCertificates generated successfully!\n")
    print(f"CA Certificate:     {ca_cert}")
    print(f"CA Private Key:     {ca_key}")
    print(f"Server Certificate: {server_cert}")
    print(f"Server Private Key: {server_key}")
    run(
        [
            "openssl",
            "x509",
            "-in",
            str(server_cert),
            "-noout",
            "-subject",
            "-issuer",
            "-dates",
            "-ext",
            "subjectAltName",
        ]
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
