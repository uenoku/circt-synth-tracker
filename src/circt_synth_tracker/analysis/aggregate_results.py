#!/usr/bin/env python3
"""
Aggregate results from synthesis tool runs into a single JSON summary.

Usage:
    aggregate-results --tool circt-synth --results-dir output/results
    aggregate-results --tool yosys --results-dir output/results -o yosys-summary.json
"""

import sys
import json
import argparse
from pathlib import Path
from datetime import datetime


def main():
    parser = argparse.ArgumentParser(
        description="Aggregate synthesis benchmark results into JSON summary"
    )
    parser.add_argument(
        "--tool", required=True, help="Tool name (circt, yosys, etc.)"
    )
    parser.add_argument(
        "--results-dir", required=True, help="Directory containing result files"
    )
    parser.add_argument(
        "-o", "--output", help="Output JSON file (default: <tool>-summary.json)"
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    args = parser.parse_args()

    results_dir = Path(args.results_dir)

    if not results_dir.exists():
        print(f"Error: Results directory not found: {results_dir}", file=sys.stderr)
        return 1

    # Default output file
    if not args.output:
        args.output = f"{args.tool}-summary.json"

    output_path = Path(args.output)

    print(f"Aggregating results for tool: {args.tool}")
    print(f"Results directory: {results_dir}")
    print(f"Output file: {output_path}")

    # Collect all JSON result files
    results = {}

    # Search for results in 'results' subdirectories
    json_files = list(results_dir.glob(f"**/results/{args.tool}/*.json"))

    if not json_files:
        print(
            f"Warning: No JSON files found in {results_dir}/**/results/",
            file=sys.stderr,
        )
        print("Trying to find all JSON files...", file=sys.stderr)
        json_files = list(results_dir.glob("**/*.json"))

    if not json_files:
        print(f"Warning: No JSON files found in {results_dir}", file=sys.stderr)

    for json_file in json_files:
        try:
            with open(json_file, "r") as f:
                data = json.load(f)
                benchmark_name = data.get("benchmark", json_file.stem)
                metrics = data.get("metrics", {})
                # Preserve category if available (from submit.py)
                if "category" in data:
                    metrics["category"] = data["category"]

                results[benchmark_name] = metrics

                if args.verbose:
                    print(f"  Processed: {benchmark_name}")
                    print(f"    Metrics: {metrics}")

        except Exception as e:
            print(f"Warning: Failed to process {json_file}: {e}", file=sys.stderr)

    # Create summary
    summary = {
        "tool": args.tool,
        "timestamp": datetime.now().isoformat(),
        "total_benchmarks": len(results),
        "benchmarks": results,
    }

    # Write summary JSON
    with open(output_path, "w") as f:
        json.dump(summary, f, indent=2)

    print(f"\nAggregated {len(results)} results")
    print(f"Summary written to: {output_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
