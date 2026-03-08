# Pass Benchmark Suite (`benchmarks/pass`)

This suite runs pass-level compile-time benchmarks on pre-generated LSILS AIG inputs.
It compares CIRCT pass execution with equivalent ABC commands.

## Run

```bash
# Single config
lit -v benchmarks/pass/ -DLUT_SIZE=6 -DCUT_SIZE=8 -DTEST_OUTPUT_DIR=build_pass
```

## Parameters

Use `lit -D<NAME>=<VALUE>` to set parameters.

### Pass-suite-specific parameters

| Parameter | Default | Description |
|---|---|---|
| `LUT_SIZE` | `6` | LUT size used in pass benchmark commands |
| `CUT_SIZE` | `8` | Cut limit used in pass benchmark commands |
| `TOOL` | `circt` | Engine to benchmark: `circt` or `abc` |

### Inherited parameters from parent lit config

| Parameter | Default | Description |
|---|---|---|
| `TEST_OUTPUT_DIR` | `build` | Output root for lit execution artifacts |

Notes:
- `SYNTH_TOOL`, `BW`, and `ABC_COMMANDS` are combinational-flow parameters and are not used by the pass benchmark tests.
- Pass tests use `%PASS_LUT_SIZE` and `%PASS_CUT_SIZE` substitutions internally.
- To collect both engines, run pass tests twice (`-DTOOL=circt` and `-DTOOL=abc`) and aggregate both result sets.

## Sweep example

For LUT/CUT sweeps, use the top-level helper script:

```bash
LUT_SIZES=4,6 CUT_SIZES=8,12 OUT_DIR=build_pass ./run.sh
```
