#!/usr/bin/env bash
set -euo pipefail

export PATH="$HOME/dev/circt-synth/build/bin:$PATH"

LUT_SIZE="${LUT_SIZE:-6}"
LUT_SIZES="${LUT_SIZES:-6}"
CUT_SIZE="${CUT_SIZE:-8}"
CUT_SIZES="${CUT_SIZES:-}"
OUT_DIR="${OUT_DIR:-build_pass}"
JOBS="${JOBS:-$(nproc)}"

if [[ -n "${CUT_SIZES}" ]]; then
  CUT_LIST="${CUT_SIZES}"
else
  CUT_LIST="${CUT_SIZE}"
fi

if [[ -n "${LUT_SIZES}" ]]; then
  LUT_LIST="${LUT_SIZES}"
else
  LUT_LIST="${LUT_SIZE}"
fi

rm -rf "${OUT_DIR}"

echo "Running pass benchmarks: LUT_SIZES=${LUT_LIST}, CUT_SIZES=${CUT_LIST}, OUT_DIR=${OUT_DIR}, JOBS=${JOBS}"

IFS=',' read -ra LUT_ARR <<< "${LUT_LIST}"
IFS=',' read -ra CUT_ARR <<< "${CUT_LIST}"
for L in "${LUT_ARR[@]}"; do
  for C in "${CUT_ARR[@]}"; do
    lit -v benchmarks/pass/ \
      -j "${JOBS}" \
      -DTEST_OUTPUT_DIR="${OUT_DIR}" \
      -DLUT_SIZE="${L}" \
      -DCUT_SIZE="${C}" -DTOOL=abc
    lit -v benchmarks/pass/ \
      -j "${JOBS}" \
      -DTEST_OUTPUT_DIR="${OUT_DIR}" \
      -DLUT_SIZE="${L}" \
      -DCUT_SIZE="${C}" -DTOOL=circt
  done
done

VERSION="$(circt-synth --version | tail -1 | xargs || echo local)"
aggregate-results --tool circt-lut-mapping-pass --version "${VERSION}" --results-dir "${OUT_DIR}" -o circt-lut-summary.json
aggregate-results --tool abc-lut-mapping-pass --version "${VERSION}" --results-dir "${OUT_DIR}" -o abc-lut-summary.json
aggregate-results --tool circt-sop-balancing-pass --version "${VERSION}" --results-dir "${OUT_DIR}" -o circt-sop-summary.json
aggregate-results --tool abc-sop-balancing-pass --version "${VERSION}" --results-dir "${OUT_DIR}" -o abc-sop-summary.json

VERSION="${VERSION}" python3 - <<'PY'
import json
import os
from pathlib import Path


def merge(out, tool, version, a, b):
    ja = json.loads(Path(a).read_text())
    jb = json.loads(Path(b).read_text())
    merged = {
        "tool": tool,
        "version": version,
        "timestamp": ja.get("timestamp", ""),
        "total_benchmarks": len(ja.get("benchmarks", {})) + len(jb.get("benchmarks", {})),
        "benchmarks": {**ja.get("benchmarks", {}), **jb.get("benchmarks", {})},
    }
    Path(out).write_text(json.dumps(merged, indent=2))


version = os.environ.get("VERSION", "local")
merge("circt-summary.json", "circt-pass", version, "circt-lut-summary.json", "circt-sop-summary.json")
merge("abc-summary.json", "abc-pass", version, "abc-lut-summary.json", "abc-sop-summary.json")
PY

pass-pr-compare-report single \
  --a circt-summary.json \
  --b abc-summary.json \
  --label-a CIRCT \
  --label-b ABC \
  --version "${VERSION}" \
  --title "Pass Benchmark (CIRCT vs ABC)" \
  --markdown-out pass-benchmark-report.md \
  --html-out pass-benchmark-report.html
