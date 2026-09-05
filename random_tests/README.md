# Random Adversarial-Arithmetic Suite (`random_tests/`)

A fuzz-style suite of randomly generated combinational arithmetic logic.
It is intentionally **separate from `benchmarks/`**: running the normal
benchmark tracks never executes these tests. Run it explicitly:

```bash
lit -v random_tests/
```

The generated modules deliberately stress error-prone corners of
arithmetic synthesis, e.g.:

- Mixed-extension arithmetic: `(zext(a) + sext(b)) * c`
- `$signed` / `$unsigned` casts mixed into one expression (SV silently
  makes the whole expression unsigned as soon as one operand is unsigned)
- Part selects, which drop signedness even from signed signals
- Arithmetic right shifts (`>>>`) whose sign-fill depends on casts
- Comparisons feeding muxes and arithmetic
- Truncations via slicing and concatenation

## Generating tests

Tests are **not committed** to the repository; generate them on demand
with a seeded script, so any batch is reproducible:

```bash
cd random_tests
./generate_tests.py --seed 1 --num-tests 10
```

Generated `.sv` files land in `tests/` (gitignored) and contain their own
lit `RUN:` directives, so afterwards simply run `lit -v random_tests/`
from the repository root. Files are validated with `circt-verilog`
before being kept (disable with `--no-validate`). Regenerate freely or
use new seeds for fresh batches.

## Parameters

All shared parameters from `benchmarks/README.md` are inherited, for
example:

```bash
lit -v random_tests/ -DSYNTH_TOOL=circt -DTV_SOLVER=bitwuzla
lit -v random_tests/ -DSYNTH_TOOL=yosys -DBW=8 -DTEST_OUTPUT_DIR=build_yosys
```

Note that `BW` here bounds only the *maximum input* width of newly
generated tests.

For equivalence checking against pre-synthesis MLIR, enable LEC:

```bash
lit -v random_tests/ -DRUN_LEC=1
```

## CI

`.github/workflows/ci-random-arith.yml` regenerates and runs this suite
nightly (1000 cases from a fixed seed) and on PRs touching it (100
cases), always with LEC enabled. The job fails on any
`non-equiv`/`error` LEC result; timeouts are tolerated and reported in
the step summary.
