#!/usr/bin/env python3
"""Append pass-benchmark ratios to a cumulative history JSON file."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from circt_synth_tracker.analysis.pass_compare_results import (
    compare_rows,
    compare_rows_for_metric,
    geomean_ratio,
)

_METRICS = [
    ("lut_mapping_time", "lut-mapping", "compile_time_s"),
    ("sop_balancing_time", "sop-balancing", "compile_time_s"),
    ("lut_count", "lut-mapping", "lut_count"),
    ("lut_depth", "lut-mapping", "lut_depth"),
    ("aig_count", "sop-balancing", "aig_count"),
    ("aig_depth", "sop-balancing", "aig_depth"),
]


def _load_summary(path_arg: str, label: str) -> dict:
    path = Path(path_arg)
    if not path.exists():
        raise FileNotFoundError(f"{label} summary not found: {path}")
    with path.open() as f:
        return json.load(f)


def build_history_entry(circt: dict, abc: dict, date: str) -> dict:
    ratios = {}
    matched = {}
    for key, mode, metric in _METRICS:
        rows = (
            compare_rows(circt, abc, mode)
            if metric == "compile_time_s"
            else compare_rows_for_metric(circt, abc, mode, metric)
        )
        ratios[key] = geomean_ratio(rows)
        matched[key] = len(rows)

    return {
        "date": date,
        "circt_version": circt.get("version", "unknown"),
        "abc_version": abc.get("version", "unknown"),
        "ratios": ratios,
        "matched": matched,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Append pass benchmark ratios to cumulative history JSON"
    )
    parser.add_argument("--circt", required=True, help="CIRCT pass summary JSON file")
    parser.add_argument("--abc", required=True, help="ABC pass summary JSON file")
    parser.add_argument(
        "-o",
        "--output",
        required=True,
        help="History JSON file (read and updated in-place)",
    )
    parser.add_argument(
        "--max-days",
        type=int,
        default=0,
        help="Maximum entries to retain (0 = unlimited)",
    )
    parser.add_argument("--date", help="Override date (YYYY-MM-DD, default: today UTC)")
    args = parser.parse_args()

    try:
        circt = _load_summary(args.circt, "CIRCT")
        abc = _load_summary(args.abc, "ABC")
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    history_path = Path(args.output)
    if history_path.exists():
        with history_path.open() as f:
            history = json.load(f)
    else:
        history = []

    date = args.date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    entry = build_history_entry(circt, abc, date)

    history = [e for e in history if e.get("date") != date]
    history.append(entry)
    history.sort(key=lambda e: e.get("date", ""))
    if args.max_days > 0:
        history = history[-args.max_days :]

    with history_path.open("w") as f:
        json.dump(history, f, indent=2)

    print(f"History updated: {len(history)} entries, latest: {date}")
    print(f"Written to: {history_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
