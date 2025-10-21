# DatapathBench Tests

Lit-based tests for the DatapathBench suite.

## Adding New Tests

Create a new `.test` file in the `tests/` directory:

```bash
# tests/my_benchmark.test
RUN: %SYNTH_TOOL %S/../DatapathBench/benchmarks/my_benchmark/sv/my_benchmark.sv --bw %BW -top my_module -o %t.aig
RUN: %judge %t.aig | %submit %s --name my_benchmark
```

The test will be automatically discovered by lit.

## Updating Tests

Edit the corresponding `.test` file in `tests/`:
- Update the benchmark path if the DatapathBench structure changes
- Modify the top module name or parameters as needed
- Change the benchmark name passed to `%submit`
