#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14,<3.15"
# dependencies = []
# ///
"""Run the ioguard PMI/PSI benchmark gate and write evidence artifacts."""

from __future__ import annotations

import json
import os
import platform
import re
import statistics
import subprocess
from datetime import UTC, datetime
from pathlib import Path


def run(
    command: list[str],
    *,
    root: Path,
    output: Path | None = None,
    tail: int | None = None,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        cwd=root,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    content = result.stdout or ""
    if tail is not None:
        content = "\n".join(content.splitlines()[-tail:])
    if output is not None:
        output.write_text(result.stdout or "", encoding="utf-8")
    elif content:
        print(content)
    if result.returncode:
        raise subprocess.CalledProcessError(result.returncode, command, output=content)
    return result


def command_version(command: list[str], *, root: Path) -> str:
    result = subprocess.run(
        command,
        cwd=root,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    return (result.stdout or "").splitlines()[0] if result.returncode == 0 else "N/A"


def cpu_info() -> tuple[str, str]:
    model = "N/A"
    flags = "N/A"
    cpuinfo = Path("/proc/cpuinfo")
    if cpuinfo.is_file():
        text = cpuinfo.read_text(encoding="utf-8", errors="replace")
        model_match = re.search(r"^model name\s*:\s*(.+)$", text, re.MULTILINE)
        flags_match = re.search(r"^(?:flags|Features)\s*:\s*(.+)$", text, re.MULTILINE)
        model = model_match.group(1).strip() if model_match else "N/A"
        if flags_match:
            flags = " ".join(
                flag
                for flag in flags_match.group(1).split()
                if any(token in flag.lower() for token in ("avx", "sse", "neon", "sve"))
            )
    return model, flags or "N/A"


def memory_total_kb() -> str:
    meminfo = Path("/proc/meminfo")
    if not meminfo.is_file():
        return "N/A"
    match = re.search(r"^MemTotal:\s+(\d+)\s+kB$", meminfo.read_text(), re.MULTILINE)
    return match.group(1) if match else "N/A"


def write_environment(path: Path, *, root: Path, run_id: str) -> None:
    model, flags = cpu_info()
    lines = (
        f"timestamp: {run_id}",
        f"kernel: {platform.release()}",
        f"arch: {platform.machine()}",
        f"cpu_model: {model}",
        f"cpu_count: {os.cpu_count() or 1}",
        f"cpu_flags: {flags}",
        f"mem_total_kb: {memory_total_kb()}",
        "---",
        f"clang: {command_version(['clang', '--version'], root=root)}",
        f"gcc: {command_version(['gcc-15', '--version'], root=root)}",
        f"cmake: {command_version(['cmake', '--version'], root=root)}",
        f"gdb: {command_version(['gdb', '--version'], root=root)}",
        f"valgrind: {command_version(['valgrind', '--version'], root=root)}",
        f"uftrace: {command_version(['uftrace', '--version'], root=root)}",
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(path.read_text(encoding="utf-8"), end="")


def benchmark_values(text: str) -> list[float]:
    values: list[float] = []
    for line in text.splitlines():
        if "ops/s" not in line:
            continue
        matches = re.findall(r"(?:\d+(?:\.\d*)?|\.\d+)", line)
        if matches:
            values.append(float(matches[-1]))
    return values


def write_benchmark_summary(path: Path, values: list[float]) -> None:
    if not values:
        path.write_text(
            "median: N/A\nmin: N/A\nmax: N/A\nstdev: N/A\n", encoding="utf-8"
        )
        return
    stdev = statistics.stdev(values) if len(values) > 1 else None
    path.write_text(
        "\n".join(
            (
                f"median: {statistics.median(values):.0f} ops/s",
                f"min:    {min(values):.0f} ops/s",
                f"max:    {max(values):.0f} ops/s",
                f"stdev:  {stdev:.0f} ops/s" if stdev is not None else "stdev: N/A",
            )
        )
        + "\n",
        encoding="utf-8",
    )


def update_index(path: Path, *, run_id: str, preset: str, runs: int) -> None:
    header = "timestamp\tpreset\truns\tstatus"
    rows = [line for line in path.read_text(encoding="utf-8").splitlines() if line]
    if not rows or rows[0] != header:
        rows = [header]
    rows = [line for line in rows if not line.startswith(f"{run_id}\t")]
    rows.append(f"{run_id}\t{preset}\t{runs}\tpass")
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    runs = int(os.environ.get("RUNS", "5"))
    if runs < 1:
        raise SystemExit("RUNS must be positive")
    preset = os.environ.get("PRESET", "clang-debug")
    build_dir = root / "build" / preset
    output_base = Path(os.environ.get("OUT_DIR", "tests/artifacts/pmi-psi"))
    if not output_base.is_absolute():
        output_base = root / output_base
    run_stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    head = command_version(["git", "rev-parse", "--short", "HEAD"], root=root)
    run_id = f"{run_stamp}-{head}"
    run_dir = output_base / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    print("=== [1/6] Record host/toolchain info ===")
    write_environment(run_dir / "environment.txt", root=root, run_id=run_id)
    print(f"=== [2/6] Build ({preset}) ===")
    run(["cmake", "--preset", preset], root=root, tail=3)
    run(
        ["cmake", "--build", "--preset", preset, "-j", str(os.cpu_count() or 1)],
        root=root,
        tail=3,
    )
    print("=== [3/6] Run tests (correctness gate) ===")
    run(["ctest", "--preset", preset, "--output-on-failure"], root=root, tail=5)

    print(f"=== [4/6] Run benchmarks ({runs} runs each) ===")
    benchmarks = sorted(
        path
        for path in build_dir.glob("bench_*")
        if path.is_file() and os.access(path, os.X_OK)
    )
    for benchmark in benchmarks:
        name = benchmark.name
        values: list[float] = []
        for number in range(1, runs + 1):
            print(f"  {name}: run {number}/{runs}")
            result = subprocess.run(
                [str(benchmark)],
                cwd=root,
                check=True,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
            (run_dir / f"{name}_run{number}.txt").write_text(
                result.stdout, encoding="utf-8"
            )
            values.extend(benchmark_values(result.stdout))
        write_benchmark_summary(run_dir / f"{name}_summary.txt", values)

    print("=== [5/6] Generate manifest ===")
    benchmark_entries = []
    for summary in sorted(run_dir.glob("*_summary.txt")):
        name = summary.name.removesuffix("_summary.txt")
        match = re.search(r"median:\s+([\d.]+)", summary.read_text(encoding="utf-8"))
        benchmark_entries.append(
            {"name": name, "median_ops_s": float(match.group(1)) if match else 0}
        )
    manifest = {
        "timestamp": run_id,
        "preset": preset,
        "runs": runs,
        "tests": "pass",
        "benchmarks": benchmark_entries,
    }
    (run_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print((run_dir / "manifest.json").read_text(encoding="utf-8"), end="")

    print("=== [6/6] Update index ===")
    index = output_base / "index.tsv"
    if not index.exists():
        index.write_text("timestamp\tpreset\truns\tstatus\n", encoding="utf-8")
    update_index(index, run_id=run_id, preset=preset, runs=runs)
    (output_base / "latest.txt").write_text(f"{run_id}\n", encoding="utf-8")
    print(f"PMI/PSI run complete: {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
