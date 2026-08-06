#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14,<3.15"
# dependencies = []
# ///
"""Perform ioguard volume backup/restore and OCI image copy operations."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any


VOLUMES = (
    "ioguard_dev-home",
    "ioguard_build-cache",
    "ioguard_test-results",
    "ioguard_ci-reports",
)
BACKUP_IMAGE = "registry.access.redhat.com/ubi9/ubi-minimal:latest"


def info(message: str) -> None:
    print(f"[INFO] {message}")


def warn(message: str) -> None:
    print(f"[WARN] {message}")


def error(message: str) -> None:
    print(f"[ERROR] {message}", file=sys.stderr)


def run(
    command: list[str], *, capture: bool = False
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=True,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
    )


def require_tools(*tools: str) -> None:
    missing = [tool for tool in tools if shutil.which(tool) is None]
    if missing:
        raise SystemExit(f"required command(s) not found: {', '.join(missing)}")


def default_backup_base() -> Path:
    return Path(__file__).resolve().parent.parent / "volumes" / "backups"


def volume_mountpoint(volume: str) -> Path:
    result = run(
        ["podman", "volume", "inspect", volume, "--format", "{{.Mountpoint}}"],
        capture=True,
    )
    mountpoint = result.stdout.strip()
    if not mountpoint:
        raise RuntimeError(f"Podman returned no mountpoint for volume {volume}")
    return Path(mountpoint)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def backup_volume(volume: str, destination: Path) -> bool:
    archive = destination / f"{volume}.tar.gz"
    info(f"Backing up volume: {volume}")
    try:
        mountpoint = volume_mountpoint(volume)
    except subprocess.CalledProcessError:
        warn(f"Volume not found: {volume} (skipping)")
        return False
    if not mountpoint:
        error(f"Failed to get mountpoint for volume: {volume}")
        return False

    try:
        if os.access(mountpoint, os.R_OK):
            run(["tar", "czf", str(archive), "-C", str(mountpoint), "."])
        else:
            info("  Using a container to work around volume permissions")
            run(
                [
                    "podman",
                    "run",
                    "--rm",
                    "-v",
                    f"{volume}:/volume:Z",
                    "-v",
                    f"{destination}:/backup:Z",
                    BACKUP_IMAGE,
                    "tar",
                    "czf",
                    f"/backup/{archive.name}",
                    "-C",
                    "/volume",
                    ".",
                ]
            )
    except (OSError, subprocess.CalledProcessError) as exc:
        error(f"Failed to backup volume {volume}: {exc}")
        return False

    size_mb = archive.stat().st_size // 1024 // 1024
    info(f"  Created {archive} ({size_mb} MB)")
    return True


def write_manifest(
    destination: Path, timestamp: str, backed_up: int, failed: int
) -> None:
    archives = sorted(destination.glob("*.tar.gz"))
    lines = [
        "Backup Manifest",
        "===============",
        "",
        f"Timestamp: {timestamp}",
        f"Date: {datetime.now().astimezone().isoformat()}",
        f"Host: {socket.gethostname()}",
        "",
        f"Volumes Backed Up: {backed_up}",
        f"Failed Backups: {failed}",
        "",
        "Files:",
    ]
    lines.extend(
        f"  {archive.name} ({archive.stat().st_size} bytes)" for archive in archives
    )
    if not archives:
        lines.append("  No backup files created")
    lines.extend(["", "Checksums (SHA256):"])
    lines.extend(f"{sha256(archive)}  {archive.name}" for archive in archives)
    if not archives:
        lines.append("  No checksums available")
    (destination / "manifest.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def backup(backup_base: Path) -> int:
    require_tools("podman", "tar")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    destination = backup_base / timestamp
    destination.mkdir(parents=True, exist_ok=False)
    info(f"Starting volume backup: {destination}")
    backed_up = sum(backup_volume(volume, destination) for volume in VOLUMES)
    failed = len(VOLUMES) - backed_up
    write_manifest(destination, timestamp, backed_up, failed)
    latest = backup_base / "latest"
    if latest.is_symlink() or latest.exists():
        latest.unlink()
    latest.symlink_to(destination)
    info(f"Created latest link: {latest} -> {destination}")
    print(f"Volumes backed up: {backed_up}")
    print(f"Failed backups: {failed}")
    return 0 if failed == 0 else 1


def backup_archives(source: Path) -> list[Path]:
    return sorted(path for path in source.glob("*.tar.gz") if path.is_file())


def confirm_restore() -> bool:
    answer = input("Continue with restore? [y/N] ").strip().lower()
    return answer == "y"


def restore_volume(archive: Path) -> bool:
    volume = archive.name.removesuffix(".tar.gz")
    info(f"Restoring volume: {volume} from {archive}")
    try:
        try:
            run(["podman", "volume", "exists", volume])
            exists = True
        except subprocess.CalledProcessError:
            exists = False
        if not exists:
            run(["podman", "volume", "create", volume])
        else:
            warn(f"Volume already exists; overwriting data: {volume}")
            run(
                [
                    "podman",
                    "run",
                    "--rm",
                    "-v",
                    f"{volume}:/volume:Z",
                    BACKUP_IMAGE,
                    "sh",
                    "-c",
                    "rm -rf /volume/* /volume/.[!.]* /volume/..?*",
                ]
            )
        run(
            [
                "podman",
                "run",
                "--rm",
                "-v",
                f"{volume}:/volume:Z",
                "-v",
                f"{archive}:/backup.tar.gz:Z,ro",
                BACKUP_IMAGE,
                "tar",
                "xzf",
                "/backup.tar.gz",
                "-C",
                "/volume",
            ]
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        error(f"Failed to restore volume {volume}: {exc}")
        return False
    info(f"Volume restored successfully: {volume}")
    return True


def restore(source: str | None, backup_base: Path, assume_yes: bool) -> int:
    require_tools("podman")
    backup_dir = backup_base / "latest" if source in (None, "latest") else Path(source)
    if not backup_dir.is_dir():
        raise SystemExit(f"backup directory not found: {backup_dir}")
    archives = backup_archives(backup_dir)
    if not archives:
        raise SystemExit(f"no backup archives found in {backup_dir}")
    manifest = backup_dir / "manifest.txt"
    if manifest.is_file():
        print("\n".join(manifest.read_text(encoding="utf-8").splitlines()[:15]))
    warn("This will overwrite existing volume data")
    if not assume_yes and not confirm_restore():
        error("Restore aborted by user")
        return 1
    restored = sum(restore_volume(archive) for archive in archives)
    failed = len(archives) - restored
    print(f"Volumes restored: {restored}")
    print(f"Failed restores: {failed}")
    return 0 if failed == 0 else 1


def image_inspect(image: str, transport: str) -> dict[str, Any]:
    result = run(["skopeo", "inspect", f"{transport}:{image}"], capture=True)
    parsed = json.loads(result.stdout)
    if not isinstance(parsed, dict):
        raise RuntimeError(f"unexpected Skopeo response for {image}")
    return parsed


def registry_from_image(image: str) -> str:
    first = image.split("/", 1)[0]
    return (
        first if "." in first or ":" in first or first == "localhost" else "docker.io"
    )


def push(source: str, destination: str, sign: bool) -> int:
    require_tools("skopeo")
    source_ref = f"containers-storage:{source}"
    destination_ref = f"docker://{destination}"
    info(f"Inspecting source image: {source_ref}")
    try:
        source_info = image_inspect(source, "containers-storage")
    except (OSError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        raise SystemExit(
            f"source image not found or cannot be inspected: {source}: {exc}"
        )
    source_digest = source_info.get("Digest", "unknown")
    source_size = source_info.get("Size", 0)
    size = source_size if isinstance(source_size, int) else 0
    info(f"Source digest: {source_digest}; size: {size // 1024 // 1024} MB")

    registry = registry_from_image(destination)
    try:
        run(["skopeo", "login", "--get-login", registry], capture=True)
    except (OSError, subprocess.CalledProcessError):
        warn(f"Not logged in to {registry}")
        if (
            input(f"Continue without verified login to {registry}? [y/N] ")
            .strip()
            .lower()
            != "y"
        ):
            error("Push aborted by user")
            return 1

    with tempfile.NamedTemporaryFile(
        prefix="ioguard-image-", suffix=".digest"
    ) as digest_file:
        command = [
            "skopeo",
            "copy",
            "--format",
            "v2s2",
            "--override-os",
            "linux",
            "--override-arch",
            "amd64",
            "--remove-signatures",
            "--digestfile",
            digest_file.name,
        ]
        key_id = os.environ.get("GPG_KEY_ID")
        if sign and key_id:
            command.extend(["--sign-by", key_id])
        elif sign:
            warn("GPG_KEY_ID is not set; image signing is skipped")
        command.extend([source_ref, destination_ref])
        info(f"Copying image to {destination_ref}")
        try:
            run(command)
        except (OSError, subprocess.CalledProcessError) as exc:
            error(f"Failed to push image: {exc}")
            return 1
        digest_file.seek(0)
        pushed_digest = digest_file.read().strip()
    info(f"Pushed digest: {pushed_digest or 'unknown'}")

    try:
        remote_info = image_inspect(destination, "docker")
    except (OSError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        error(f"Remote verification failed: {exc}")
        return 1
    remote_digest = remote_info.get("Digest", "unknown")
    if source_digest != "unknown" and remote_digest == source_digest:
        info("Digest verification passed")
    else:
        warn(
            f"Digest verification differs: local={source_digest}; remote={remote_digest}"
        )
    print(f"Image pushed: {destination}")
    print(f"Pull command: podman pull {destination}")
    return 0


def parser() -> argparse.ArgumentParser:
    command_parser = argparse.ArgumentParser(description=__doc__)
    commands = command_parser.add_subparsers(dest="command", required=True)

    backup_parser = commands.add_parser("backup", help="backup named Podman volumes")
    backup_parser.add_argument("backup_directory", nargs="?", type=Path)

    restore_parser = commands.add_parser("restore", help="restore named Podman volumes")
    restore_parser.add_argument("backup_directory", nargs="?")
    restore_parser.add_argument(
        "--yes", action="store_true", help="skip overwrite confirmation"
    )

    push_parser = commands.add_parser("push", help="copy an image to a registry")
    push_parser.add_argument("source_image")
    push_parser.add_argument("destination_image")
    push_parser.add_argument("--sign", action="store_true")
    return command_parser


def main() -> int:
    arguments = parser().parse_args()
    backup_base = default_backup_base()
    if arguments.command == "backup":
        return backup(arguments.backup_directory or backup_base)
    if arguments.command == "restore":
        return restore(arguments.backup_directory, backup_base, arguments.yes)
    return push(arguments.source_image, arguments.destination_image, arguments.sign)


if __name__ == "__main__":
    raise SystemExit(main())
