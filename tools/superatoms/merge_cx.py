#!/usr/bin/env python3
"""Merge a CXMolScribe stage-3 run on the expansion images (cx2/run_*) into the published pair
RUN/cxmolscribe/Completed_{High,Low}Confidence_CMAGE.xlsx (build_superatoms.cx_preds reads only that
pair, one row per image). Rows are appended per confidence class; the merged files are written TEXT
ONLY (pandas: the stage-3 thumbnails embedded in the original workbooks are not carried; the first
run's image-bearing workbooks stay in git history and in cmage-work/superatoms/cx/). Refuses
duplicates and any id not in a set.json."""
import glob, json, sys
from pathlib import Path
import pandas as pd
RUN = Path("/root/C-MAGE/benchmarks/published_runs/sonnet55_api_superatoms")
CX = RUN / "cxmolscribe"
src = sorted(glob.glob(sys.argv[1] if len(sys.argv) > 1 else "/root/cmage-work/superatoms/cx2/run_*"))[-1]
ids = {x["id"] for s in ("synth", "real") for x in json.load(open(RUN / s / "set.json"))}
seen = set()
for f in ("High", "Low"):
    old = pd.read_excel(CX / f"Completed_{f}Confidence_CMAGE.xlsx")
    new = pd.read_excel(Path(src) / "03_CXMS_Results" / f"Completed_{f}Confidence_CMAGE.xlsx")
    for d in (old, new):
        for p in d["File Path"]:
            k = Path(p).stem
            assert k in ids, k
            assert k not in seen, f"{k} twice"
            seen.add(k)
    m = pd.concat([old, new.reindex(columns=old.columns)], ignore_index=True)
    m["Unnamed: 0"] = range(len(m))
    m.drop(columns=["Unnamed: 0"]).to_excel(CX / f"Completed_{f}Confidence_CMAGE.xlsx")
    print(f, len(old), "+", len(new), "=", len(m))
(CX / "RUN.txt").write_text("run_20261008-235344\n" + Path(src).name + "  (2026-10-09 expansion, merged text-only)\n")
print("ids with a CX row:", len(seen))
