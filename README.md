# circt-synth-tracker

[![CIRCT Nightly Integration Tests](https://github.com/uenoku/circt-synth-tracker/actions/workflows/ci-nightly.yml/badge.svg)](https://github.com/uenoku/circt-synth-tracker/actions/workflows/ci-nightly.yml)
[![Report](https://img.shields.io/badge/report-html-blue)](https://uenoku.github.io/circt-synth-tracker/report.html)
[![Pass Report](https://img.shields.io/badge/pass--report-html-teal)](https://uenoku.github.io/circt-synth-tracker/report-pass.html)
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

This repository has two benchmark tracks:
- `comb` (`benchmarks/comb/`): end-to-end combinational synthesis benchmarks
- `pass` (`benchmarks/pass/`): pass-level compile-time benchmarks

Make sure to run the correct track for your objective; parameters and outputs differ between `comb` and `pass`.

Suite-specific parameter docs:
- Combinational suite: `benchmarks/comb/README.md`
- Pass benchmark suite: `benchmarks/pass/README.md`

```bash
# Make sure yosys, circt-synth, circt-verilog and circt-translate are in PATH.
# Run all benchmarks
lit -v benchmarks/comb/ # Test results are stored in build/ by default
# Run specific test suite
lit -v benchmarks/comb/DatapathBench/

# Run with custom parameters (pass parameters using -D<name>=<value>)
lit -v benchmarks/comb/ -DBW=8 -DSYNTH_TOOL=yosys -DTEST_OUTPUT_DIR=build_yosys
# Run pass-level compile-time benchmark suite on LSILS AIG inputs (CIRCT vs ABC equivalents)
lit -v benchmarks/pass/ -DTEST_OUTPUT_DIR=build_pass -DLUT_SIZE=6 -DCUT_SIZE=8
# circt-synth has custom parameters to pass additional arguments
lit -v benchmarks/comb/ -DSYNTH_TOOL=circt -DCIRCT_SYNTH_EXTRA_ARGS="--disable-datapath"
# Apply ABC optimization between synthesis and judging
lit -v benchmarks/comb/ -DSYNTH_TOOL=circt -DABC_COMMANDS="resyn"

# Run SMT Translation Validation (TV)
# TV verifies each CIRCT synthesis pass preserves circuit semantics using circt-lec + SMT solver
lit -v benchmarks/comb/ -DSYNTH_TOOL=circt -DTV_SOLVER=bitwuzla  # or -DTV_SOLVER=z3

# Run specific circt-synth version
export CIRCT_SYNTH=/path/to/circt-synth
lit -v benchmarks/comb/
(or add specific version of circt-synth to PATH)

# Compare Results
# 1. Aggregate results from test runs
aggregate-results --tool circt --results-dir build -o circt-summary.json
aggregate-results --tool yosys --results-dir build_yosys -o yosys-summary.json

# 2. Compare the summaries
compare-results circt-summary.json yosys-summary.json

# 3. Generate HTML report
compare-results circt-summary.json yosys-summary.json -o report.html

# 4. Run combinational equivalence check (CEC) between AIG outputs using ABC
#    Produces cec.json with per-benchmark equivalence status
check-cec circt-summary.json yosys-summary.json -o cec.json -j 4

# 5. Pass pre-computed CEC results to compare-results
compare-results circt-summary.json yosys-summary.json -o report.html --cec cec.json

# Alternatively, run CEC inline (convenience wrapper):
compare-results circt-summary.json yosys-summary.json -o report.html --equiv-check -j 4
```

Detailed lit parameters are documented per suite:
- `benchmarks/comb/README.md`
- `benchmarks/pass/README.md`

ABC alias usage for comb benchmarks is documented in `benchmarks/comb/README.md`.

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

# 2. Run combinational equivalence check (CEC) between AIG outputs
check-cec circt-summary.json yosys-summary.json -o cec.json

# 3. Compare and generate a report, annotated with CEC results
compare-results circt-summary.json yosys-summary.json -o report.html --cec cec.json
```

## SMT Translation Validation

SMT Translation Validation (TV) details and usage are documented in `benchmarks/comb/README.md`.

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

Supports optional inputs:
- `abc_commands`: apply ABC optimization via `%AIG_TOOL`
- `equiv_check`: run combinational equivalence check (CEC) via `check-cec`

SMT Translation Validation runs automatically for CIRCT using Bitwuzla.

### PR Benchmark (`ci-pr-benchmark.yml`)
Triggered manually, or via an `@circt-tracker-bot check-pr <N>` or
`@circt-tracker-bot check-pr https://github.com/llvm/circt/pull/<N>` comment, to
benchmark
a specific CIRCT PR. Builds CIRCT from source at the PR base and head SHAs,
runs benchmarks, and posts a before/after comparison.

Supports optional inputs:
- `abc_commands`: apply ABC optimization
- `extra_circt_synth_args`: extra flags to pass through to `circt-synth`
- `equiv_check`: run CEC between the before/after AIG outputs

SMT Translation Validation runs automatically on both the base and head builds using Bitwuzla.

### Experiment (`ci-experiment.yml`)
Triggered manually to compare two arbitrary configurations side by side.
Each configuration independently specifies:
- `synth_tool`: `circt` or `yosys`
- `abc_commands`: ABC optimization script
- `circt_synth_extra_args`: extra flags for `circt-synth`

Shared optional input:
- `equiv_check`: run CEC between the two configurations' AIG outputs

Useful for evaluating the effect of ABC passes, synthesis options, or tool choice.

### Pass Experiment (`ci-pass-experiment.yml`)
Triggered manually to compare pass-benchmark config A vs config B using two separate runs, then `compare-results` on aggregated summaries.
Each config can override pass commands independently:
- LUT mode: CIRCT command and ABC command
- SOP mode: CIRCT command and ABC command

This enables before/after comparisons such as:
- CIRCT pass pipeline tweaks (`circt` command changes)
- ABC script tweaks (`abc` command changes)
- or both, while keeping the same benchmark set and LUT/CUT sweep.

### PR Bot (`ci-pr-bot.yml`)
Listens for `@circt-tracker-bot` commands on issues and dispatches benchmark
workflows automatically. Supported commands:

| Command | Description |
|---|---|
| `@circt-tracker-bot check-pr <N>` | Full benchmark (standard benchmark + pass benchmark, with translation validation and equivalence check on the standard flow) |
| `@circt-tracker-bot check-pr-quick <N>` | Quick benchmark (no TV or equivalence check) |
| `@circt-tracker-bot check-pr-pass <N>` | Pass benchmark (AIG/pass track only) |
| `@circt-tracker-bot rerun` | Re-run the most recent `check-pr*` command in the issue |

The bot also accepts a full GitHub PR URL in place of `<N>` and an optional
`--extra-args="..."` syntax for CIRCT benchmark runs.

## Time Series Tracking

The nightly CI publishes a rolling 90-day history to GitHub Pages:
- [report.html](https://uenoku.github.io/circt-synth-tracker/report.html) — latest comparison
- [report-pass.html](https://uenoku.github.io/circt-synth-tracker/report-pass.html) — latest pass benchmark comparison (CIRCT vs ABC)
- [timeseries.html](https://uenoku.github.io/circt-synth-tracker/timeseries.html) — geo-mean trends
- [history.json](https://uenoku.github.io/circt-synth-tracker/history.json) — raw data
- [pass-timeseries.html](https://uenoku.github.io/circt-synth-tracker/pass-timeseries.html) — pass benchmark ratio trends
- [pass-history.json](https://uenoku.github.io/circt-synth-tracker/pass-history.json) — raw pass benchmark history

To generate a local time series report:
```bash
append-history --circt circt-summary.json --yosys yosys-summary.json \
               -o history.json
timeseries-report history.json -o timeseries.html

append-pass-history --circt circt-summary.json --abc abc-summary.json \
                    -o pass-history.json
pass-timeseries-report pass-history.json -o pass-timeseries.html
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
| `check-cec` | Run combinational equivalence check (CEC) between two summaries; outputs `cec.json` |
| `compare-results` | Compare two summaries; output HTML / Markdown / JSON. Pass `--cec cec.json` for CEC annotations, or `--equiv-check` to run CEC inline |
| `append-history` | Append a day's summaries to `history.json` |
| `timeseries-report` | Generate interactive HTML time series from `history.json` |
| `append-pass-history` | Append pass benchmark ratios to `pass-history.json` |
| `pass-timeseries-report` | Generate interactive HTML time series from `pass-history.json` |
| `prepare` | Build `mockturtle-aig-judge` and fetch `benchmarks/abc.rc` |
