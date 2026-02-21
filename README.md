# circt-synth-tracker

[![CIRCT Nightly Integration Tests](https://github.com/uenoku/circt-synth-tracker/actions/workflows/ci-nightly.yml/badge.svg)](https://github.com/uenoku/circt-synth-tracker/actions/workflows/ci-nightly.yml)
[![Report](https://img.shields.io/badge/report-html-blue)](https://uenoku.github.io/circt-synth-tracker/report.html)
[![History](https://img.shields.io/badge/history-timeseries-green)](https://uenoku.github.io/circt-synth-tracker/timeseries.html)

> **Note:** This repository is a prototype and under active development.

A testing framework for tracking synthesis quality of the [Circuit IR and Tools (CIRCT)](https://circt.llvm.org/) project using LLVM lit. It runs combinational benchmarks through configurable synthesis and AIG optimization pipelines, then measures area and delay using mockturtle or ABC technology mapping.

## Prerequisites

- [uv](https://github.com/astral-sh/uv)
- cmake and a C++17-compatible compiler (for building the mockturtle judge)
- `yosys`, `circt-synth`, `circt-verilog`, `circt-translate` in PATH
- `abc` or `yosys-abc` in PATH (for ABC-based judging and AIG optimization)

## Setup

```bash
# Install Python dependencies and build C++ components + fetch abc.rc
uv sync
uv run prepare

# Activate the virtual environment
source .venv/bin/activate
```

`uv run prepare` builds the `mockturtle-aig-judge` C++ binary and fetches
`benchmarks/abc.rc` (ABC's standard alias file) from the ABC repository.

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
# Apply ABC optimization between synthesis and judging
lit -v benchmarks/ -DABC_COMMANDS="resyn"

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

### Available Lit Parameters

| Parameter | Default | Description |
|---|---|---|
| `SYNTH_TOOL` | `circt` | Synthesis tool: `circt` or `yosys` |
| `TECH_MAP` | `mockturtle` | Technology mapper for `%judge`: `mockturtle` or `abc` |
| `ABC_COMMANDS` | _(empty)_ | ABC commands run via `%AIG_TOOL` between synthesis and judging (e.g. `"compress2rs;"`) |
| `BW` | `16` | Bitwidth for parameterized benchmarks |
| `TEST_OUTPUT_DIR` | `build` | Directory for lit test outputs |
| `CIRCT_SYNTH_EXTRA_ARGS` | _(empty)_ | Extra flags passed to `circt-synth` |

### Lit Substitutions

| Substitution | Description |
|---|---|
| `%SYNTH_TOOL` | Synthesis pipeline (SV → AIG) |
| `%AIG_TOOL` | AIG optimization layer (`run-abc-opt`); no-op when `ABC_COMMANDS` is empty |
| `%judge` | AIG evaluation tool (`mockturtle-aig-judge` or `abc-aig-judge`) |
| `%submit` | Stores benchmark results as JSON |
| `%BW` | Bitwidth parameter |

### ABC Aliases (`benchmarks/abc.rc`)

After `uv run prepare`, `benchmarks/abc.rc` is populated with ABC's standard
aliases (fetched from the ABC repository at a pinned commit). These can be
referenced by name in `ABC_COMMANDS`:

```bash
lit -v benchmarks/ -DABC_COMMANDS="resyn2;"
lit -v benchmarks/ -DABC_COMMANDS="compress2rs;"
```

### Environment Variables

| Variable | Description |
|---|---|
| `CIRCT_SYNTH`, `CIRCT_VERILOG`, `CIRCT_TRANSLATE` | Override CIRCT binary paths |
| `YOSYS` | Override Yosys binary path |
| `ABC` | Override ABC binary path |

## Comparing Results

```bash
# 1. Aggregate results from a test run
aggregate-results --tool circt --results-dir build -o circt-summary.json
aggregate-results --tool yosys --results-dir build_yosys -o yosys-summary.json

# 2. Compare and generate a report
compare-results circt-summary.json yosys-summary.json -o report.html
```

## Project Structure

```
circt-synth-tracker/
├── src/circt_synth_tracker/
│   ├── tools/                  # Synthesis and AIG tool wrappers
│   │   ├── circt_synth.py      # run-circt-synth
│   │   ├── yosys.py            # run-yosys
│   │   ├── abc_opt.py          # run-abc-opt (%AIG_TOOL)
│   │   └── abc.py              # abc-aig-judge
│   ├── utils/                  # Judge and submission tools
│   │   └── judge/              # mockturtle-aig-judge C++ build
│   └── analysis/               # Aggregation and reporting tools
├── benchmarks/
│   ├── abc.rc                  # ABC aliases (fetched by `prepare`)
│   ├── lit.cfg.py              # Top-level lit configuration
│   └── comb/
│       ├── microbenchmarks/    # Small inline SV benchmarks
│       ├── ELAU/               # ELAU arithmetic library benchmarks
│       └── DatapathBench/      # Datapath-oriented benchmarks
└── pyproject.toml
```

## CI Workflows

### Nightly (`ci-nightly.yml`)
Runs daily against the latest CIRCT nightly build. Compares CIRCT vs Yosys
across configured bitwidths, publishes HTML reports and time series to GitHub Pages.

Supports optional `abc_commands` input to apply ABC optimization via `%AIG_TOOL`.

### PR Benchmark (`ci-pr-benchmark.yml`)
Triggered manually (or via `@tracker-bot check-pr <N>` comment) to benchmark
a specific CIRCT PR. Builds CIRCT from source at the PR base and head SHAs,
runs benchmarks, and posts a before/after comparison.

Supports optional `abc_commands` input.

### Experiment (`ci-experiment.yml`)
Triggered manually to compare two arbitrary configurations side by side.
Each configuration independently specifies:
- `synth_tool`: `circt` or `yosys`
- `abc_commands`: ABC optimization script
- `circt_synth_extra_args`: extra flags for `circt-synth`

Useful for evaluating the effect of ABC passes, synthesis options, or tool choice.

### PR Bot (`ci-pr-bot.yml`)
Listens for `@tracker-bot check-pr <N>` comments on issues and dispatches
the PR benchmark workflow automatically.

## Time Series Tracking

The nightly CI publishes a rolling 90-day history to GitHub Pages:
- [report.html](https://uenoku.github.io/circt-synth-tracker/report.html) — latest comparison
- [timeseries.html](https://uenoku.github.io/circt-synth-tracker/timeseries.html) — geo-mean trends
- [history.json](https://uenoku.github.io/circt-synth-tracker/history.json) — raw data

To generate a local time series report:
```bash
append-history --circt circt-summary.json --yosys yosys-summary.json \
               -o history.json
timeseries-report history.json -o timeseries.html
```

## Command-Line Tools

Installed via `uv sync`:

| Tool | Description |
|---|---|
| `run-circt-synth` | CIRCT pipeline: circt-verilog → circt-synth → circt-translate → AIG |
| `run-yosys` | Yosys wrapper producing AIG output |
| `run-abc-opt` | AIG optimizer using ABC commands and `abc.rc` aliases (`%AIG_TOOL`) |
| `mockturtle-aig-judge` | Evaluate AIG with mockturtle (ASAP7 + Sky130) |
| `abc-aig-judge` | Evaluate AIG with ABC technology mapping (ASAP7 + Sky130) |
| `submit-results` | Store benchmark result JSON |
| `aggregate-results` | Aggregate per-benchmark JSONs into a summary |
| `compare-results` | Compare two summaries; output HTML / Markdown / JSON |
| `append-history` | Append a day's summaries to `history.json` |
| `timeseries-report` | Generate interactive HTML time series from `history.json` |
| `prepare` | Build `mockturtle-aig-judge` and fetch `benchmarks/abc.rc` |
