#!/usr/bin/env bash
#
# Run C-MAGE stage 3 (CXMolScribe) directly on a directory of images, skipping
# stage 2 (DECIMER segmentation). This is the "no segmentation" arm of the
# ablation: same model, same stage-3 script (folder_ms.py), same spreadsheet
# output, one variable removed.
#
# The run directory mirrors run_pipeline.sh's layout so the same scorer reads
# both arms:
#   <out>/run_<timestamp>/02_DIS_Segments/DIS_CMAGE_results.xlsx   lists the raw images
#   <out>/run_<timestamp>/03_CXMS_Results/Completed_{High,Low}Confidence_CMAGE.xlsx
#   <out>/run_<timestamp>/logs/stage3.log
#
#   benchmarks/run_stage3_only.sh --images DIR --out DIR [--device cpu]
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGES=""
OUT_ROOT="${REPO_ROOT}/results"
DEVICE="${CMAGE_DEVICE:-cpu}"

while [ $# -gt 0 ]; do
    case "$1" in
        --images) IMAGES="$2"; shift 2 ;;
        --out)    OUT_ROOT="$2"; shift 2 ;;
        --device) DEVICE="$2"; shift 2 ;;
        -h|--help) sed -n '2,17p' "$0"; exit 0 ;;
        *) echo "unknown argument '$1'" >&2; exit 2 ;;
    esac
done
[ -d "$IMAGES" ] || { echo "--images DIR is required and must exist" >&2; exit 2; }

# Same environment discovery as run_pipeline.sh (uv venvs first, then conda roots).
env_prefix() {
    local name="$1" root
    for root in "${REPO_ROOT}/.venvs" "${REPO_ROOT}/.micromamba/envs" \
                "${MAMBA_ROOT_PREFIX:-/nonexistent}/envs" \
                "${HOME}/micromamba/envs" "${HOME}/miniforge3/envs" "${HOME}/miniconda3/envs" \
                "${HOME}/anaconda3/envs" "/opt/miniconda3/envs" "/opt/anaconda3/envs"; do
        [ -x "${root}/${name}/bin/python" ] && { echo "${root}/${name}"; return 0; }
    done
    return 1
}
PREFIX="$(env_prefix cmage-cxmolscribe)" || { echo "environment cmage-cxmolscribe not found; run install first" >&2; exit 1; }

RUN_DIR="${OUT_ROOT}/run_$(date +%Y%m%d-%H%M%S)"
mkdir -p "${RUN_DIR}"/{02_DIS_Segments,03_CXMS_Results,logs}
RESULTS_XLSX="${RUN_DIR}/02_DIS_Segments/DIS_CMAGE_results.xlsx"

# Stage 3 reads its inputs from a spreadsheet with one column, "DIS Result File
# Paths". Write that column with the raw image paths instead of segment paths.
"${PREFIX}/bin/python" - "$IMAGES" "$RESULTS_XLSX" <<'PY'
import sys, os
import pandas as pd
src, out = sys.argv[1], sys.argv[2]
exts = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}
paths = [os.path.abspath(os.path.join(src, f)) for f in sorted(os.listdir(src))
         if not f.startswith(".") and os.path.splitext(f)[1].lower() in exts
         and os.path.isfile(os.path.join(src, f))]
pd.DataFrame(paths, columns=["DIS Result File Paths"]).to_excel(out)
print(f"{len(paths)} images listed in {out}")
PY

echo "==> Run directory: ${RUN_DIR}"
echo "==> Stage 3 only  CXMolScribe on raw images from ${IMAGES}"
CMAGE_DEVICE="$DEVICE" LD_LIBRARY_PATH="${PREFIX}/lib:${LD_LIBRARY_PATH:-}" PATH="${PREFIX}/bin:${PATH}" \
    "${PREFIX}/bin/python" "${REPO_ROOT}/cxmolscribe-wd/folder_ms.py" \
        --results-excel "$RESULTS_XLSX" \
        --output-dir "${RUN_DIR}/03_CXMS_Results" \
        --canvas "${REPO_ROOT}/cxmolscribe-wd/DECIMER-Image-Segmentation/canvas.xlsx" \
        2>&1 | tee "${RUN_DIR}/logs/stage3.log"

echo "==> Done"
echo "Results:  ${RUN_DIR}/03_CXMS_Results"
