#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14,<3.15"
# dependencies = []
# ///
"""Verify rootless Podman and SELinux container-volume support."""

from __future__ import annotations

import argparse
import getpass
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path


class Checks:
    def __init__(self) -> None:
        self.passed = 0
        self.failed = 0
        self.warned = 0

    def pass_(self, message: str) -> None:
        self.passed += 1
        print(f"[PASS] {message}")

    def fail(self, message: str) -> None:
        self.failed += 1
        print(f"[FAIL] {message}")

    def warn(self, message: str) -> None:
        self.warned += 1
        print(f"[WARN] {message}")

    @property
    def status(self) -> int:
        return 0 if self.failed == 0 else 1


def command_output(command: list[str]) -> str | None:
    try:
        return subprocess.run(
            command,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def command_ok(command: list[str]) -> bool:
    try:
        subprocess.run(
            command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
    except (OSError, subprocess.CalledProcessError):
        return False
    return True


def rootless() -> int:
    checks = Checks()
    print("Checking rootless mode...")
    if os.geteuid() == 0:
        checks.fail("Running as root - rootless mode requires non-root user")
    else:
        checks.pass_(f"Running as non-root user (UID: {os.geteuid()})")

    print("Checking user namespace support...")
    namespaces = Path("/proc/sys/user/max_user_namespaces")
    if namespaces.is_file():
        maximum = int(namespaces.read_text(encoding="utf-8").strip())
        if maximum > 0:
            checks.pass_(f"User namespaces enabled (max: {maximum})")
        else:
            checks.fail("User namespaces disabled (max_user_namespaces = 0)")
            print("Enable with: sudo sysctl -w user.max_user_namespaces=28633")
    else:
        checks.warn("Cannot determine user namespace support")

    print("Checking subuid/subgid configuration...")
    username = getpass.getuser()
    subuid = Path("/etc/subuid")
    subgid = Path("/etc/subgid")
    if subuid.is_file() and subgid.is_file():
        uid_entries = [
            line.split(":", 2)
            for line in subuid.read_text(encoding="utf-8").splitlines()
        ]
        gid_entries = [
            line.split(":", 2)
            for line in subgid.read_text(encoding="utf-8").splitlines()
        ]
        uid_match = next(
            (
                entry
                for entry in uid_entries
                if len(entry) == 3 and entry[0] == username
            ),
            None,
        )
        gid_match = next(
            (
                entry
                for entry in gid_entries
                if len(entry) == 3 and entry[0] == username
            ),
            None,
        )
        if uid_match and gid_match:
            checks.pass_(f"subuid configured: {uid_match[1]}:{uid_match[2]}")
            checks.pass_(f"subgid configured: {gid_match[1]}:{gid_match[2]}")
        else:
            checks.fail(f"No subuid/subgid entries for user: {username}")
            print(
                f"Configure with: sudo usermod --add-subuids 100000-165535 --add-subgids 100000-165535 {username}"
            )
    else:
        checks.fail("subuid/subgid files not found")

    print("Checking crun runtime...")
    if shutil.which("crun"):
        checks.pass_(
            f"crun installed: {(command_output(['crun', '--version']) or 'unknown').splitlines()[0]}"
        )
    else:
        checks.warn("crun not found (will fall back to runc)")
        print("Install with: sudo dnf install crun")

    print("Checking fuse-overlayfs...")
    if shutil.which("fuse-overlayfs"):
        checks.pass_("fuse-overlayfs installed")
    else:
        checks.fail("fuse-overlayfs not found (required for rootless overlay storage)")
        print("Install with: sudo dnf install fuse-overlayfs")

    print("Checking slirp4netns...")
    if shutil.which("slirp4netns"):
        checks.pass_("slirp4netns installed")
    else:
        checks.warn("slirp4netns not found (needed for rootless networking)")
        print("Install with: sudo dnf install slirp4netns")

    print("Checking XDG_RUNTIME_DIR...")
    runtime = os.environ.get("XDG_RUNTIME_DIR")
    if runtime and Path(runtime).is_dir():
        checks.pass_(f"XDG_RUNTIME_DIR set: {runtime}")
    else:
        checks.fail("XDG_RUNTIME_DIR not set or invalid")
        print("Usually set automatically by systemd --user")

    print("Checking Podman storage...")
    storage_paths = (
        Path.home() / ".config" / "containers" / "storage.conf",
        Path("/etc/containers/storage.conf"),
    )
    if any(path.is_file() for path in storage_paths):
        checks.pass_("Podman storage configured")
    else:
        checks.warn("No storage.conf found (will use defaults)")

    print("Testing rootless container execution...")
    if command_ok(
        [
            "podman",
            "run",
            "--rm",
            "registry.access.redhat.com/ubi9/ubi-micro:latest",
            "echo",
            "Rootless test successful",
        ]
    ):
        checks.pass_("Successfully ran rootless container")
    else:
        checks.fail("Failed to run rootless container")
        print("Check: podman info for diagnostics")

    print("Checking cgroups version...")
    if Path("/sys/fs/cgroup/cgroup.controllers").is_file():
        checks.pass_("Using cgroups v2 (recommended)")
    else:
        checks.warn("Using cgroups v1 (v2 recommended for better rootless support)")
    return summary(checks, "Rootless Verification Summary")


def selinux_context(path: Path) -> str | None:
    output = command_output(["ls", "-Zd", str(path)])
    return output.split()[0] if output else None


def selinux() -> int:
    checks = Checks()
    print("Checking SELinux status...")
    status = command_output(["getenforce"])
    if status is None:
        checks.warn("SELinux tools not installed")
        print("Install with: sudo dnf install policycoreutils")
        return 0
    if status == "Disabled":
        checks.warn("SELinux is disabled; most checks will be skipped")
        return 0
    if status == "Enforcing":
        checks.pass_("SELinux is enforcing")
    elif status == "Permissive":
        checks.warn("SELinux is permissive (not enforcing)")

    print("Checking container SELinux contexts...")
    if command_ok(["seinfo", "-t", "container_file_t"]):
        checks.pass_("container_file_t context available")
    else:
        checks.warn("container_file_t not found (install container-selinux)")

    source = Path("/opt/projects/repositories/ioguard")
    print("Checking source code directory SELinux labels...")
    if source.is_dir():
        context = selinux_context(source) or "unknown"
        print(f"Source directory context: {context}")
        if any(
            value in context
            for value in ("user_home_t", "admin_home_t", "container_file_t")
        ):
            checks.pass_("Source directory has compatible SELinux context")
        else:
            checks.warn("Source directory may need relabeling for container access")
            print(f"Fix with: chcon -R -t container_file_t {source}")
    else:
        checks.warn(f"Source directory not found: {source}")

    for suffix, flag in (("Z", ":Z"), ("z", ":z")):
        print(f"Testing volume mount with {flag} flag...")
        with tempfile.TemporaryDirectory(
            prefix=f"podman-selinux-test-{suffix}-"
        ) as temporary:
            test_file = Path(temporary) / "testfile"
            test_file.write_text("test\n", encoding="utf-8")
            mounted = command_ok(
                [
                    "podman",
                    "run",
                    "--rm",
                    "-v",
                    f"{temporary}:/test:{flag}",
                    "registry.access.redhat.com/ubi9/ubi-micro:latest",
                    "cat",
                    "/test/testfile",
                ]
            )
            if mounted:
                checks.pass_(f"Volume mount with {flag} flag works correctly")
                if suffix == "Z":
                    context = selinux_context(Path(temporary)) or "unknown"
                    if "container_file_t" in context:
                        checks.pass_(
                            "Directory correctly relabeled to container_file_t"
                        )
                    else:
                        checks.warn(f"Directory not relabeled as expected: {context}")
            else:
                checks.fail(f"Volume mount with {flag} flag failed")

    print("Checking SELinux policy modules...")
    modules = command_output(["semodule", "-l"])
    container_modules = [
        line for line in (modules or "").splitlines() if "container" in line
    ]
    if container_modules:
        checks.pass_(
            f"Container SELinux policy modules loaded ({len(container_modules)} modules)"
        )
    else:
        checks.warn("No container SELinux policy modules found")
        print("Install with: sudo dnf install container-selinux")

    print("Checking if Podman can set SELinux labels...")
    if command_ok(
        [
            "podman",
            "run",
            "--rm",
            "--security-opt",
            "label=disable",
            "registry.access.redhat.com/ubi9/ubi-micro:latest",
            "echo",
            "test",
        ]
    ):
        checks.pass_("Podman can manage SELinux labels")
    else:
        checks.fail("Podman cannot manage SELinux labels")

    print("Checking for recent SELinux denials...")
    audit_log = Path("/var/log/audit/audit.log")
    if audit_log.is_file() and os.access(audit_log, os.R_OK):
        denials = len(
            re.findall(
                r"denied.*container",
                audit_log.read_text(encoding="utf-8", errors="replace"),
            )
        )
        if denials == 0:
            checks.pass_("No recent container-related SELinux denials")
        else:
            checks.warn(f"Found {denials} recent container-related SELinux denials")
            print("Check with: sudo ausearch -m avc -ts recent | grep container")
    else:
        print("Audit log not accessible (may need sudo)")
    return summary(checks, "SELinux Verification Summary")


def summary(checks: Checks, title: str) -> int:
    print(f"\n{title}")
    print(f"Passed: {checks.passed}")
    print(f"Warnings: {checks.warned}")
    print(f"Failed: {checks.failed}")
    if checks.failed == 0:
        print("Verification completed without failures")
    else:
        print("Some checks failed; review the diagnostics above")
    return checks.status


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("check", choices=("rootless", "selinux"))
    args = parser.parse_args()
    return rootless() if args.check == "rootless" else selinux()


if __name__ == "__main__":
    raise SystemExit(main())
