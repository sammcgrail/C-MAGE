#!/usr/bin/env bash
#
# Build C-MAGE's three environments with uv instead of conda.
#
#   ./install-uv.sh              all three stages
#   ./install-uv.sh decimer      one stage
#   ./install-uv.sh --force      rebuild environments that already exist
#
# WHY THIS EXISTS, alongside install.sh rather than replacing it: conda is a
# hard prerequisite in the upstream README, and on a machine that has no conda
# and no intention of getting one, the three specs are just three pinned pip
# requirement sets plus poppler. uv builds them in a fraction of the time and
# needs nothing but a python. The pins are NOT relaxed — envs/uv/*.txt carry the
# same versions and the same reasoning as envs/*.yml, and the two conda-only
# entries are handled here:
#
#   poppler                -> apt/brew (pdf2image shells out to pdftoppm)
#   cudatoolkit + cudnn    -> dropped; this path is CPU-only. A CUDA box should
#                             use install.sh, where conda pins the pair that
#                             TensorFlow 2.12 needs.
#
# The venvs are created as .venv-<short> and then symlinked into .venvs/ under
# the conda environment names. That is deliberate: run_pipeline.sh and
# run_pipeline.py find an environment by probing <root>/<name>/bin/python, so
# one extra root in their list makes them work with uv unchanged. No rewrite of
# the runner, and the diff back to upstream stays two lines.
#
# Still three environments, not one. The conflict is irreducible: stage 2's
# TensorFlow 2.12 requires numpy < 1.24 and the torch stages require >= 1.24.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FORCE="no"
STAGES=()

for arg in "$@"; do
    case "$arg" in
        --force) FORCE="yes" ;;
        -h|--help)
            sed -n '3,8p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
            echo; echo "Stages: visualheist  decimer  cxmolscribe"; exit 0 ;;
        visualheist|decimer|cxmolscribe) STAGES+=("$arg") ;;
        *) echo "install-uv.sh: unknown argument '$arg'" >&2; exit 2 ;;
    esac
done
[ ${#STAGES[@]} -eq 0 ] && STAGES=(visualheist decimer cxmolscribe)

log() { printf '\n\033[1m==> %s\033[0m\n' "$*"; }
die() { echo "install-uv.sh: $*" >&2; exit 1; }

command -v uv >/dev/null 2>&1 || die "uv is not installed -- https://docs.astral.sh/uv/"

# poppler is a conda dependency in the yml specs; pdf2image shells out to its
# pdftoppm/pdftocairo binaries and fails with PDFInfoNotInstalledError without
# them. Check rather than assume, and say which command to run.
if ! command -v pdftoppm >/dev/null 2>&1; then
    if command -v apt-get >/dev/null 2>&1; then
        log "Installing poppler-utils (pdf2image needs pdftoppm)"
        # Needs root. Report the command rather than dying inside set -e with
        # -qq having swallowed the reason.
        apt-get install -y poppler-utils || die \
            "could not install poppler-utils. Run: sudo apt-get update && sudo apt-get install -y poppler-utils"
    else
        die "poppler not found. Install it: brew install poppler / dnf install poppler-utils"
    fi
fi

# stage name -> venv dir, python version, requirements, editable package.
# The editable installs are what make `import visualheist` / `import
# decimer_segmentation` resolve; without them the stage scripts die on
# ModuleNotFoundError even though everything is present on disk.
venv_for()    { case "$1" in visualheist) echo .venv-vh ;; decimer) echo .venv-decimer ;; cxmolscribe) echo .venv-ms ;; esac; }
python_for()  { case "$1" in cxmolscribe) echo 3.11 ;; *) echo 3.10 ;; esac; }
reqs_for()    { case "$1" in visualheist) echo envs/uv/stage1-visualheist.txt ;;
                             decimer)     echo envs/uv/stage2-decimer.txt ;;
                             cxmolscribe) echo envs/uv/stage3-cxmolscribe.txt ;; esac; }
