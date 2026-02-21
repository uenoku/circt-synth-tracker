"""
Synthesis tool wrappers.

This module contains wrappers for various synthesis tools:
- circt_synth: CIRCT-based SystemVerilog to AIG conversion
- yosys: Yosys-based synthesis
- abc: ABC-based technology mapping
"""

import shutil
import subprocess
import sys
from pathlib import Path


def find_abc(explicit: str | None = None) -> str:
    """Return the ABC executable to use, in priority order:
    1. *explicit* path if provided and executable
    2. ``abc`` on PATH
    3. ``yosys-abc`` on PATH
    """
    candidates = []
    if explicit:
        candidates.append(explicit)
    candidates.extend(("abc", "yosys-abc"))
    for candidate in candidates:
        if shutil.which(candidate):
            return candidate
    raise FileNotFoundError(
        "No ABC executable found. Install 'abc' or 'yosys-abc', "
        "or pass --abc <path>."
    )


def run_abc_commands(
    input_file: Path,
    output_file: Path,
    commands: str,
    abc_exe: str | None = None,
    rc_file: Path | None = None,
) -> None:
    """Run ABC commands on an AIG file, writing the result to a separate output path.

    Args:
        input_file:  Path to the input AIGER file.
        output_file: Path where the optimized AIGER will be written.
        commands:    Semicolon-separated ABC commands to run (e.g. ``"dc2; dc2;"``).
        abc_exe:     Explicit path/name hint for the ABC executable. Falls back to
                     ``abc`` then ``yosys-abc`` when *None* or not found on PATH.
        rc_file:     Optional ABC script file loaded via ``-F`` before ``-c`` commands,
                     useful for pre-defining aliases.
    """
    if not commands:
        return

    abc_exe = find_abc(abc_exe)

    cmd = [abc_exe]
    if rc_file is not None and rc_file.exists():
        cmd += ["-F", str(rc_file)]

    script = f"read {input_file}; {commands}; write {output_file};"
    cmd += ["-c", script]

    print(f"Running ABC commands: {commands}", file=sys.stderr)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print("Error during ABC optimization:", file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        sys.exit(result.returncode)
