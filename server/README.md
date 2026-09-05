# circt-synth-server-rs

Production-quality HTTP front end for `circt-synth-server`
(or plain `circt-synth`-compatible single-shot backends).

- `POST /synthesize {mlir, top?, strategy?, ...}` — bounded worker pool
  (one backend process each), per-request timeouts, SHA-256 fingerprint
  cache, optional JSONL admit log + content-addressed blobs compatible
  with `circt_synth_tracker.db`.
- `GET /health` — liveness including a backend `--version` probe.

```bash
cargo build --release
CIRCT_SYNTH_SERVER_BIN=/path/to/circt-synth-server \
  ./target/release/circt-synth-server-rs --port 8932 --jobs 4 \
  --db-dir ./db
```

Tests: `cargo test` (unit) plus one ignored integration test needing a
backend: `CIRCT_SYNTH_SERVER_BIN=... cargo test -- --ignored`.
