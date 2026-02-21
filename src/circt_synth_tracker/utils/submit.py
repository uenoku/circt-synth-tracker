"""
Submit tool for DatapathBench results.
"""

import sys
import os
import json
import argparse
import subprocess
from pathlib import Path
from datetime import datetime


def _git(cmd, cwd):
    """Run a git command and return stdout, or None on failure."""
    try:
        result = subprocess.run(
            ["git"] + cmd, cwd=cwd, capture_output=True, text=True, check=True
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def _remote_to_github_blob(remote_url, rel_path, commit):
    """Convert a git remote URL + relative path + commit to a GitHub blob URL."""
    # Normalise SSH and HTTPS forms to https://github.com/owner/repo
    url = remote_url
    if url.endswith(".git"):
        url = url[:-4]
    if url.startswith("git@github.com:"):
        url = "https://github.com/" + url[len("git@github.com:"):]
    elif url.startswith("ssh://git@github.com/"):
        url = "https://github.com/" + url[len("ssh://git@github.com/"):]
    if not url.startswith("https://github.com/"):
        return None
    return f"{url}/blob/{commit}/{rel_path}"


def _source_file_to_url(source_file):
    """Derive a GitHub blob URL from a source file path using git submodule info."""
    path = Path(source_file).resolve()
    if not path.exists():
        return None

    cwd = str(path.parent)
    # Find the git root that owns this file (may be a submodule root)
    git_root = _git(["rev-parse", "--show-toplevel"], cwd=cwd)
    if not git_root:
        return None

    remote = _git(["remote", "get-url", "origin"], cwd=git_root)
    if not remote:
        return None

    commit = _git(["rev-parse", "HEAD"], cwd=git_root)
    if not commit:
        return None

    rel_path = path.relative_to(git_root).as_posix()
    return _remote_to_github_blob(remote, rel_path, commit)


def main():
    parser = argparse.ArgumentParser(description="Submit benchmark results")
    parser.add_argument("test_file", nargs="?", help="Test file path (optional)")
    parser.add_argument("--name", required=True, help="Benchmark name")
    parser.add_argument("--tool", help="Tool name (default: auto-detect from env)")
    parser.add_argument("--output-dir", help="Output directory for results")
    parser.add_argument("--bw", "--bitwidth", dest="bitwidth", type=int, help="Bit width to append to benchmark name (e.g. 16 → name_16)")
    parser.add_argument("--url", help="URL to the original benchmark source file")
    parser.add_argument("--source-file", help="Path to the source file; URL is auto-derived from git submodule info")

    args = parser.parse_args()

    # Read the JSON statistics from stdin (output from %judge)
    input_data = sys.stdin.read().strip()

    # Parse the JSON from judge
    try:
        judge_data = json.loads(input_data)
    except json.JSONDecodeError:
        # Fallback: treat as raw text if not JSON
        judge_data = {"raw_output": input_data}

    # Append bitwidth suffix to benchmark name if provided
    benchmark_name = args.name
    if args.bitwidth is not None:
        benchmark_name = f"{args.name}_{args.bitwidth}"

    # Determine tool name
    tool_name = args.tool or os.environ.get("synth_tool", "unknown")
    category = "unknown"
    if args.test_file:
        for part in args.test_file.split("/")[:-1][::-1]:
            if part != "tests" and part != "Output":
                category = part
                break

    # Resolve URL from --source-file if --url not provided
    url = args.url
    if not url and args.source_file:
        url = _source_file_to_url(args.source_file)

    # Create result record
    results = {
        "benchmark": benchmark_name,
        "tool": tool_name,
        "test_file": args.test_file,
        "url": url,
        "timestamp": datetime.now().isoformat(),
        "metrics": judge_data,
        "category": category,
    }

    # Determine output directory
    if args.output_dir:
        results_dir = Path(args.output_dir)
    else:
        # Default: use results directory in current working directory
        results_dir = Path.cwd() / "results" / tool_name

    results_dir.mkdir(parents=True, exist_ok=True)

    # Save result file
    results_file = results_dir / f"{benchmark_name}.json"
    with open(results_file, "w") as f:
        json.dump(results, f, indent=2)

    print(f"Results saved: {results_file}", file=sys.stderr)

    # Also output to stdout for piping
    print(json.dumps(results, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main())
