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


def geomean_ratio(rows: list[tuple[str, float, float, float]]) -> float | None:
    a_geo = geomean([r[1] for r in rows])
    b_geo = geomean([r[2] for r in rows])
    return (a_geo / b_geo) if (a_geo is not None and b_geo is not None and b_geo > 0) else None


def rows_html(rows: list[tuple[str, float, float, float]]) -> str:
    return "\n".join(
        f"<tr><td>{escape(name)}</td><td>{a:.6f}</td><td>{b:.6f}</td><td>{r:.4f}</td></tr>"
        for name, a, b, r in rows
    )


def render_pair(
    *,
    title: str,
    label_a: str,
    label_b: str,
    a: dict,
    b: dict,
    markdown_out: Path,
    html_out: Path,
    subtitle_lines: list[str] | None = None,
) -> None:
    lut_rows = compare_rows(a, b, "lut-mapping")
    sop_rows = compare_rows(a, b, "sop-balancing")
    lut_ratio = geomean_ratio(lut_rows)
    sop_ratio = geomean_ratio(sop_rows)

    md = [f"## {title}", ""]
    for line in subtitle_lines or []:
        md.append(f"- {line}")
    if subtitle_lines:
        md.append("")
    md.extend(
        [
            f"| Mode | Geomean {label_a}/{label_b} | Matched |",
            "|---|---:|---:|",
            f"| LUT Mapping | {fmt(lut_ratio)} | {len(lut_rows)} |",
            f"| SOP Balancing | {fmt(sop_ratio)} | {len(sop_rows)} |",
            "",
            f"Interpretation: lower `{label_a}/{label_b}` is better.",
        ]
    )
    markdown_out.write_text("\n".join(md) + "\n")

    html = f"""<!doctype html>
<html lang="en"><head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{escape(title)}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 24px; color: #111; }}
    table {{ border-collapse: collapse; width: 100%; margin: 8px 0 24px; }}
    th, td {{ border: 1px solid #ddd; padding: 6px 8px; text-align: left; font-size: 13px; }}
    th {{ background: #f3f3f3; }}
  </style>
</head><body>
  <h1>{escape(title)}</h1>
  {''.join(f'<p>{escape(line)}</p>' for line in (subtitle_lines or []))}
  <table>
    <thead><tr><th>Mode</th><th>Geomean {escape(label_a)}/{escape(label_b)}</th><th>Matched</th></tr></thead>
    <tbody>
      <tr><td>LUT Mapping</td><td>{fmt(lut_ratio)}</td><td>{len(lut_rows)}</td></tr>
      <tr><td>SOP Balancing</td><td>{fmt(sop_ratio)}</td><td>{len(sop_rows)}</td></tr>
    </tbody>
  </table>
  <h2>LUT Mapping Details</h2>
  <table><thead><tr><th>Benchmark</th><th>{escape(label_a)} (s)</th><th>{escape(label_b)} (s)</th><th>{escape(label_a)}/{escape(label_b)}</th></tr></thead><tbody>{rows_html(lut_rows)}</tbody></table>
  <h2>SOP Balancing Details</h2>
  <table><thead><tr><th>Benchmark</th><th>{escape(label_a)} (s)</th><th>{escape(label_b)} (s)</th><th>{escape(label_a)}/{escape(label_b)}</th></tr></thead><tbody>{rows_html(sop_rows)}</tbody></table>
</body></html>"""
    html_out.write_text(html)


def run_single(args: argparse.Namespace) -> int:
    a = load_json(args.a)
    b = load_json(args.b)
    render_pair(
        title=args.title,
        label_a=args.label_a,
        label_b=args.label_b,
        a=a,
        b=b,
        markdown_out=args.markdown_out,
        html_out=args.html_out,
        subtitle_lines=[f"Version: `{args.version}`"] if args.version else None,
    )
    return 0


