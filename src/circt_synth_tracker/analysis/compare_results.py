#!/usr/bin/env python3
"""
Compare synthesis results across different tools from JSON summary files.

Usage:
    compare-results circt-synth-summary.json yosys-summary.json
    compare-results *.json --format table
    compare-results *.json --benchmark add_three_16
    compare-results *.json --export report.html
"""

import sys
import json
import argparse
from pathlib import Path
from tabulate import tabulate


def main():
    parser = argparse.ArgumentParser(
        description="Compare synthesis benchmark results from JSON summaries"
    )
    parser.add_argument("summaries", nargs="+", help="JSON summary files to compare")
    parser.add_argument("--benchmark", help="Specific benchmark to compare")
    parser.add_argument(
        "--format",
        default="",
        choices=["table", "json", "markdown", "html"],
        help="Output format",
    )
    parser.add_argument(
        "--metric", help="Specific metric to compare (gates, depth, etc.)"
    )
    parser.add_argument(
        "--export", "-o", help="Export to file (use with --format html for report)"
    )

    args = parser.parse_args()

    # If export specified without format, infer from extension
    if args.export and not args.format:
        ext = Path(args.export).suffix.lower()
        if ext == ".html":
            print("Exporting to HTML report")
            args.format = "html"
        elif ext == ".json":
            args.format = "json"
        elif ext == ".md":
            args.format = "markdown"

    # Load all summary files
    summaries = {}
    for summary_file in args.summaries:
        path = Path(summary_file)
        if not path.exists():
            print(f"Error: File not found: {path}", file=sys.stderr)
            continue

        try:
            with open(path, "r") as f:
                data = json.load(f)
                tool_name = data.get("tool", path.stem)
                summaries[tool_name] = data
        except Exception as e:
            print(f"Error loading {path}: {e}", file=sys.stderr)

    if not summaries:
        print("Error: No valid summary files loaded", file=sys.stderr)
        return 1

    print(f"Loaded summaries for {len(summaries)} tools: {', '.join(summaries.keys())}")

    if args.benchmark:
        # Compare specific benchmark across tools
        compare_benchmark(
            summaries, args.benchmark, args.format, args.metric, args.export
        )
    else:
        # Compare all benchmarks
        compare_all(summaries, args.format, args.export)

    return 0


def compare_benchmark(
    summaries, benchmark_name, format_type, metric_filter=None, export_path=None
):
    """Compare a specific benchmark across all tools."""

    comparison = {}

    for tool_name, summary in summaries.items():
        benchmarks = summary.get("benchmarks", {})
        if benchmark_name in benchmarks:
            comparison[tool_name] = benchmarks[benchmark_name]

    if export_path:
        output = None
        if format_type == "json":
            import json

            output = json.dumps(comparison, indent=2)
        elif format_type == "markdown":
            # Capture Markdown output
            import io
            from contextlib import redirect_stdout

            f = io.StringIO()
            with redirect_stdout(f):
                display_markdown(comparison, metric_filter)
            output = f.getvalue()
        elif format_type == "html":
            # Capture HTML output
            import io
            from contextlib import redirect_stdout

            f = io.StringIO()
            with redirect_stdout(f):
                display_html(comparison, benchmark_name, metric_filter)
            output = f.getvalue()

        if output:
            with open(export_path, "w") as f:
                f.write(output)
            print(f"Results exported to {export_path}")
    else:
        display_comparison(comparison, benchmark_name, format_type, metric_filter)


def compare_all(summaries, format_type, export_path=None):
    """Compare all benchmarks across all tools."""

    # Collect all unique benchmark names
    all_benchmarks = set()
    for summary in summaries.values():
        all_benchmarks.update(summary.get("benchmarks", {}).keys())

    if not all_benchmarks:
        print("No benchmarks found in summaries")
        return

    print(f"\nFound {len(all_benchmarks)} unique benchmarks\n")

    # If HTML export requested, generate full report
    if export_path and format_type == "html":
        generate_html_report(summaries, all_benchmarks, export_path)
        return

    # If JSON export requested, generate combined JSON
    if export_path and format_type == "json":
        generate_json_report(summaries, all_benchmarks, export_path)
        return

    # If Markdown export requested, generate combined Markdown
    if export_path and format_type == "markdown":
        generate_markdown_report(summaries, all_benchmarks, export_path)
        return

    # Compare each benchmark
    for benchmark_name in sorted(all_benchmarks):
        comparison = {}

        for tool_name, summary in summaries.items():
            benchmarks = summary.get("benchmarks", {})
            if benchmark_name in benchmarks:
                comparison[tool_name] = benchmarks[benchmark_name]

        if len(comparison) > 1:  # Only show if multiple tools have this benchmark
            display_comparison(comparison, benchmark_name, format_type)


