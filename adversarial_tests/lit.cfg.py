"""
Configuration file for the adversarial arithmetic test suite.

Hand-crafted combinational benchmarks that each target a specific,
known error-prone corner of arithmetic synthesis (extension fills,
signedness of compares/shifts, wraparound vs widening, rewidthing
identities). Unlike random_tests/, these files are committed and stable.

Loads the shared benchmark configuration to inherit tool substitutions
(%SYNTH_TOOL, %AIG_TOOL, %judge, ...) and -D parameters.
"""
import os
from pathlib import Path

import lit.formats

shared_config = Path(__file__).parent.parent / "benchmarks" / "lit.cfg.py"
if not shared_config.exists():
    raise FileNotFoundError(f"Shared config not found: {shared_config}")
lit_config.load_config(config, str(shared_config))

# name: The name of this test suite.
config.name = "adversarial-tests"

# testFormat: The test format to use to interpret tests.
config.test_format = lit.formats.ShTest(True)

# suffixes: A list of file extensions to treat as test files.
config.suffixes = [".sv"]

# test_source_root: The root path where tests are located.
config.test_source_root = Path(__file__).parent

# test_exec_root: Namespaced under TEST_OUTPUT_DIR like random_tests.
test_output_dir = getattr(config, "test_output_dir", "build")
project_root = Path(__file__).parent.parent
config.test_exec_root = os.path.join(project_root, test_output_dir, "adversarial_tests")

os.makedirs(config.test_exec_root, exist_ok=True)
