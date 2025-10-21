# ELAU Benchmarks

Lit-based tests for ELAU arithmetic library benchmarks.

## Adding New Tests

Edit `generate_tests.py` and add to the `tests` list:

```python
tests = [
    ("AddMop", "behavioural_AddMop", ["width"]),
    ("MyModule", "behavioural_MyModule", ["width"]),  # Add new test here
    # Format: (file_name, top_module, [parameter_names])
]
```

Then regenerate test files:

```bash
./generate_tests.py
```

This creates `tests/MyModule.test` with the proper RUN directives.

## Updating Tests

For auto-generated tests, edit `generate_tests.py` and re-run it.

For manual tests, edit the `.test` file directly in `tests/`.

## Test Parameters

Multi-parameter modules example:

```python
("AddMulUns", "behavioural_AddMulUns", ["widthX", "widthY"]),
```

This generates: `-G widthX=%BW -G widthY=%BW` in the test.