def generate_html_report(summaries, all_benchmarks, output_path):
    """Generate a comprehensive HTML report comparing all benchmarks."""

    tool_names = list(summaries.keys())

    # Helper function to extract category from benchmark data
    def get_category(benchmark_name, summaries):
        """Extract category from benchmark data (direct field or parsed from path)."""
        for tool_name, summary in summaries.items():
            benchmarks = summary.get("benchmarks", {})
            if benchmark_name in benchmarks:
                benchmark_data = benchmarks[benchmark_name]
                category = benchmark_data["category"]
                return category
        return "Other"

    # Group benchmarks by category
    benchmarks_by_category = {}
    for benchmark_name in all_benchmarks:
        category = get_category(benchmark_name, summaries)
        if category not in benchmarks_by_category:
            benchmarks_by_category[category] = []
        benchmarks_by_category[category].append(benchmark_name)

    # Sort categories and benchmarks within each category
    sorted_categories = sorted(benchmarks_by_category.keys())

    html = (
        """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Synthesis Benchmark Comparison Report</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .container {
            max-width: 1400px;
            margin: 0 auto;
            background-color: white;
            padding: 30px;
            box-shadow: 0 0 10px rgba(0,0,0,0.1);
        }
        h1 {
            color: #333;
            border-bottom: 3px solid #4CAF50;
            padding-bottom: 10px;
        }
        h2 {
            color: #555;
            margin-top: 30px;
            border-bottom: 2px solid #ddd;
            padding-bottom: 5px;
        }
        .summary {
            background-color: #f9f9f9;
            padding: 15px;
            border-left: 4px solid #4CAF50;
            margin-bottom: 20px;
        }
        table {
            border-collapse: collapse;
            width: 100%;
            margin: 20px 0;
            font-size: 14px;
        }
        th, td {
            border: 1px solid #ddd;
            padding: 12px 8px;
            text-align: left;
        }
        th {
            background-color: #4CAF50;
            color: white;
            font-weight: bold;
            position: sticky;
            top: 0;
        }
        tr:nth-child(even) {
            background-color: #f9f9f9;
        }
        tr:hover {
            background-color: #f5f5f5;
        }
        .metric {
            text-align: right;
            font-family: 'Courier New', monospace;
        }
        .metric-value {
            padding: 2px 4px;
            border-radius: 3px;
        }
        .benchmark-name {
            font-weight: bold;
            color: #333;
        }
        .diff {
            font-size: 0.9em;
            color: #666;
        }
        .footer {
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #ddd;
            text-align: center;
            color: #666;
            font-size: 0.9em;
        }
        .tool-column {
            min-width: 150px;
        }
        .category-header {
            background-color: #e8f5e9;
            font-weight: bold;
            color: #2e7d32;
            padding: 10px 8px;
            border-top: 2px solid #4CAF50;
        }
        .copy-button {
            background-color: #4CAF50;
            color: white;
            border: none;
            padding: 8px 16px;
            text-align: center;
            text-decoration: none;
            display: inline-block;
            font-size: 14px;
            margin: 4px 2px;
            cursor: pointer;
            border-radius: 4px;
            transition: background-color 0.3s;
        }
        .copy-button:hover {
            background-color: #45a049;
        }
        .copy-button:active {
            background-color: #3d8b40;
        }
        .copy-feedback {
            display: inline-block;
            margin-left: 10px;
            color: #4CAF50;
            font-weight: bold;
            opacity: 0;
            transition: opacity 0.3s;
        }
        .copy-feedback.show {
            opacity: 1;
        }
    </style>
    <script>
        function copyGeomeanAsMarkdown() {
            try {
                // Build markdown table from the geometric mean comparison table
                const markdown = generateGeomeanMarkdown();
                
                console.log('Attempting to copy markdown...');
                
                // Copy to clipboard
                navigator.clipboard.writeText(markdown).then(() => {
                    console.log('Copy successful!');
                    // Show feedback
                    const feedback = document.getElementById('copy-feedback');
                    feedback.classList.add('show');
                    setTimeout(() => {
                        feedback.classList.remove('show');
                    }, 2000);
                }).catch(err => {
                    console.error('Clipboard error:', err);
                    alert('Failed to copy to clipboard: ' + err + '\\n\\nTry opening the browser console to see the markdown table.');
                });
            } catch (err) {
                console.error('Error generating markdown:', err);
                alert('Error: ' + err);
            }
        }
        
        function generateGeomeanMarkdown() {
            const tool1 = '"""
        + tool_names[0]
        + """';
            const tool2 = '"""
        + tool_names[1]
        + """';
            
            let md = '| Category | Metric | ' + tool1 + ' | ' + tool2 + ' |' + '\\n';
            md += '|----------|--------|' + '-'.repeat(tool1.length + 2) + '|' + '-'.repeat(tool2.length + 2) + '|' + '\\n';
            
            // Get all rows from the geomean table
            const rows = document.querySelectorAll('#geomean-table tbody tr');
            let currentCategory = '';
            
            rows.forEach(row => {{
                const cells = row.querySelectorAll('td');
                if (cells.length === 0) return;
                
                // Check if this row has a category cell
                const categoryCell = cells[0];
                if (categoryCell.classList.contains('category-cell')) {{
                    currentCategory = categoryCell.textContent.trim();
                }}
                
                // Extract metric and values
                const metricIdx = categoryCell.classList.contains('category-cell') ? 1 : 0;
                const metric = cells[metricIdx].textContent.trim();
                const val1 = cells[metricIdx + 1].textContent.trim();
                const val2 = cells[metricIdx + 2].textContent.trim();
                
                // Format category (only show on first metric)
                const categoryText = (metric === 'Gates' || metric === '**Gates**') ? currentCategory : '';
                
                md += '| ' + categoryText + ' | ' + metric.replace(/\*\*/g, '') + ' | ' + 
                      val1.replace(/\*\*/g, '') + ' | ' + val2.replace(/\*\*/g, '') + ' |' + '\\n';
            }});
            
            console.log('Generated markdown:');
            console.log(md);
            return md;
        }
    </script>
</head>
<body>
    <div class="container">
        <h1>Synthesis Benchmark Comparison Report</h1>
        
        <div class="summary">
            <strong>Tools Compared:</strong> """
        + ", ".join(tool_names)
        + """<br>
            <strong>Total Benchmarks:</strong> """
        + str(len(all_benchmarks))
        + """<br>
            <strong>Categories:</strong> """
        + str(len(sorted_categories))
        + """<br>
            <strong>Generated:</strong> """
        + summaries[tool_names[0]].get("timestamp", "N/A")
        + """
        </div>
"""
    )

    # Generate comparison table
    html += """
        <h2>Benchmark Comparison</h2>
        <table>
            <thead>
                <tr>
                    <th>Benchmark</th>
"""

    # Add headers for each tool
    for tool in tool_names:
        html += f"                    <th class='tool-column' colspan='7'>{tool}</th>\n"

    html += """
                </tr>
                <tr>
                    <th></th>
"""

    # Sub-headers for metrics
    for _ in tool_names:
        html += "                    <th class='metric'>Gates</th><th class='metric'>Depth</th><th class='metric'>Area (ASAP7)</th><th class='metric'>Delay (ASAP7)</th><th class='metric'>Area (Sky130)</th><th class='metric'>Delay (Sky130)</th><th class='metric'>Runtime</th>\n"

    html += """
                </tr>
            </thead>
            <tbody>
"""

    # Add rows for each benchmark, grouped by category
    for category in sorted_categories:
        # Add category header row
        num_columns = 1 + (
            len(tool_names) * 7
        )  # 1 for benchmark name + 7 metrics per tool
        html += "                <tr>\n"
        html += f"                    <td colspan='{num_columns}' class='category-header'>📁 {category}</td>\n"
        html += "                </tr>\n"

        # Add benchmarks in this category
        for benchmark_name in sorted(benchmarks_by_category[category]):
            comparison = {}

            for tool_name, summary in summaries.items():
                benchmarks = summary.get("benchmarks", {})
                if benchmark_name in benchmarks:
                    comparison[tool_name] = benchmarks[benchmark_name]

            if len(comparison) < 2:
                continue

            html += "                <tr>\n"
            html += f"                    <td class='benchmark-name'>{benchmark_name}</td>\n"

            # Get baseline (first tool)
            baseline_tool = tool_names[0]
            baseline_result = comparison.get(baseline_tool, {})
            baseline_gates = baseline_result.get("gates", 0)
            baseline_depth = baseline_result.get("depth", 0)
            baseline_area_asap7 = baseline_result.get("area_asap7", 0)
            baseline_delay_asap7 = baseline_result.get("delay_asap7", 0)
            baseline_area_sky130 = baseline_result.get("area_sky130", 0)
            baseline_delay_sky130 = baseline_result.get("delay_sky130", 0)
            baseline_runtime = baseline_result.get("runtime_ms", 0)

            for tool in tool_names:
                result = comparison.get(tool, {})
                gates = result.get("gates", "N/A")
                depth = result.get("depth", "N/A")
                area_asap7 = result.get("area_asap7", "N/A")
                delay_asap7 = result.get("delay_asap7", "N/A")
                area_sky130 = result.get("area_sky130", "N/A")
                delay_sky130 = result.get("delay_sky130", "N/A")
                runtime = result.get("runtime_ms", "N/A")

                # Helper function to format metric with percentage and background color
                def format_metric(value, baseline, lower_is_better=True):
                    if value == "N/A" or not baseline or tool == baseline_tool:
                        return (str(value), "")  # (content, style)

                    diff = value - baseline
                    diff_pct = (diff / baseline * 100) if baseline > 0 else 0
                    abs_pct = abs(diff_pct)

                    # Skip coloring if difference is nearly zero (< 0.01%)
                    if abs_pct < 0.01:
                        if diff > 0:
                            content = (
                                f"{value} <span class='diff'>(+{diff_pct:.1f}%)</span>"
                            )
                        elif diff < 0:
                            content = (
                                f"{value} <span class='diff'>({diff_pct:.1f}%)</span>"
                            )
                        else:
                            content = str(value)
                        return (content, "")

                    # Determine if this is better or worse
                    is_better = (diff < 0) if lower_is_better else (diff > 0)

                    # Calculate background color based on percentage
                    # Green for better, red for worse, intensity based on percentage
                    if is_better:
                        # Green: scale from light green (0%) to darker green (20%+)
                        intensity = min(abs_pct / 20.0, 1.0)  # Cap at 20%
                        # RGB: light green (200,255,200) to darker green (150,255,150)
                        green_val = int(200 - (50 * intensity))
                        bg_color = f"rgb({green_val},255,{green_val})"
                    else:
                        # Red: scale from light red (0%) to darker red (20%+)
                        intensity = min(abs_pct / 20.0, 1.0)  # Cap at 20%
                        # RGB: light red (255,200,200) to darker red (255,150,150)
                        red_val = int(200 - (50 * intensity))
                        bg_color = f"rgb(255,{red_val},{red_val})"

                    # Return content and style for the cell
                    if diff > 0:
                        content = (
                            f"{value} <span class='diff'>(+{diff_pct:.1f}%)</span>"
                        )
                    elif diff < 0:
                        content = f"{value} <span class='diff'>({diff_pct:.1f}%)</span>"
                    else:
                        content = str(value)

                    return (content, f" style='background-color: {bg_color};'")

                # Format each metric (lower is better for all these metrics)
                gates_content, gates_style = format_metric(
                    gates, baseline_gates, lower_is_better=True
                )
                depth_content, depth_style = format_metric(
                    depth, baseline_depth, lower_is_better=True
                )
                area_asap7_content, area_asap7_style = format_metric(
                    area_asap7, baseline_area_asap7, lower_is_better=True
                )
                delay_asap7_content, delay_asap7_style = format_metric(
                    delay_asap7, baseline_delay_asap7, lower_is_better=True
                )
                area_sky130_content, area_sky130_style = format_metric(
                    area_sky130, baseline_area_sky130, lower_is_better=True
                )
                delay_sky130_content, delay_sky130_style = format_metric(
                    delay_sky130, baseline_delay_sky130, lower_is_better=True
                )
                runtime_content, runtime_style = format_metric(
                    runtime, baseline_runtime, lower_is_better=True
                )

                html += f"                    <td class='metric'{gates_style}>{gates_content}</td>\n"
                html += f"                    <td class='metric'{depth_style}>{depth_content}</td>\n"
                html += f"                    <td class='metric'{area_asap7_style}>{area_asap7_content}</td>\n"
                html += f"                    <td class='metric'{delay_asap7_style}>{delay_asap7_content}</td>\n"
                html += f"                    <td class='metric'{area_sky130_style}>{area_sky130_content}</td>\n"
                html += f"                    <td class='metric'{delay_sky130_style}>{delay_sky130_content}</td>\n"
                html += f"                    <td class='metric'{runtime_style}>{runtime_content}</td>\n"

            html += "                </tr>\n"

    html += """
            </tbody>
        </table>
"""

    # Add geometric mean comparison table
    if len(tool_names) == 2:
        html += """
        <h2>Geometric Mean Comparison
            <button class="copy-button" onclick="copyGeomeanAsMarkdown()">📋 Copy as Markdown</button>
            <span id="copy-feedback" class="copy-feedback">✓ Copied!</span>
        </h2>
        <table id="geomean-table">
            <thead>
                <tr>
                    <th>Category</th>
                    <th>Metric</th>
                    <th>{}</th>
                    <th>{}</th>
                </tr>
            </thead>
            <tbody>
""".format(tool_names[0], tool_names[1])

        baseline_tool = tool_names[0]
        compare_tool = tool_names[1]

        # Helper function for geometric mean
        def geo_mean(values):
            valid_values = [v for v in values if v and v > 0]
            if not valid_values:
                return 0
            product = 1
            for v in valid_values:
                product *= v
            return product ** (1.0 / len(valid_values))

        # Calculate overall geometric mean across all benchmarks
        all_baseline_benchmarks = list(
            summaries[baseline_tool].get("benchmarks", {}).values()
        )
        all_compare_benchmarks = list(
            summaries[compare_tool].get("benchmarks", {}).values()
        )

        metrics_data = [
            ("Gates", "gates"),
            ("Depth", "depth"),
            ("Area (ASAP7)", "area_asap7"),
            ("Delay (ASAP7)", "delay_asap7"),
            ("Area (Sky130)", "area_sky130"),
            ("Delay (Sky130)", "delay_sky130"),
        ]

        # Add overall row
        first_row = True
        for metric_name, metric_key in metrics_data:
            baseline_values = [b.get(metric_key, 0) for b in all_baseline_benchmarks]
            compare_values = [b.get(metric_key, 0) for b in all_compare_benchmarks]

            baseline_geo = geo_mean(baseline_values)
            compare_geo = geo_mean(compare_values)

            # Calculate background color for compare_geo cell
            if baseline_geo > 0 and compare_geo != "N/A":
                diff = compare_geo - baseline_geo
                diff_pct = (diff / baseline_geo * 100) if baseline_geo > 0 else 0
                abs_pct = abs(diff_pct)

                ratio = compare_geo / baseline_geo
                ratio_pct = (ratio - 1) * 100
                compare_display = (
                    f"{compare_geo:.1f} <span class='diff'>({ratio_pct:+.1f}%)</span>"
                )

                # Skip coloring if difference is nearly zero (< 0.01%)
                if abs_pct < 0.01:
                    compare_style = ""
                else:
                    is_better = diff < 0  # Lower is better

                    if is_better:
                        intensity = min(abs_pct / 20.0, 1.0)
                        green_val = int(200 - (50 * intensity))
                        compare_bg = f"rgb({green_val},255,{green_val})"
                    else:
                        intensity = min(abs_pct / 20.0, 1.0)
                        red_val = int(200 - (50 * intensity))
                        compare_bg = f"rgb(255,{red_val},{red_val})"
                    compare_style = f" style='background-color: {compare_bg};'"
            else:
                compare_style = ""
                compare_display = (
                    f"{compare_geo:.1f}" if compare_geo != "N/A" else "N/A"
                )

            category_cell = (
                f"<td rowspan='6' class='category-cell' style='background-color: #e3f2fd; font-weight: bold;'>Overall ({len(all_baseline_benchmarks)} benchmarks)</td>"
                if first_row
                else ""
            )
            html += f"""
                <tr style='background-color: #e3f2fd;'>
                    {category_cell}
                    <td><strong>{metric_name}</strong></td>
                    <td class='metric'><strong>{baseline_geo:.1f}</strong></td>
                    <td class='metric'{compare_style}><strong>{compare_display}</strong></td>
                </tr>
"""
            first_row = False

        for category in sorted_categories:
            # Get benchmarks for this category from both tools
            baseline_benchmarks = []
            compare_benchmarks = []

            for benchmark_name in benchmarks_by_category[category]:
                if benchmark_name in summaries[baseline_tool].get("benchmarks", {}):
                    baseline_benchmarks.append(
                        summaries[baseline_tool]["benchmarks"][benchmark_name]
                    )
                if benchmark_name in summaries[compare_tool].get("benchmarks", {}):
                    compare_benchmarks.append(
                        summaries[compare_tool]["benchmarks"][benchmark_name]
                    )

            if not baseline_benchmarks or not compare_benchmarks:
                continue

            # Calculate per-category geometric means
            first_row = True
            for metric_name, metric_key in metrics_data:
                baseline_values = [b.get(metric_key, 0) for b in baseline_benchmarks]
                compare_values = [b.get(metric_key, 0) for b in compare_benchmarks]

                baseline_geo = geo_mean(baseline_values)
                compare_geo = geo_mean(compare_values)

                # Calculate background color for compare_geo cell
                if baseline_geo > 0 and compare_geo != "N/A":
                    diff = compare_geo - baseline_geo
                    diff_pct = (diff / baseline_geo * 100) if baseline_geo > 0 else 0
                    abs_pct = abs(diff_pct)

                    ratio = compare_geo / baseline_geo
                    ratio_pct = (ratio - 1) * 100
                    compare_display = f"{compare_geo:.1f} <span class='diff'>({ratio_pct:+.1f}%)</span>"

                    # Skip coloring if difference is nearly zero (< 0.01%)
                    if abs_pct < 0.01:
                        compare_style = ""
                    else:
                        is_better = diff < 0  # Lower is better

                        if is_better:
                            intensity = min(abs_pct / 20.0, 1.0)
                            green_val = int(200 - (50 * intensity))
                            compare_bg = f"rgb({green_val},255,{green_val})"
                        else:
                            intensity = min(abs_pct / 20.0, 1.0)
                            red_val = int(200 - (50 * intensity))
                            compare_bg = f"rgb(255,{red_val},{red_val})"
                        compare_style = f" style='background-color: {compare_bg};'"
                else:
                    compare_style = ""
                    compare_display = (
                        f"{compare_geo:.1f}" if compare_geo != "N/A" else "N/A"
                    )

                category_cell = (
                    f"<td rowspan='6' class='category-cell benchmark-name'>{category}</td>"
                    if first_row
                    else ""
                )
                html += f"""
                <tr>
                    {category_cell}
                    <td>{metric_name}</td>
                    <td class='metric'>{baseline_geo:.1f}</td>
                    <td class='metric'{compare_style}>{compare_display}</td>
                </tr>
"""
                first_row = False

        html += """
            </tbody>
        </table>
"""

    html += """
        <div class="footer">
            Generated by circt-synth-tracker compare-results
        </div>
    </div>
</body>
</html>
"""

    # Write HTML file
    with open(output_path, "w") as f:
        f.write(html)

    print(f"HTML report generated: {output_path}")


