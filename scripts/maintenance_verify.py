#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14,<3.15"
# dependencies = []
# ///
"""Run read-only namespace and legacy-artifact verification checks."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


COMMON_PATTERNS = {
    "legacy": (
        "rwctl",
        "ioguard-dev",
        "ioguard-test",
        "ioguard-build",
        "ioguard-ci",
        "ioguard\\.toml",
        "/etc/ioguard",
        "/var/lib/ioguard",
        "io\\.ioguard\\.",
        "ioguard-connect",
        "ioguard-docs",
    ),
    "wave13": (
        r"\bRW_IPC_MAX_MSG_SIZE\b",
        r"\brw_dpd_",
        r"\brw_compress_",
        r"\brw_lzs_",
        r"\brw_fw_",
        r"\brw_dtls_parse_accept_encoding\b",
        r"\brw_security_build_fw_session\b",
        r"\bRW_FW_CHAIN_NAME_MAX\b",
        r"\bRW_LZS_",
    ),
    "wave14_build": (r"\brw_dpd\b", r"\brw_compress(_lzs|_lz4)?\b", r"\brw_firewall\b"),
    "wave16_storage": (
        r"\brw_mdbx_",
        r"\brw_migrate\b",
        r"\brw_vault\b",
        r"\brw_totp\b",
        r"\bRW_MDBX_",
        "IOGUARD_STORAGE_MDBX_H",
        "IOGUARD_STORAGE_MIGRATE_H",
        "IOGUARD_AUTH_TOTP_H",
        r"struct iog_vault",
        r"typedef struct iog_vault",
        r"TARGET iog_mdbx",
        r"TARGET iog_totp",
        r"TARGET iog_vault",
    ),
    "wave18_config_session_build": (
        "IOGUARD_CONFIG_CONFIG_H",
        "IOGUARD_CORE_SESSION_H",
        "IOGUARD_SESSION_CACHE_H",
        r"\brw_(memory|config|main_helpers|session)\b",
    ),
    "wave19_fdpass_process": (
        "IOGUARD_IPC_FDPASS_H",
        "IOGUARD_CORE_PROCESS_H",
        "IOGUARD_CORE_MAIN_H",
        r"\bRW_FDPASS_MAX_FDS\b",
        r"\brw_fdpass_(send|recv)\b",
        r"\brw_process_(spawn|wait|signal|cleanup)\b",
        r"\brw_process_t\b",
        r"\brw_main_(parse_args|create_ipc_pair|create_accept_pair|create_signalfd)\b",
        r"\brw_fdpass\b",
        r"\brw_core\b",
    ),
}

SOURCE_PATHS = {
    "wave13": (
        ".claude/skills/c23-standards/SKILL.md",
        "docs/plans/2026-03-07-sprint-1-foundation.md",
        "docs/plans/2026-03-08-ioguard-rebranding-plan.md",
        "docs/plans/2026-03-08-sprint-4-dtls-compression.md",
        "docs/plans/2026-03-08-sprint-5-storage-security.md",
        "docs/plans/2026-03-08-sprint-6-vertical-integration.md",
        "src/core/conn_data.c",
        "src/core/conn_data.h",
        "src/core/conn_timer.c",
        "src/core/conn_timer.h",
        "src/core/secmod.c",
        "src/core/security_hooks.c",
        "src/core/security_hooks.h",
        "src/core/worker.c",
        "src/core/worker.h",
        "src/ipc/transport.h",
        "src/network/channel.h",
        "src/network/compress.c",
        "src/network/compress.h",
        "src/network/compress_lzs.c",
        "src/network/compress_lzs.h",
        "src/network/dpd.c",
        "src/network/dpd.h",
        "src/network/dtls_headers.c",
        "src/network/dtls_headers.h",
        "src/security/firewall.c",
        "src/security/firewall.h",
        "tests/integration/test_auth_flow.c",
        "tests/integration/test_auth_mfa.c",
        "tests/integration/test_data_path.c",
        "tests/integration/test_dtls_channel.c",
        "tests/integration/test_ipc_roundtrip.c",
        "tests/integration/test_vpn_flow.c",
        "tests/unit/test_compress.c",
        "tests/unit/test_compress_cstp.c",
        "tests/unit/test_compress_lzs.c",
        "tests/unit/test_conn_data.c",
        "tests/unit/test_conn_timer.c",
        "tests/unit/test_dpd.c",
        "tests/unit/test_dtls_headers.c",
        "tests/unit/test_firewall.c",
        "tests/unit/test_ipc_messages.c",
        "tests/unit/test_secmod.c",
        "tests/unit/test_security_hooks.c",
    ),
    "wave14_build": ("CMakeLists.txt",),
    "wave16_storage": (
        ".claude/skills/storage-patterns/SKILL.md",
        "docs/plans/2026-03-08-sprint-5-storage-security.md",
        "docs/plans/2026-03-08-sprint-6-vertical-integration.md",
        "src/core/secmod.c",
        "src/core/secmod.h",
        "src/storage/mdbx.c",
        "src/storage/mdbx.h",
        "src/storage/migrate.c",
        "src/storage/migrate.h",
        "src/storage/vault.c",
        "src/storage/vault.h",
        "src/auth/totp.h",
        "tests/fuzz/fuzz_session_key.c",
        "tests/integration/test_storage.c",
        "tests/unit/test_storage_mdbx.c",
        "tests/unit/test_storage_migrate.c",
        "CMakeLists.txt",
    ),
    "wave18_config_session_build": (
        ".claude/skills/c23-standards/SKILL.md",
        ".claude/skills/coding-standards/SKILL.md",
        ".claude/skills/security-coding/SKILL.md",
        ".claude/skills/storage-patterns/SKILL.md",
        "CMakeLists.txt",
        "docs/plans/2026-03-07-sprint-1-foundation.md",
        "docs/plans/2026-03-07-sprint-2-tls-auth.md",
        "docs/plans/2026-03-08-ioguard-rebranding-plan.md",
        "docs/plans/2026-03-08-sprint-5-storage-security.md",
        "docs/plans/2026-03-10-sprint-7-auth-observability.md",
        "src/config/config.h",
        "src/core/session.h",
        "src/crypto/session_cache.h",
    ),
    "wave19_fdpass_process": (
        "src/ipc/fdpass.h",
        "src/ipc/fdpass.c",
        "src/core/process.h",
        "src/core/process.c",
        "src/core/main.h",
        "src/core/main.c",
        "tests/unit/test_fdpass.c",
        "tests/unit/test_process.c",
        "tests/unit/test_main_bootstrap.c",
        "tests/unit/test_worker_loop.c",
        "src/core/worker_loop.c",
        "CMakeLists.txt",
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", choices=sorted(COMMON_PATTERNS))
    return parser.parse_args()


def main() -> int:
    target = parse_args().target
    root = Path(__file__).resolve().parents[1]
    command = ["rg", "-n", "--color", "never"]
    command.extend(
        argument for pattern in COMMON_PATTERNS[target] for argument in ("-e", pattern)
    )
    if target == "legacy":
        command.extend(
            (
                "--glob",
                "!docs/tmp/**",
                "--glob",
                "!docs/plans/2026-03-11-ioguard-legacy-name-inventory.md",
                "--glob",
                "!docs/plans/2026-03-11-ioguard-naming-options.md",
                "--glob",
                "!scripts/maintenance/**",
                ".",
            )
        )
    else:
        command.extend(SOURCE_PATHS[target])
    result = subprocess.run(command, cwd=root, check=False, text=True)
    if result.returncode > 1:
        return result.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
