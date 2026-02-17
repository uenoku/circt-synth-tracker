# circt-synth-tracker

[![CIRCT Nightly Integration Tests](https://github.com/uenoku/circt-synth-tracker/actions/workflows/ci-nightly.yml/badge.svg)](https://github.com/uenoku/circt-synth-tracker/actions/workflows/ci-nightly.yml)
[![Report](https://img.shields.io/badge/report-html-blue)](https://uenoku.github.io/circt-synth-tracker/report.html)
[![History](https://img.shields.io/badge/history-timeseries-green)](https://uenoku.github.io/circt-synth-tracker/timeseries.html)

NOTE: This repository is a prototype and under active development.

A testing framework for tracking synthesis results for the [Circuit IR and Tools (CIRCT)](https://circt.llvm.org/) project using LLVM lit.

## Prerequisites
- uv
- cmake and cpp17-compatible compiler (for building aig-judge)
- yosys, circt-synth, circt-verilog and circt-translate

## Setup

```bash
# Install dependencies
uv sync

# Build C++ components (aig-judge)
uv run build-judge

# Activate the virtual environment
source .venv/bin/activate
```

**Note:** The `aig-judge` tool is a C++ binary that runs AIG technology mapping using mockturtle. It must be built before running tests.

## Running Tests

```bash

# Make sure yosys, circt-synth, circt-verilog and circt-translate are in PATH.

# Run all benchmarks
lit -v benchmarks/ # Test results are stored in build/ by default
# Run specific test suite
lit -v benchmarks/comb/DatapathBench/

# Run with custom parameters (pass parameters using -D<name>=<value>)
lit -v benchmarks/ -DBW=8 -DSYNTH_TOOL=yosys -DTEST_OUTPUT_DIR=build_yosys
# circt-synth has custom parameters to pass additional arguments
lit -v benchmarks/ -DSYNTH_TOOL=circt -DCIRCT_SYNTH_EXTRA_ARGS="--disable-datapath"

# Run specific circt-synth version
export CIRCT_SYNTH=/path/to/circt-synth
lit -v benchmarks/
(or add specific version of circt-synth to PATH)

# Compare Results
# 1. Aggregate results from test runs
aggregate-results --tool circt --results-dir build -o circt-summary.json
aggregate-results --tool yosys --results-dir build_yosys -o yosys-summary.json

# 2. Compare the summaries
compare-results circt-summary.json yosys-summary.json

# 3. Generate HTML report
compare-results circt-summary.json yosys-summary.json -o report.html
```

### Available Parameters

These parameters can be set when invoking `lit` using `-D<name>=<value>`:
- `BW` - Bitwidth for parameterized tests (default: 16)
- `SYNTH_TOOL` - Synthesis tool to use: `circt` or `yosys` (default: circt)
- `TEST_OUTPUT_DIR` - Test output directory (default: build)
- `RESULTS_DIR` - Results storage directory (default: empty, stores in test output dir)
- `CIRCT_SYNTH_EXTRA_ARGS` - Additional arguments for circt-synth (default: empty)

Environment variables for tool paths:
- `CIRCT_SYNTH`, `CIRCT_VERILOG`, `CIRCT_TRANSLATE` - CIRCT binaries
- `YOSYS` - Yosys binary

Examples:
```bash
# Run with custom synthesis arguments
lit -v benchmarks/ -DCIRCT_SYNTH_EXTRA_ARGS="--some-opt --another-flag"
```

## Project Structure

```
circt-synth-tracker/
├── src/circt_synth_tracker/        # Python package
│   ├── tools/                      # Synthesis tool wrappers
│   ├── utils/                      # Utility tools
│   └── analysis/                   # Analysis tools
├── benchmarks/comb/                # Combinational logic benchmarks
│   ├── microbenchmarks/
│   ├── ELAU/
│   └── DatapathBench/
├── lit.cfg.py                      # Top-level lit configuration
└── pyproject.toml                  # Project configuration
```

### Available Substitutions

- `%SYNTH_TOOL` - Selected synthesis tool
- `%BW` - Bitwidth parameter
- `%judge` - AIG evaluation tool
- `%submit` - Results submission tool

## Benchmark Suites

### Microbenchmarks (`benchmarks/comb/microbenchmarks/`)
Small combinational logic tests for basic operations.

### ELAU (`benchmarks/comb/ELAU/`)
Arithmetic benchmarks from the ELAU library. Tests are auto-generated using `generate_tests.py`.

### DatapathBench (`benchmarks/comb/DatapathBench/`)
Datapath-oriented benchmarks.

## Time Series Tracking

The CI runs nightly and publishes a historical report to GitHub Pages at
[timeseries.html](https://uenoku.github.io/circt-synth-tracker/timeseries.html).
It shows geo-mean trends for gates, depth, area (ASAP7), and delay (ASAP7)
for both CIRCT and Yosys over the past 90 days, plus per-benchmark detail
selectable via a dropdown.

The raw history data is available at
[history.json](https://uenoku.github.io/circt-synth-tracker/history.json).

To generate a local time series report from past data:

```bash
# Build history from existing summary files (one per day)
append-history --circt circt-summary.json --yosys yosys-summary.json \
               -o history.json --date 2026-02-16

# Generate interactive HTML report
timeseries-report history.json -o timeseries.html
```

## Command-Line Tools

Installed via `uv sync`:

**Synthesis:**
- `run-circt-synth` - CIRCT pipeline (circt-verilog → circt-synth → circt-translate)
- `run-yosys` - Yosys wrapper with unified interface

**Analysis:**
- `aig-judge` - Evaluate AIG files (outputs JSON)
- `submit-results` - Store benchmark results as JSON
- `aggregate-results` - Aggregate results into summaries
- `compare-results` - Compare results across tools, generate HTML/Markdown/JSON reports
- `append-history` - Append a day's summaries to a cumulative `history.json`
- `timeseries-report` - Generate an interactive HTML time series report from `history.json`
