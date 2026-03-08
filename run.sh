#!/usr/bin/env bash
set -euo pipefail

 export PATH="$HOME/dev/circt-synth/build/bin:$PATH"
rm -rf build_pass
 
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

pass-benchmark-report \
  --circt-lut circt-lut-summary.json \
  --abc-lut abc-lut-summary.json \
  --circt-sop circt-sop-summary.json \
  --abc-sop abc-sop-summary.json \
  --sweep-lut-sizes "${LUT_LIST}" \
  --sweep-cut-sizes "${CUT_LIST}" \
  --markdown-out pass-benchmark-report.md \
  --html-out pass-benchmark-report.html
