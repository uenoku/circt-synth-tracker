#!/usr/bin/env python3
"""Unified pass report tool supporting single-run and PR comparison modes."""

from __future__ import annotations

import argparse
import json
import math
from html import escape
from pathlib import Path

from circt_synth_tracker.analysis.report_formatting import (
    format_metric_cell_html,
    format_ratio_with_pct,
)


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


def compare_rows_for_metric(
    a: dict, b: dict, mode: str, metric: str
) -> list[tuple[str, float, float, float]]:
    rows: list[tuple[str, float, float, float]] = []
    amap = a.get("benchmarks", {})
    bmap = b.get("benchmarks", {})
    for name in sorted(set(amap).intersection(bmap)):
        av = amap[name]
        bv = bmap[name]
        if av.get("mode") != mode or bv.get("mode") != mode:
            continue
        at = av.get(metric)
        bt = bv.get(metric)
        if at is None or bt is None or at <= 0 or bt <= 0:
            continue
        rows.append((name, float(at), float(bt), float(at) / float(bt)))
    return rows


def compare_rows(a: dict, b: dict, mode: str) -> list[tuple[str, float, float, float]]:
    return compare_rows_for_metric(a, b, mode, "compile_time_s")


def geomean_ratio(rows: list[tuple[str, float, float, float]]) -> float | None:
    a_geo = geomean([r[1] for r in rows])
    b_geo = geomean([r[2] for r in rows])
    return (
        (a_geo / b_geo)
        if (a_geo is not None and b_geo is not None and b_geo > 0)
        else None
    )


def rows_html(rows: list[tuple[str, float, float, float]]) -> str:
    return "\n".join(
        f"<tr><td>{escape(name)}</td><td>{a:.6f}</td><td>{b:.6f}</td><td>{r:.4f}</td></tr>"
        for name, a, b, r in rows
    )


def rows_html_with_struct(
    a: dict, b: dict, mode: str, label_a: str, label_b: str
) -> str:
    amap = a.get("benchmarks", {})
    bmap = b.get("benchmarks", {})
    lines: list[str] = []
    if mode == "lut-mapping":
        count_key = "lut_count"
        depth_key = "lut_depth"
    else:
        count_key = "aig_count"
        depth_key = "aig_depth"
    for name in sorted(set(amap).intersection(bmap)):
        av = amap[name]
        bv = bmap[name]
        if av.get("mode") != mode or bv.get("mode") != mode:
            continue
        at = av.get("compile_time_s")
        bt = bv.get("compile_time_s")
        if at is None or bt is None or at <= 0 or bt <= 0:
            continue
        ac = av.get(count_key)
        bc = bv.get(count_key)
        ad = av.get(depth_key)
        bd = bv.get(depth_key)
        time_b_content, time_b_style = format_metric_cell_html(
            float(bt), float(at), lower_is_better=True, value_digits=6
        )
        lut_b_content, lut_b_style = (
            format_metric_cell_html(
                float(bc), float(ac), lower_is_better=True, value_digits=2
            )
            if ac is not None and bc is not None
            else (fmt(float(bc), 2) if bc is not None else "n/a", "")
        )
        depth_b_content, depth_b_style = (
            format_metric_cell_html(
                float(bd), float(ad), lower_is_better=True, value_digits=2
            )
            if ad is not None and bd is not None
            else (fmt(float(bd), 2) if bd is not None else "n/a", "")
        )

        lines.append(
            "<tr>"
            f"<td>{escape(name)}</td>"
            f"<td>{float(at):.6f}</td>"
            f"<td{time_b_style}>{time_b_content}</td>"
            f"<td>{fmt(float(ac), 2) if ac is not None else 'n/a'}</td>"
            f"<td{lut_b_style}>{lut_b_content}</td>"
            f"<td>{fmt(float(ad), 2) if ad is not None else 'n/a'}</td>"
            f"<td{depth_b_style}>{depth_b_content}</td>"
            "</tr>"
        )
    return "\n".join(lines)


