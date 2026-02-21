#!/usr/bin/env python3
"""
AIG optimization tool for the circt-synth-tracker framework.

Runs optional ABC commands on an AIGER file and writes the result to a
separate output path.  When no --abc-commands are given the input is copied
to the output unchanged, making this a transparent no-op in the lit pipeline.

Usage:
    run-aig-opt input.aig -o output.aig [--abc-commands "dc2; dc2;"] [--abc abc]
"""

import shutil
import sys
import argparse
from pathlib import Path

from circt_synth_tracker.tools import run_abc_commands


def main():
    parser = argparse.ArgumentParser(
        description="Optimize an AIGER file using ABC commands",
        epilog="Without --abc-commands the input is copied to the output unchanged",
    )
    parser.add_argument("input", help="Input AIGER file")
    parser.add_argument("-o", "--output", required=True, help="Output AIGER file")
    parser.add_argument(
        "--abc-commands",
        default="",
        help="Semicolon-separated ABC commands to run (e.g. 'dc2; dc2;')",
    )
    parser.add_argument(
        "--abc",
        default=None,
        help="Path to abc executable (default: auto-detect 'abc' or 'yosys-abc')",
    )

    args = parser.parse_args()

    input_file = Path(args.input)
    output_file = Path(args.output)

    if not input_file.exists():
        print(f"Error: Input file not found: {input_file}", file=sys.stderr)
        sys.exit(1)

    if args.abc_commands:
        run_abc_commands(input_file, output_file, args.abc_commands, abc_exe=args.abc)
    else:
        shutil.copy2(input_file, output_file)

    return 0


if __name__ == "__main__":
    sys.exit(main())