def generate_json_report(summaries, all_benchmarks, output_path):
    """Generate a comprehensive JSON report comparing all benchmarks."""
    import json

    tool_names = list(summaries.keys())

    # Build comprehensive JSON structure
    report = {
        "metadata": {
            "tools_compared": tool_names,
            "total_benchmarks": len(all_benchmarks),
            "generated": summaries[tool_names[0]].get("timestamp", "N/A")
        },
        "benchmarks": {}
    }

    for benchmark_name in sorted(all_benchmarks):
        comparison = {}

        for tool_name, summary in summaries.items():
            benchmarks = summary.get("benchmarks", {})
            if benchmark_name in benchmarks:
                comparison[tool_name] = benchmarks[benchmark_name]

        if len(comparison) >= 2:  # Include benchmarks with at least 2 tools
            report["benchmarks"][benchmark_name] = comparison

    # Write JSON file
    with open(output_path, "w") as f:
        json.dump(report, f, indent=2)

    print(f"JSON report generated: {output_path}")


def generate_markdown_report(summaries, all_benchmarks, output_path):
    """Generate a comprehensive Markdown report comparing all benchmarks."""

    tool_names = list(summaries.keys())

    markdown = f"""# Synthesis Benchmark Comparison Report

**Tools Compared:** {", ".join(tool_names)}\\
**Total Benchmarks:** {len(all_benchmarks)}\\
**Generated:** {summaries[tool_names[0]].get("timestamp", "N/A")}

"""

    for benchmark_name in sorted(all_benchmarks):
        comparison = {}

        for tool_name, summary in summaries.items():
            benchmarks = summary.get("benchmarks", {})
            if benchmark_name in benchmarks:
                comparison[tool_name] = benchmarks[benchmark_name]

        if len(comparison) < 2:
            continue

        markdown += f"## {benchmark_name}\n\n"

        # Get baseline (first tool)
        baseline_tool = tool_names[0]
        baseline_result = comparison.get(baseline_tool, {})
        baseline_gates = baseline_result.get("gates", 0)
        baseline_depth = baseline_result.get("depth", 0)
        baseline_area_asap7 = baseline_result.get("area_asap7", 0)
        baseline_delay_asap7 = baseline_result.get("delay_asap7", 0)
        baseline_area_sky130 = baseline_result.get("area_sky130", 0)
        baseline_delay_sky130 = baseline_result.get("delay_sky130", 0)
        baseline_runtime = baseline_result.get("runtime_ms", 0)

        headers = ["Tool", "Gates", "Depth", "Area (ASAP7)", "Delay (ASAP7)", "Area (Sky130)", "Delay (Sky130)", "Runtime"]
        rows = []

        for tool in sorted(comparison.keys()):
            result = comparison[tool]

            # Helper to format value with percentage
            def fmt(value, baseline):
                if value is None or value == "N/A":
                    return "-"
                if not baseline or tool == baseline_tool:
                    return str(value)
                diff = value - baseline
                diff_pct = (diff / baseline * 100) if baseline > 0 else 0
                if diff > 0:
                    return f"{value} (+{diff_pct:.1f}%)"
                elif diff < 0:
                    return f"**{value}** ({diff_pct:.1f}%)"
                else:
                    return str(value)

            row = [
                tool,
                fmt(result.get("gates"), baseline_gates),
                fmt(result.get("depth"), baseline_depth),
                fmt(result.get("area_asap7"), baseline_area_asap7),
                fmt(result.get("delay_asap7"), baseline_delay_asap7),
                fmt(result.get("area_sky130"), baseline_area_sky130),
                fmt(result.get("delay_sky130"), baseline_delay_sky130),
                fmt(result.get("runtime_ms"), baseline_runtime),
            ]
            rows.append(row)

        # Add table using tabulate
        from tabulate import tabulate
        markdown += tabulate(rows, headers=headers, tablefmt="github") + "\n\n"

    # Write Markdown file
    with open(output_path, "w") as f:
        f.write(markdown)

    print(f"Markdown report generated: {output_path}")