editable_for(){ case "$1" in visualheist) echo MERMaid ;;
                             decimer)     echo cxmolscribe-wd/DECIMER-Image-Segmentation ;;
                             cxmolscribe) echo cxmolscribe-wd/MolScribe ;; esac; }
condaname_for(){ echo "cmage-$1"; }

# Up front, before any work: a missing spec should cost zero minutes, not two
# completed installs.
for stage in "${STAGES[@]}"; do
    [ -f "${REPO_ROOT}/$(reqs_for "$stage")" ] || die "missing requirements file: $(reqs_for "$stage")"
done

mkdir -p "${REPO_ROOT}/.venvs"

for stage in "${STAGES[@]}"; do
    venv="${REPO_ROOT}/$(venv_for "$stage")"
    reqs="${REPO_ROOT}/$(reqs_for "$stage")"
    pkg="${REPO_ROOT}/$(editable_for "$stage")"

    [ -f "$reqs" ] || die "missing requirements file: ${reqs}"

    # A directory is not a finished environment. Stamp it only after the editable
    # install returns, and treat a missing or stale stamp as "rebuild" -- otherwise
    # an interrupted install leaves a venv that passes verification and dies at
    # stage runtime, which the installer would then refuse to repair.
    stamp="${venv}/.cmage-install-complete"
    want="$(sha256sum "$reqs" | cut -d" " -f1)"
    if [ -d "$venv" ] && [ "$FORCE" = "no" ] && [ "$(cat "$stamp" 2>/dev/null)" = "$want" ]; then
        log "${stage}: ${venv##*/} already built (--force to rebuild)"
    else
        [ "$FORCE" = "yes" ] && rm -rf "$venv"
        log "${stage}: creating ${venv##*/} (python $(python_for "$stage"))"
        uv venv "$venv" --python "$(python_for "$stage")"
        log "${stage}: installing pinned requirements"
        VIRTUAL_ENV="$venv" uv pip install -r "$reqs"
        log "${stage}: installing ${pkg##*/} (editable, --no-deps)"
        # --no-deps on purpose: every dependency is already pinned above, and
        # letting the package resolve its own install_requires pulls an
        # incompatible torch. Same reasoning as upstream install.sh.
        VIRTUAL_ENV="$venv" uv pip install -e "$pkg" --no-deps
        echo "$want" > "$stamp"
    fi

    # The conda-named symlink the runners probe for.
    # RELATIVE, not absolute: an absolute link embeds this machine's path and
    # dangles the moment the repo is moved or cloned elsewhere.
    ln -sfn "../$(venv_for "$stage")" "${REPO_ROOT}/.venvs/$(condaname_for "$stage")"
done

log "Verifying the runners can see the environments"
missing=0
for stage in "${STAGES[@]}"; do
    p="${REPO_ROOT}/.venvs/$(condaname_for "$stage")/bin/python"
    # NOT just "is there an interpreter" -- that is true of an empty venv. Import
    # the stage's own package. (decimer_segmentation is deliberately NOT imported:
    # importing it triggers the 260 MB weights download.)
    probe() { case "$1" in visualheist) echo visualheist ;; decimer) echo decimer_segmentation.complete_structure ;;
                           cxmolscribe) echo molscribe ;; esac; }
    if [ -x "$p" ] && "$p" -c "import $(probe "$stage")" >/dev/null 2>&1; then
        printf '  ok   %-28s %s\n' "$(condaname_for "$stage")" "$("$p" --version 2>&1)"
    else
        printf '  FAIL %-28s cannot import %s (rerun: ./install-uv.sh --force %s)\n' \
            "$(condaname_for "$stage")" "$(probe "$stage")" "$stage"; missing=1
    fi
done
[ "$missing" -eq 0 ] || die "one or more environments did not build"

log "Done. Run:  ./run_pipeline.sh --device cpu"
