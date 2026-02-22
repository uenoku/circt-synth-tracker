#!/usr/bin/env python3
"""
Yosys synthesis wrapper for the circt-synth-tracker framework.

This tool provides a unified interface for Yosys synthesis, compatible
with the circt-synth interface. It generates AIG output from SystemVerilog input.
"""

import sys
import os
import subprocess
import argparse
import tempfile
from pathlib import Path


def run_command(cmd, description, shell=False):
    """Run a command and handle errors."""
    print(f"Running: {cmd if isinstance(cmd, str) else ' '.join(cmd)}", file=sys.stderr)
    result = subprocess.run(cmd, capture_output=True, text=True, shell=shell)

    if result.returncode != 0:
        print(f"Error during {description}:", file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        sys.exit(result.returncode)

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Synthesize SystemVerilog using Yosys",
        epilog="This tool provides a Yosys wrapper compatible with circt-synth",
    )
    parser.add_argument("input", help="Input SystemVerilog file")
    parser.add_argument("-o", "--output", required=True, help="Output AIG file")
    parser.add_argument("-top", "--top-module", dest="top", help="Top module name")
    parser.add_argument(
        "--bw",
        "--bitwidth",
        dest="bitwidth",
        type=int,
        help="Bitwidth for BW parameter",
    )
    parser.add_argument("--yosys", default="yosys", help="Path to yosys")

    args = parser.parse_args()

    input_file = Path(args.input)
    output_file = Path(args.output)

    if not input_file.exists():
        print(f"Error: Input file not found: {input_file}", file=sys.stderr)
        sys.exit(1)

    # Generate Yosys script
    script_fd, script_path = tempfile.mkstemp(suffix=".ys")
    os.close(script_fd)
    script_file = Path(script_path)

    script_content = generate_yosys_script(
        input_file=input_file,
        output_file=output_file,
        top_module=args.top,
        bitwidth=args.bitwidth,
    )

    with open(script_file, "w") as f:
        f.write(script_content)

    print(f"Generated Yosys script: {script_file}", file=sys.stderr)

    try:
        # Run Yosys
        yosys_cmd = [args.yosys, "-s", str(script_file)]

        print("Running Yosys synthesis...", file=sys.stderr)
        result = run_command(yosys_cmd, "Yosys synthesis")

        # Print Yosys output
        if result.stdout:
            print(result.stdout, file=sys.stderr)

        if output_file.exists():
            print(f"Success! Generated {output_file}", file=sys.stderr)
        else:
            print(
                f"Error: Output file was not generated: {output_file}", file=sys.stderr
            )
            sys.exit(1)

    finally:
        # Clean up temporary script file
        if script_file.exists():
            script_file.unlink()

    return 0


def generate_yosys_script(input_file, output_file, top_module, bitwidth):
    """Generate a Yosys synthesis script for AIG output."""

    script = []

    # Read input file (use -sv for SystemVerilog support)
    script.append("# Read input file")
    script.append(f"read_verilog -sv {input_file}")
    script.append("")

    # Set hierarchy if top module specified
    if top_module:
        script.append("# Set top module")
        chparam_opts = ""
        if bitwidth is not None:
            chparam_opts = f" -chparam BW {bitwidth}"
        script.append(f"hierarchy -top {top_module}{chparam_opts}")
        script.append("")
    else:
        script.append("# Auto-detect hierarchy")
        script.append("hierarchy -auto-top")
        script.append("")

    # Synthesis
    script.append("# Synthesis")
    script.append("synth")
    script.append("")

    # Output as AIG
    script.append("# Write AIG output")
    script.append("aigmap")
    script.append(f"write_aiger -symbols {output_file}")

    return "\n".join(script)


if __name__ == "__main__":
    sys.exit(main())