def display_comparison(comparison, benchmark_name, format_type, metric_filter=None):
    """Display comparison in requested format."""

    if not comparison:
        print(f"No results found for benchmark: {benchmark_name}")
        return

    print(f"\n=== Comparison for {benchmark_name} ===\n")

    if format_type == "table":
        display_table(comparison, metric_filter)
    elif format_type == "json":
        import json

        print(json.dumps(comparison, indent=2))
    elif format_type == "markdown":
        display_markdown(comparison, metric_filter)
    elif format_type == "html":
        display_html(comparison, benchmark_name, metric_filter)


def display_table(comparison, metric_filter=None):
    """Display comparison as a table."""

    # Prepare table data
    headers = [
        "Tool",
        "Gates",
        "Inputs",
        "Outputs",
        "Depth",
        "Area (ASAP7)",
        "Delay (ASAP7)",
        "Area (Sky130)",
        "Delay (Sky130)",
        "Runtime (ms)",
    ]
    rows = []

    for tool, result in sorted(comparison.items()):
        # Support both 'inputs'/'outputs' and 'num_inputs'/'num_outputs'
        row = [
            tool,
            result.get("gates", "N/A"),
            result.get("inputs") or result.get("num_inputs", "N/A"),
            result.get("outputs") or result.get("num_outputs", "N/A"),
            result.get("depth", "N/A"),
            result.get("area_asap7", "N/A"),
            result.get("delay_asap7", "N/A"),
            result.get("area_sky130", "N/A"),
            result.get("delay_sky130", "N/A"),
            result.get("runtime_ms", "N/A"),
        ]
        rows.append(row)

    # Display table
    print(tabulate(rows, headers=headers, tablefmt="grid"))

    # Calculate differences
    if len(rows) > 1:
        print("\n=== Relative Differences ===\n")
        display_differences(comparison)


