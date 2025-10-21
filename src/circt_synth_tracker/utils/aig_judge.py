#!/usr/bin/env python3
"""
AIG judge tool - wrapper for the C++ aig-judge binary.
Performs technology mapping using mockturtle's emap algorithm.
"""

import sys
import json
import argparse
import subprocess
from pathlib import Path


def find_binary():
    """Find the aig-judge binary."""
    # Try project root judge-build directory
    script_dir = Path(__file__).parent
    project_root = script_dir.parent.parent.parent
    binary_path = project_root / "judge-build" / "aig-judge"

    if binary_path.exists():
        return binary_path

    # Try relative to this file (old location)
    binary_path = script_dir / "judge" / "build" / "aig-judge"
    if binary_path.exists():
        return binary_path

    return None


def main():
    parser = argparse.ArgumentParser(
        description="AIG technology mapping and evaluation tool"
    )
    parser.add_argument("aig_file", help="AIG file to evaluate")
    parser.add_argument("--text", action="store_true", help="Output in text format")

    args = parser.parse_args()

    aig_path = Path(args.aig_file)

    if not aig_path.exists():
        print(f"Error: AIG file not found: {aig_path}", file=sys.stderr)
        return 1

    # Find the C++ binary
    binary = find_binary()
    if not binary:
        print(
            "Error: aig-judge binary not found. Please run 'uv run build-judge' first.",
            file=sys.stderr,
        )
        return 1

    # Run the C++ binary for both technologies
    results = {}
    technologies = ["asap7", "sky130"]
    
    for tech in technologies:
        try:
            result = subprocess.run(
                [str(binary), str(aig_path), "--tech", tech],
                capture_output=True,
                text=True,
                check=True,
            )

            # Parse JSON output from C++ binary
            tech_stats = json.loads(result.stdout)
            results[tech] = tech_stats

        except subprocess.CalledProcessError as e:
            print(
                f"Error: aig-judge binary failed for {tech} with exit code {e.returncode}",
                file=sys.stderr,
            )
            if e.stderr:
                print(e.stderr, file=sys.stderr)
            return e.returncode
        except json.JSONDecodeError as e:
            print("Error: Failed to parse JSON output from aig-judge", file=sys.stderr)
            print(f"  {e}", file=sys.stderr)
            print(f"Output was: {result.stdout}", file=sys.stderr)
            return 1

    # Merge results into a single metrics object
    merged_stats = {}
    
    # Use the first successful result for common fields
    base_result = None
    for tech in technologies:
        if results[tech].get('success', False):
            base_result = results[tech]
            break
    
    if base_result is None:
        print("Error: All technology mappings failed", file=sys.stderr)
        return 1
    
    # Copy common fields
    merged_stats['filename'] = base_result.get('filename', '')
    merged_stats['gates'] = base_result.get('gates', 0)
    merged_stats['num_inputs'] = base_result.get('num_inputs', 0)
    merged_stats['num_outputs'] = base_result.get('num_outputs', 0)
    merged_stats['depth'] = base_result.get('depth', 0)
    
    # Add technology-specific area/delay fields
    for tech in technologies:
        if results[tech].get('success', False):
            merged_stats[f'area_{tech}'] = results[tech].get('area', 0)
            merged_stats[f'delay_{tech}'] = results[tech].get('delay', 0)
        else:
            merged_stats[f'area_{tech}'] = None
            merged_stats[f'delay_{tech}'] = None
    
    # Overall success if at least one technology succeeded
    merged_stats['success'] = any(results[tech].get('success', False) for tech in technologies)

    # Output format
    if args.text:
        # Text format for human readability
        print(f"AIG Technology Mapping Results for {aig_path.name}:")
        print(f"  File: {merged_stats.get('filename', 'N/A')}")
        print(f"  AIG Gates: {merged_stats.get('gates', 'N/A')}")
        print(f"  Inputs: {merged_stats.get('num_inputs', 'N/A')}")
        print(f"  Outputs: {merged_stats.get('num_outputs', 'N/A')}")
        print(f"  AIG Depth: {merged_stats.get('depth', 'N/A')}")
        print(f"  ASAP7 Area: {merged_stats.get('area_asap7', 'N/A')}")
        print(f"  ASAP7 Delay: {merged_stats.get('delay_asap7', 'N/A')}")
        print(f"  Sky130 Area: {merged_stats.get('area_sky130', 'N/A')}")
        print(f"  Sky130 Delay: {merged_stats.get('delay_sky130', 'N/A')}")
        print(f"  Success: {merged_stats.get('success', False)}")
    else:
        # JSON format (default) - easier for automation
        print(json.dumps(merged_stats, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main())
