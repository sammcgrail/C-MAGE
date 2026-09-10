"""Fail if the published payloads disagree with each other or with the scored data.

The corpus grows batch by batch, and several published numbers are derived from
its size: the images hero, the Sonnet progress bar, the "N structures" counts.
Each is correct when written and silently wrong the moment a batch lands without
a rebuild -- and a stale number looks exactly like a fresh one.

So this asserts agreement rather than trusting a rebuild happened:

  1. images.json's row count equals the distinct scored compounds on disk.
  2. sonnet.json's `corpus` equals images.json's row count.
  3. sonnet.json's read count equals the lines in results.jsonl.
  4. No payload is older than the newest scored CSV feeding it.

Run after every build. Exit 1 on any disagreement.
"""
import csv
import glob
import json
import os
import sys
from pathlib import Path

ROOT = Path("/root/C-MAGE/benchmarks")
WALL = ROOT / "wall"


def main() -> int:
    bad = []
    imgs = json.load(open(WALL / "images.json"))
    n_img = len(imgs["rows"])

    keys = set()
    newest = 0.0
    for p in glob.glob(str(ROOT / "scored/*corpus_rdkit_1500/structures.csv")):
        newest = max(newest, os.path.getmtime(p))
        for r in csv.DictReader(open(p)):
            keys.add(r["file_name"].rsplit(".", 1)[0])
    if n_img != len(keys):
        bad.append(f"images.json has {n_img} rows but {len(keys)} distinct compounds are scored "
                   f"on disk — rebuild with tools/build_wall.py all")
    if imgs["stats"]["n"] != n_img:
        bad.append(f"images.json stats.n={imgs['stats']['n']} disagrees with its own "
                   f"{n_img} rows")

    sp = WALL / "sonnet.json"
    if sp.exists():
        son = json.load(open(sp))
        c = son.get("compare") or {}
        if c.get("corpus") != n_img:
            bad.append(f"sonnet.json says the corpus is {c.get('corpus')} but images.json has "
                       f"{n_img} — the two tabs would show different totals")
        res = Path("/root/cmage-work/sonnet/results.jsonl")
        if res.exists():
            n_read = sum(1 for l in open(res) if l.strip())
            if c.get("n") != n_read:
                bad.append(f"sonnet.json reports {c.get('n')} images read but results.jsonl "
                           f"holds {n_read}")
        if newest and os.path.getmtime(sp) < newest:
            bad.append("sonnet.json is older than the newest scored CSV — stale")
    if newest and os.path.getmtime(WALL / "images.json") < newest:
        bad.append("images.json is older than the newest scored CSV — stale")

    for b in bad:
        print("  FAIL " + b)
    if not bad:
        print(f"  PASS corpus {n_img} consistent across images.json"
              + (", sonnet.json" if sp.exists() else "") + " and the scored CSVs")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