def display_differences(comparison):
    """Display relative differences between tools."""

    tools = list(comparison.keys())
    if len(tools) < 2:
        return

    base_tool = tools[0]
    base_result = comparison[base_tool]

    # Include technology-specific metric names
    metrics = [
        ("gates", "gates"),
        ("depth", "depth"),
        ("area_asap7", "area (ASAP7)"),
        ("delay_asap7", "delay (ASAP7)"),
        ("area_sky130", "area (sky130)"),
        ("delay_sky130", "delay (sky130)"),
        ("runtime_ms", "runtime_ms"),
    ]

    for metric_key, metric_display in metrics:
        base_value = base_result.get(metric_key)
        if base_value is None or base_value == 0:
            continue

        print(
            f"\n{metric_display.capitalize().replace('_', ' ')} comparison (relative to {base_tool}):"
        )
        for tool in tools[1:]:
            tool_value = comparison[tool].get(metric_key)
            if tool_value is None:
                continue

            diff = tool_value - base_value
            diff_pct = (diff / base_value) * 100

            sign = "+" if diff > 0 else ""
            print(f"  {tool:15s}: {sign}{diff:6d} ({sign}{diff_pct:+6.2f}%)")


def display_markdown(comparison, metric_filter=None):
    """Display comparison as Markdown table with percentages."""

    tools = list(comparison.keys())
    if not tools:
        return

    # Compact headers - show technology-specific metrics
    headers = [
        "Tool",
        "Gates",
        "Depth",
        "Area (ASAP7)",
        "Delay (ASAP7)",
        "Area (Sky130)",
        "Delay (Sky130)",
        "Runtime",
    ]
    rows = []

    # Get baseline (first tool)
    baseline_tool = tools[0]
    baseline_result = comparison.get(baseline_tool, {})
    baseline_gates = baseline_result.get("gates", 0)
    baseline_depth = baseline_result.get("depth", 0)
    baseline_area_asap7 = baseline_result.get("area_asap7", 0)
    baseline_delay_asap7 = baseline_result.get("delay_asap7", 0)
    baseline_area_sky130 = baseline_result.get("area_sky130", 0)
    baseline_delay_sky130 = baseline_result.get("delay_sky130", 0)
    baseline_runtime = baseline_result.get("runtime_ms", 0)

    for tool in sorted(comparison.keys()):
        result = comparison[tool]

        # Helper to format value with percentage
        def fmt(value, baseline):
            if value is None or value == "N/A":
                return "-"
            if not baseline or tool == baseline_tool:
                return str(value)
            diff = value - baseline
            diff_pct = (diff / baseline * 100) if baseline > 0 else 0
            if diff > 0:
                return f"{value} (+{diff_pct:.1f}%)"
            elif diff < 0:
                return f"**{value}** ({diff_pct:.1f}%)"
            else:
                return str(value)

        row = [
            tool,
            fmt(result.get("gates"), baseline_gates),
            fmt(result.get("depth"), baseline_depth),
            fmt(result.get("area_asap7"), baseline_area_asap7),
            fmt(result.get("delay_asap7"), baseline_delay_asap7),
            fmt(result.get("area_sky130"), baseline_area_sky130),
            fmt(result.get("delay_sky130"), baseline_delay_sky130),
            fmt(result.get("runtime_ms"), baseline_runtime),
        ]
        rows.append(row)

    # Display table using tabulate's markdown format
    print(tabulate(rows, headers=headers, tablefmt="github"))


