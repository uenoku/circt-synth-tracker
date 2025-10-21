#!/usr/bin/env python3
"""Build script for the aig-judge C++ tool."""

import subprocess
import sys
from pathlib import Path


def main():
    """Build the aig-judge C++ tool using CMake."""
    # Get the directories
    judge_dir = Path(__file__).parent
    # Build directory at project root: circt-synth-tracker/judge-build/
    project_root = judge_dir.parent.parent.parent.parent
    build_dir = project_root / "judge-build"

    print("=" * 60)
    print("Building aig-judge C++ tool...")
    print("=" * 60)

    # Create build directory
    build_dir.mkdir(exist_ok=True)

    # Run CMake configure
    print("\n[1/3] Configuring with CMake...")
    try:
        subprocess.run(
            ["cmake", str(judge_dir)],
            cwd=build_dir,
            check=True,
            capture_output=False,
        )
    except subprocess.CalledProcessError as e:
        print(f"Error: CMake configuration failed: {e}", file=sys.stderr)
        return 1
    except FileNotFoundError:
        print("Error: CMake not found. Please install CMake.", file=sys.stderr)
        return 1

    # Run CMake build
    print("\n[2/3] Building...")
    try:
        subprocess.run(
            ["cmake", "--build", ".", "--config", "RelWithDebInfo"],
            cwd=build_dir,
            check=True,
            capture_output=False,
        )
    except subprocess.CalledProcessError as e:
        print(f"Error: Build failed: {e}", file=sys.stderr)
        return 1

    # Check if binary was created
    binary_path = build_dir / "aig-judge"
    if binary_path.exists():
        print("\n[3/3] Build successful!")
        print(f"Binary location: {binary_path}")
        print("=" * 60)
        return 0
    else:
        print("\nError: Binary not found after build", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
