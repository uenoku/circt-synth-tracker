#!/usr/bin/env python3
"""Generate markdown and HTML reports for CIRCT vs ABC pass benchmarks."""

from __future__ import annotations

import argparse
import json
import math
from html import escape
from pathlib import Path


def load_json(path: Path) -> dict:
    with path.open() as f:
        return json.load(f)


def ratios(a: dict, b: dict) -> list[tuple[str, float, float, float]]:
    out: list[tuple[str, float, float, float]] = []
    shared = set(a.get("benchmarks", {})).intersection(b.get("benchmarks", {}))
    for name in sorted(shared):
        ta = a["benchmarks"][name].get("compile_time_s")
        tb = b["benchmarks"][name].get("compile_time_s")
        if ta is None or tb is None:
            continue
        if tb == 0:
            ratio = 1.0 if ta == 0 else 1.0e9
        else:
            ratio = ta / tb
        out.append((name, ta, tb, ratio))
    return out


def geomean(values: list[float], min_time_s: float = 1e-3) -> float | None:
    if not values:
        return None
    # Ignore very small timings to reduce noise in geomean reporting.
    values = [v for v in values if v >= min_time_s]
    # Ignore negative/invalid timings defensively.
    values = [v for v in values if v > 0]
    if not values:
        return None
    return math.exp(sum(math.log(v) for v in values) / len(values))


def fmt_or_na(v: float | None, digits: int = 3) -> str:
    if v is None:
        return "n/a"
    return f"{v:.{digits}f}"


def parse_int_list(value: str) -> list[int]:
    out: list[int] = []
    for part in value.split(","):
        part = part.strip()
        if part:
            out.append(int(part))
    return out


def sweep_rows_for_lut_sizes(
    circt: dict,
    abc: dict,
    lut_sizes: list[int],
    cut_sizes: list[int] | None,
    min_time_s: float,
) -> dict[int, list[tuple[int, int, float | None, float | None, float | None]]]:
    return {
        lut: sweep_rows(circt, abc, lut, cut_sizes, min_time_s) for lut in lut_sizes
    }


def sweep_rows(
    circt: dict,
    abc: dict,
    lut_size: int,
    cut_sizes: list[int] | None,
    min_time_s: float,
) -> list[tuple[int, int, float | None, float | None, float | None]]:
    if cut_sizes is None:
        cut_sizes = sorted(
            {
                int(m.get("cut_size"))
                for m in circt.get("benchmarks", {}).values()
                if m.get("lut_size") == lut_size and m.get("cut_size") is not None
            }
        )

    rows: list[tuple[int, int, float | None, float | None, float | None]] = []
    for cut in cut_sizes:
        cvals: list[float] = []
        avals: list[float] = []
        shared = set(circt.get("benchmarks", {})).intersection(
            abc.get("benchmarks", {})
        )
        for name in shared:
            cm = circt["benchmarks"][name]
            am = abc["benchmarks"][name]
            if cm.get("lut_size") != lut_size or cm.get("cut_size") != cut:
                continue
            if am.get("lut_size") != lut_size or am.get("cut_size") != cut:
                continue
            ct = cm.get("compile_time_s")
            at = am.get("compile_time_s")
            if ct is None or at is None:
                continue
            cvals.append(float(ct))
            avals.append(float(at))

        cgeo = geomean(cvals, min_time_s=min_time_s)
        ageo = geomean(avals, min_time_s=min_time_s)
        ratio = None
        if cgeo is not None and ageo is not None:
            ratio = (1.0 if cgeo == 0 else 1.0e9) if ageo == 0 else cgeo / ageo
        rows.append((cut, len(cvals), cgeo, ageo, ratio))
    return rows


