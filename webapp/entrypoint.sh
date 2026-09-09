#!/bin/sh
# Container entry point for the C-MAGE web app.
#
# The pipeline's model weights are expected to be present already (baked into
# the image, or mounted). The one fragile download is DECIMER's 260 MB Zenodo
# file, so if it is missing it is fetched in the background with retries while
# the UI comes up; /api/health reports when it has arrived.
set -eu

ROOT="${CMAGE_ROOT:-/opt/cmage}"
DATA="${CMAGE_DATA:-/data}"
PORT="${CMAGE_PORT:-8080}"

mkdir -p "${DATA}/jobs"

if ! python3 "${ROOT}/tools/fetch_weights.py" --check >/dev/null 2>&1; then
    echo "[entrypoint] DECIMER weights not found; fetching in the background (see ${DATA}/fetch_weights.log)"
    ( python3 "${ROOT}/tools/fetch_weights.py" --wait "${CMAGE_WEIGHTS_WAIT:-3600}" >> "${DATA}/fetch_weights.log" 2>&1 || true ) &
fi

# Warm the benchmark cache. Building it walks every run directory and every
# scored CSV under the benchmark mount, which takes ~21 s cold and 37 ms warm --
# so without this the FIRST visitor after any deploy sits on "Loading..." for
# twenty seconds and every later one sees it instantly, which is exactly the kind
# of problem that never reproduces when you go to look at it. Backgrounded, so a
# slow or failing warm-up can never stop the server coming up.
(
    for _ in $(seq 1 60); do
        if curl -sf -o /dev/null "http://127.0.0.1:${PORT}/api/health" 2>/dev/null; then break; fi
        sleep 1
    done
    curl -sf -o /dev/null --max-time 300 "http://127.0.0.1:${PORT}/api/benchmark" 2>/dev/null \
        && echo "[entrypoint] benchmark cache warm" \
        || echo "[entrypoint] benchmark warm-up did not complete; first visitor will pay for it"
) &

cd "${ROOT}/webapp"
exec python3 -m uvicorn server.app:app --host 0.0.0.0 --port "${PORT}" --workers 1 \
    --proxy-headers --forwarded-allow-ips '*' --no-server-header
