#!/usr/bin/env python3
"""
Append current synthesis results to a cumulative history JSON file.

Usage:
    append-history --circt circt-summary.json --yosys yosys-summary.json -o history.json
    append-history --circt circt-summary.json --yosys yosys-summary.json -o history.json --max-days 90
"""

import sys
import json
import argparse
from datetime import datetime, timezone
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        description="Append synthesis results to cumulative history JSON"
    )
    parser.add_argument("--circt", required=True, help="CIRCT summary JSON file")
    parser.add_argument("--yosys", required=True, help="Yosys summary JSON file")
    parser.add_argument(
        "-o", "--output", required=True, help="History JSON file (read and updated in-place)"
    )
    parser.add_argument(
        "--max-days", type=int, default=0, help="Maximum entries to retain (0 = unlimited)"
    )
    parser.add_argument(
        "--date", help="Override date (YYYY-MM-DD, default: today UTC)"
    )

    args = parser.parse_args()

    # Load existing history
    history_path = Path(args.output)
    if history_path.exists():
        with open(history_path) as f:
            history = json.load(f)
    else:
        history = []

    # Load summaries
    for path_arg, label in [(args.circt, "CIRCT"), (args.yosys, "Yosys")]:
        if not Path(path_arg).exists():
            print(f"Error: {label} summary not found: {path_arg}", file=sys.stderr)
            return 1

    with open(args.circt) as f:
        circt = json.load(f)
    with open(args.yosys) as f:
        yosys = json.load(f)

    date = args.date or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    entry = {
        "date": date,
        "circt_version": circt.get("version", "unknown"),
        "yosys_version": yosys.get("version", "unknown"),
        "circt": {"benchmarks": circt.get("benchmarks", {})},
        "yosys": {"benchmarks": yosys.get("benchmarks", {})},
    }

    # Replace any existing entry for the same date (idempotent)
    history = [e for e in history if e.get("date") != date]
    history.append(entry)
    history.sort(key=lambda e: e.get("date", ""))

    if args.max_days > 0:
        history = history[-args.max_days :]

    with open(history_path, "w") as f:
        json.dump(history, f, indent=2)

    print(f"History updated: {len(history)} entries, latest: {date}")
    print(f"Written to: {history_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
