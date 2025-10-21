"""
Submit tool for DatapathBench results.
"""

import sys
import os
import json
import argparse
from pathlib import Path
from datetime import datetime


def main():
    parser = argparse.ArgumentParser(description="Submit benchmark results")
    parser.add_argument("test_file", nargs="?", help="Test file path (optional)")
    parser.add_argument("--name", required=True, help="Benchmark name")
    parser.add_argument("--tool", help="Tool name (default: auto-detect from env)")
    parser.add_argument("--output-dir", help="Output directory for results")

    args = parser.parse_args()

    # Read the JSON statistics from stdin (output from %judge)
    input_data = sys.stdin.read().strip()

    # Parse the JSON from judge
    try:
        judge_data = json.loads(input_data)
    except json.JSONDecodeError:
        # Fallback: treat as raw text if not JSON
        judge_data = {"raw_output": input_data}

    # Determine tool name
    tool_name = args.tool or os.environ.get("synth_tool", "unknown")
    category = "unknown"
    if args.test_file:
        for part in args.test_file.split("/")[:-1][::-1]:
            if part != "tests" and part != "Output":
                category = part
                break

    # Create result record
    results = {
        "benchmark": args.name,
        "tool": tool_name,
        "test_file": args.test_file,
        "timestamp": datetime.now().isoformat(),
        "metrics": judge_data,
        "category": category,
    }

    # Determine output directory
    if args.output_dir:
        results_dir = Path(args.output_dir)
    else:
        # Default: use results directory in current working directory
        results_dir = Path.cwd() / "results" / tool_name

    results_dir.mkdir(parents=True, exist_ok=True)

    # Save result file
    results_file = results_dir / f"{args.name}.json"
    with open(results_file, "w") as f:
        json.dump(results, f, indent=2)

    print(f"Results saved: {results_file}", file=sys.stderr)

    # Also output to stdout for piping
    print(json.dumps(results, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main())
