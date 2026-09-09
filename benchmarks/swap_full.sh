#!/usr/bin/env bash
# Swap the full-arm runner for the thread-capped one, WITHOUT losing b01.
# Waits for b01's completion row so the swap happens between batches.
set -u
while ! grep -q "^| b01" /tmp/cmage-synth2/full/RUN_STATUS.md 2>/dev/null; do sleep 20; done
OLD=$(grep -o '[0-9]\+' /tmp/cmage-synth2/full.pid | tail -1)
# kill the wrapper and its whole descendant tree, nothing else
for p in $(pstree -p "$OLD" 2>/dev/null | grep -o '([0-9]\+)' | tr -d '()'); do kill "$p" 2>/dev/null; done
kill "$OLD" 2>/dev/null
sleep 5
nohup /tmp/cmage-synth2/run_full2.sh > /tmp/cmage-synth2/run_full2.log 2>&1 &
echo "$!" > /tmp/cmage-synth2/full.pid
echo "swapped at $(date -Is), new pid $(cat /tmp/cmage-synth2/full.pid)" >> /tmp/cmage-synth2/swap.log
