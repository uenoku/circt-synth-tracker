#!/usr/bin/env python3
"""Generate DatapathBench AIG fixtures from SystemVerilog sources."""

from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
from pathlib import Path


BENCHMARKS = [
    "DotProduct",
    "DotProductSgn",
    "Fma",
    "FmaSgn",
    "Fmaa",
    "FmaaSgn",
    "FmaShare",
    "FmaShareSgn",
]

WIDTHS = [16, 48]


def benchmark_sv(datapathbench_root: Path, top: str) -> Path:
    return datapathbench_root / "benchmarks" / top / "sv" / f"{top}.sv"


def fixture_name(top: str, bw: int) -> str:
    return f"{top}_{bw}"


def run_command(cmd: list[str]) -> None:
    print("Running:", " ".join(cmd), file=sys.stderr)
    subprocess.run(cmd, check=True)


def write_pass_tests(pass_tests_dir: Path,
                     benchmarks: list[tuple[str, int, Path]]) -> None:
    pass_tests_dir.mkdir(parents=True, exist_ok=True)
    for top, bw, _ in benchmarks:
        name = fixture_name(top, bw)
        benchmark_name = f"datapathbench_{name}"
        test_file = pass_tests_dir / f"{benchmark_name}.test"
        test_file.write_text(
            "RUN: run-pass-benchmark --benchmarks-root %S/../.. --output-dir %T "
            "--mode lut-mapping --lut-size %PASS_LUT_SIZE "
            "--cut-size %PASS_CUT_SIZE --tool %PASS_TOOL "
            f"--input-aig %DATAPATHBENCH_AIG/{name}.aig "
            f"--name {benchmark_name} --suite datapathbench\n"
            "RUN: run-pass-benchmark --benchmarks-root %S/../.. --output-dir %T "
            "--mode sop-balancing --lut-size %PASS_LUT_SIZE "
            "--cut-size %PASS_CUT_SIZE --tool %PASS_TOOL "
            f"--input-aig %DATAPATHBENCH_AIG/{name}.aig "
            f"--name {benchmark_name} --suite datapathbench\n"
        )


def main() -> int:
    benchmarks_root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(
        description="Lower DatapathBench SV files to checked-in AIG fixtures."
    )
    parser.add_argument(
        "--datapathbench-root",
        type=Path,
        default=benchmarks_root / "comb" / "DatapathBench" / "DatapathBench",
        help="DatapathBench checkout root",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parent / "benchmarks",
        help="Directory where generated .aig files are written",
    )
    parser.add_argument(
        "--bw",
        action="append",
        type=int,
        default=[],
        help=(
            "BW parameter passed to DatapathBench modules; may be repeated "
            f"(default: {','.join(str(bw) for bw in WIDTHS)})"
        ),
    )
    parser.add_argument(
        "--run-circt-synth",
        default="run-circt-synth",
        help="SV-to-AIG wrapper command",
    )
    parser.add_argument("--circt-verilog", default="circt-verilog")
    parser.add_argument("--circt-synth", default="circt-synth")
    parser.add_argument("--circt-translate", default="circt-translate")
    parser.add_argument(
        "--pass-tests-dir",
        type=Path,
        default=benchmarks_root / "pass" / "tests",
        help="Directory where pass-benchmark .test files are written",
    )
    parser.add_argument(
        "--skip-pass-tests",
        action="store_true",
        help="Only generate AIG fixtures, leaving pass tests untouched",
    )

    args = parser.parse_args()
    datapathbench_root = args.datapathbench_root.resolve()
    output_dir = args.output_dir.resolve()
    widths = args.bw or WIDTHS

    benchmarks = [
        (top, bw, benchmark_sv(datapathbench_root, top)) for bw in widths
        for top in BENCHMARKS
    ]
    missing = [str(sv_file) for _, _, sv_file in benchmarks if not sv_file.exists()]
    if missing:
        print("Missing DatapathBench SV file(s):", file=sys.stderr)
        for sv_file in missing:
            print(f"  {sv_file}", file=sys.stderr)
        return 1

    output_dir.mkdir(parents=True, exist_ok=True)
    for top, bw, sv_file in benchmarks:
        output_file = output_dir / f"{fixture_name(top, bw)}.aig"
        run_command(
            [
                *shlex.split(args.run_circt_synth),
                str(sv_file),
                "--bw",
                str(bw),
                "-top",
                top,
                "--circt-verilog",
                args.circt_verilog,
                "--circt-synth",
                args.circt_synth,
                "--circt-translate",
                args.circt_translate,
                "-o",
                str(output_file),
            ]
        )

    if not args.skip_pass_tests:
        write_pass_tests(args.pass_tests_dir.resolve(), benchmarks)

    print(f"Generated {len(benchmarks)} DatapathBench AIG fixture(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
