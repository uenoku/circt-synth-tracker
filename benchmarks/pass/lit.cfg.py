"""Configuration file for pass benchmark lit suite."""

import os
from pathlib import Path

import lit.formats

# Load parent configuration to inherit substitutions.
parent_config = Path(__file__).parent.parent / "lit.cfg.py"
if parent_config.exists():
    lit_config.load_config(config, str(parent_config))
else:
    raise FileNotFoundError(f"Parent config not found: {parent_config}")

config.name = "pass-benchmarks"
config.test_format = lit.formats.ShTest(True)
config.suffixes = [".test"]
config.test_source_root = os.path.dirname(__file__)

# Inherit output root from parent config and place pass suite under it.
test_output_dir = getattr(config, "test_output_dir", "build")
benchmarks_root = Path(__file__).parent.parent
relative_path = Path(__file__).parent.relative_to(benchmarks_root)
lut_size = lit_config.params.get("LUT_SIZE", "6")
cut_size = lit_config.params.get("CUT_SIZE", "8")

config.test_exec_root = os.path.join(
    benchmarks_root.parent, test_output_dir, str(relative_path)
)
os.makedirs(config.test_exec_root, exist_ok=True)

config.substitutions.append(("%PASS_LUT_SIZE", lut_size))
config.substitutions.append(("%PASS_CUT_SIZE", cut_size))
config.substitutions.append(
    ("%LSILS_AIG", str(benchmarks_root / "aig" / "lsils" / "benchmarks"))
)