def write_markdown(
    out: Path,
    version: str,
    lut_rows: list[tuple[str, float, float, float]],
    sop_rows: list[tuple[str, float, float, float]],
    lut_geo: float | None,
    sop_geo: float | None,
    lut_sweeps: dict[
        int, list[tuple[int, int, float | None, float | None, float | None]]
    ],
    sop_sweeps: dict[
        int, list[tuple[int, int, float | None, float | None, float | None]]
    ],
) -> None:
    with out.open("w") as f:
        f.write("## Pass Benchmark (Report-only)\n\n")
        f.write(f"- CIRCT version: `{version}`\n")
        f.write(f"- LUT mode geomean ratio (CIRCT/ABC): `{fmt_or_na(lut_geo, 3)}`\n")
        f.write(f"- SOP mode geomean ratio (CIRCT/ABC): `{fmt_or_na(sop_geo, 3)}`\n")
        f.write("\n")

        f.write("### LUT Mapping\n\n")
        f.write("| Benchmark | CIRCT pass time (s) | ABC time (s) | CIRCT/ABC |\n")
        f.write("|---|---:|---:|---:|\n")
        for n, tc, ta, r in lut_rows:
            f.write(f"| {n} | {tc:.4f} | {ta:.4f} | {r:.3f} |\n")

        f.write("\n### SOP Balancing\n\n")
        f.write("| Benchmark | CIRCT pass time (s) | ABC time (s) | CIRCT/ABC |\n")
        f.write("|---|---:|---:|---:|\n")
        for n, tc, ta, r in sop_rows:
            f.write(f"| {n} | {tc:.4f} | {ta:.4f} | {r:.3f} |\n")

        for lut_size, lut_sweep in lut_sweeps.items():
            sop_sweep = sop_sweeps.get(lut_size, [])
            f.write(f"\n### Sweep Summary (lut_size={lut_size})\n\n")
            f.write("#### LUT Mapping\n\n")
            f.write(
                "| cut_size | compared | CIRCT geomean (s) | ABC geomean (s) | CIRCT/ABC |\n"
            )
            f.write("|---:|---:|---:|---:|---:|\n")
            for cut, n, cgeo, ageo, ratio in lut_sweep:
                f.write(
                    f"| {cut} | {n} | {fmt_or_na(cgeo, 6)} | {fmt_or_na(ageo, 6)} | {fmt_or_na(ratio, 4)} |\n"
                )
            f.write("\n#### SOP Balancing\n\n")
            f.write(
                "| cut_size | compared | CIRCT geomean (s) | ABC geomean (s) | CIRCT/ABC |\n"
            )
            f.write("|---:|---:|---:|---:|---:|\n")
            for cut, n, cgeo, ageo, ratio in sop_sweep:
                f.write(
                    f"| {cut} | {n} | {fmt_or_na(cgeo, 6)} | {fmt_or_na(ageo, 6)} | {fmt_or_na(ratio, 4)} |\n"
                )


