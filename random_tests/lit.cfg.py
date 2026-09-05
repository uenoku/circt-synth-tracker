"""
Configuration file for the random adversarial-arithmetic test suite.

This suite lives *outside* benchmarks/ on purpose: it is a fuzz-style
regression suite and is not included when running `lit benchmarks/`.
Run it explicitly with `lit -v random_tests/`.

It loads the shared benchmark configuration to inherit all tool
substitutions (%SYNTH_TOOL, %AIG_TOOL, %judge, %submit, ...) and
parameters (SYNTH_TOOL, TECH_MAP, BW, ABC_COMMANDS, TV_SOLVER, ...).
"""
import os
from pathlib import Path

import lit.formats

# Load the shared benchmarks configuration to inherit substitutions.
shared_config = Path(__file__).parent.parent / "benchmarks" / "lit.cfg.py"
if not shared_config.exists():
    raise FileNotFoundError(f"Shared config not found: {shared_config}")
lit_config.load_config(config, str(shared_config))

# name: The name of this test suite.
config.name = "random-tests"

# testFormat: The test format to use to interpret tests.
config.test_format = lit.formats.ShTest(True)

# suffixes: A list of file extensions to treat as test files.
config.suffixes = [".sv"]

# test_source_root: The root path where tests are located.
# Created on demand by generate_tests.py; kept out of version control.
config.test_source_root = Path(__file__).parent / "tests"
os.makedirs(config.test_source_root, exist_ok=True)

# test_exec_root: Keep artifacts under TEST_OUTPUT_DIR but namespaced so
# they never collide with the regular benchmark tracks.
test_output_dir = getattr(config, "test_output_dir", "build")
project_root = Path(__file__).parent.parent
bw = lit_config.params.get("BW", "16")
config.test_exec_root = os.path.join(project_root, test_output_dir, "random_tests", bw)

# Ensure output directory exists.
os.makedirs(config.test_exec_root, exist_ok=True)
