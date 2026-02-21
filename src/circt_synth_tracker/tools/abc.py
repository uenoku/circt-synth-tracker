#!/usr/bin/env python3
"""
ABC synthesis wrapper for the circt-synth-tracker framework.

This tool provides a unified interface for ABC synthesis, compatible
with the aig-judge interface. It generates netlists from aiger input.
"""

import sys
import re
import subprocess
import argparse
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
import json

from circt_synth_tracker.tools import find_abc


def run_command(cmd, description, shell=False):
    """Run a command and handle errors."""
    # print(f"Running: {cmd if isinstance(cmd, str) else ' '.join(cmd)}", file=sys.stderr)
    result = subprocess.run(cmd, capture_output=True, text=True, shell=shell)

    if result.returncode != 0:
        print(f"Error during {description}:", file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        sys.exit(result.returncode)

    return result

def grep_stat(input, pattern, group=1):
    """Extract a number from a file using a regex pattern."""
    m = re.search(pattern, input)
    if m:
        return m.group(group)
    return "unknown"



@dataclass
class BenchmarkResult:
    filename: str
    num_gates: int
    num_inputs: int
    num_outputs: int
    depth: int
    area_asap: float
    delay_asap: float
    area_sky: float
    delay_sky: float
    success: bool
    error_message: str = ""


def to_json_string(r: BenchmarkResult) -> str:
    """Convert BenchmarkResult to JSON string."""
    data = {
        "filename": r.filename,
        "gates": r.num_gates,
        "num_inputs": r.num_inputs,
        "num_outputs": r.num_outputs,
        "depth": r.depth,
        "area_asap7": r.area_asap,
        "delay_asap7": r.delay_asap,
        "area_sky130": r.area_sky,
        "delay_sky130": r.delay_sky,
        "success": r.success,
    }

    if not r.success:
        data["error"] = r.error_message

    return json.dumps(data, indent=2)

def main():
    parser = argparse.ArgumentParser(
        description="Technology map AIGER file using ABC",
        epilog="This tool provides an ABC wrapper compatible with aig-judge",
    )
    parser.add_argument("input", help="Input AIGER file")
    parser.add_argument(
        "--abc",
        default=None,
        help="Path to abc executable (default: auto-detect 'abc' or 'yosys-abc')",
    )

    args = parser.parse_args()

    input_file = Path(args.input)
    abc_exe = find_abc(args.abc)

    if not input_file.exists():
        print(f"Error: Input file not found: {input_file}", file=sys.stderr)
        sys.exit(1)

    # Run ABC - asap7
    # Take libraries from judge-build directory
    script_dir = Path(__file__).parent
    project_root = script_dir.parent.parent.parent
    asap7_path = project_root / "judge-build" / "_deps" / "mockturtle-src" / "experiments" / "cell_libraries" / "multioutput.genlib"
    sky130_path = project_root / "judge-build" / "_deps" / "mockturtle-src" / "experiments" / "cell_libraries" / "sky130.genlib"

    assert asap7_path.exists(), f'Need to build aig-judge first. Unable to find ASAP7 library: {asap7_path}'
    result = run_command([abc_exe, "-c",  f'read_genlib {asap7_path}; read {input_file}; strash; map; print_stats;'], "ABC Tech Mapping ASAP7")
    # Extract I/O counts from the output line: "i/o =   64/   32"
    io_match = re.search(r'i/o\s+=\s*(\d+)/\s*(\d+)', result.stdout)
    num_inputs = int(io_match.group(1)) if io_match else 0
    num_outputs = int(io_match.group(2)) if io_match else 0
    num_gates = grep_stat(result.stdout, r'nd\s+=\s*([0-9.]+)')
    num_levels = grep_stat(result.stdout, r'lev\s+=\s*([0-9.]+)')
    area_asap = grep_stat(result.stdout, r'area\s+=\s*([0-9.]+)')
    delay_asap = grep_stat(result.stdout, r'delay\s+=\s*([0-9.]+)')

    # Run ABC - sky130
    assert sky130_path.exists(), f'Need to build aig-judge first. Unable to find Sky130 library: {sky130_path}'
    result = run_command([abc_exe, "-c",  f'read_genlib {sky130_path}; read {input_file}; strash; map; print_stats;'], "ABC Tech Mapping")
    area_sky = grep_stat(result.stdout, r'area\s+=\s*([0-9.]+)')
    delay_sky = grep_stat(result.stdout, r'delay\s+=\s*([0-9.]+)')

    # Create BenchmarkResult
    benchmark = BenchmarkResult(
        filename=str(input_file),
        num_gates=int(num_gates),
        num_inputs=num_inputs,
        num_outputs=num_outputs,
        depth=int(num_levels),
        area_asap=float(area_asap),
        delay_asap=float(delay_asap),
        area_sky=float(area_sky),
        delay_sky=float(delay_sky),
        success=True
    )

    print(to_json_string(benchmark))


    return 0

if __name__ == "__main__":
    sys.exit(main())
