#!/usr/bin/env python3
"""
Generate an interactive time series HTML report from synthesis history.

Usage:
    timeseries-report history.json -o timeseries.html
    timeseries-report history.json -o timeseries.html --max-days 90
"""

import sys
import json
import argparse
from math import prod, exp, log
from pathlib import Path


METRICS = [
    ("gates", "Gates"),
    ("depth", "Depth"),
    ("area_asap7", "Area (ASAP7)"),
    ("delay_asap7", "Delay (ASAP7)"),
    ("area_sky130", "Area (Sky130)"),
    ("delay_sky130", "Delay (Sky130)"),
]

# Palette for category coloring in the all-benchmarks chart
_CATEGORY_PALETTE = [
    (33,  150, 243),   # blue
    (255, 152,   0),   # orange
    (76,  175,  80),   # green
    (156,  39, 176),   # purple
    (233,  30,  99),   # pink
    (0,   188, 212),   # cyan
    (255,  87,  34),   # deep-orange
    (96,  125, 139),   # blue-grey
]


def geo_mean(values):
    valid = [v for v in values if isinstance(v, (int, float)) and v > 0]
    if not valid:
        return None
    return exp(sum(log(v) for v in valid) / len(valid))


def build_chart_data(history):
    dates = [e["date"] for e in history]
    circt_versions = [e.get("circt_version", "unknown") for e in history]
    yosys_versions = [e.get("yosys_version", "unknown") for e in history]

    # Collect all benchmark names across all history entries
    all_benchmarks = set()
    for entry in history:
        all_benchmarks.update(entry.get("circt", {}).get("benchmarks", {}).keys())
        all_benchmarks.update(entry.get("yosys", {}).get("benchmarks", {}).keys())
    all_benchmarks = sorted(all_benchmarks)

    # Overview: geo-mean across all benchmarks per metric
    overview = {}
    for metric_key, _ in METRICS:
        circt_geo = []
        yosys_geo = []
        for entry in history:
            circt_vals = [
                b.get(metric_key)
                for b in entry.get("circt", {}).get("benchmarks", {}).values()
            ]
            yosys_vals = [
                b.get(metric_key)
                for b in entry.get("yosys", {}).get("benchmarks", {}).values()
            ]
            circt_geo.append(geo_mean(circt_vals))
            yosys_geo.append(geo_mean(yosys_vals))
        overview[metric_key] = {"circt": circt_geo, "yosys": yosys_geo}

    # Per-benchmark absolute values per metric
    benchmark_data = {}
    for bname in all_benchmarks:
        bdata = {}
        for metric_key, _ in METRICS:
            circt_vals = []
            yosys_vals = []
            for entry in history:
                cb = entry.get("circt", {}).get("benchmarks", {}).get(bname, {})
                yb = entry.get("yosys", {}).get("benchmarks", {}).get(bname, {})
                circt_vals.append(cb.get(metric_key))
                yosys_vals.append(yb.get(metric_key))
            bdata[metric_key] = {"circt": circt_vals, "yosys": yosys_vals}
        benchmark_data[bname] = bdata

    # Per-benchmark % difference (CIRCT vs Yosys) over time
    benchmark_pct = {}
    for bname in all_benchmarks:
        bpct = {}
        for metric_key, _ in METRICS:
            pcts = []
            for entry in history:
                cv = entry.get("circt", {}).get("benchmarks", {}).get(bname, {}).get(metric_key)
                yv = entry.get("yosys", {}).get("benchmarks", {}).get(bname, {}).get(metric_key)
                if cv and yv and yv > 0:
                    pcts.append(round((cv - yv) / yv * 100, 2))
                else:
                    pcts.append(None)
            bpct[metric_key] = pcts
        benchmark_pct[bname] = bpct

    # Category per benchmark (take from most recent entry that has it)
    benchmark_categories = {}
    for bname in all_benchmarks:
        for entry in reversed(history):
            cat = entry.get("circt", {}).get("benchmarks", {}).get(bname, {}).get("category")
            if cat:
                benchmark_categories[bname] = cat
                break
        else:
            benchmark_categories[bname] = "Other"

    return {
        "dates": dates,
        "circt_versions": circt_versions,
        "yosys_versions": yosys_versions,
        "overview": overview,
        "benchmarks": all_benchmarks,
        "benchmark_data": benchmark_data,
        "benchmark_pct": benchmark_pct,
        "benchmark_categories": benchmark_categories,
        "metrics": [{"key": k, "label": l} for k, l in METRICS],
    }


