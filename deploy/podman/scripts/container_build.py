#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14,<3.15"
# dependencies = []
# ///
"""Build ioguard OCI images through the Podman/Buildah backend."""

from __future__ import annotations

import argparse
import subprocess
from datetime import UTC, datetime
from pathlib import Path

TARGETS = ("dev", "test", "build", "ci")
NETWORK_MODES = ("bridge", "host", "none")
IMAGE_NAMES = {
    "dev": "localhost/ioguard-dev:latest",
    "test": "localhost/ioguard-test:latest",
    "build": "localhost/ioguard-build:latest",
    "ci": "localhost/ioguard-ci:latest",
}
DEPENDENCIES = {"dev": None, "test": "dev", "build": "dev", "ci": "build"}
CONTAINERFILES = {
    "dev": "Containerfile",
    "test": "Containerfile.test",
    "build": "Containerfile.build",
    "ci": "Containerfile.ci",
}


def root() -> Path:
    return Path(__file__).resolve().parents[1]


def git_revision(project_root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=project_root,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
        )
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return result.stdout.strip()


def image_exists(image: str) -> bool:
    return (
        subprocess.run(
            ["podman", "image", "exists", image],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode
        == 0
    )


def build(
    target: str,
    image: str | None,
    base_image: str | None,
    log_level: str | None,
    network: str,
) -> int:
    project_root = root().parent.parent
    deploy_root = root()
    dependency = DEPENDENCIES[target]
    dependency_image = IMAGE_NAMES[dependency] if dependency else None
    if dependency_image and not image_exists(dependency_image):
        raise SystemExit(
            f"required image not found: {dependency_image}; build {dependency} first"
        )
    target_image = image or IMAGE_NAMES[target]
    command = [
        "podman",
        "build",
        "--format",
        "oci",
        "--layers",
        "--network",
        network,
        "--file",
        str(deploy_root / CONTAINERFILES[target]),
        "--tag",
        target_image,
        "--build-arg",
        f"OCI_REVISION={git_revision(project_root)}",
        "--build-arg",
        f"OCI_CREATED={datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%SZ')}",
    ]
    if base_image:
        command.extend(["--build-arg", f"BASE_IMAGE={base_image}"])
    if log_level:
        command.extend(["--log-level", log_level])
    command.append(str(project_root))
    print(f"Building {target} image: {target_image}")
    print(f"Containerfile: {CONTAINERFILES[target]}")
    return subprocess.run(command, cwd=project_root, check=False).returncode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", choices=TARGETS)
    parser.add_argument("--image")
    parser.add_argument("--base-image")
    parser.add_argument(
        "--log-level", choices=("error", "warn", "info", "debug", "trace")
    )
    parser.add_argument(
        "--network",
        choices=NETWORK_MODES,
        default="host",
        help="network namespace used only while building image layers",
    )
    args = parser.parse_args()
    return build(args.target, args.image, args.base_image, args.log_level, args.network)


if __name__ == "__main__":
    raise SystemExit(main())
