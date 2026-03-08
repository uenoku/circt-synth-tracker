# Combinational Benchmark Suite (`benchmarks/comb`)

This suite runs end-to-end synthesis flows on SystemVerilog benchmarks.

## Run

```bash
# All combinational benchmarks
lit -v benchmarks/comb/

# One subset
lit -v benchmarks/comb/DatapathBench/
```

## Parameters

Use `lit -D<NAME>=<VALUE>` to set parameters.

### Core flow parameters

| Parameter | Default | Description |
|---|---|---|
| `SYNTH_TOOL` | `circt` | Synthesis frontend: `circt` or `yosys` |
| `TECH_MAP` | `mockturtle` | Judge backend: `mockturtle` or `abc` |
| `BW` | `16` | Bitwidth for parameterized benchmarks |
| `TEST_OUTPUT_DIR` | `build` | Output root for lit execution artifacts |
| `RESULTS_DIR` | _(empty)_ | Optional explicit directory for `%submit` JSON output |

### CIRCT-specific parameters

| Parameter | Default | Description |
|---|---|---|
| `CIRCT_SYNTH_EXTRA_ARGS` | _(empty)_ | Extra flags passed to `circt-synth` |
| `RUN_LEC` | _(empty)_ | If set, run LEC in the CIRCT flow |
| `TV_SOLVER` | _(empty)_ | Enables translation validation (TV) and runs this solver (for example `bitwuzla`, `z3`) |
| `KEEP_TV_ARTIFACTS` | _(empty)_ | Keep per-pass TV IR/SMT artifacts |

### AIG optimization parameter

| Parameter | Default | Description |
|---|---|---|
| `ABC_COMMANDS` | _(empty)_ | ABC script run by `%AIG_TOOL` between synthesis and judging |

## Common examples

```bash
# Yosys synthesis, 8-bit
lit -v benchmarks/comb/ -DSYNTH_TOOL=yosys -DBW=8 -DTEST_OUTPUT_DIR=build_yosys

# CIRCT with custom synthesis flags
lit -v benchmarks/comb/ -DSYNTH_TOOL=circt -DCIRCT_SYNTH_EXTRA_ARGS="--disable-datapath"

# CIRCT + ABC optimization pass script
lit -v benchmarks/comb/ -DSYNTH_TOOL=circt -DABC_COMMANDS="resyn2;"

# Translation validation using Bitwuzla
lit -v benchmarks/comb/ -DSYNTH_TOOL=circt -DTV_SOLVER=bitwuzla
```

## ABC Aliases (`benchmarks/abc.rc`)

After `uv run prepare`, `benchmarks/abc.rc` is populated with ABC standard
aliases (fetched from the ABC repository at a pinned commit). These can be
referenced from `ABC_COMMANDS`.

```bash
lit -v benchmarks/comb/ -DABC_COMMANDS="resyn2;"
lit -v benchmarks/comb/ -DABC_COMMANDS="compress2rs;"
```

## SMT Translation Validation

Translation Validation (TV) uses `circt-lec` to verify that each CIRCT synthesis
pass preserves logical equivalence. When enabled, `circt-synth` dumps per-pass
MLIR snapshots and `circt-lec --emit-smtlib` is piped to an SMT solver (Bitwuzla
or Z3) for each consecutive step:

```
input.mlir -> pass_0 -> pass_1 -> ... -> synth_output.mlir
```

Results are recorded as a `.tv` sidecar near the AIG output and are aggregated as
`tv_status` (`pass` / `fail` / `error`) and `tv_results` (per-step status).

When non-equivalence is detected, failing MLIR pair(s) are saved under `.tv-pairs/`
alongside the AIG output, with a `reproduce.sh` helper.

Set `-DKEEP_TV_ARTIFACTS=1` to keep per-pass IR and SMT-LIB dumps in:
- `<output>.tv-ir-tree`
- `<output>.tv-ir-tree/tv-smt`

### Running TV locally

TV requires `circt-lec` in `PATH` and an SMT solver that reads SMT-LIB from stdin.

```bash
# Bitwuzla (recommended)
lit -v benchmarks/comb/ -DSYNTH_TOOL=circt -DTV_SOLVER=bitwuzla

# Z3
lit -v benchmarks/comb/ -DSYNTH_TOOL=circt -DTV_SOLVER=z3

# Any compatible SMT solver
lit -v benchmarks/comb/ -DSYNTH_TOOL=circt -DTV_SOLVER="your-solver -your-flags"
```

### TV in CI

TV runs automatically for CIRCT benchmark runs in CI workflows. Bitwuzla is
downloaded as a static binary during setup.
