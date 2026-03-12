#!/usr/bin/env python3
"""Generate fallback reports for CIRCT PR build failures."""

from __future__ import annotations

import argparse
import json
from html import escape
from pathlib import Path


def extract_log_excerpt(log_text: str, max_lines: int) -> str:
    """Return a concise build-log excerpt centered around the first failure."""
    lines = [line.rstrip() for line in log_text.splitlines()]
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    if not lines:
        return "No build log output was captured."

    failure_indices = [
        index
        for index, line in enumerate(lines)
        if "error:" in line.lower() or line.startswith(("FAILED:", "failed:"))
    ]
    if failure_indices:
        start = max(0, failure_indices[0] - 5)
        excerpt = lines[start:]
    else:
        excerpt = lines

    if len(excerpt) > max_lines:
        excerpt = ["..."] + excerpt[-max_lines:]

    return "\n".join(excerpt)


def render_markdown(summary: str, details: list[str], log_excerpt: str) -> str:
    """Render the Markdown body used in workflow summaries and issue comments."""
    lines = [
        "## Status",
        "",
        f"- {summary}",
        *[f"- {detail}" for detail in details],
        "",
        "### Build log excerpt",
        "",
        "```text",
        log_excerpt,
        "```",
        "",
    ]
    return "\n".join(lines)


def render_html(title: str, summary: str, details: list[str], log_excerpt: str) -> str:
    """Render a standalone HTML page for GitHub Pages/artifact browsing."""
    detail_items = "".join(f"<li>{escape(detail)}</li>" for detail in details)
    return f"""<!doctype html>
<html lang="en"><head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{escape(title)}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 24px; color: #111; }}
    .status {{ padding: 12px 16px; border-left: 4px solid #b42318; background: #fef3f2; margin-bottom: 24px; }}
    code, pre {{ font-family: ui-monospace, SFMono-Regular, "SF Mono", Consolas, monospace; }}
    pre {{ background: #f6f8fa; border: 1px solid #d0d7de; border-radius: 6px; padding: 12px; overflow-x: auto; }}
  </style>
</head><body>
  <h1>{escape(title)}</h1>
  <div class="status">
    <p><strong>{escape(summary)}</strong></p>
    <ul>{detail_items}</ul>
  </div>
  <h2>Build log excerpt</h2>
  <pre>{escape(log_excerpt)}</pre>
</body></html>
"""


def write_report(
    *,
    title: str,
    summary: str,
    details: list[str],
    log_path: Path,
    markdown_out: Path,
    html_out: Path,
    json_out: Path | None,
    max_log_lines: int,
) -> None:
    """Write Markdown/HTML(/JSON) fallback reports for a CIRCT build failure."""
    log_excerpt = extract_log_excerpt(log_path.read_text(), max_lines=max_log_lines)
    markdown_out.write_text(render_markdown(summary, details, log_excerpt))
    html_out.write_text(render_html(title, summary, details, log_excerpt))
    if json_out is not None:
        json_out.write_text(
            json.dumps(
                {
                    "status": "build-failed",
                    "title": title,
                    "summary": summary,
                    "details": details,
                    "log_excerpt": log_excerpt,
                },
                indent=2,
            )
            + "\n"
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--title", required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--detail", action="append", default=[])
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--markdown-out", type=Path, required=True)
    parser.add_argument("--html-out", type=Path, required=True)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--max-log-lines", type=int, default=40)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    write_report(
        title=args.title,
        summary=args.summary,
        details=args.detail,
        log_path=args.log,
        markdown_out=args.markdown_out,
        html_out=args.html_out,
        json_out=args.json_out,
        max_log_lines=args.max_log_lines,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
