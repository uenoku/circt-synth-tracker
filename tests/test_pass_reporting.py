import json
from argparse import Namespace

import pytest

from circt_synth_tracker.analysis.append_pass_history import build_history_entry
from circt_synth_tracker.analysis.pass_compare_results import run_pr
from circt_synth_tracker.analysis.pass_timeseries_report import build_chart_data


def _write_json(path, payload):
    path.write_text(json.dumps(payload))
    return path


def _table_cells(section, row_label):
    for line in section.splitlines():
        if line.startswith(f"| {row_label} |"):
            return [cell.strip() for cell in line.strip("|").split("|")]
    raise AssertionError(f"missing row: {row_label}")


@pytest.fixture
def pass_summaries():
    base = {
        "version": "base-v1",
        "benchmarks": {
            "adder": {
                "mode": "lut-mapping",
                "compile_time_s": 10.0,
                "lut_count": 100,
                "lut_depth": 20,
            },
            "adder_sop": {
                "mode": "sop-balancing",
                "compile_time_s": 8.0,
                "aig_count": 50,
                "aig_depth": 10,
            },
        },
    }
    pr = {
        "version": "pr-v1",
        "benchmarks": {
            "adder": {
                "mode": "lut-mapping",
                "compile_time_s": 5.0,
                "lut_count": 90,
                "lut_depth": 18,
            },
            "adder_sop": {
                "mode": "sop-balancing",
                "compile_time_s": 12.0,
                "aig_count": 60,
                "aig_depth": 11,
            },
        },
    }
    abc_base = {
        "version": "abc-base",
        "benchmarks": {
            "adder": {
                "mode": "lut-mapping",
                "compile_time_s": 20.0,
                "lut_count": 120,
                "lut_depth": 25,
            },
            "adder_sop": {
                "mode": "sop-balancing",
                "compile_time_s": 4.0,
                "aig_count": 55,
                "aig_depth": 12,
            },
        },
    }
    abc_pr = {
        "version": "abc-pr",
        "benchmarks": {
            "adder": {
                "mode": "lut-mapping",
                "compile_time_s": 10.0,
                "lut_count": 95,
                "lut_depth": 19,
            },
            "adder_sop": {
                "mode": "sop-balancing",
                "compile_time_s": 6.0,
                "aig_count": 58,
                "aig_depth": 11,
            },
        },
    }
    return base, pr, abc_base, abc_pr


def test_run_pr_report_uses_base_to_pr_order(tmp_path, pass_summaries):
    base, pr, abc_base, abc_pr = pass_summaries
    markdown_out = tmp_path / "report.md"
    html_out = tmp_path / "report.html"

    args = Namespace(
        before=_write_json(tmp_path / "base.json", base),
        after=_write_json(tmp_path / "pr.json", pr),
        label_a="Base",
        label_b="PR",
        ref_before=_write_json(tmp_path / "abc-base.json", abc_base),
        ref_after=_write_json(tmp_path / "abc-pr.json", abc_pr),
        ref_label="ABC",
        before_version="base-v1",
        after_version="pr-v1",
        pr_number="123",
        pr_title="Improve pass flow",
        base_sha="12345678deadbeef",
        head_sha="87654321feedface",
        title="Pass PR Comparison",
        markdown_out=markdown_out,
        html_out=html_out,
    )

    assert run_pr(args) == 0

    markdown = markdown_out.read_text()
    html = html_out.read_text()

    assert "### Base → PR (PR/Base)" in markdown
    assert (
        "| Mode | Geometric Mean Base (s) | Geometric Mean PR (s) | Delta (PR/Base) | Matched |"
        in markdown
    )
    assert "### Base/ABC → PR/ABC" in markdown
    assert "Geometric Mean ABC (Base) (s)" in markdown
    assert "Geometric Mean ABC (PR) (s)" in markdown
    abc_section = markdown.split("### Base/ABC → PR/ABC", 1)[1]
    assert _table_cells(abc_section, "LUT Mapping") == [
        "LUT Mapping",
        "10.0000",
        "5.0000",
        "20.0000",
        "10.0000",
        "0.5000",
        "0.5000",
        "1.0000",
    ]
    assert _table_cells(abc_section, "SOP Balancing") == [
        "SOP Balancing",
        "8.0000",
        "12.0000",
        "4.0000",
        "6.0000",
        "2.0000",
        "2.0000",
        "1.0000",
    ]
    assert "### Structural Metrics (PR/Base)" in markdown

    assert "<h2>Base → PR (PR/Base)</h2>" in html
    assert "Geometric Mean Base (s)" in html
    assert "Geometric Mean ABC (Base) (s)" in html
    assert "Geometric Mean ABC (PR) (s)" in html
    assert "Delta (PR/Base)" in html
    assert "LUT Mapping Details (Base → PR)" in html


def test_build_pass_history_entry_and_chart_data(pass_summaries):
    base, _, abc_base, _ = pass_summaries
    entry = build_history_entry(base, abc_base, "2026-04-18")

    assert entry["date"] == "2026-04-18"
    assert entry["circt_version"] == "base-v1"
    assert entry["abc_version"] == "abc-base"
    assert entry["ratios"]["lut_mapping_time"] == pytest.approx(0.5)
    assert entry["ratios"]["sop_balancing_time"] == pytest.approx(2.0)
    assert entry["ratios"]["lut_count"] == pytest.approx(100 / 120)
    assert entry["matched"]["aig_depth"] == 1

    chart_data = build_chart_data(
        [
            entry,
            {
                **entry,
                "date": "2026-04-19",
                "ratios": {**entry["ratios"], "lut_mapping_time": 0.75},
            },
        ]
    )

    assert chart_data["dates"] == ["2026-04-18", "2026-04-19"]
    assert chart_data["metrics"][0]["key"] == "lut_mapping_time"
    assert chart_data["metrics"][0]["values"] == [pytest.approx(0.5), 0.75]
