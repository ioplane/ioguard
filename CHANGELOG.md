# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- io_uring abstraction layer for all I/O (network, TUN, timers, signals).
- mimalloc memory allocator wrapper (MI_SECURE mode).
- IPC transport over SOCK_SEQPACKET with SCM_RIGHTS fd passing.
- IPC message serialization via protobuf-c (auth, worker status).
- TOML configuration parser (tomlc99).
- Process management with pidfd_spawn, pidfd_send_signal, signalfd.
- wolfSSL TLS 1.3 backend (native API, not OpenSSL compat).
- GnuTLS TLS backend (dual-backend build support).
- TLS priority string parser for cipher suite selection.
- TLS session cache with configurable limits.
- PAM authentication module.
- sec-mod (authentication manager) process.
- Session cookie generation and validation (wolfCrypt HMAC-SHA256).
- HTTP parser integration (llhttp) for OpenConnect protocol.
- XML auth request/response builder.
- CSTP packet framing (encode/decode with zero-copy).
- TUN device allocation and MTU calculation.
- DPD state machine with channel tracking.
- Worker process context and connection tracking.
- DTLS 1.2 Cisco-compatible handshake and session management.
- Channel state machine (CSTP-only, DTLS-primary, DTLS-fallback).
- LZ4 and LZS compression with CSTP integration.
- DTLS keying material extraction and header parsing.
- CodeChecker and PVS-Studio static analyzer integration.
- libmdbx and SQLite added to dev container.
- Community health files (CONTRIBUTING, SECURITY, SUPPORT, CHANGELOG).
- GitHub issue templates (YAML forms), PR template, CODEOWNERS, dependabot.
- Bilingual documentation structure (docs/en/, docs/ru/).
- Unity test framework (100+ tests, ASan+UBSan clean).

### Changed

- Project renamed from wolfguard to ioguard (`iog_` prefix, `IOGUARD_` guards).
- License changed from GPLv2 to GPLv3 (wolfSSL dependency requirement).
- Rootless Podman and SELinux verification now use the modular `container_verify.py` CLI.
- Local image inspection now uses `image_inspect.py` with structured Skopeo JSON parsing.
- Benchmark certificate generation now uses an explicit OpenSSL argv-based Python CLI.
- Benchmark GO/NO-GO comparison now uses deterministic JSON parsing in `compare_results.py`.
- PoC GnuTLS/wolfSSL comparison now uses `tests/poc/compare.py`.
- TLS benchmark execution now uses `tests/bench/benchmark.py` with explicit process and socket handling.
- Volume backup/restore and registry image copy now use the modular `container_ops.py` CLI.
- PoC backend benchmarking and compatibility testing now use `tests/poc/benchmark.py` and `tests/poc/run_tests.py`.
- OCI image builds now use `container_build.py` with layered target-specific Containerfiles and Python runtime runners.

### Removed

- Removed the separate `verify-rootless.sh` and `verify-selinux.sh` entrypoints.
- Removed the `inspect-images.sh` entrypoint.
- Removed the `generate_certs.sh` entrypoint.
- Removed the `compare_results.sh` entrypoint.
- Removed the `tests/poc/compare.sh` entrypoint.
- Removed the `tests/bench/benchmark.sh` entrypoint.
- Removed the `tests/poc/benchmark.sh` and `tests/poc/run_tests.sh` entrypoints.
- Removed the four Buildah build shell entrypoints.
- Removed the `backup-volumes.sh`, `restore-volumes.sh`, and `push-image.sh` entrypoints.

[Unreleased]: https://github.com/dantte-lp/ioguard/commits/master