def _category_palette_js():
    """Return JS snippet defining the category-color mapping."""
    palette = _CATEGORY_PALETTE
    return f"const CAT_PALETTE = {json.dumps([list(c) for c in palette])};"


def generate_html(history, chart_data):
    last_date = history[-1]["date"] if history else "N/A"
    n = len(history)
    data_json = json.dumps(chart_data)
    cat_palette_js = _category_palette_js()

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>CIRCT Synth Tracker – History</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-annotation@3.0.1/dist/chartjs-plugin-annotation.min.js"></script>
  <style>
    * {{ box-sizing: border-box; }}
    body {{
      font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
      margin: 0;
      padding: 20px;
      background: #f5f5f5;
      color: #333;
    }}
    .container {{
      max-width: 1400px;
      margin: 0 auto;
      background: white;
      padding: 30px;
      box-shadow: 0 0 10px rgba(0,0,0,0.1);
    }}
    h1 {{
      color: #333;
      border-bottom: 3px solid #4CAF50;
      padding-bottom: 10px;
      margin-top: 0;
    }}
    h2 {{
      color: #555;
      margin-top: 40px;
      border-bottom: 2px solid #ddd;
      padding-bottom: 5px;
    }}
    .meta {{
      color: #777;
      font-size: 0.9em;
      margin: 0 0 20px;
    }}
    nav {{
      margin-bottom: 30px;
    }}
    nav a {{
      display: inline-block;
      padding: 6px 16px;
      margin-right: 8px;
      border-radius: 4px;
      text-decoration: none;
      color: #4CAF50;
      border: 1px solid #4CAF50;
    }}
    nav a.active {{
      background: #4CAF50;
      color: white;
    }}
    .charts-grid {{
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 24px;
      margin-top: 20px;
    }}
    @media (max-width: 800px) {{
      .charts-grid {{ grid-template-columns: 1fr; }}
    }}
    .chart-card {{
      background: #fafafa;
      border: 1px solid #e0e0e0;
      border-radius: 6px;
      padding: 16px;
    }}
    .chart-card-full {{
      background: #fafafa;
      border: 1px solid #e0e0e0;
      border-radius: 6px;
      padding: 16px;
      margin-top: 16px;
    }}
    .selector-row {{
      display: flex;
      align-items: center;
      gap: 24px;
      flex-wrap: wrap;
      margin: 20px 0 10px;
    }}
    .selector-row label {{
      font-weight: bold;
    }}
    select {{
      margin-left: 8px;
      padding: 6px 12px;
      border: 1px solid #ccc;
      border-radius: 4px;
      font-size: 14px;
      min-width: 200px;
    }}
    .cat-legend {{
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      margin: 10px 0 4px;
      font-size: 0.85em;
    }}
    .cat-legend-item {{
      display: flex;
      align-items: center;
      gap: 5px;
    }}
    .cat-swatch {{
      width: 12px;
      height: 12px;
      border-radius: 50%;
      flex-shrink: 0;
    }}
    .footnote {{
      color: #888;
      font-size: 0.82em;
      margin: 4px 0 0;
    }}
    .footer {{
      margin-top: 40px;
      padding-top: 20px;
      border-top: 1px solid #ddd;
      text-align: center;
      color: #999;
      font-size: 0.85em;
    }}
  </style>
