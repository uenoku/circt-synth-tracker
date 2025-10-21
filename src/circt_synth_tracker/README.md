# CIRCT Synth Tracker Tools

This directory contains the Python package for the CIRCT synthesis tracking utilities.

All tools are installed as command-line scripts via `pyproject.toml` and are available after running `uv sync`.

## Available Tools

### `run-circt-synth` (tools/circt_synth.py)
CIRCT synthesis pipeline wrapper that runs the three-stage CIRCT synthesis process.

```bash
run-circt-synth input.mlir --bw 16 -top module_name -o output.aig
```

**Options:**
- `-o, --output` - Output AIG file (required)
- `-top, --top-module` - Top module name
- `--bw, --bitwidth` - Bitwidth for operations
- `--circt-verilog` - Path to circt-verilog binary
- `--circt-synth` - Path to circt-synth binary
- `--circt-translate` - Path to circt-translate binary
- `--extra-args` - Additional arguments to pass to circt-synth

### `run-yosys` (tools/yosys.py)
Yosys synthesis wrapper with unified interface compatible with CIRCT tools.

```bash
run-yosys input.sv --bw 16 -top module_name -o output.aig
```

**Options:**
- `-o, --output` - Output AIG file (required)
- `-top, --top-module` - Top module name
- `--bw, --bitwidth` - Bitwidth for operations
- `--yosys` - Path to yosys binary

### `aig-judge` (utils/aig_judge.py)
AIG evaluation tool that analyzes AIG files and outputs synthesis metrics as JSON.

```bash
aig-judge input.aig
```

Outputs JSON with metrics like gate count, depth, etc.

### `submit-results` (submit.py)
Results submission tool. Records benchmark results to JSON files.

```bash
submit-results <test_file> --name <benchmark_name>
```

Results are saved to `benchmarks/external/DatapathBench/output/results/`.

## Usage in Tests

These tools are available in lit tests through substitutions:
- `%sv_to_aig` - Maps to `sv-to-aig` wrapper command
- `%judge` - Maps to `aig-judge` command
- `%submit` - Maps to `submit-results` command

Example:
```
// RUN: %sv_to_aig input.sv --bw 16 -top module_name -o %t.aig
// RUN: %judge %t.aig | %submit %s --name benchmark_name
```