def write_html(
    out: Path,
    version: str,
    lut_rows: list[tuple[str, float, float, float]],
    sop_rows: list[tuple[str, float, float, float]],
    lut_geo: float | None,
    sop_geo: float | None,
    lut_sweeps: dict[
        int, list[tuple[int, int, float | None, float | None, float | None]]
    ],
    sop_sweeps: dict[
        int, list[tuple[int, int, float | None, float | None, float | None]]
    ],
) -> None:
    def write_rows(rows: list[tuple[str, float, float, float]]) -> str:
        return "\n".join(
            f"<tr><td>{escape(n)}</td><td>{tc:.6f}</td><td>{ta:.6f}</td><td>{r:.4f}</td></tr>"
            for n, tc, ta, r in rows
        )

    def write_sweep(
        rows: list[tuple[int, int, float | None, float | None, float | None]],
    ) -> str:
        return "\n".join(
            f"<tr><td>{cut}</td><td>{n}</td><td>{fmt_or_na(cgeo, 6)}</td><td>{fmt_or_na(ageo, 6)}</td><td>{fmt_or_na(ratio, 4)}</td></tr>"
            for cut, n, cgeo, ageo, ratio in rows
        )

    def sweep_block() -> str:
        blocks = []
        for lut_size, lut_rows_sweep in lut_sweeps.items():
            sop_rows_sweep = sop_sweeps.get(lut_size, [])
            blocks.append(
                f"""
  <h2>Sweep Summary (lut_size={lut_size})</h2>
  <h3>LUT Mapping</h3>
  <table>
    <thead><tr><th>cut_size</th><th>compared</th><th>CIRCT geomean (s)</th><th>ABC geomean (s)</th><th>CIRCT/ABC</th></tr></thead>
    <tbody>
      {write_sweep(lut_rows_sweep)}
    </tbody>
  </table>
  <h3>SOP Balancing</h3>
  <table>
    <thead><tr><th>cut_size</th><th>compared</th><th>CIRCT geomean (s)</th><th>ABC geomean (s)</th><th>CIRCT/ABC</th></tr></thead>
    <tbody>
      {write_sweep(sop_rows_sweep)}
    </tbody>
  </table>
"""
            )
        return "\n".join(blocks)

    html = f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>Pass Benchmark Report</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, \"Segoe UI\", sans-serif; margin: 24px; color: #111; }}
    h1, h2 {{ margin: 0 0 12px; }}
    .meta {{ margin: 0 0 20px; }}
    .cards {{ display: flex; gap: 12px; flex-wrap: wrap; margin: 12px 0 20px; }}
    .card {{ border: 1px solid #ddd; border-radius: 8px; padding: 12px 14px; min-width: 220px; background: #fafafa; }}
    table {{ border-collapse: collapse; width: 100%; margin: 8px 0 24px; }}
    th, td {{ border: 1px solid #ddd; padding: 6px 8px; text-align: left; font-size: 13px; }}
    th {{ background: #f3f3f3; }}
    .small {{ color: #555; font-size: 12px; }}
  </style>
</head>
<body>
  <h1>Pass Benchmark Report</h1>
  <p class=\"meta\">CIRCT version: <code>{escape(version)}</code></p>
  <div class=\"cards\">
    <div class=\"card\"><div class=\"small\">LUT geomean ratio (CIRCT/ABC)</div><div><strong>{fmt_or_na(lut_geo, 4)}</strong></div></div>
    <div class=\"card\"><div class=\"small\">SOP geomean ratio (CIRCT/ABC)</div><div><strong>{fmt_or_na(sop_geo, 4)}</strong></div></div>
    <div class=\"card\"><div class=\"small\">LUT compared benchmarks</div><div><strong>{len(lut_rows)}</strong></div></div>
    <div class=\"card\"><div class=\"small\">SOP compared benchmarks</div><div><strong>{len(sop_rows)}</strong></div></div>
  </div>

  <h2>LUT Mapping</h2>
  <table>
    <thead><tr><th>Benchmark</th><th>CIRCT pass time (s)</th><th>ABC time (s)</th><th>CIRCT/ABC</th></tr></thead>
    <tbody>
      {write_rows(lut_rows)}
    </tbody>
  </table>

  <h2>SOP Balancing</h2>
  <table>
    <thead><tr><th>Benchmark</th><th>CIRCT pass time (s)</th><th>ABC time (s)</th><th>CIRCT/ABC</th></tr></thead>
    <tbody>
      {write_rows(sop_rows)}
    </tbody>
  </table>
  {sweep_block()}
</body>
</html>
"""
    out.write_text(html)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate pass benchmark markdown/html with geomean (CIRCT/ABC)"
    )
    parser.add_argument(
        "--circt-lut", type=Path, required=True, help="CIRCT LUT summary JSON"
    )
    parser.add_argument(
        "--abc-lut", type=Path, required=True, help="ABC LUT summary JSON"
    )
    parser.add_argument(
        "--circt-sop", type=Path, required=True, help="CIRCT SOP summary JSON"
    )
    parser.add_argument(
        "--abc-sop", type=Path, required=True, help="ABC SOP summary JSON"
    )
    parser.add_argument(
        "--sweep-lut-sizes",
        default="",
        help="Comma-separated LUT sizes for sweep tables (for example: 4,6)",
    )
    parser.add_argument(
        "--sweep-cut-sizes",
        default="",
        help="Comma-separated cut sizes for sweep tables (for example: 8,12)",
    )
    parser.add_argument(
        "--markdown-out", type=Path, default=Path("pass-benchmark-report.md")
    )
    parser.add_argument(
        "--html-out", type=Path, default=Path("pass-benchmark-report.html")
    )
    parser.add_argument(
        "--geomean-min-time",
        type=float,
        default=1e-3,
        help="Ignore per-benchmark times below this threshold (seconds) in geomean calculations",
    )
    args = parser.parse_args()

    circt_lut = load_json(args.circt_lut)
    abc_lut = load_json(args.abc_lut)
    circt_sop = load_json(args.circt_sop)
    abc_sop = load_json(args.abc_sop)

    lut_rows = ratios(circt_lut, abc_lut)
    sop_rows = ratios(circt_sop, abc_sop)
    lut_geo = geomean([r[3] for r in lut_rows], min_time_s=args.geomean_min_time)
    sop_geo = geomean([r[3] for r in sop_rows], min_time_s=args.geomean_min_time)
    sweep_cut_sizes = (
        parse_int_list(args.sweep_cut_sizes) if args.sweep_cut_sizes else None
    )
    lut_sizes = parse_int_list(args.sweep_lut_sizes) if args.sweep_lut_sizes else []
    lut_sweeps = (
        sweep_rows_for_lut_sizes(
            circt_lut, abc_lut, lut_sizes, sweep_cut_sizes, args.geomean_min_time
        )
        if lut_sizes
        else {}
    )
    sop_sweeps = (
        sweep_rows_for_lut_sizes(
            circt_sop, abc_sop, lut_sizes, sweep_cut_sizes, args.geomean_min_time
        )
        if lut_sizes
        else {}
    )

    version = circt_lut.get("version", "unknown")
    write_markdown(
        args.markdown_out,
        version,
        lut_rows,
        sop_rows,
        lut_geo,
        sop_geo,
        lut_sweeps,
        sop_sweeps,
    )
    write_html(
        args.html_out,
        version,
        lut_rows,
        sop_rows,
        lut_geo,
        sop_geo,
        lut_sweeps,
        sop_sweeps,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
