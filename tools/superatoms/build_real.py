#!/usr/bin/env python3
"""Sample the real superatom set from real/candidates.json, write neutral-named, metadata-free
copies (rs_NNNN.png) and the run set + section metadata into the published run dir."""
import json, random, collections, sys
from pathlib import Path
from PIL import Image
sys.path.insert(0, "/root/cmage-work/superatoms")
from select_real import SAMPLE, SHOW, main as select
from build_set import assert_clean
ROOT = Path("/root/cmage-work/superatoms")
OUT = Path("/root/C-MAGE/benchmarks/published_runs/sonnet55_api_superatoms/real")
IMG = ROOT / "real/images"
SEED = 20261008
LICENCE = {
    "USPTO": "MolScribe USPTO test set: drawings from US patent grants (USPTO public data; US patent drawings are generally free of copyright restrictions). Shown.",
    "CLEF": "CLEF-IP 2012 chemical-structure recognition test set (via MolScribe): drawings cropped from patent documents, distributed for research. Shown, as patent drawings.",
    "UOB": "UOB set (University of Birmingham, via MolScribe): drawings from the Maybridge catalogue, distributed for research; third-party catalogue artwork, so metrics only, no images republished.",
    "acs": "ACS set (via MolScribe): figures cropped from American Chemical Society journal articles, copyright ACS; used for research measurement only, no images republished.",
}


def main():
    cands = select()
    rng = random.Random(SEED)
    picked = []
    for s, n in SAMPLE.items():
        c = sorted([x for x in cands if x["set"] == s], key=lambda x: x["id"])
        rng.shuffle(c)
        multi = [x for x in c if len(x["verified"]) >= 2]
        single = [x for x in c if len(x["verified"]) < 2]
        take = multi[: n // 2]
        take += single[: n - len(take)]
        if len(take) < n:
            take += [x for x in multi[n // 2:]][: n - len(take)]
        picked += take
        print(s, len(c), "candidates,", len(multi), "with >= 2 labels; picked", len(take))
    rng.shuffle(picked)
    IMG.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    out = []
    for i, x in enumerate(picked, 1):
        rid = f"rs_{i:04d}"
        im = Image.open(ROOT / "dl/molscribe_real" / x["file"]).convert("RGB")
        p = IMG / f"{rid}.png"
        im.save(p)
        assert_clean(p)
        out.append({"id": rid, "src": {"acs": "ACS"}.get(x["set"], x["set"]), "orig_id": x["id"].split("/", 1)[1],
                    "orig_file": x["file"], "png": str(p), "truth": x["truth"], "labels": x["verified"],
                    "written": x["written"], "unmapped": x["unmapped"], "heavy": x["heavy"], "show": SHOW[x["set"]]})
    json.dump(out, open(OUT / "set.json", "w"), indent=1)
    json.dump([{"id": o["id"], "png": o["png"], "truth": o["truth"]} for o in out], open(OUT / "run_set.json", "w"), indent=0)
    cl = [json.loads(l) for l in open(ROOT / "real/classify.jsonl")]
    screened = collections.Counter(r["set"] for r in cl)
    sc = sum(r.get("cost") or 0 for r in cl)
    meta = {"screen_cost": f"${sc:.2f} for {len(cl)} images", "licence": LICENCE,
            "screened": dict(screened), "candidates": dict(collections.Counter(c["set"] for c in cands)),
            "picked": dict(collections.Counter(o["src"] for o in out)),
            "method": (f"Published drawings from the MolScribe real-image benchmarks (USPTO, CLEF-2012, UOB, ACS; "
                       f"huggingface.co/yujieq/MolScribe real.zip), truth = the benchmark's own full SMILES. All "
                       f"{len(cl)} images were screened by Haiku 5.5 (one call each, ${sc:.2f}) for text labels standing "
                       f"for two or more atoms; a label counts only if it maps to a known group AND that group is in the "
                       f"truth, and an image with any known label missing from its truth is dropped. Candidates: "
                       + ", ".join(f"{k} {v}" for k, v in sorted(collections.Counter(c['set'] for c in cands).items()))
                       + f". Sampled at random, half with two or more verified labels where available: "
                       + ", ".join(f"{k} {v}" for k, v in sorted(collections.Counter(o['src'] for o in out).items()))
                       + ". Renamed rs_NNNN, re-saved as pixels only. UOB (Maybridge catalogue art) and ACS (journal "
                       "figures) count in the metrics but are not shown; USPTO and CLEF drawings come from patents and "
                       "are shown. Truth SMILES with R groups or dummy atoms are excluded.")}
    json.dump(meta, open(OUT / "sources.json", "w"), indent=1)
    print(len(out), "real images;", meta["screen_cost"])


if __name__ == "__main__":
    main()
