#!/usr/bin/env python3
"""Generate an HTML time-series report for pass-benchmark ratios."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

METRICS = [
    ("lut_mapping_time", "LUT Mapping Time Ratio (CIRCT/ABC)"),
    ("sop_balancing_time", "SOP Balancing Time Ratio (CIRCT/ABC)"),
    ("lut_count", "LUT Count Ratio (CIRCT/ABC)"),
    ("lut_depth", "LUT Depth Ratio (CIRCT/ABC)"),
    ("aig_count", "AIG Count Ratio (CIRCT/ABC)"),
    ("aig_depth", "AIG Depth Ratio (CIRCT/ABC)"),
]


def build_chart_data(history: list[dict]) -> dict:
    return {
        "dates": [entry.get("date", "unknown") for entry in history],
        "circt_versions": [entry.get("circt_version", "unknown") for entry in history],
        "abc_versions": [entry.get("abc_version", "unknown") for entry in history],
        "metrics": [
            {
                "key": key,
                "label": label,
                "values": [entry.get("ratios", {}).get(key) for entry in history],
                "matched": [entry.get("matched", {}).get(key, 0) for entry in history],
            }
            for key, label in METRICS
        ],
    }


def generate_html(history: list[dict], chart_data: dict) -> str:
    last_date = history[-1]["date"] if history else "N/A"
    data_json = json.dumps(chart_data)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Pass Benchmark History</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
  <style>
    body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; color: #333; }}
    .container {{ max-width: 1400px; margin: 0 auto; background: white; padding: 30px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }}
    h1 {{ color: #333; border-bottom: 3px solid #4CAF50; padding-bottom: 10px; margin-top: 0; }}
    .meta {{ color: #777; font-size: 0.9em; margin: 0 0 20px; }}
    .charts-grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 24px; }}
    .chart-card {{ background: #fafafa; border: 1px solid #e0e0e0; border-radius: 6px; padding: 16px; }}
    @media (max-width: 800px) {{ .charts-grid {{ grid-template-columns: 1fr; }} }}
  </style>
</head>
<body>
  <div class="container">
    <h1>Pass Benchmark History</h1>
    <p class="meta">Entries: {len(history)} | Latest: {last_date} | Ratios below 1.0 mean CIRCT is better than ABC.</p>
    <div class="charts-grid">
      <div class="chart-card"><canvas id="chart-lut_mapping_time"></canvas></div>
      <div class="chart-card"><canvas id="chart-sop_balancing_time"></canvas></div>
      <div class="chart-card"><canvas id="chart-lut_count"></canvas></div>
      <div class="chart-card"><canvas id="chart-lut_depth"></canvas></div>
      <div class="chart-card"><canvas id="chart-aig_count"></canvas></div>
      <div class="chart-card"><canvas id="chart-aig_depth"></canvas></div>
    </div>
  </div>
  <script>
    const DATA = {data_json};
    function makeChart(metric) {{
      const ctx = document.getElementById(`chart-${{metric.key}}`);
      if (!ctx) return;
      new Chart(ctx, {{
        type: 'line',
        data: {{
          labels: DATA.dates,
          datasets: [{{
            label: metric.label,
            data: metric.values,
            borderColor: '#4CAF50',
            backgroundColor: 'rgba(76, 175, 80, 0.15)',
            tension: 0.2,
            spanGaps: true,
          }}],
        }},
        options: {{
          responsive: true,
          maintainAspectRatio: true,
          plugins: {{
            legend: {{ display: false }},
            tooltip: {{
              callbacks: {{
                afterLabel: (ctx) => {{
                  const i = ctx.dataIndex;
                  const matched = metric.matched[i];
                  const circt = DATA.circt_versions[i];
                  const abc = DATA.abc_versions[i];
                  return [`Matched: ${{matched}}`, `CIRCT: ${{circt}}`, `ABC: ${{abc}}`];
                }},
              }},
            }},
          }},
          scales: {{
            y: {{
              title: {{ display: true, text: 'Ratio' }},
            }},
          }},
        }},
        plugins: [{{
          id: 'baseline',
          afterDraw(chart) {{
            const yScale = chart.scales.y;
            const y = yScale.getPixelForValue(1.0);
            const {{ctx, chartArea}} = chart;
            ctx.save();
            ctx.strokeStyle = 'rgba(0, 0, 0, 0.35)';
            ctx.setLineDash([5, 5]);
            ctx.beginPath();
            ctx.moveTo(chartArea.left, y);
            ctx.lineTo(chartArea.right, y);
            ctx.stroke();
            ctx.restore();
          }},
        }}],
      }});
    }}
    DATA.metrics.forEach(makeChart);
  </script>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate pass benchmark time-series HTML report"
    )
    parser.add_argument("history", help="Pass benchmark history JSON file")
    parser.add_argument("-o", "--output", required=True, help="Output HTML file")
    args = parser.parse_args()

    history_path = Path(args.history)
    if not history_path.exists():
        print(f"Error: History file not found: {history_path}", file=sys.stderr)
        return 1

    with history_path.open() as f:
        history = json.load(f)

    chart_data = build_chart_data(history)
    output_path = Path(args.output)
    output_path.write_text(generate_html(history, chart_data))
    print(f"Pass time-series report generated: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
