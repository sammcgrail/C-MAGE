#!/usr/bin/env bash
# Score a finished Sonnet batch and PUBLISH it, in one command.
#
# Sam asked that the page update every time a batch finishes. Every step below was
# previously separate, which meant "finished" and "published" could differ by
# hours and nothing on the page said so. One script, and it fails loudly rather
# than leaving the site half-updated.
set -euo pipefail
SLOT="${1:-a}"
ANS="/tmp/sonnet_answers_${SLOT}.json"
PY=/root/C-MAGE/.venv-ms/bin/python

[ -f "$ANS" ] || { echo "no answers for slot $SLOT at $ANS"; exit 2; }
[ -f "/root/cmage-work/sonnet/pending_${SLOT}.json" ] || {
  echo "slot $SLOT has no outstanding claim -- already scored"; exit 0; }

$PY /root/C-MAGE/tools/sonnet_batch.py score "$ANS" "$SLOT"
# `all` chains the Sonnet build, so the two tabs cannot report different corpus sizes.
$PY /root/C-MAGE/tools/build_wall.py all
# Refuses to pass if the payloads disagree with each other or with the scored data.
$PY /root/C-MAGE/tools/check_wall_consistent.py
( cd /root/cmage && docker compose up -d --build >/dev/null 2>&1 )
for i in $(seq 1 25); do curl -sf localhost:20079/api/health >/dev/null 2>&1 && break; sleep 3; done

# Prove the DEPLOY carries the new count, not just the file on disk. A rebuilt
# container that served a cached layer looks identical to a successful one.
want=$($PY -c "import json;print(json.load(open('/root/C-MAGE/benchmarks/wall/sonnet.json'))['compare']['n'])")
got=$(curl -s localhost:20079/wall/sonnet.json | $PY -c "import json,sys;print(json.load(sys.stdin)['compare']['n'])")
[ "$want" = "$got" ] || { echo "DEPLOY STALE: disk says $want, server says $got"; exit 1; }
echo "published: $got images live on the Sonnet tab"
