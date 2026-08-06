#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14,<3.15"
# dependencies = []
# ///
"""Inspect the local ioguard container images through Skopeo."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from typing import cast


IMAGES = (
    "localhost/ioguard-dev:latest",
    "localhost/ioguard-test:latest",
    "localhost/ioguard-build:latest",
    "localhost/ioguard-ci:latest",
)


def string_list(value: object) -> list[str]:
    return [str(item) for item in value] if isinstance(value, list) else []


def inspect(image: str) -> dict[str, object] | None:
    try:
        result = subprocess.run(
            ["skopeo", "inspect", f"containers-storage:{image}"],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return json.loads(result.stdout)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    if shutil.which("skopeo") is None:
        raise SystemExit("skopeo is required")
    print("======================================")
    print("Inspecting ioguard Container Images")
    print("======================================")
    total_size = 0
    for image in IMAGES:
        print(
            f"\n======================================\nImage: {image}\n======================================"
        )
        info = inspect(image)
        if info is None:
            print(f"[SKIP] Image not found: {image}")
            continue
        print("Basic Information:")
        print(f"  Name:         {info.get('Name', 'unknown')}")
        print(f"  Digest:       {info.get('Digest', 'unknown')}")
        print(f"  Created:      {info.get('Created', 'unknown')}")
        size_value = info.get("Size", 0)
        size = size_value if isinstance(size_value, int) else 0
        total_size += size
        print(f"  Size:         {size // 1024 // 1024} MB")
        print("\nPlatform:")
        print(f"  OS:           {info.get('Os', 'unknown')}")
        print(f"  Architecture: {info.get('Architecture', 'unknown')}")
        print("\nLabels:")
        labels = info.get("Labels", {}) or {}
        if isinstance(labels, dict):
            for key, value in list(labels.items())[:10]:
                print(f"  {key}: {value}")
        layers = info.get("Layers", [])
        print(f"\nLayers: {len(layers) if isinstance(layers, list) else 0}")
        print("\nEnvironment Variables:")
        environment = info.get("Env", [])
        if isinstance(environment, list):
            for value in environment[:5]:
                print(f"  {value}")
            if len(environment) > 5:
                print("  ... (truncated)")
        config_value = info.get("Config", {})
        config = (
            cast(dict[str, object], config_value)
            if isinstance(config_value, dict)
            else {}
        )
        print("\nExecution:")
        entrypoint = string_list(config.get("Entrypoint", []))
        command = string_list(config.get("Cmd", []))
        working_dir = config.get("WorkingDir", "/")
        user = config.get("User", "root")
        print(f"  Entrypoint:   {' '.join(entrypoint) or 'none'}")
        print(f"  Cmd:          {' '.join(command) or 'none'}")
        print(
            f"  WorkingDir:   {working_dir if isinstance(working_dir, str) and working_dir else '/'}"
        )
        print(f"  User:         {user if isinstance(user, str) and user else 'root'}")
    print(
        "\n======================================\nSummary\n======================================"
    )
    print(f"Total size of all images: {total_size // 1024 // 1024} MB")
    print("Inspection complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
