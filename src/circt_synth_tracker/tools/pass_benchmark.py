#!/usr/bin/env python3
"""Run pass-level compile-time benchmarks for CIRCT vs ABC on LSILS AIG inputs."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from circt_synth_tracker.tools import find_abc


@dataclass
class Workload:
    name: str
    suite: str
    aig_file: Path


def run_command(cmd: list[str]) -> tuple[str, str, float]:
    start = time.perf_counter()
    proc = subprocess.run(cmd, capture_output=True, text=True)
    elapsed = time.perf_counter() - start
    if proc.returncode != 0:
        raise RuntimeError(
            f"command failed ({proc.returncode}): {' '.join(cmd)}\n{proc.stderr}"
        )
    return proc.stdout, proc.stderr, elapsed


def parse_mlir_timing(stderr: str) -> dict[str, float]:
    timings: dict[str, float] = {}
    in_table = False
    for line in stderr.splitlines():
        if "----Wall Time----" in line:
            in_table = True
            continue
        if not in_table:
            continue
        m = re.match(r"\s+(\d+\.\d+)\s+\(\s*[\d.]+%\)\s+(.+)", line)
        if not m:
            continue
        t = float(m.group(1))
        name = m.group(2).strip()
        if name in ("root", "Total") or name.endswith("Pipeline"):
            continue
        timings[name] = t
    return timings


def extract_target_pass_time(
    target_pass_name: str, pass_timings: dict[str, float]
) -> tuple[float | None, list[str]]:
    """Extract runtime of the target CIRCT pass for the selected mode."""
    matched: list[tuple[str, float]] = []
    for name, t in pass_timings.items():
        if target_pass_name in name:
            matched.append((name, t))
            print(f"Matched pass '{name}' with time {t:.3f}s for target '{target_pass_name}'")

    if not matched:
        return None, []

    # Sum matched times in case timing output includes wrapper + concrete pass lines.
    total = sum(t for _, t in matched)
    names = [name for name, _ in matched]
    return total, names


def parse_abc_time(output: str) -> float | None:
    for line in output.splitlines():
        m = re.search(
            r"\belapse\s*:\s*([+-]?\d+(?:\.\d+)?)\s+seconds\b", line
        )
        if m:
            return float(m.group(1))
    return None


def resolve_tool(path_or_name: str) -> str:
    p = Path(path_or_name)
    if p.exists():
        return str(p)
    if p.name and p.name != path_or_name:
        return p.name
    return path_or_name


def load_command_templates(root: Path) -> dict[str, dict[str, str]]:
    path = root / "pass" / "commands.json"
    data = json.loads(path.read_text())
    templates: dict[str, dict[str, str]] = {}
    for entry in data:
        name = entry.get("name")
        if not name:
            continue
        templates[name] = {
            "circt": entry.get("circt", ""),
            "abc": entry.get("abc", ""),
            "circt-pass-name": entry.get("circt-pass-name", ""),
        }
    return templates


def command_for_mode(
    templates: dict[str, dict[str, str]], mode: str, lut_size: int, cut_size: int
) -> tuple[str, str, str]:
    template = templates.get(mode)
    if not template:
        raise ValueError(f"missing mode in commands.json: {mode}")
    target_pass_name = template.get("circt-pass-name", "")
    if not target_pass_name:
        raise ValueError(f"missing 'circt-pass-name' in commands.json: {mode}")
    circt_cmd = (
        template["circt"]
        .replace("{lut-k}", str(lut_size))
        .replace("{lut-max-cut-size}", str(cut_size))
    )
    abc_cmd = (
        template["abc"]
        .replace("{lut-k}", str(lut_size))
        .replace("{lut-max-cut-size}", str(cut_size))
    )
    return circt_cmd, abc_cmd, target_pass_name


def discover_lsils_workloads(benchmarks_root: Path) -> list[Workload]:
    lsils_root = benchmarks_root / "aig" / "lsils" / "benchmarks"
    workloads: list[Workload] = []
    for aig in sorted(lsils_root.rglob("*.aig")):
        if "best_results" in aig.parts:
            continue
        rel = aig.relative_to(lsils_root)
        name = f"{rel.parent.name}_{aig.stem}" if rel.parent.name != "." else aig.stem
        workloads.append(Workload(name=name, suite="lsils", aig_file=aig))
    return workloads


def write_result(output_dir: Path, tool: str, bench_name: str, metrics: dict[str, Any]) -> None:
    results_dir = output_dir / "results" / tool
    results_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "benchmark": bench_name,
        "tool": tool,
        "test_file": metrics.get("aig_file"),
        "timestamp": datetime.now().isoformat(),
        "metrics": metrics,
        "category": metrics.get("suite", "unknown"),
    }
    (results_dir / f"{bench_name}.json").write_text(json.dumps(payload, indent=2) + "\n")


def run_one(
    wl: Workload,
    mode: str,
    lut_size: int,
    cut_size: int,
    circt_translate: str,
    circt_opt: str,
    abc: str,
    command_templates: dict[str, dict[str, str]],
    output_dir: Path,
    tool: str,
) -> None:
    bench_id = f"{wl.name}_k{lut_size}_c{cut_size}"
    common = {
        "benchmark": bench_id,
        "suite": wl.suite,
        "aig_file": str(wl.aig_file),
        "mode": mode,
        "lut_size": lut_size,
        "cut_size": cut_size,
    }

    circt_cmd, abc_cmd, target_pass_name = command_for_mode(
        command_templates, mode, lut_size, cut_size
    )

    with tempfile.TemporaryDirectory(prefix=f"passbench-{wl.name}-") as td:
        tdp = Path(td)

        circt_pass_time = None
        circt_wall = None
        circt_timings: dict[str, float] = {}
        circt_matched: list[str] = []
        abc_elapsed = None
        abc_wall = None

        if tool == "circt":
            mlir_in = tdp / "input.mlir"
            # Convert AIGER -> MLIR once, then benchmark pass execution.
            run_command(
                [circt_translate, str(wl.aig_file), "--import-aiger", "-o", str(mlir_in)]
            )

            circt_pipeline = f"builtin.module(hw.module({circt_cmd}))"
            _, circt_stderr, circt_wall = run_command(
                [
                    circt_opt,
                    str(mlir_in),
                    "--pass-pipeline",
                    circt_pipeline,
                    "--mlir-timing",
                    "--mlir-timing-display=list",
                    "-o",
                    str(tdp / "circt_out.mlir"),
                ]
            )
            circt_timings = parse_mlir_timing(circt_stderr)
            circt_pass_time, circt_matched = extract_target_pass_time(
                target_pass_name, circt_timings
            )
            if circt_pass_time is None:
                available = ", ".join(sorted(circt_timings.keys()))
                raise RuntimeError(
                    f"failed to match target pass '{target_pass_name}' in MLIR timings. "
                    f"available passes: [{available}]"
                )
        else:
            abc_script = f"read {wl.aig_file}; {abc_cmd}; time;"
            abc_stdout, abc_stderr, abc_wall = run_command([abc, "-c", abc_script])
            print(f"ABC output:\n{abc_stdout}\n{abc_stderr}")
            abc_elapsed = parse_abc_time(abc_stdout + "\n" + abc_stderr)

    if tool == "circt":
        circt_pipeline = f"builtin.module(hw.module({circt_cmd}))"
        write_result(
            output_dir,
            tool=f"circt-{mode}-pass",
            bench_name=bench_id,
            metrics={
                **common,
                "compile_time_s": circt_pass_time,
                "pass_time_s": circt_pass_time,
                "runner_wall_time_s": circt_wall,
                "matched_passes": circt_matched,
                "mlir_pass_timings_s": circt_timings,
                "pipeline": circt_pipeline,
            },
        )
    else:
        write_result(
            output_dir,
            tool=f"abc-{mode}-pass",
            bench_name=bench_id,
            metrics={
                **common,
                "compile_time_s": abc_elapsed if abc_elapsed is not None else abc_wall,
                "runner_wall_time_s": abc_wall,
                "abc_commands": abc_cmd,
            },
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Benchmark CIRCT pass compile time vs ABC equivalent commands"
    )
    parser.add_argument(
        "--benchmarks-root", type=Path, default=Path("benchmarks"), help="Benchmarks root"
    )
    parser.add_argument(
        "--output-dir", type=Path, required=True, help="Directory where results are stored"
    )
    parser.add_argument(
        "--input-aig",
        type=Path,
        default=None,
        help="Single AIG input to benchmark (enables lit-parallel per-file tests)",
    )
    parser.add_argument(
        "--name",
        default=None,
        help="Benchmark name override (default: inferred from input path)",
    )
    parser.add_argument("--mode", choices=["lut-mapping", "sop-balancing"], required=True)
    parser.add_argument("--lut-size", type=int, default=6)
    parser.add_argument("--cut-size", type=int, default=8)
    parser.add_argument(
        "--tool",
        choices=["circt", "abc"],
        default="circt",
        help="Benchmark engine to run (default: circt)",
    )
    parser.add_argument("--max-benchmarks", type=int, default=0)
    parser.add_argument("--circt-translate", default="circt-translate")
    parser.add_argument("--circt-opt", default="../build/bin/circt-opt")
    parser.add_argument(
        "--abc",
        default=None,
        help="Path to ABC executable (default: auto-detect 'abc' or 'yosys-abc')",
    )

    args = parser.parse_args()

    benchmarks_root = args.benchmarks_root.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.input_aig is not None:
        input_aig = args.input_aig
        if not input_aig.is_absolute():
            input_aig = (Path.cwd() / input_aig).resolve()
        if not input_aig.exists():
            print(f"Input AIG not found: {input_aig}", file=sys.stderr)
            return 1
        if args.name:
            name = args.name
        else:
            if len(input_aig.parts) >= 2:
                name = f"{input_aig.parent.name}_{input_aig.stem}"
            else:
                name = input_aig.stem
        workloads = [Workload(name=name, suite="lsils", aig_file=input_aig)]
    else:
        workloads = discover_lsils_workloads(benchmarks_root)
        if args.max_benchmarks > 0:
            workloads = workloads[: args.max_benchmarks]

    if not workloads:
        print("No LSILS AIG workloads discovered", file=sys.stderr)
        return 1

    circt_translate = resolve_tool(args.circt_translate)
    circt_opt = resolve_tool(args.circt_opt)
    abc = find_abc(args.abc) if args.tool == "abc" else ""
    command_templates = load_command_templates(benchmarks_root)

    failures: list[str] = []
    for wl in workloads:
        try:
            run_one(
                wl=wl,
                mode=args.mode,
                lut_size=args.lut_size,
                cut_size=args.cut_size,
                circt_translate=circt_translate,
                circt_opt=circt_opt,
                abc=abc,
                command_templates=command_templates,
                output_dir=output_dir,
                tool=args.tool,
            )
            print(f"PASS {wl.suite}/{wl.name}")
        except Exception as e:  # pragma: no cover
            failures.append(f"{wl.suite}/{wl.name}: {e}")
            print(f"FAIL {wl.suite}/{wl.name}: {e}", file=sys.stderr)

    meta = {
        "mode": args.mode,
        "lut_size": args.lut_size,
        "cut_size": args.cut_size,
        "total": len(workloads),
        "failed": len(failures),
        "failures": failures,
    }
    (output_dir / f"pass-benchmark-{args.mode}-meta.json").write_text(
        json.dumps(meta, indent=2) + "\n"
    )

    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
