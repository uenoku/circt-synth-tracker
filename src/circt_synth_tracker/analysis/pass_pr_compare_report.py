#!/usr/bin/env python3
"""Unified pass report tool supporting single-run and PR comparison modes."""

from __future__ import annotations

import argparse
import json
import math
from html import escape
from pathlib import Path


def load_json(path: Path) -> dict:
    with path.open() as f:
        return json.load(f)


def geomean(values: list[float]) -> float | None:
    vals = [v for v in values if v > 0]
    if not vals:
        return None
    return math.exp(sum(math.log(v) for v in vals) / len(vals))


def fmt(v: float | None, digits: int = 4) -> str:
    if v is None:
        return "n/a"
    return f"{v:.{digits}f}"


def compare_rows(a: dict, b: dict, mode: str) -> list[tuple[str, float, float, float]]:
    rows: list[tuple[str, float, float, float]] = []
    amap = a.get("benchmarks", {})
    bmap = b.get("benchmarks", {})
    for name in sorted(set(amap).intersection(bmap)):
        av = amap[name]
        bv = bmap[name]
        if av.get("mode") != mode or bv.get("mode") != mode:
            continue
        at = av.get("compile_time_s")
        bt = bv.get("compile_time_s")
        if at is None or bt is None or at <= 0 or bt <= 0:
            continue
        rows.append((name, float(at), float(bt), float(at) / float(bt)))
    return rows


def rows_html(rows: list[tuple[str, float, float, float]]) -> str:
    return "\n".join(
        f"<tr><td>{escape(n)}</td><td>{a:.6f}</td><td>{b:.6f}</td><td>{r:.4f}</td></tr>"
        for n, a, b, r in rows
    )


def geomean_ratio(rows: list[tuple[str, float, float, float]]) -> float | None:
    av = geomean([r[1] for r in rows])
    bv = geomean([r[2] for r in rows])
    return (av / bv) if (av is not None and bv is not None and bv > 0) else None


def run_single(args: argparse.Namespace) -> int:
    cl = load_json(args.circt_lut)
    cs = load_json(args.circt_sop)
    al = load_json(args.abc_lut)
    a_s = load_json(args.abc_sop)

    lut_rows = compare_rows(cl, al, "lut-mapping")
    sop_rows = compare_rows(cs, a_s, "sop-balancing")
    lut_ratio = geomean_ratio(lut_rows)
    sop_ratio = geomean_ratio(sop_rows)

    md = [
        f"## {args.title}",
        "",
        f"- CIRCT version: `{args.version}`",
        "",
        "| Mode | Geomean CIRCT/ABC | Matched |",
        "|---|---:|---:|",
        f"| LUT Mapping | {fmt(lut_ratio)} | {len(lut_rows)} |",
        f"| SOP Balancing | {fmt(sop_ratio)} | {len(sop_rows)} |",
        "",
        "Interpretation: lower `CIRCT/ABC` is better.",
    ]
    args.markdown_out.write_text("\n".join(md) + "\n")

    html = f"""<!doctype html>
<html lang="en"><head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{escape(args.title)}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 24px; color: #111; }}
    table {{ border-collapse: collapse; width: 100%; margin: 8px 0 24px; }}
    th, td {{ border: 1px solid #ddd; padding: 6px 8px; text-align: left; font-size: 13px; }}
    th {{ background: #f3f3f3; }}
  </style>
</head><body>
  <h1>{escape(args.title)}</h1>
  <p>CIRCT version: <code>{escape(args.version)}</code></p>
  <table>
    <thead><tr><th>Mode</th><th>Geomean CIRCT/ABC</th><th>Matched</th></tr></thead>
    <tbody>
      <tr><td>LUT Mapping</td><td>{fmt(lut_ratio)}</td><td>{len(lut_rows)}</td></tr>
      <tr><td>SOP Balancing</td><td>{fmt(sop_ratio)}</td><td>{len(sop_rows)}</td></tr>
    </tbody>
  </table>
  <h2>LUT Mapping Details</h2>
  <table><thead><tr><th>Benchmark</th><th>CIRCT (s)</th><th>ABC (s)</th><th>CIRCT/ABC</th></tr></thead><tbody>{rows_html(lut_rows)}</tbody></table>
  <h2>SOP Balancing Details</h2>
  <table><thead><tr><th>Benchmark</th><th>CIRCT (s)</th><th>ABC (s)</th><th>CIRCT/ABC</th></tr></thead><tbody>{rows_html(sop_rows)}</tbody></table>
</body></html>"""
    args.html_out.write_text(html)
    return 0


