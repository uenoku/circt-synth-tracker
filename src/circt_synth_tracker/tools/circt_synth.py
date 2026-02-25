#!/usr/bin/env python3
"""
sv_to_aig: Wrapper tool to convert SystemVerilog to AIG format.

This tool chains CIRCT tools:
  1. circt-verilog: Parse SystemVerilog to MLIR
  2. circt-synth: Synthesize MLIR
  3. circt-translate --export-aiger: Export synthesized MLIR to AIG format

Usage:
    sv_to_aig input.sv [options] -o output.aig
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path


def run_command(cmd, description):
    """Run a command and handle errors."""
    print(f"Running: {' '.join(cmd)}", file=sys.stderr)
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"Error during {description}:", file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        sys.exit(result.returncode)

    return result


def _tv_sort_key(p):
    """Sort key for MLIR pass output files by their numeric prefix (e.g. 0_10_ -> (0,10))."""
    m = re.match(r"^(\d+)_(\d+)_", p.name)
    if m:
        return (int(m.group(1)), int(m.group(2)))
    m = re.match(r"^(\d+)_", p.name)
    if m:
        return (int(m.group(1)), float("inf"))
    return (float("inf"), float("inf"))


def _run_lec_pair(args, from_file, to_file, smt_output_path=None):
    """Run circt-lec on a pair of MLIR files and return status string.

    Emits SMT-LIB via circt-lec --emit-smtlib and pipes to args.tv_solver.
    Returns one of: "equiv", "non-equiv", "error", "timeout".
    """
    lec_base = [args.circt_lec, str(from_file), str(to_file)]
    if args.top:
        lec_base.extend(["--c1", args.top, "--c2", args.top])

    lec_cmd = lec_base + ["--emit-smtlib"]
    solver_cmd = args.tv_solver.split()
    # Handle common solvers that need specific flags for stdin
    if solver_cmd[0] == "z3" and "-in" not in solver_cmd:
        solver_cmd.append("-in")
    try:
        lec_proc = subprocess.run(lec_cmd, capture_output=True)
        if smt_output_path is not None:
            smt_output_path.parent.mkdir(parents=True, exist_ok=True)
            smt_output_path.write_bytes(lec_proc.stdout)
        if lec_proc.returncode != 0:
            print(
                f"    circt-lec error: {lec_proc.stderr.decode()[:200]}",
                file=sys.stderr,
            )
            return "error"
        solver_result = subprocess.run(
            solver_cmd,
            input=lec_proc.stdout,
            capture_output=True,
            timeout=args.tv_timeout,
        )
        out = solver_result.stdout.decode()
        if "unsat" in out:
            return "equiv"
        elif "sat" in out:
            return "non-equiv"
        else:
            print(f"    Solver unexpected output: {out[:200]}", file=sys.stderr)
            return "error"
    except subprocess.TimeoutExpired:
        return "timeout"


def run_tv(
    args, mlir_file, synth_mlir_file, output_file, tree_dir, keep_artifacts=False
):
    """Run translation validation between consecutive pass outputs using circt-lec.

    Collects all .mlir files under tree_dir, sorts them by their numeric prefix,
    then runs circt-lec --emit-smtlib piped to args.tv_solver between each
    consecutive pair in the sequence:
        input.mlir -> 0_0_... -> 0_1_... -> ... -> synth_output.mlir
    """
    if not args.tv_solver:
        print(
            "Error: --tv-solver is required when using --run-tv (e.g. --tv-solver bitwuzla)",
            file=sys.stderr,
        )
        sys.exit(1)

    tree_files = sorted(Path(tree_dir).rglob("*.mlir"), key=_tv_sort_key)

    sequence = [mlir_file] + tree_files + [synth_mlir_file]

    smt_dir = None
    if keep_artifacts:
        smt_dir = Path(tree_dir) / "tv-smt"
        smt_dir.mkdir(parents=True, exist_ok=True)

    tv_results = []
    overall_status = "pass"
    failed_pairs = []

    for i, (from_file, to_file) in enumerate(zip(sequence, sequence[1:])):
        print(f"  TV: {from_file.name} -> {to_file.name}", file=sys.stderr)
        smt_output_path = None
        if smt_dir is not None:
            smt_name = f"{i:03d}_{from_file.stem}_to_{to_file.stem}.smt2"
            smt_output_path = smt_dir / smt_name
        status = _run_lec_pair(args, from_file, to_file, smt_output_path)
        if status == "non-equiv":
            overall_status = "fail"
            failed_pairs.append((from_file, to_file))
            print("    NON-EQUIV detected!", file=sys.stderr)
        elif status == "timeout":
            print(f"    Timeout after {args.tv_timeout}s", file=sys.stderr)
        if status not in ("equiv", "non-equiv") and overall_status not in ("fail",):
            overall_status = "error"

        tv_results.append(
            {"from": from_file.name, "to": to_file.name, "status": status}
        )

    tv_sidecar = Path(str(output_file) + ".tv")
    tv_sidecar.write_text(
        json.dumps({"tv_status": overall_status, "tv_results": tv_results}, indent=2)
        + "\n"
    )
    print(f"  TV: overall_status={overall_status}, wrote {tv_sidecar}", file=sys.stderr)

    # Preserve failed MLIR pairs for debugging (only on non-equiv, not timeout)
    if failed_pairs:
        import shutil

        tv_pair_dir = Path(str(output_file) + ".tv-pairs")
        tv_pair_dir.mkdir(parents=True, exist_ok=True)
        reproduce_lines = [
            "#!/usr/bin/env bash",
            "# Reproducer for TV non-equiv failures",
            "",
            f'TOP_MODULE="{args.top}"',
            "",
        ]

        # Normalize solver command for reproduce.sh
        solver_cmd = args.tv_solver
        if solver_cmd.split()[0] == "z3" and "-in" not in solver_cmd:
            solver_cmd = f"{args.tv_solver} -in"

        for i, (from_file, to_file) in enumerate(failed_pairs):
            shutil.copy2(from_file, tv_pair_dir / from_file.name)
            shutil.copy2(to_file, tv_pair_dir / to_file.name)

            reproduce_lines.append(f"# Pair {i}: {from_file.name} -> {to_file.name}")
            cmd = f'circt-lec {from_file.name} {to_file.name} --c1 "$TOP_MODULE" --c2 "$TOP_MODULE" --emit-smtlib | {solver_cmd}'
            reproduce_lines.append(cmd)
            reproduce_lines.append("")

        (tv_pair_dir / "reproduce.sh").write_text("\n".join(reproduce_lines))
        (tv_pair_dir / "reproduce.sh").chmod(0o755)
        print(
            f"  TV: preserved {len(failed_pairs)} failed pair(s) at {tv_pair_dir}",
            file=sys.stderr,
        )

    if keep_artifacts and smt_dir is not None:
        print(f"  TV: kept SMT inputs in {smt_dir}", file=sys.stderr)

    return overall_status


def main():
    parser = argparse.ArgumentParser(
        description="Convert SystemVerilog to AIG format",
        epilog="This tool chains circt-verilog, circt-synth, and circt-translate",
    )
    parser.add_argument("input", help="Input SystemVerilog file")
    parser.add_argument("-o", "--output", required=True, help="Output AIG file")
    parser.add_argument("-top", "--top-module", dest="top", help="Top module name")
    parser.add_argument(
        "--bw", "--bitwidth", dest="bitwidth", type=int, help="Bitwidth for operations"
    )
    parser.add_argument(
        "--circt-verilog", default="circt-verilog", help="Path to circt-verilog"
    )
    parser.add_argument(
        "--circt-synth", default="circt-synth", help="Path to circt-synth"
    )
    parser.add_argument(
        "--circt-translate", default="circt-translate", help="Path to circt-translate"
    )
    parser.add_argument("--circt-lec", default="circt-lec", help="Path to circt-lec")
    parser.add_argument(
        "--run-lec",
        action="store_true",
        help="Run circt-lec to verify equivalence between pre-synth and post-synth MLIR",
    )
    parser.add_argument(
        "--lec-timeout",
        type=int,
        default=10,
        help="Timeout in seconds for circt-lec (default: 10)",
    )
    parser.add_argument(
        "--run-tv",
        action="store_true",
        help=(
            "Run translation validation: dump per-pass MLIR via --mlir-print-ir-tree-dir "
            "and verify equivalence between consecutive pass outputs using circt-lec"
        ),
    )
    parser.add_argument(
        "--tv-timeout",
        type=int,
        default=10,
        help="Timeout in seconds per circt-lec invocation during TV (default: 10)",
    )
    parser.add_argument(
        "--tv-solver",
        default="",
        help=(
            "External SMT solver command for TV (e.g. 'z3 -in' or 'bitwuzla'). "
            "Required when --run-tv is used. "
            "circt-lec --emit-smtlib output is piped to this solver; "
            "unsat=equiv, sat=non-equiv."
        ),
    )
    parser.add_argument(
        "--keep-tv-artifacts",
        action="store_true",
        help="Keep translation validation MLIR dumps and SMT-LIB inputs for debugging",
    )
    parser.add_argument(
        "--keep-mlir", action="store_true", help="Keep intermediate MLIR files"
    )
    parser.add_argument(
        "--mlir-output", help="Output path for intermediate MLIR file (after verilog)"
    )
    parser.add_argument(
        "--synth-mlir-output",
        help="Output path for synthesized MLIR file (after synth)",
    )
    parser.add_argument(
        "--circt-synth-extra-args",
        default="",
        help="Additional synthesis options for circt-synth",
    )
    args, extra_args = parser.parse_known_args()

    input_file = Path(args.input)
    output_file = Path(args.output)

    if not input_file.exists():
        print(f"Error: Input file not found: {input_file}", file=sys.stderr)
        sys.exit(1)

    # Create temporary files for intermediate MLIR if not specified
    if args.mlir_output:
        mlir_file = Path(args.mlir_output)
        keep_mlir = True
    else:
        mlir_fd, mlir_path = tempfile.mkstemp(suffix=f"{input_file.stem}.mlir")
        os.close(mlir_fd)
        mlir_file = Path(mlir_path)
        keep_mlir = args.keep_mlir

    if args.synth_mlir_output:
        synth_mlir_file = Path(args.synth_mlir_output)
        keep_synth_mlir = True
    else:
        synth_mlir_fd, synth_mlir_path = tempfile.mkstemp(suffix=".synth.mlir")
        os.close(synth_mlir_fd)
        synth_mlir_file = Path(synth_mlir_path)
        keep_synth_mlir = args.keep_mlir

    tv_tree_dir = None
    try:
        # Step 1: Convert SystemVerilog to MLIR using circt-verilog
        verilog_cmd = [args.circt_verilog, str(input_file)]
        if args.top:
            verilog_cmd.extend(["-top", args.top])
        if args.bitwidth:
            verilog_cmd.extend(["-G", f"BW={args.bitwidth}"])
        verilog_cmd.extend(extra_args)

        print("Step 1: Converting SystemVerilog to MLIR...", file=sys.stderr)
        result = run_command(verilog_cmd, "SystemVerilog parsing")

        # Write MLIR to temporary file
        with open(mlir_file, "w") as f:
            f.write(result.stdout)

        print(f"  Generated MLIR: {mlir_file}", file=sys.stderr)

        # Step 2: Synthesize MLIR using circt-synth
        synth_cmd = [args.circt_synth, str(mlir_file)]
        if args.circt_synth_extra_args:
            synth_cmd.extend(args.circt_synth_extra_args.split())

        if args.run_tv:
            if args.keep_tv_artifacts:
                import shutil

                tv_tree_dir = Path(str(output_file) + ".tv-ir-tree")
                shutil.rmtree(tv_tree_dir, ignore_errors=True)
                tv_tree_dir.mkdir(parents=True, exist_ok=True)
            else:
                tv_tree_dir = tempfile.mkdtemp(suffix="-tv-ir-tree")
            synth_cmd.extend(
                [
                    f"--mlir-print-ir-tree-dir={tv_tree_dir}",
                    "-mlir-print-ir-after-all",
                    "-mlir-print-ir-after-change",
                ]
            )
            print(f"  TV: dumping per-pass IR to {tv_tree_dir}", file=sys.stderr)

        print("Step 2: Synthesizing MLIR...", file=sys.stderr)
        result = run_command(synth_cmd, "MLIR synthesis")

        # Write synthesized MLIR to temporary file
        with open(synth_mlir_file, "w") as f:
            f.write(result.stdout)

        print(f"  Generated synthesized MLIR: {synth_mlir_file}", file=sys.stderr)

        # Step 2b: Run LEC if requested
        if args.run_lec:
            lec_cmd = [
                args.circt_lec,
                str(mlir_file),
                str(synth_mlir_file),
                "--run",
            ]
            if args.top:
                lec_cmd.extend(["--c1", args.top, "--c2", args.top])

            print("Step 2b: Running LEC (circt-lec)...", file=sys.stderr)
            lec_sidecar = Path(str(output_file) + ".lec")
            try:
                lec_result = subprocess.run(
                    lec_cmd, capture_output=True, text=True, timeout=args.lec_timeout
                )
                output = lec_result.stdout + lec_result.stderr
                if "c1 == c2" in output:
                    lec_status = "equiv"
                    print("  LEC: EQUIV.", file=sys.stderr)
                elif "c1 != c2" in output:
                    lec_status = "non-equiv"
                    print("  LEC: NON-EQUIV.", file=sys.stderr)
                    print(output, file=sys.stderr)
                else:
                    lec_status = "error"
                    print("  LEC: TOOL ERROR.", file=sys.stderr)
                    print(output, file=sys.stderr)
                lec_sidecar.write_text(f'{{"lec_status": "{lec_status}"}}\n')
            except subprocess.TimeoutExpired:
                print(f"  LEC: TIMEOUT after {args.lec_timeout}s.", file=sys.stderr)
                lec_sidecar.write_text('{"lec_status": "timeout"}\n')

        # Step 2c: Run translation validation if requested
        if args.run_tv and tv_tree_dir:
            print("Step 2c: Running translation validation (TV)...", file=sys.stderr)
            run_tv(
                args,
                mlir_file,
                synth_mlir_file,
                output_file,
                tv_tree_dir,
                args.keep_tv_artifacts,
            )

        # Step 3: Export to AIG using circt-translate
        translate_cmd = [
            args.circt_translate,
            str(synth_mlir_file),
            "--export-aiger",
            "-o",
            str(output_file),
        ]

        print("Step 3: Exporting to AIG...", file=sys.stderr)
        run_command(translate_cmd, "AIG export")

        print(f"Success! Generated {output_file}", file=sys.stderr)

    finally:
        # Clean up temporary MLIR files if not keeping them
        if not keep_mlir and mlir_file.exists():
            mlir_file.unlink()
        if not keep_synth_mlir and synth_mlir_file.exists():
            synth_mlir_file.unlink()
        # Clean up TV tree dir
        if tv_tree_dir is not None:
            if args.keep_tv_artifacts:
                print(
                    f"  TV: keeping per-pass IR tree at {tv_tree_dir}", file=sys.stderr
                )
            else:
                import shutil

                shutil.rmtree(tv_tree_dir, ignore_errors=True)

    return 0


if __name__ == "__main__":
    sys.exit(main())
