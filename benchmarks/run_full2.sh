#!/usr/bin/env bash
# Full-pipeline arm over the v2 synthetic corpus, in page-bounded batches.
#
# THREAD CAP added: nothing in the stack sets an OMP limit, so every torch/TF
# process grabbed all 8 cores. With two arms plus a parallel real-PDF run that
# is ~24 threads on 8 cores and throughput collapses.
#
# RESUME FIX: the previous version skipped any batch whose out/ directory
# existed. A batch killed mid-run leaves out/ behind, so it would have been
# skipped FOREVER and the corpus would have carried a silent hole -- which the
# scorer reports as failures, not as missing data. Resume now keys on the
# stage-3 workbook, i.e. on a batch that actually FINISHED.
export DECIMER_WEIGHTS=/root/cmage-models/decimer/mask_rcnn_molecule.h5
export OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 NUMEXPR_NUM_THREADS=4
set -u
ROOT=/root/C-MAGE
OUT=/tmp/cmage-synth2/full
STATUS=$OUT/RUN_STATUS.md
mkdir -p "$OUT"
[ -f "$DECIMER_WEIGHTS" ] || { echo "FATAL: local weights missing"; exit 2; }
[ -f "$STATUS" ] || { echo "| batch | pdfs | pages | wall s | figures | segments | status |"; echo "|---|---|---|---|---|---|---|"; } >> "$STATUS"
cd "$ROOT" || exit 2
mapfile -t PDFS < <(ls benchmarks/corpus_synth2/*.pdf | sort)
b=0; batch=(); pages=0
flush() {
  [ ${#batch[@]} -eq 0 ] && return
  b=$((b+1)); local name; name=$(printf "b%02d" $b)
  if ls "$OUT/$name/out"/run_*/03_CXMS_Results/Completed_HighConfidence_CMAGE.xlsx >/dev/null 2>&1; then
    batch=(); pages=0; return
  fi
  rm -rf "$OUT/$name"; mkdir -p "$OUT/$name/in"
  for p in "${batch[@]}"; do cp "$p" "$OUT/$name/in/"; done
  local s; s=$(date +%s)
  ./run_pipeline.sh --pdfs "$OUT/$name/in" --out "$OUT/$name/out" --device cpu --local \
      > "$OUT/$name/run.log" 2>&1
  local rc=$?; local wall=$(( $(date +%s) - s ))
  local figs segs
  figs=$(find "$OUT/$name/out" -path '*01_VH_Figures*' -name '*.png' 2>/dev/null | wc -l)
  segs=$(find "$OUT/$name/out" -path '*02_DIS_Segments*' -name '*.png' 2>/dev/null | wc -l)
  echo "| $name | ${#batch[@]} | $pages | $wall | $figs | $segs | $([ $rc -eq 0 ] && echo ok || echo FAILED_rc=$rc) |" >> "$STATUS"
  rm -rf "$OUT/$name/in"
  batch=(); pages=0
}
for pdf in "${PDFS[@]}"; do
  n=$(pdfinfo "$pdf" 2>/dev/null | awk '/^Pages:/{print $2}'); n=${n:-2}
  if [ $((pages + n)) -gt 25 ] && [ ${#batch[@]} -gt 0 ]; then flush; fi
  batch+=("$pdf"); pages=$((pages + n))
done
flush
echo -e "\nFinished $(date -u +%FT%TZ)" >> "$STATUS"
