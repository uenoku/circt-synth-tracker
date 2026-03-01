#!/usr/bin/env python3
"""
Test generator for lsils EPFL combinational benchmarks.

This script automatically generates lit test files for the lsils benchmarks
in both arithmetic and random_control categories.

Usage:
    ./generate_tests.py

The script reads the benchmark definitions from the `benchmarks` dict at the
bottom and generates corresponding .test files in the tests/ directory.
Each .test file:
  1. Uses circt-translate --import-aiger to convert AIGER to MLIR
  2. Runs CIRCT LUT mapping and optional ABC optimization
  3. Evaluates with the judge tool and submits results
"""

from pathlib import Path


def generate_test(benchmarks):
    """
    Generate test cases for lsils EPFL benchmarks.

    Args:
        benchmarks: Dict of {benchmark_name: (aiger_path, category)}
            - benchmark_name: Name to use in test
            - aiger_path: Relative path to .aig file (e.g. "arithmetic/adder.aig")
            - category: Category name for organization (e.g. "arithmetic", "random_control")
    """
    for name, (aiger_path, category) in benchmarks.items():
        # Generate test file content with RUN directives
        # Optionally optimizes with ABC, then evaluates with judge tool
        test = f"""RUN: %AIG_TOOL %LSILS_AIG/{aiger_path} -o %t.aig
RUN: %judge %t.aig | %submit %s --name {name}
"""

        # Write to tests/{name}.test
        test_file = Path(__file__).parent / f"tests/{name}.test"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        with open(test_file, "w") as f:
            f.write(test)
        print(f"Generated test file: tests/{name}.test")


if __name__ == "__main__":
    # Benchmark definitions: {name: (aiger_path, category)}
    # EPFL arithmetic (10 benchmarks)
    arithmetic = {
        "adder": ("arithmetic/adder.aig", "arithmetic"),
        "bar": ("arithmetic/bar.aig", "arithmetic"),
        "div": ("arithmetic/div.aig", "arithmetic"),
        "hyp": ("arithmetic/hyp.aig", "arithmetic"),
        "log2": ("arithmetic/log2.aig", "arithmetic"),
        "max": ("arithmetic/max.aig", "arithmetic"),
        "multiplier": ("arithmetic/multiplier.aig", "arithmetic"),
        "sin": ("arithmetic/sin.aig", "arithmetic"),
        "sqrt": ("arithmetic/sqrt.aig", "arithmetic"),
        "square": ("arithmetic/square.aig", "arithmetic"),
    }

    # EPFL random/control (10 benchmarks)
    random_control = {
        "arbiter": ("random_control/arbiter.aig", "random_control"),
        "cavlc": ("random_control/cavlc.aig", "random_control"),
        "ctrl": ("random_control/ctrl.aig", "random_control"),
        "dec": ("random_control/dec.aig", "random_control"),
        "i2c": ("random_control/i2c.aig", "random_control"),
        "int2float": ("random_control/int2float.aig", "random_control"),
        "mem_ctrl": ("random_control/mem_ctrl.aig", "random_control"),
        "priority": ("random_control/priority.aig", "random_control"),
        "router": ("random_control/router.aig", "random_control"),
        "voter": ("random_control/voter.aig", "random_control"),
    }

    benchmarks = {**arithmetic, **random_control}
    generate_test(benchmarks)
    print(f"Generated {len(benchmarks)} test files")
