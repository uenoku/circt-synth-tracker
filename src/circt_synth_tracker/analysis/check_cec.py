#!/usr/bin/env python3
"""
Combinational equivalence check between two synthesis summary files.

Usage:
    check-cec circt-summary.json yosys-summary.json -o cec.json
"""

import sys
import json
import argparse
from pathlib import Path

from circt_synth_tracker.analysis.compare_results import _run_one_cec
from circt_synth_tracker.tools import find_abc


def run_cec(summaries, abc_exe=None, jobs=None):
    """Run CEC between the first two tools in summaries. Returns status_map dict."""
    import os
    from concurrent.futures import ThreadPoolExecutor, as_completed

    try:
        abc = find_abc(abc_exe)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return {}

    tool_names = list(summaries.keys())
    if len(tool_names) < 2:
        print("Error: Need at least 2 tools for equivalence check", file=sys.stderr)
        return {}

    all_benchmarks = set()
    for summary in summaries.values():
        all_benchmarks.update(summary.get("benchmarks", {}).keys())

    print(f"\n=== Equivalence Check ({tool_names[0]} vs {tool_names[1]}) ===\n")

    results = {"equivalent": [], "not_equivalent": [], "missing": [], "error": [], "timeout": []}

    to_check = []
    for benchmark_name in sorted(all_benchmarks):
        aig_files = {}
        for tool_name in tool_names[:2]:
            bdata = summaries[tool_name].get("benchmarks", {}).get(benchmark_name, {})
            aig_path = bdata.get("filename")
            if aig_path:
                aig_files[tool_name] = aig_path

        if len(aig_files) < 2:
            missing = [t for t in tool_names[:2] if t not in aig_files]
            print(f"  SKIP  {benchmark_name} (no AIG for: {', '.join(missing)})")
            results["missing"].append(benchmark_name)
            continue

        aig1 = aig_files[tool_names[0]]
        aig2 = aig_files[tool_names[1]]

        missing_files = [p for p in (aig1, aig2) if not Path(p).exists()]
        if missing_files:
            print(f"  SKIP  {benchmark_name} (file not found: {', '.join(missing_files)})")
            results["missing"].append(benchmark_name)
            continue

        to_check.append((benchmark_name, aig1, aig2))

    workers = jobs if jobs is not None else (os.cpu_count() or 1)
    workers = max(1, workers)

    if workers == 1:
        cec_results = [_run_one_cec(abc, name, a1, a2) for name, a1, a2 in to_check]
    else:
        print(f"Running {len(to_check)} checks with {workers} parallel workers...\n")
        cec_results = [None] * len(to_check)
        name_to_idx = {name: i for i, (name, _, _) in enumerate(to_check)}
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(_run_one_cec, abc, name, a1, a2): name
                for name, a1, a2 in to_check
            }
            for future in as_completed(futures):
                result = future.result()
                benchmark_name, status, detail, output = result
                if output and status != "equivalent":
                    print(f"[cec] {benchmark_name}:\n{output}", file=sys.stderr)
                cec_results[name_to_idx[benchmark_name]] = result

    for benchmark_name, status, detail, output in cec_results:
        if output and status != "equivalent":
            print(f"[cec] {benchmark_name}:\n{output}", file=sys.stderr)
        if status == "equivalent":
            print(f"  PASS    {benchmark_name}")
            results["equivalent"].append(benchmark_name)
        elif status == "not_equivalent":
            print(f"  FAIL    {benchmark_name}")
            results["not_equivalent"].append(benchmark_name)
        elif status == "timeout":
            print(f"  TIMEOUT {benchmark_name}")
            results["timeout"].append(benchmark_name)
        else:
            print(f"  ERR     {benchmark_name} ({detail})")
            results["error"].append(benchmark_name)

    total = len(all_benchmarks)
    print(
        f"\nSummary: {len(results['equivalent'])} equivalent, "
        f"{len(results['not_equivalent'])} not equivalent, "
        f"{len(results['timeout'])} timeout, "
        f"{len(results['missing'])} skipped, "
        f"{len(results['error'])} errors  (total {total})"
    )

    if results["not_equivalent"]:
        print("\nNot equivalent:")
        for name in results["not_equivalent"]:
            print(f"  {name}")

    status_map = {}
    for category, names in results.items():
        for name in names:
            status_map[name] = category

    return status_map


def main():
    parser = argparse.ArgumentParser(
        description="Run combinational equivalence check between two synthesis summary files"
    )
    parser.add_argument("summaries", nargs=2, help="Two JSON summary files to compare")
    parser.add_argument("-o", "--output", help="Output CEC results to JSON file")
    parser.add_argument(
        "--abc", default=None,
        help="Path to ABC executable (default: auto-detect 'abc' or 'yosys-abc')"
    )
    parser.add_argument(
        "-j", "--jobs", type=int, default=None,
        help="Number of parallel checks (default: number of available CPU cores)"
    )

    args = parser.parse_args()

    summaries = {}
    for summary_file in args.summaries:
        path = Path(summary_file)
        if not path.exists():
            print(f"Error: File not found: {path}", file=sys.stderr)
            return 1
        try:
            with open(path) as f:
                data = json.load(f)
                tool_name = data.get("tool", path.stem)
                summaries[tool_name] = data
        except Exception as e:
            print(f"Error loading {path}: {e}", file=sys.stderr)
            return 1

    status_map = run_cec(summaries, args.abc, args.jobs)

    if args.output:
        output = {"benchmarks": status_map}
        with open(args.output, "w") as f:
            json.dump(output, f, indent=2)
        print(f"\nCEC results written to {args.output}")
    else:
        print(json.dumps({"benchmarks": status_map}, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main())