def run_pr(args: argparse.Namespace) -> int:
    before = load_json(args.before)
    after = load_json(args.after)

    cc_lut_rows = compare_rows(after, before, "lut-mapping")
    cc_sop_rows = compare_rows(after, before, "sop-balancing")
    cc_lut_before = geomean([r[2] for r in cc_lut_rows])
    cc_lut_after = geomean([r[1] for r in cc_lut_rows])
    cc_sop_before = geomean([r[2] for r in cc_sop_rows])
    cc_sop_after = geomean([r[1] for r in cc_sop_rows])
    cc_lut_delta = (cc_lut_after / cc_lut_before) if (cc_lut_after and cc_lut_before) else None
    cc_sop_delta = (cc_sop_after / cc_sop_before) if (cc_sop_after and cc_sop_before) else None

    ref_before_lut = ref_before_sop = ref_after_lut = ref_after_sop = None
    if args.ref_before and args.ref_after:
        ref_before = load_json(args.ref_before)
        ref_after = load_json(args.ref_after)
        ref_before_lut = geomean_ratio(compare_rows(before, ref_before, "lut-mapping"))
        ref_before_sop = geomean_ratio(compare_rows(before, ref_before, "sop-balancing"))
        ref_after_lut = geomean_ratio(compare_rows(after, ref_after, "lut-mapping"))
        ref_after_sop = geomean_ratio(compare_rows(after, ref_after, "sop-balancing"))

    md = [
        f"## {args.title}",
        "",
        f"- PR: [{args.pr_title}](https://github.com/llvm/circt/pull/{args.pr_number})",
        f"- Commit: `{args.base_sha[:8]}` -> `{args.head_sha[:8]}`",
        f"- Version: `{args.before_version}` -> `{args.after_version}`",
        "",
        f"### {args.label_a} vs {args.label_b} ({args.label_a}/{args.label_b})",
        "",
        f"| Mode | Geomean {args.label_b} (s) | Geomean {args.label_a} (s) | Delta ({args.label_a}/{args.label_b}) | Matched |",
        "|---|---:|---:|---:|---:|",
        f"| LUT Mapping | {fmt(cc_lut_before)} | {fmt(cc_lut_after)} | {fmt(cc_lut_delta)} | {len(cc_lut_rows)} |",
        f"| SOP Balancing | {fmt(cc_sop_before)} | {fmt(cc_sop_after)} | {fmt(cc_sop_delta)} | {len(cc_sop_rows)} |",
    ]
    if ref_before_lut is not None:
        md.extend(
            [
                "",
                f"### {args.label_a} vs {args.ref_label} ({args.label_a}/{args.ref_label})",
                "",
                f"| Mode | Before Ratio | After Ratio | Ratio Delta (After/Before) |",
                "|---|---:|---:|---:|",
                f"| LUT Mapping | {fmt(ref_before_lut)} | {fmt(ref_after_lut)} | {fmt((ref_after_lut / ref_before_lut) if (ref_before_lut and ref_after_lut) else None)} |",
                f"| SOP Balancing | {fmt(ref_before_sop)} | {fmt(ref_after_sop)} | {fmt((ref_after_sop / ref_before_sop) if (ref_before_sop and ref_after_sop) else None)} |",
            ]
        )
    md.extend(["", "Interpretation: lower ratios are better."])
    args.markdown_out.write_text("\n".join(md) + "\n")

    html_parts = [
        "<!doctype html><html lang=\"en\"><head>",
        "<meta charset=\"utf-8\" />",
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />",
        f"<title>{escape(args.title)}</title>",
        "<style>body { font-family: -apple-system, BlinkMacSystemFont, \"Segoe UI\", sans-serif; margin: 24px; color: #111; } table { border-collapse: collapse; width: 100%; margin: 8px 0 24px; } th, td { border: 1px solid #ddd; padding: 6px 8px; text-align: left; font-size: 13px; } th { background: #f3f3f3; }</style>",
        "</head><body>",
        f"<h1>{escape(args.title)}</h1>",
        f"<p><a href=\"https://github.com/llvm/circt/pull/{args.pr_number}\">{escape(args.pr_title)}</a><br/>",
        f"Commit: <code>{escape(args.base_sha[:8])}</code> -> <code>{escape(args.head_sha[:8])}</code><br/>",
        f"Version: <code>{escape(args.before_version)}</code> -> <code>{escape(args.after_version)}</code></p>",
        f"<h2>{escape(args.label_a)} vs {escape(args.label_b)} ({escape(args.label_a)}/{escape(args.label_b)})</h2>",
        f"<table><thead><tr><th>Mode</th><th>Geomean {escape(args.label_b)} (s)</th><th>Geomean {escape(args.label_a)} (s)</th><th>Delta ({escape(args.label_a)}/{escape(args.label_b)})</th><th>Matched</th></tr></thead><tbody>",
        f"<tr><td>LUT Mapping</td><td>{fmt(cc_lut_before)}</td><td>{fmt(cc_lut_after)}</td><td>{fmt(cc_lut_delta)}</td><td>{len(cc_lut_rows)}</td></tr>",
        f"<tr><td>SOP Balancing</td><td>{fmt(cc_sop_before)}</td><td>{fmt(cc_sop_after)}</td><td>{fmt(cc_sop_delta)}</td><td>{len(cc_sop_rows)}</td></tr>",
        "</tbody></table>",
    ]
    if ref_before_lut is not None:
        html_parts.extend(
            [
                f"<h2>{escape(args.label_a)} vs {escape(args.ref_label)} ({escape(args.label_a)}/{escape(args.ref_label)})</h2>",
                f"<table><thead><tr><th>Mode</th><th>Before Ratio</th><th>After Ratio</th><th>Ratio Delta (After/Before)</th></tr></thead><tbody>",
                f"<tr><td>LUT Mapping</td><td>{fmt(ref_before_lut)}</td><td>{fmt(ref_after_lut)}</td><td>{fmt((ref_after_lut / ref_before_lut) if (ref_before_lut and ref_after_lut) else None)}</td></tr>",
                f"<tr><td>SOP Balancing</td><td>{fmt(ref_before_sop)}</td><td>{fmt(ref_after_sop)}</td><td>{fmt((ref_after_sop / ref_before_sop) if (ref_before_sop and ref_after_sop) else None)}</td></tr>",
                "</tbody></table>",
            ]
        )
    html_parts.extend(
        [
            f"<h2>LUT Mapping Details ({escape(args.label_a)} vs {escape(args.label_b)})</h2>",
            f"<table><thead><tr><th>Benchmark</th><th>{escape(args.label_a)} (s)</th><th>{escape(args.label_b)} (s)</th><th>{escape(args.label_a)}/{escape(args.label_b)}</th></tr></thead><tbody>{rows_html(cc_lut_rows)}</tbody></table>",
            f"<h2>SOP Balancing Details ({escape(args.label_a)} vs {escape(args.label_b)})</h2>",
            f"<table><thead><tr><th>Benchmark</th><th>{escape(args.label_a)} (s)</th><th>{escape(args.label_b)} (s)</th><th>{escape(args.label_a)}/{escape(args.label_b)}</th></tr></thead><tbody>{rows_html(cc_sop_rows)}</tbody></table>",
            "</body></html>",
        ]
    )
    args.html_out.write_text("\n".join(html_parts))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Unified pass benchmark reporting tool")
    sub = parser.add_subparsers(dest="mode", required=True)

    single = sub.add_parser("single", help="Single-run comparison from A.json vs B.json")
    single.add_argument("--a", type=Path, required=True, help="A summary JSON")
    single.add_argument("--b", type=Path, required=True, help="B summary JSON")
    single.add_argument("--label-a", default="CIRCT")
    single.add_argument("--label-b", default="ABC")
    single.add_argument("--version", default="")
    single.add_argument("--title", default="Pass Benchmark Report")
    single.add_argument("--markdown-out", type=Path, default=Path("pass-benchmark-report.md"))
    single.add_argument("--html-out", type=Path, default=Path("pass-benchmark-report.html"))
    single.set_defaults(func=run_single)

    pr = sub.add_parser("pr", help="PR comparison from before.json vs after.json")
    pr.add_argument("--before", type=Path, required=True, help="Before summary JSON")
    pr.add_argument("--after", type=Path, required=True, help="After summary JSON")
    pr.add_argument("--label-a", default="CIRCT(PR)")
    pr.add_argument("--label-b", default="CIRCT(Base)")
    pr.add_argument("--ref-before", type=Path, help="Optional reference before JSON (e.g. ABC base)")
    pr.add_argument("--ref-after", type=Path, help="Optional reference after JSON (e.g. ABC PR)")
    pr.add_argument("--ref-label", default="ABC")
    pr.add_argument("--before-version", required=True)
    pr.add_argument("--after-version", required=True)
    pr.add_argument("--pr-number", required=True)
    pr.add_argument("--pr-title", required=True)
    pr.add_argument("--base-sha", required=True)
    pr.add_argument("--head-sha", required=True)
    pr.add_argument("--title", default="CIRCT PR Unified Pass Comparison")
    pr.add_argument("--markdown-out", type=Path, default=Path("pr-pass-compare.md"))
    pr.add_argument("--html-out", type=Path, default=Path("pr-pass-compare.html"))
    pr.set_defaults(func=run_pr)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
