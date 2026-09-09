#!/usr/bin/env bash
# Stage-3-only arm: CXMolScribe straight onto the clean cell crops, no segmentation.
#
# THREAD CAP: three torch processes were each grabbing all 8 cores (no OMP limit
# anywhere), so 24 threads thrashed on 8 and throughput collapsed to ~2 images a
# minute against a quiet-box rate of 25. Capped so the arms and the parallel
# real-PDF run can coexist.
#
# ORDER: crops are processed ROUND-ROBIN across groups, not alphabetically. The
# arm gap can only be reported for a stratum BOTH arms covered, and alphabetical
# order puts salt, stereo, markush and vocab last -- so a cutoff would delete
# exactly the strata the comparison needs. Any prefix of a round-robin list is a
# stratified sample.
export DECIMER_WEIGHTS=/root/cmage-models/decimer/mask_rcnn_molecule.h5
export OMP_NUM_THREADS=3 MKL_NUM_THREADS=3 OPENBLAS_NUM_THREADS=3 NUMEXPR_NUM_THREADS=3
set -u
ROOT=/root/C-MAGE
OUT=/tmp/cmage-synth2/stage3
STATUS=$OUT/RUN_STATUS.md
mkdir -p "$OUT"
[ -f "$STATUS" ] || { echo "| batch | images | wall s | status |"; echo "|---|---|---|---|"; } >> "$STATUS"
cd "$ROOT" || exit 2
mapfile -t IMGS < /tmp/cmage-synth2/crop_order.txt
total=${#IMGS[@]}
b=0
for ((i=0; i<total; i+=100)); do
  b=$((b+1)); name=$(printf "c%02d" $b)
  # resume must key on a COMPLETED batch, not on the directory existing: a batch
  # killed mid-run leaves out/ behind and would otherwise be skipped forever
  if ls "$OUT/$name/out"/run_*/03_CXMS_Results/Completed_HighConfidence_CMAGE.xlsx >/dev/null 2>&1; then continue; fi
  rm -rf "$OUT/$name"; mkdir -p "$OUT/$name/in"
  for ((j=i; j<i+100 && j<total; j++)); do cp "${IMGS[$j]}" "$OUT/$name/in/"; done
  n=$(ls "$OUT/$name/in" | wc -l)
  s=$(date +%s)
  ./benchmarks/run_stage3_only.sh --images "$OUT/$name/in" --out "$OUT/$name/out" --device cpu \
      > "$OUT/$name/run.log" 2>&1
  rc=$?; wall=$(( $(date +%s) - s ))
  echo "| $name | $n | $wall | $([ $rc -eq 0 ] && echo ok || echo FAILED_rc=$rc) |" >> "$STATUS"
  rm -rf "$OUT/$name/in"
done
echo -e "\nFinished $(date -u +%FT%TZ)" >> "$STATUS"
