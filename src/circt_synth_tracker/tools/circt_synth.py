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

import sys
import os
import subprocess
import argparse
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

        print("Step 2: Synthesizing MLIR...", file=sys.stderr)
        result = run_command(synth_cmd, "MLIR synthesis")

        # Write synthesized MLIR to temporary file
        with open(synth_mlir_file, "w") as f:
            f.write(result.stdout)

        print(f"  Generated synthesized MLIR: {synth_mlir_file}", file=sys.stderr)

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

        print(f"  Generated AIG: {output_file}", file=sys.stderr)
        print(f"Success! Generated {output_file}", file=sys.stderr)

    finally:
        # Clean up temporary MLIR files if not keeping them
        if not keep_mlir and mlir_file.exists():
            mlir_file.unlink()
        if not keep_synth_mlir and synth_mlir_file.exists():
            synth_mlir_file.unlink()

    return 0


if __name__ == "__main__":
    sys.exit(main())
