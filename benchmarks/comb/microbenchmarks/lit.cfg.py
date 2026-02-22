"""
Configuration file for microbenchmarks test suite using lit.
"""
import os
import lit.formats
from pathlib import Path

# Load parent configuration to inherit substitutions
parent_config = Path(__file__).parent.parent.parent / 'lit.cfg.py'
if parent_config.exists():
    lit_config.load_config(config, str(parent_config))
else:
    raise FileNotFoundError(f"Parent config not found: {parent_config}")

# name: The name of this test suite.
config.name = 'microbenchmarks'

# testFormat: The test format to use to interpret tests.
config.test_format = lit.formats.ShTest(True)

# suffixes: A list of file extensions to treat as test files.
config.suffixes = ['.sv']

# test_source_root: The root path where tests are located.
config.test_source_root = os.path.dirname(__file__)

# test_exec_root: The root path where tests should be run.
# Inherit test_output_dir from parent config
test_output_dir = getattr(config, 'test_output_dir', 'test-output')

# Calculate relative path from benchmarks directory to this test suite
benchmarks_root = Path(__file__).parent.parent.parent  # Points to benchmarks/
relative_path = Path(__file__).parent.relative_to(benchmarks_root)  # Gets comb/microbenchmarks

bw = lit_config.params.get('BW', '16')
config.test_exec_root = os.path.join(benchmarks_root.parent, test_output_dir, str(relative_path), bw)

# Ensure output directory exists
os.makedirs(config.test_exec_root, exist_ok=True)

# Note: Substitutions like %SYNTH_TOOL, %BW, %judge, %submit are inherited
# from benchmarks/lit.cfg.py via lit_config.load_config()