</head>
<body>
  <div class="container">
    <h1>CIRCT Synth Tracker – History</h1>
    <p class="meta">Last updated: {last_date} &nbsp;·&nbsp; {n} data point{'s' if n != 1 else ''}</p>

    <nav>
      <a href="report.html">Latest Report</a>
      <a href="timeseries.html" class="active">History</a>
    </nav>

    <!-- ── Overview ───────────────────────────────────────────── -->
    <h2>Overview (Geometric Mean Across All Benchmarks)</h2>
    <div class="charts-grid">
      <div class="chart-card"><canvas id="ov-gates"></canvas></div>
      <div class="chart-card"><canvas id="ov-depth"></canvas></div>
      <div class="chart-card"><canvas id="ov-area_asap7"></canvas></div>
      <div class="chart-card"><canvas id="ov-delay_asap7"></canvas></div>
      <div class="chart-card"><canvas id="ov-area_sky130"></canvas></div>
      <div class="chart-card"><canvas id="ov-delay_sky130"></canvas></div>
    </div>

    <!-- ── All benchmarks normalized % ───────────────────────── -->
    <h2>All Benchmarks – CIRCT vs Yosys (%)</h2>
    <p style="color:#555; font-size:0.9em; margin-bottom:6px;">
      Each line is one benchmark.
      <span style="color:#4CAF50; font-weight:bold">Negative</span> = CIRCT uses fewer resources (better).
      <span style="color:#f44336; font-weight:bold">Positive</span> = Yosys is better.
      Hover to identify a benchmark.
    </p>
    <div class="selector-row">
      <label>Metric: <select id="pct-metric-select"></select></label>
    </div>
    <div id="cat-legend" class="cat-legend"></div>
    <p class="footnote">Lines are colored by benchmark category.</p>
    <div class="chart-card-full">
      <canvas id="pct-chart"></canvas>
    </div>

    <!-- ── Benchmark detail ───────────────────────────────────── -->
    <h2>Benchmark Detail</h2>
    <div class="selector-row">
      <label>Benchmark: <select id="benchmark-select"></select></label>
    </div>
    <div class="charts-grid">
      <div class="chart-card"><canvas id="bm-gates"></canvas></div>
      <div class="chart-card"><canvas id="bm-depth"></canvas></div>
      <div class="chart-card"><canvas id="bm-area_asap7"></canvas></div>
      <div class="chart-card"><canvas id="bm-delay_asap7"></canvas></div>
      <div class="chart-card"><canvas id="bm-area_sky130"></canvas></div>
      <div class="chart-card"><canvas id="bm-delay_sky130"></canvas></div>
    </div>

    <div class="footer">
      Generated by circt-synth-tracker timeseries-report
    </div>
  </div>

  <script>
    const DATA = {data_json};
    {cat_palette_js}

    const CIRCT_COLOR = '#2196F3';
    const YOSYS_COLOR = '#FF9800';

    // ── category color helpers ──────────────────────────────────
    const _catIndex = {{}};
    (function() {{
      const cats = [...new Set(Object.values(DATA.benchmark_categories))].sort();
      cats.forEach((c, i) => {{ _catIndex[c] = i % CAT_PALETTE.length; }});
    }})();

    function catColor(cat, alpha) {{
      const [r, g, b] = CAT_PALETTE[_catIndex[cat] ?? 0];
      return `rgba(${{r}},${{g}},${{b}},${{alpha}})`;
    }}

    // ── build category legend ───────────────────────────────────
    (function() {{
      const seen = {{}};
      const leg = document.getElementById('cat-legend');
      DATA.benchmarks.forEach(function(bname) {{
        const cat = DATA.benchmark_categories[bname] || 'Other';
        if (seen[cat]) return;
        seen[cat] = true;
        const item = document.createElement('div');
        item.className = 'cat-legend-item';
        item.innerHTML =
          `<span class="cat-swatch" style="background:${{catColor(cat, 1)}}"></span>` +
          `<span>${{cat}}</span>`;
        leg.appendChild(item);
      }});
    }})();

    // ── CIRCT version change annotations ───────────────────────
    function shortVer(v) {{
      const m = v.match(/firtool-(\d+\.\d+\.\d+-\d+)/);
      return m ? m[1] : v.substring(0, 14);
    }}

    function getVersionAnnotations() {{
      const anns = {{}};
      for (let i = 1; i < DATA.circt_versions.length; i++) {{
        if (DATA.circt_versions[i] !== DATA.circt_versions[i - 1]) {{
          anns['ver' + i] = {{
            type: 'line',
            scaleID: 'x',
            value: DATA.dates[i],
            borderColor: 'rgba(33,150,243,0.45)',
            borderWidth: 1.5,
            borderDash: [5, 4],
            label: {{
              content: shortVer(DATA.circt_versions[i]),
              display: true,
              position: 'start',
              font: {{ size: 9 }},
              color: 'rgba(33,150,243,0.9)',
              backgroundColor: 'rgba(255,255,255,0.7)',
              padding: 3,
            }},
          }};
        }}
      }}
      return anns;
    }}

    // ── shared tooltip helpers ──────────────────────────────────
    function versionTooltip() {{
      return {{
        callbacks: {{
          footer: function(items) {{
            const i = items[0].dataIndex;
            return 'CIRCT: ' + DATA.circt_versions[i] + '\\nYosys: ' + DATA.yosys_versions[i];
          }}
        }}
      }};
    }}

    // ── overview charts ─────────────────────────────────────────
    const chartInstances = {{}};

    function createOrUpdateChart(canvasId, labels, circtData, yosysData, title) {{
      if (chartInstances[canvasId]) chartInstances[canvasId].destroy();
      const ctx = document.getElementById(canvasId).getContext('2d');
      chartInstances[canvasId] = new Chart(ctx, {{
        type: 'line',
        data: {{
          labels,
          datasets: [
            {{ label: 'CIRCT', data: circtData, borderColor: CIRCT_COLOR,
               backgroundColor: CIRCT_COLOR, pointRadius: 4, tension: 0.1, spanGaps: true }},
            {{ label: 'Yosys', data: yosysData, borderColor: YOSYS_COLOR,
               backgroundColor: YOSYS_COLOR, pointRadius: 4, tension: 0.1, spanGaps: true }},
          ],
        }},
        options: {{
          responsive: true,
          plugins: {{
            title: {{ display: true, text: title, font: {{ size: 14 }} }},
            tooltip: versionTooltip(),
            annotation: {{ annotations: getVersionAnnotations() }},
          }},
          scales: {{
            x: {{ ticks: {{ maxRotation: 45, minRotation: 0 }} }},
            y: {{ beginAtZero: false }},
          }},
        }},
      }});
    }}

    function renderOverview() {{
      DATA.metrics.forEach(function(m) {{
        const ov = DATA.overview[m.key];
        createOrUpdateChart('ov-' + m.key, DATA.dates, ov.circt, ov.yosys, m.label + ' (geo-mean)');
      }});
    }}

    // ── all-benchmarks normalized % chart ──────────────────────
    let pctChart = null;

    function renderPctChart(metricKey) {{
      if (pctChart) {{ pctChart.destroy(); pctChart = null; }}

      const datasets = DATA.benchmarks.map(function(bname) {{
        const cat = DATA.benchmark_categories[bname] || 'Other';
        return {{
          label: bname,
          data: DATA.benchmark_pct[bname][metricKey],
          borderColor: catColor(cat, 0.55),
          backgroundColor: catColor(cat, 0.55),
          borderWidth: 1.5,
          pointRadius: 2,
          pointHoverRadius: 5,
          tension: 0.1,
          spanGaps: true,
        }};
      }});

      const metricLabel = DATA.metrics.find(m => m.key === metricKey)?.label ?? metricKey;

      pctChart = new Chart(document.getElementById('pct-chart'), {{
        type: 'line',
        data: {{ labels: DATA.dates, datasets }},
        options: {{
          responsive: true,
          interaction: {{ mode: 'nearest', intersect: false }},
          plugins: {{
            title: {{ display: true, text: metricLabel + ' – CIRCT vs Yosys (% per benchmark)', font: {{ size: 14 }} }},
            legend: {{ display: false }},
            annotation: {{ annotations: getVersionAnnotations() }},
            tooltip: {{
              callbacks: {{
                title: (items) => items[0].dataset.label,
                label: function(ctx) {{
                  const v = ctx.parsed.y;
                  if (v === null || v === undefined) return 'N/A';
                  const sign = v > 0 ? '+' : '';
                  return sign + v.toFixed(1) + '% vs Yosys';
                }},
                footer: function(items) {{
                  const i = items[0].dataIndex;
                  return 'Date: ' + DATA.dates[i] +
                    '\\nCIRCT: ' + DATA.circt_versions[i];
                }},
              }},
            }},
          }},
          scales: {{
            x: {{ ticks: {{ maxRotation: 45, minRotation: 0 }} }},
            y: {{
              title: {{ display: true, text: '% vs Yosys  (negative = CIRCT better)', font: {{ size: 11 }} }},
              grid: {{
                color: (ctx) => ctx.tick.value === 0 ? 'rgba(0,0,0,0.35)' : 'rgba(0,0,0,0.07)',
                lineWidth: (ctx) => ctx.tick.value === 0 ? 2 : 1,
              }},
            }},
          }},
        }},
      }});
    }}

    // populate metric selector for pct chart
    const pctSel = document.getElementById('pct-metric-select');
    DATA.metrics.forEach(function(m) {{
      const opt = document.createElement('option');
      opt.value = m.key;
      opt.textContent = m.label;
      pctSel.appendChild(opt);
    }});
    pctSel.addEventListener('change', function() {{ renderPctChart(this.value); }});

    // ── benchmark detail charts ─────────────────────────────────
    function renderBenchmark(name) {{
      const bdata = DATA.benchmark_data[name];
      DATA.metrics.forEach(function(m) {{
        const d = bdata[m.key];
        createOrUpdateChart('bm-' + m.key, DATA.dates, d.circt, d.yosys, name + ' – ' + m.label);
      }});
    }}

    const bmSel = document.getElementById('benchmark-select');
    DATA.benchmarks.forEach(function(name) {{
      const opt = document.createElement('option');
      opt.value = name;
      opt.textContent = name;
      bmSel.appendChild(opt);
    }});
    bmSel.addEventListener('change', function() {{ renderBenchmark(this.value); }});

    // ── initial render ──────────────────────────────────────────
    renderOverview();
    if (DATA.metrics.length > 0) renderPctChart(DATA.metrics[0].key);
    if (DATA.benchmarks.length > 0) renderBenchmark(DATA.benchmarks[0]);
  </script>
</body>
</html>
"""


def main():
    parser = argparse.ArgumentParser(
        description="Generate interactive time series HTML report from synthesis history"
    )
    parser.add_argument("history", help="History JSON file")
    parser.add_argument(
        "-o", "--output", default="timeseries.html",
        help="Output HTML file (default: timeseries.html)"
    )
    parser.add_argument(
        "--max-days", type=int, default=0, help="Use only the last N entries (0 = all)"
    )

    args = parser.parse_args()

    history_path = Path(args.history)
    if not history_path.exists():
        print(f"Error: History file not found: {history_path}", file=sys.stderr)
        return 1

    with open(history_path) as f:
        history = json.load(f)

    if not history:
        print("Error: history is empty", file=sys.stderr)
        return 1

    if args.max_days > 0:
        history = history[-args.max_days :]

    chart_data = build_chart_data(history)
    html = generate_html(history, chart_data)

    output_path = Path(args.output)
    with open(output_path, "w") as f:
        f.write(html)

    print(f"Time series report generated: {output_path} ({len(history)} data points)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
