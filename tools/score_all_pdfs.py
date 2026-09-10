"""Score every finished per-document pipeline run against the merged manifest.

The corpus run puts each PDF in its own run directory so a failure is isolated.
score_run.py takes one run directory, so this scores each and concatenates.

Only rows whose `group` equals that run's own document are kept. Given the whole
138-group manifest, score_run reports a row of zeros for every document it did
not see; concatenating those would multiply the corpus by 138 and every extra row
would be an invisible miss.
"""
import csv
import json
import os
import subprocess
import sys
from pathlib import Path

RUNS = Path("/root/cmage-work/allpdfs/runs")
BENCH = Path("/root/C-MAGE/benchmarks")
MANIFEST = BENCH / "ground_truth/pdf_manifest_all.json"
OUT = BENCH / "scored/pdfs_all"
PY_ = "/root/C-MAGE/.venv-ms/bin/python"


def main() -> int:
    truth = json.load(open(MANIFEST))["groups"]
    OUT.mkdir(parents=True, exist_ok=True)
    rows, done, skipped, nogt = [], 0, 0, 0
    for d in sorted(RUNS.iterdir()):
        stem = d.name
        run = next(iter(sorted(d.glob("out/run_*"))), None)
        if run is None or not list(run.glob("03_CXMS_Results/Completed_HighConfidence*.xlsx")):
            skipped += 1
            continue
        if stem not in truth:
            nogt += 1
            continue
        tmp = Path(f"/tmp/score_{stem}")
        r = subprocess.run([PY_, str(BENCH / "score_run.py"), "--run-dir", str(run),
                            "--manifest", str(MANIFEST), "--out", str(tmp),
                            "--label", stem],
                           capture_output=True, text=True)
        f = tmp / "structures.csv"
        if r.returncode != 0 or not f.exists():
            print(f"  FAILED {stem}: {r.stderr.strip()[-160:]}", file=sys.stderr)
            continue
        mine = [x for x in csv.DictReader(open(f)) if x["group"] == stem]
        rows.extend(mine)
        done += 1
        if done % 20 == 0:
            print(f"  scored {done} documents, {len(rows)} structures", flush=True)

    if not rows:
        print("no rows -- nothing finished yet", file=sys.stderr)
        return 1
    with open(OUT / "structures.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"DONE documents={done} structures={len(rows)} "
          f"unfinished={skipped} no_ground_truth={nogt}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
