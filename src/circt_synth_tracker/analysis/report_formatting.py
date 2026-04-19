"""Shared report-formatting helpers for compare/pass analysis outputs."""

from __future__ import annotations

from typing import Any

NEAR_ZERO_PCT_POINTS_THRESHOLD = 0.05


def _to_float(v: Any) -> float | None:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    return None


def format_ratio_with_pct(ratio: float | None, digits: int = 4) -> str:
    if ratio is None:
        return "n/a"
    pct = (ratio - 1.0) * 100.0
    if abs(pct) < NEAR_ZERO_PCT_POINTS_THRESHOLD:
        pct = 0.0
    return f"{ratio:.{digits}f} ({pct:+.1f}%)"


def format_value_with_pct(
    value: float | None, baseline: float | None, value_digits: int
) -> str:
    if value is None:
        return "n/a"
    if baseline is None or baseline == 0:
        return f"{value:.{value_digits}f}"
    pct = (value / baseline - 1.0) * 100.0
    return f"{value:.{value_digits}f} ({pct:+.1f}%)"


def format_metric_cell_html(
    value: Any,
    baseline: Any,
    *,
    lower_is_better: bool = True,
    value_digits: int | None = None,
    neutral_epsilon_pct: float = 0.01,
    intensity_cap_pct: float = 20.0,
    line_break: bool = False,
) -> tuple[str, str]:
    """Return (html_content, html_style_attr) for a metric cell."""
    v = _to_float(value)
    b = _to_float(baseline)
    if v is None:
        return str(value), ""
    if b is None or b == 0:
        s = f"{v:.{value_digits}f}" if value_digits is not None else str(value)
        return s, ""

    diff = v - b
    diff_pct = (diff / b) * 100.0
    abs_pct = abs(diff_pct)
    is_better = (diff < 0) if lower_is_better else (diff > 0)
    cls = "better" if is_better else "worse"
    sep = "<br>" if line_break else " "

    if value_digits is not None:
        base_text = f"{v:.{value_digits}f}"
    else:
        base_text = str(value)

    content = f"{base_text}{sep}<span class='diff {cls}'>({diff_pct:+.1f}%)</span>"

    if abs_pct < neutral_epsilon_pct:
        content = (
            f"{base_text}{sep}<span class='diff neutral'>({diff_pct:+.1f}%)</span>"
        )
        return content, ""

    intensity = min(abs_pct / intensity_cap_pct, 1.0)
    if is_better:
        green_val = int(200 - (50 * intensity))
        bg_color = f"rgb({green_val},255,{green_val})"
    else:
        red_val = int(200 - (50 * intensity))
        bg_color = f"rgb(255,{red_val},{red_val})"
    return content, f" style='background-color: {bg_color};'"
