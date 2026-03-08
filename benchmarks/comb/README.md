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
