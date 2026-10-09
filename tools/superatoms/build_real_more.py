#!/usr/bin/env python3
"""Expansion of the real superatom set (2026-10-09): EVERY remaining qualifying USPTO and CLEF image
(the showable sources; UOB and ACS are not used), screened exactly as before (select_real.py: Haiku
labels mapped to a known group that is present in the truth, no unverifiable known label, truth without
R/dummy atoms), plus the parsed re-screens of replies that had not parsed. Images already in the set
(same source file) are skipped. Neutral names continue rs_0341..., pixels-only copies, appended to
real/set.json and real/run_set.json in one write each."""
import json, random, collections, sys
from pathlib import Path
from PIL import Image
sys.path.insert(0, "/root/cmage-work/superatoms")
from select_real import main as select
from build_set import assert_clean
ROOT = Path("/root/cmage-work/superatoms")
OUT = Path("/root/C-MAGE/benchmarks/published_runs/sonnet55_api_superatoms/real")
IMG = ROOT / "real/images"
SEED = 20261009
SETS = ("USPTO", "CLEF")


def main():
    old = json.load(open(OUT / "set.json"))
    used = {x["orig_file"] for x in old}
    n0 = max(int(x["id"][3:]) for x in old)
    assert n0 == 340, n0
    cands = select()
    new = sorted([c for c in cands if c["set"] in SETS and c["file"] not in used], key=lambda x: x["id"])
    random.Random(SEED).shuffle(new)
    out = []
    for i, x in enumerate(new, n0 + 1):
        rid = f"rs_{i:04d}"
        p = IMG / f"{rid}.png"
        assert not p.exists(), p
        Image.open(ROOT / "dl/molscribe_real" / x["file"]).convert("RGB").save(p)
        assert_clean(p)
        out.append({"id": rid, "src": x["set"], "orig_id": x["id"].split("/", 1)[1], "orig_file": x["file"],
                    "png": str(p), "truth": x["truth"], "labels": x["verified"], "written": x["written"],
                    "unmapped": x["unmapped"], "heavy": x["heavy"], "show": True, "batch": "2026-10-09"})
    json.dump(old + out, open(OUT / "set.json", "w"), indent=1)
    rs = json.load(open(OUT / "run_set.json"))
    assert [x["id"] for x in rs] == [x["id"] for x in old]
    json.dump(rs + [{"id": o["id"], "png": o["png"], "truth": o["truth"]} for o in out],
              open(OUT / "run_set.json", "w"), indent=0)
    json.dump(out, open(ROOT / "more/real_new.json", "w"), indent=1)
    print(len(out), "new real images", dict(collections.Counter(o["src"] for o in out)),
          "with >= 2 labels:", sum(len(o["labels"]) >= 2 for o in out))


if __name__ == "__main__":
    main()