def display_html(comparison, benchmark_name, metric_filter=None):
    """Display comparison as HTML."""

    html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Benchmark Comparison: {benchmark_name}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #4CAF50; color: white; }}
        tr:nth-child(even) {{ background-color: #f2f2f2; }}
        .better {{ color: green; font-weight: bold; }}
        .worse {{ color: red; }}
    </style>
</head>
<body>
    <h1>Benchmark Comparison: {benchmark_name}</h1>
    <table>
        <tr>
            <th>Tool</th>
            <th>Gates</th>
            <th>Inputs</th>
            <th>Outputs</th>
            <th>Depth</th>
            <th>Area (ASAP7)</th>
            <th>Delay (ASAP7)</th>
            <th>Area (Sky130)</th>
            <th>Delay (Sky130)</th>
            <th>Runtime (ms)</th>
        </tr>
"""

    for tool, result in sorted(comparison.items()):
        html += f"""
        <tr>
            <td>{tool}</td>
            <td>{result.get("gates", "N/A")}</td>
            <td>{result.get("inputs", "N/A")}</td>
            <td>{result.get("outputs", "N/A")}</td>
            <td>{result.get("depth", "N/A")}</td>
            <td>{result.get("area_asap7", "N/A")}</td>
            <td>{result.get("delay_asap7", "N/A")}</td>
            <td>{result.get("area_sky130", "N/A")}</td>
            <td>{result.get("delay_sky130", "N/A")}</td>
            <td>{result.get("runtime_ms", "N/A")}</td>
        </tr>
"""

    html += """
    </table>
</body>
</html>
"""

    print(html)


if __name__ == "__main__":
    sys.exit(main())