def build_relative_section(
    *,
    primary_before: dict,
    primary_after: dict,
    relative_before: dict,
    relative_after: dict,
    label_before: str,
    label_after: str,
    relative_label: str,
) -> tuple[list[str], list[str]]:
    before_lut_rows = compare_rows(primary_before, relative_before, "lut-mapping")
    before_sop_rows = compare_rows(primary_before, relative_before, "sop-balancing")
    after_lut_rows = compare_rows(primary_after, relative_after, "lut-mapping")
    after_sop_rows = compare_rows(primary_after, relative_after, "sop-balancing")

    before_lut_ratio = geomean_ratio(before_lut_rows)
    before_sop_ratio = geomean_ratio(before_sop_rows)
    after_lut_ratio = geomean_ratio(after_lut_rows)
    after_sop_ratio = geomean_ratio(after_sop_rows)

    header = [
        "Mode",
        f"Geometric Mean {label_before} (s)",
        f"Geometric Mean {label_after} (s)",
        f"Geometric Mean {relative_label} ({label_before}) (s)",
        f"Geometric Mean {relative_label} ({label_after}) (s)",
        f"{label_before} Ratio",
        f"{label_after} Ratio",
        f"Ratio Delta ({label_after}/{label_before})",
    ]
    html_header = "".join(f"<th>{escape(col)}</th>" for col in header)

    rows = [
        (
            "LUT Mapping",
            geomean([r[1] for r in before_lut_rows]),
            geomean([r[1] for r in after_lut_rows]),
            geomean([r[2] for r in before_lut_rows]),
            geomean([r[2] for r in after_lut_rows]),
            before_lut_ratio,
            after_lut_ratio,
            (
                (after_lut_ratio / before_lut_ratio)
                if (before_lut_ratio and after_lut_ratio)
                else None
            ),
        ),
        (
            "SOP Balancing",
            geomean([r[1] for r in before_sop_rows]),
            geomean([r[1] for r in after_sop_rows]),
            geomean([r[2] for r in before_sop_rows]),
            geomean([r[2] for r in after_sop_rows]),
            before_sop_ratio,
            after_sop_ratio,
            (
                (after_sop_ratio / before_sop_ratio)
                if (before_sop_ratio and after_sop_ratio)
                else None
            ),
        ),
    ]

    section_title = f"{label_before}/{relative_label} → {label_after}/{relative_label}"
    md = ["", f"### {section_title}", "", f"| {' | '.join(header)} |"]
    md.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for name, base, after, rel_base, rel_after, base_ratio, after_ratio, delta in rows:
        md.append(
            f"| {name} | {fmt(base)} | {fmt(after)} | {fmt(rel_base)} | {fmt(rel_after)} | "
            f"{fmt(base_ratio)} | {fmt(after_ratio)} | {fmt(delta)} |"
        )

    html = [
        f"<h2>{escape(section_title)}</h2>",
        f"<table><thead><tr>{html_header}</tr></thead><tbody>",
    ]
    for name, base, after, rel_base, rel_after, base_ratio, after_ratio, delta in rows:
        html.append(
            f"<tr><td>{escape(name)}</td><td>{fmt(base)}</td><td>{fmt(after)}</td>"
            f"<td>{fmt(rel_base)}</td><td>{fmt(rel_after)}</td><td>{fmt(base_ratio)}</td>"
            f"<td>{fmt(after_ratio)}</td><td>{fmt(delta)}</td></tr>"
        )
    html.append("</tbody></table>")
    return md, html


