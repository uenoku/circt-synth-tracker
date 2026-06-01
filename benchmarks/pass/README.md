# Pass Benchmark Suite (`benchmarks/pass`)

This suite runs pass-level compile-time benchmarks on pre-generated LSILS AIG inputs,
plus a fixed set of DatapathBench AIG fixtures generated from SystemVerilog.
It compares CIRCT pass execution with equivalent ABC commands.

`benchmarks/pass/commands.json` defines each mode and now includes `output`:
- `output: "lut"`: report `lut_count`/`lut_depth`
- `output: "aig"`: report `aig_count`/`aig_depth`

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
- SOP balancing reports AIG metrics after structural hashing (`synth-structural-hash` for CIRCT, `strash` for ABC) so structurally equivalent nodes are normalized before comparison.
- To collect both engines, run pass tests twice (`-DTOOL=circt` and `-DTOOL=abc`) and aggregate both result sets.

## DatapathBench AIG fixtures

DatapathBench pass tests use checked-in AIG fixtures generated from a fixed set of
SV sources at `BW=16` and `BW=48` with `run-circt-synth`:

```bash
benchmarks/aig/datapathbench/generate_aigs.py \
  --circt-verilog /path/to/circt-verilog \
  --circt-synth /path/to/circt-synth \
  --circt-translate /path/to/circt-translate
```

## Sweep example

For LUT/CUT sweeps, use the top-level helper script:

```bash
LUT_SIZES=4,6 CUT_SIZES=8,12 OUT_DIR=build_pass ./run.sh
```
