#!/usr/bin/env python3
"""
run-abc-opt: Optimize an AIGER file using ABC commands.

Runs optional ABC commands on an AIGER file and writes the result to a
separate output path.  When no --abc-commands are given the input is copied
to the output unchanged, making this a transparent no-op in the lit pipeline.

An abc.rc file is auto-loaded from the benchmarks/ directory if present,
allowing aliases to be defined and referenced in --abc-commands.

Usage:
    run-abc-opt input.aig -o output.aig [--abc-commands "compress2rs;"] [--abc abc]
"""

import shutil
import sys
import argparse
from pathlib import Path

from circt_synth_tracker.tools import run_abc_commands

# Auto-detect abc.rc relative to the project root (benchmarks/abc.rc)
_PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
DEFAULT_ABC_RC = _PROJECT_ROOT / "benchmarks" / "abc.rc"


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
        help="Semicolon-separated ABC commands to run (e.g. 'compress2rs;')",
    )
    parser.add_argument(
        "--abc",
        default=None,
        help="Path to abc executable (default: auto-detect 'abc' or 'yosys-abc')",
    )
    parser.add_argument(
        "--abc-rc",
        default=None,
        help=f"ABC script file loaded via -F before commands (default: {DEFAULT_ABC_RC} if it exists)",
    )

    args = parser.parse_args()

    input_file = Path(args.input)
    output_file = Path(args.output)

    if not input_file.exists():
        print(f"Error: Input file not found: {input_file}", file=sys.stderr)
        sys.exit(1)

    # Resolve rc file: explicit arg > auto-detected default
    rc_file = Path(args.abc_rc) if args.abc_rc else DEFAULT_ABC_RC
    if rc_file.exists():
        print(f"Loading ABC rc file: {rc_file}", file=sys.stderr)
    else:
        rc_file = None

    if args.abc_commands:
        run_abc_commands(input_file, output_file, args.abc_commands,
                         abc_exe=args.abc, rc_file=rc_file)
    else:
        shutil.copy2(input_file, output_file)

    return 0


if __name__ == "__main__":
    sys.exit(main())