def run_pr(args: argparse.Namespace) -> int:
    b_cl = load_json(args.before_circt_lut)
    b_cs = load_json(args.before_circt_sop)
    a_cl = load_json(args.after_circt_lut)
    a_cs = load_json(args.after_circt_sop)
    b_al = load_json(args.before_abc_lut)
    b_as = load_json(args.before_abc_sop)
    a_al = load_json(args.after_abc_lut)
    a_as = load_json(args.after_abc_sop)

    cc_lut_rows = compare_rows(a_cl, b_cl, "lut-mapping")
    cc_sop_rows = compare_rows(a_cs, b_cs, "sop-balancing")
    cc_lut_before = geomean([r[2] for r in cc_lut_rows])
    cc_lut_after = geomean([r[1] for r in cc_lut_rows])
    cc_sop_before = geomean([r[2] for r in cc_sop_rows])
    cc_sop_after = geomean([r[1] for r in cc_sop_rows])
    cc_lut_delta = (cc_lut_after / cc_lut_before) if (cc_lut_after and cc_lut_before) else None
    cc_sop_delta = (cc_sop_after / cc_sop_before) if (cc_sop_after and cc_sop_before) else None

    ca_before_lut = geomean_ratio(compare_rows(b_cl, b_al, "lut-mapping"))
    ca_before_sop = geomean_ratio(compare_rows(b_cs, b_as, "sop-balancing"))
    ca_after_lut = geomean_ratio(compare_rows(a_cl, a_al, "lut-mapping"))
    ca_after_sop = geomean_ratio(compare_rows(a_cs, a_as, "sop-balancing"))

    md = [
        f"## CIRCT PR #{args.pr_number} Unified Pass Comparison",
        "",
        f"- PR: [{args.pr_title}](https://github.com/llvm/circt/pull/{args.pr_number})",
        f"- Commit: `{args.base_sha[:8]}` -> `{args.head_sha[:8]}`",
        f"- Version: `{args.before_version}` -> `{args.after_version}`",
        "",
        "### CIRCT vs CIRCT (After/Before)",
        "",
        "| Mode | Geomean Before (s) | Geomean After (s) | Delta (After/Before) | Matched |",
        "|---|---:|---:|---:|---:|",
        f"| LUT Mapping | {fmt(cc_lut_before)} | {fmt(cc_lut_after)} | {fmt(cc_lut_delta)} | {len(cc_lut_rows)} |",
        f"| SOP Balancing | {fmt(cc_sop_before)} | {fmt(cc_sop_after)} | {fmt(cc_sop_delta)} | {len(cc_sop_rows)} |",
        "",
        "### CIRCT vs ABC (CIRCT/ABC)",
        "",
        "| Mode | Before Ratio | After Ratio | Ratio Delta (After/Before) |",
        "|---|---:|---:|---:|",
        f"| LUT Mapping | {fmt(ca_before_lut)} | {fmt(ca_after_lut)} | {fmt((ca_after_lut / ca_before_lut) if (ca_before_lut and ca_after_lut) else None)} |",
        f"| SOP Balancing | {fmt(ca_before_sop)} | {fmt(ca_after_sop)} | {fmt((ca_after_sop / ca_before_sop) if (ca_before_sop and ca_after_sop) else None)} |",
        "",
        "Interpretation: lower is better for both `After/Before` and `CIRCT/ABC` ratios.",
    ]
    args.markdown_out.write_text("\n".join(md) + "\n")

    html = f"""<!doctype html>
<html lang="en"><head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>CIRCT PR #{args.pr_number} Unified Pass Comparison</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 24px; color: #111; }}
    table {{ border-collapse: collapse; width: 100%; margin: 8px 0 24px; }}
    th, td {{ border: 1px solid #ddd; padding: 6px 8px; text-align: left; font-size: 13px; }}
    th {{ background: #f3f3f3; }}
  </style>
</head><body>
  <h1>CIRCT PR #{args.pr_number} Unified Pass Comparison</h1>
  <p><a href="https://github.com/llvm/circt/pull/{args.pr_number}">{escape(args.pr_title)}</a><br/>
  Commit: <code>{escape(args.base_sha[:8])}</code> -> <code>{escape(args.head_sha[:8])}</code><br/>
  Version: <code>{escape(args.before_version)}</code> -> <code>{escape(args.after_version)}</code></p>
  <h2>CIRCT vs CIRCT (After/Before)</h2>
  <table><thead><tr><th>Mode</th><th>Geomean Before (s)</th><th>Geomean After (s)</th><th>Delta (After/Before)</th><th>Matched</th></tr></thead>
  <tbody>
    <tr><td>LUT Mapping</td><td>{fmt(cc_lut_before)}</td><td>{fmt(cc_lut_after)}</td><td>{fmt(cc_lut_delta)}</td><td>{len(cc_lut_rows)}</td></tr>
    <tr><td>SOP Balancing</td><td>{fmt(cc_sop_before)}</td><td>{fmt(cc_sop_after)}</td><td>{fmt(cc_sop_delta)}</td><td>{len(cc_sop_rows)}</td></tr>
  </tbody></table>
  <h2>CIRCT vs ABC (CIRCT/ABC)</h2>
  <table><thead><tr><th>Mode</th><th>Before Ratio</th><th>After Ratio</th><th>Ratio Delta (After/Before)</th></tr></thead>
  <tbody>
    <tr><td>LUT Mapping</td><td>{fmt(ca_before_lut)}</td><td>{fmt(ca_after_lut)}</td><td>{fmt((ca_after_lut / ca_before_lut) if (ca_before_lut and ca_after_lut) else None)}</td></tr>
    <tr><td>SOP Balancing</td><td>{fmt(ca_before_sop)}</td><td>{fmt(ca_after_sop)}</td><td>{fmt((ca_after_sop / ca_before_sop) if (ca_before_sop and ca_after_sop) else None)}</td></tr>
  </tbody></table>
  <h2>LUT Mapping Details (CIRCT After vs Before)</h2>
  <table><thead><tr><th>Benchmark</th><th>After (s)</th><th>Before (s)</th><th>After/Before</th></tr></thead><tbody>{rows_html(cc_lut_rows)}</tbody></table>
  <h2>SOP Balancing Details (CIRCT After vs Before)</h2>
  <table><thead><tr><th>Benchmark</th><th>After (s)</th><th>Before (s)</th><th>After/Before</th></tr></thead><tbody>{rows_html(cc_sop_rows)}</tbody></table>
</body></html>"""
    args.html_out.write_text(html)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Unified pass benchmark reporting tool")
    sub = parser.add_subparsers(dest="mode", required=True)

    p_single = sub.add_parser("single", help="Single-run CIRCT vs ABC report")
    p_single.add_argument("--circt-lut", type=Path, required=True)
    p_single.add_argument("--abc-lut", type=Path, required=True)
    p_single.add_argument("--circt-sop", type=Path, required=True)
    p_single.add_argument("--abc-sop", type=Path, required=True)
    p_single.add_argument("--version", required=True)
    p_single.add_argument("--title", default="Pass Benchmark Report")
    p_single.add_argument("--markdown-out", type=Path, default=Path("pass-benchmark-report.md"))
    p_single.add_argument("--html-out", type=Path, default=Path("pass-benchmark-report.html"))
    p_single.set_defaults(func=run_single)

    p_pr = sub.add_parser("pr", help="PR report with CIRCT-vs-CIRCT and CIRCT-vs-ABC")
    p_pr.add_argument("--before-circt-lut", type=Path, required=True)
    p_pr.add_argument("--before-circt-sop", type=Path, required=True)
    p_pr.add_argument("--after-circt-lut", type=Path, required=True)
    p_pr.add_argument("--after-circt-sop", type=Path, required=True)
    p_pr.add_argument("--before-abc-lut", type=Path, required=True)
    p_pr.add_argument("--before-abc-sop", type=Path, required=True)
    p_pr.add_argument("--after-abc-lut", type=Path, required=True)
    p_pr.add_argument("--after-abc-sop", type=Path, required=True)
    p_pr.add_argument("--before-version", required=True)
    p_pr.add_argument("--after-version", required=True)
    p_pr.add_argument("--pr-number", required=True)
    p_pr.add_argument("--pr-title", required=True)
    p_pr.add_argument("--base-sha", required=True)
    p_pr.add_argument("--head-sha", required=True)
    p_pr.add_argument("--markdown-out", type=Path, default=Path("pr-pass-compare.md"))
    p_pr.add_argument("--html-out", type=Path, default=Path("pr-pass-compare.html"))
    p_pr.set_defaults(func=run_pr)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