def collect_pr_relatives(args: argparse.Namespace) -> list[tuple[str, dict, dict]]:
    relatives: list[tuple[str, dict, dict]] = []
    if getattr(args, "ref_before", None) and getattr(args, "ref_after", None):
        relatives.append(
            (
                args.ref_label,
                load_json(args.ref_before),
                load_json(args.ref_after),
            )
        )
    for label, before_path, after_path in getattr(args, "relative", []) or []:
        relatives.append(
            (label, load_json(Path(before_path)), load_json(Path(after_path)))
        )
    return relatives


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
    lut_count_rows = compare_rows_for_metric(a, b, "lut-mapping", "lut_count")
    lut_depth_rows = compare_rows_for_metric(a, b, "lut-mapping", "lut_depth")
    aig_count_rows = compare_rows_for_metric(a, b, "sop-balancing", "aig_count")
    aig_depth_rows = compare_rows_for_metric(a, b, "sop-balancing", "aig_depth")

    md = [f"## {title}", ""]
    for line in subtitle_lines or []:
        md.append(f"- {line}")
    if subtitle_lines:
        md.append("")
    md.extend(
        [
            f"| Mode | Geometric Mean {label_a}/{label_b} | Matched |",
            "|---|---:|---:|",
            f"| LUT Mapping | {format_ratio_with_pct(lut_ratio)} | {len(lut_rows)} |",
            f"| SOP Balancing | {format_ratio_with_pct(sop_ratio)} | {len(sop_rows)} |",
            "",
            f"| Structural Metric | Geometric Mean {label_a}/{label_b} | Matched |",
            "|---|---:|---:|",
            f"| LUT Count | {format_ratio_with_pct(geomean_ratio(lut_count_rows))} | {len(lut_count_rows)} |",
            f"| LUT Depth | {format_ratio_with_pct(geomean_ratio(lut_depth_rows))} | {len(lut_depth_rows)} |",
            f"| AIG Count | {format_ratio_with_pct(geomean_ratio(aig_count_rows))} | {len(aig_count_rows)} |",
            f"| AIG Depth | {format_ratio_with_pct(geomean_ratio(aig_depth_rows))} | {len(aig_depth_rows)} |",
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
    .diff {{ font-weight: 600; }}
    .diff.better {{ color: #0a7f2e; }}
    .diff.worse {{ color: #b42318; }}
    .diff.neutral {{ color: #57606a; }}
  </style>
</head><body>
  <h1>{escape(title)}</h1>
  {"".join(f"<p>{escape(line)}</p>" for line in (subtitle_lines or []))}
  <table>
    <thead><tr><th>Mode</th><th>Geometric Mean {escape(label_a)}/{escape(label_b)}</th><th>Matched</th></tr></thead>
    <tbody>
      <tr><td>LUT Mapping</td><td>{format_ratio_with_pct(lut_ratio)}</td><td>{len(lut_rows)}</td></tr>
      <tr><td>SOP Balancing</td><td>{format_ratio_with_pct(sop_ratio)}</td><td>{len(sop_rows)}</td></tr>
    </tbody>
  </table>
  <h2>Structural Metrics ({escape(label_a)}/{escape(label_b)})</h2>
  <table>
    <thead><tr><th>Metric</th><th>Geometric Mean Ratio</th><th>Matched</th></tr></thead>
    <tbody>
      <tr><td>LUT Count</td><td>{format_ratio_with_pct(geomean_ratio(lut_count_rows))}</td><td>{len(lut_count_rows)}</td></tr>
      <tr><td>LUT Depth</td><td>{format_ratio_with_pct(geomean_ratio(lut_depth_rows))}</td><td>{len(lut_depth_rows)}</td></tr>
      <tr><td>AIG Count</td><td>{format_ratio_with_pct(geomean_ratio(aig_count_rows))}</td><td>{len(aig_count_rows)}</td></tr>
      <tr><td>AIG Depth</td><td>{format_ratio_with_pct(geomean_ratio(aig_depth_rows))}</td><td>{len(aig_depth_rows)}</td></tr>
    </tbody>
  </table>
  <h2>LUT Mapping Details</h2>
  <table><thead><tr><th>Benchmark</th><th>{escape(label_a)} Time (s)</th><th>{escape(label_b)} Time (s)</th><th>{escape(label_a)} LUT Count</th><th>{escape(label_b)} LUT Count</th><th>{escape(label_a)} LUT Depth</th><th>{escape(label_b)} LUT Depth</th></tr></thead><tbody>{rows_html_with_struct(a, b, "lut-mapping", label_a, label_b)}</tbody></table>
  <h2>SOP Balancing Details</h2>
  <table><thead><tr><th>Benchmark</th><th>{escape(label_a)} Time (s)</th><th>{escape(label_b)} Time (s)</th><th>{escape(label_a)} AIG Count</th><th>{escape(label_b)} AIG Count</th><th>{escape(label_a)} AIG Depth</th><th>{escape(label_b)} AIG Depth</th></tr></thead><tbody>{rows_html_with_struct(a, b, "sop-balancing", label_a, label_b)}</tbody></table>
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
    cc_lut_count_rows = compare_rows_for_metric(
        after, before, "lut-mapping", "lut_count"
    )
    cc_lut_depth_rows = compare_rows_for_metric(
        after, before, "lut-mapping", "lut_depth"
    )
    cc_aig_count_rows = compare_rows_for_metric(
        after, before, "sop-balancing", "aig_count"
    )
    cc_aig_depth_rows = compare_rows_for_metric(
        after, before, "sop-balancing", "aig_depth"
    )
    cc_lut_before = geomean([r[2] for r in cc_lut_rows])
    cc_lut_after = geomean([r[1] for r in cc_lut_rows])
    cc_sop_before = geomean([r[2] for r in cc_sop_rows])
    cc_sop_after = geomean([r[1] for r in cc_sop_rows])
    cc_lut_delta = (
        (cc_lut_after / cc_lut_before) if (cc_lut_after and cc_lut_before) else None
    )
    cc_sop_delta = (
        (cc_sop_after / cc_sop_before) if (cc_sop_after and cc_sop_before) else None
    )
    relative_sections = [
        build_relative_section(
            primary_before=before,
            primary_after=after,
            relative_before=relative_before,
            relative_after=relative_after,
            label_before=args.label_a,
            label_after=args.label_b,
            relative_label=relative_label,
        )
        for relative_label, relative_before, relative_after in collect_pr_relatives(args)
    ]

    md = [
        f"## {args.title}",
        "",
        f"- PR: [{args.pr_title}](https://github.com/llvm/circt/pull/{args.pr_number})",
        f"- Commit: `{args.base_sha[:8]}` -> `{args.head_sha[:8]}`",
        f"- Version: `{args.before_version}` -> `{args.after_version}`",
        "",
        f"### {args.label_a} → {args.label_b} ({args.label_b}/{args.label_a})",
        "",
        f"| Mode | Geometric Mean {args.label_a} (s) | Geometric Mean {args.label_b} (s) | Delta ({args.label_b}/{args.label_a}) | Matched |",
        "|---|---:|---:|---:|---:|",
        f"| LUT Mapping | {fmt(cc_lut_before)} | {fmt(cc_lut_after)} | {fmt(cc_lut_delta)} | {len(cc_lut_rows)} |",
        f"| SOP Balancing | {fmt(cc_sop_before)} | {fmt(cc_sop_after)} | {fmt(cc_sop_delta)} | {len(cc_sop_rows)} |",
    ]
    for relative_md, _ in relative_sections:
        md.extend(relative_md)
    md.extend(["", "Interpretation: lower ratios are better."])
    md.extend(
        [
            "",
            f"### Structural Metrics ({args.label_b}/{args.label_a})",
            "",
            "| Metric | Geometric Mean Ratio | Matched |",
            "|---|---:|---:|",
            f"| LUT Count | {format_ratio_with_pct(geomean_ratio(cc_lut_count_rows))} | {len(cc_lut_count_rows)} |",
            f"| LUT Depth | {format_ratio_with_pct(geomean_ratio(cc_lut_depth_rows))} | {len(cc_lut_depth_rows)} |",
            f"| AIG Count | {format_ratio_with_pct(geomean_ratio(cc_aig_count_rows))} | {len(cc_aig_count_rows)} |",
            f"| AIG Depth | {format_ratio_with_pct(geomean_ratio(cc_aig_depth_rows))} | {len(cc_aig_depth_rows)} |",
        ]
    )
    args.markdown_out.write_text("\n".join(md) + "\n")

    html_parts = [
        '<!doctype html><html lang="en"><head>',
        '<meta charset="utf-8" />',
        '<meta name="viewport" content="width=device-width, initial-scale=1" />',
        f"<title>{escape(args.title)}</title>",
        '<style>body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 24px; color: #111; } table { border-collapse: collapse; width: 100%; margin: 8px 0 24px; } th, td { border: 1px solid #ddd; padding: 6px 8px; text-align: left; font-size: 13px; } th { background: #f3f3f3; } .diff { font-weight: 600; } .diff.better { color: #0a7f2e; } .diff.worse { color: #b42318; } .diff.neutral { color: #57606a; }</style>',
        "</head><body>",
        f"<h1>{escape(args.title)}</h1>",
        f'<p><a href="https://github.com/llvm/circt/pull/{args.pr_number}">{escape(args.pr_title)}</a><br/>',
        f"Commit: <code>{escape(args.base_sha[:8])}</code> -> <code>{escape(args.head_sha[:8])}</code><br/>",
        f"Version: <code>{escape(args.before_version)}</code> -> <code>{escape(args.after_version)}</code></p>",
        f"<h2>{escape(args.label_a)} → {escape(args.label_b)} ({escape(args.label_b)}/{escape(args.label_a)})</h2>",
        f"<table><thead><tr><th>Mode</th><th>Geometric Mean {escape(args.label_a)} (s)</th><th>Geometric Mean {escape(args.label_b)} (s)</th><th>Delta ({escape(args.label_b)}/{escape(args.label_a)})</th><th>Matched</th></tr></thead><tbody>",
        f"<tr><td>LUT Mapping</td><td>{fmt(cc_lut_before)}</td><td>{fmt(cc_lut_after)}</td><td>{fmt(cc_lut_delta)}</td><td>{len(cc_lut_rows)}</td></tr>",
        f"<tr><td>SOP Balancing</td><td>{fmt(cc_sop_before)}</td><td>{fmt(cc_sop_after)}</td><td>{fmt(cc_sop_delta)}</td><td>{len(cc_sop_rows)}</td></tr>",
        "</tbody></table>",
    ]
    for _, relative_html in relative_sections:
        html_parts.extend(relative_html)
    html_parts.extend(
        [
            f"<h2>Structural Metrics ({escape(args.label_b)}/{escape(args.label_a)})</h2>",
            "<table><thead><tr><th>Metric</th><th>Geometric Mean Ratio</th><th>Matched</th></tr></thead><tbody>",
            f"<tr><td>LUT Count</td><td>{format_ratio_with_pct(geomean_ratio(cc_lut_count_rows))}</td><td>{len(cc_lut_count_rows)}</td></tr>",
            f"<tr><td>LUT Depth</td><td>{format_ratio_with_pct(geomean_ratio(cc_lut_depth_rows))}</td><td>{len(cc_lut_depth_rows)}</td></tr>",
            f"<tr><td>AIG Count</td><td>{format_ratio_with_pct(geomean_ratio(cc_aig_count_rows))}</td><td>{len(cc_aig_count_rows)}</td></tr>",
            f"<tr><td>AIG Depth</td><td>{format_ratio_with_pct(geomean_ratio(cc_aig_depth_rows))}</td><td>{len(cc_aig_depth_rows)}</td></tr>",
            "</tbody></table>",
            f"<h2>LUT Mapping Details ({escape(args.label_a)} → {escape(args.label_b)})</h2>",
            f"<table><thead><tr><th>Benchmark</th><th>{escape(args.label_a)} Time (s)</th><th>{escape(args.label_b)} Time (s)</th><th>{escape(args.label_a)} LUT Count</th><th>{escape(args.label_b)} LUT Count</th><th>{escape(args.label_a)} LUT Depth</th><th>{escape(args.label_b)} LUT Depth</th></tr></thead><tbody>{rows_html_with_struct(before, after, 'lut-mapping', args.label_a, args.label_b)}</tbody></table>",
            f"<h2>SOP Balancing Details ({escape(args.label_a)} → {escape(args.label_b)})</h2>",
            f"<table><thead><tr><th>Benchmark</th><th>{escape(args.label_a)} Time (s)</th><th>{escape(args.label_b)} Time (s)</th><th>{escape(args.label_a)} AIG Count</th><th>{escape(args.label_b)} AIG Count</th><th>{escape(args.label_a)} AIG Depth</th><th>{escape(args.label_b)} AIG Depth</th></tr></thead><tbody>{rows_html_with_struct(before, after, 'sop-balancing', args.label_a, args.label_b)}</tbody></table>",
            "</body></html>",
        ]
    )
    args.html_out.write_text("\n".join(html_parts))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Unified pass benchmark reporting tool"
    )
    sub = parser.add_subparsers(dest="mode", required=True)

    single = sub.add_parser(
        "single", help="Single-run comparison from A.json vs B.json"
    )
    single.add_argument("--a", type=Path, required=True, help="A summary JSON")
    single.add_argument("--b", type=Path, required=True, help="B summary JSON")
    single.add_argument("--label-a", default="CIRCT")
    single.add_argument("--label-b", default="ABC")
    single.add_argument("--version", default="")
    single.add_argument("--title", default="Pass Benchmark Report")
    single.add_argument(
        "--markdown-out", type=Path, default=Path("pass-benchmark-report.md")
    )
    single.add_argument(
        "--html-out", type=Path, default=Path("pass-benchmark-report.html")
    )
    single.set_defaults(func=run_single)

    pr = sub.add_parser("pr", help="PR comparison from before.json vs after.json")
    pr.add_argument("--before", type=Path, required=True, help="Before summary JSON")
    pr.add_argument("--after", type=Path, required=True, help="After summary JSON")
    pr.add_argument("--label-a", default="Base")
    pr.add_argument("--label-b", default="PR")
    pr.add_argument(
        "--ref-before", type=Path, help="Optional reference before JSON (e.g. ABC base)"
    )
    pr.add_argument(
        "--ref-after", type=Path, help="Optional reference after JSON (e.g. ABC PR)"
    )
    pr.add_argument("--ref-label", default="ABC")
    pr.add_argument(
        "--relative",
        action="append",
        nargs=3,
        metavar=("LABEL", "BEFORE", "AFTER"),
        default=[],
        help="Optional relative label and before/after JSON paths; may be repeated",
    )
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
