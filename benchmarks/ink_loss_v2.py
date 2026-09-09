#!/usr/bin/env python3
"""Measure how much INK stage 2 removes, and whether that predicts a wrong answer.

THE CLAIM BEING TESTED
----------------------
On the v1 run ibuprofen's benzene came back as a cyclohexadiene. The stage-1
FIGURE has all three double bonds; the stage-2 SEGMENT is missing the bottom one,
because DECIMER's instance mask clipped an interior line. Stage 3 read the
damaged picture correctly. A whole-pipeline score charges that to the recogniser.
If ink loss predicts a wrong skeleton, the fix belongs in stage 2 (a bbox pad, a
mask dilation) and not in the recogniser -- and that is an actionable finding
rather than an anecdote.

WHY THE RATIO NEEDS NO SCALE CORRECTION
---------------------------------------
Stage 1 renders the page at pdf2image's default 200 dpi and crops; stage 2 masks
and crops again. Nothing resamples: a 1700 px page gives a 1507 px figure and a
619 px segment of a 700 px cell. So ink(segment) / ink(clean cell) counts the
same pixels twice. `--max-scale-drift` fails the run loudly if a future stage 2
starts resizing, rather than quietly reporting a ratio of two different rulers.

MATCHING SEGMENTS TO DRAWINGS WITHOUT ASKING THE RECOGNISER
-----------------------------------------------------------
DECIMER does not write segment coordinates to disk (they exist in
decimer_segmentation.sort_segments_bboxes and die there), so a segment has to be
matched to the drawing it came from. Using score_cx's assignment would be
circular: it assigns by CHEMISTRY, and the question here is whether damaged ink
causes wrong chemistry -- a segment so damaged it was read as another molecule
would be filed under that other molecule and its damage would vanish from the
measurement.

So the match is made on PIXELS: a coarse ink profile of the segment against the
ink profile of each clean cell crop in the same group, plus bbox aspect. The two
matchers are then compared on the segments score_cx grades Y or YS, where the
chemistry assignment is not in doubt; that agreement rate is printed and is the
evidence that the pixel matcher works.

  .venv-ms/bin/python benchmarks/ink_loss_v2.py \
      --run-root /tmp/cmage-synth2/full --cells /tmp/cmage-synth2/cells \
      --cell-ink /tmp/cmage-synth2/cell_ink.json \
      --manifest benchmarks/ground_truth/synthetic_manifest_v2.json \
      --scored benchmarks/scored/synthetic_v2_full --out /tmp/cmage-synth2/ink
"""
import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from PIL import Image

INK = 250
PROF = 24                 # profile grid; coarse on purpose -- damage must not
                          # break the match, only the ink count
DIS_PREFIX = "Image_DIS_VH_File_"


def descriptor(path_or_img):
    """(ink pixels, bbox w, h, PROFxPROF normalised ink profile) or None."""
    img = (Image.open(path_or_img) if not isinstance(path_or_img, Image.Image)
           else path_or_img)
    a = np.array(img.convert("L"))
    mask = a < INK
    nz = np.argwhere(mask)
    if nz.size == 0:
        return None
    y0, x0 = nz.min(0)
    y1, x1 = nz.max(0)
    sub = mask[y0:y1 + 1, x0:x1 + 1].astype(np.float32)
    h, w = sub.shape
    ys = (np.arange(PROF + 1) * h // PROF)
    xs = (np.arange(PROF + 1) * w // PROF)
    prof = np.zeros((PROF, PROF), np.float32)
    for i in range(PROF):
        for j in range(PROF):
            block = sub[ys[i]:max(ys[i] + 1, ys[i + 1]), xs[j]:max(xs[j] + 1, xs[j + 1])]
            prof[i, j] = block.mean() if block.size else 0.0
    n = np.linalg.norm(prof)
    return int(mask.sum()), int(w), int(h), (prof / n if n else prof)


def sim(a, b):
    """Profile cosine, discounted by disagreement in bbox aspect and size."""
    c = float((a[3] * b[3]).sum())
    ar = (a[1] / max(1, a[2])) / max(1e-6, b[1] / max(1, b[2]))
    ar = min(ar, 1 / ar)
    sz = min(a[1] * a[2], b[1] * b[2]) / max(1, max(a[1] * a[2], b[1] * b[2]))
    return c * (0.5 + 0.5 * ar) * (0.5 + 0.5 * sz)


def group_of(name, known):
    stem = Path(name).stem
    if stem.startswith(DIS_PREFIX):
        stem = stem[len(DIS_PREFIX):]
    stem = stem.rsplit("_molecule_", 1)[0]
    for k in sorted(known, key=len, reverse=True):
        if stem == k or stem.startswith(k + "_image_"):
            return k
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run-root", type=Path, required=True,
                    help="directory holding the batch run dirs of the FULL arm")
    ap.add_argument("--cells", type=Path, required=True)
    ap.add_argument("--cell-ink", type=Path, required=True)
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--scored", type=Path, default=None,
                    help="score_cx output dir for the full arm (for the outcome join)")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--max-scale-drift", type=float, default=0.08,
                    help="fail if segments are systematically a different size "
                         "from the page pixels they claim to be crops of")
    args = ap.parse_args()

    man = json.loads(args.manifest.read_text())
    cell_ink = json.loads(args.cell_ink.read_text())
    groups = man["groups"]

    # ---- reference descriptors, from the clean crops
    refs = defaultdict(list)
    for g, e in groups.items():
        for m in e["molecules"]:
            p = args.cells / f"{g}_image_{m['number']}.png"
            if not p.exists():
                continue
            d = descriptor(p)
            if d:
                refs[g].append((m, d))
    print(f"{sum(len(v) for v in refs.values())} reference crops in {len(refs)} groups",
          flush=True)

    # ---- which groups did stage 1 actually SEE?
    # Without this the denominator is every drawing in the manifest, and a PDF
    # that has not been run yet -- or one that failed -- contributes retention
    # 0.0, which is indistinguishable from "stage 2 erased the whole structure".
    # That is the failure mode where a null result and a missing result look the
    # same, so the two are separated here rather than averaged together.
    figs = sorted(args.run_root.glob("*/out/run_*/01_VH_Figures/*.png"))
    groups_run, figs_per_group = set(), Counter()
    for f in figs:
        g = group_of(f.name, groups.keys())
        if g:
            groups_run.add(g)
            figs_per_group[g] += 1
    pages_expected = {g: groups[g]["pages"] for g in groups_run}
    short = {g: (figs_per_group[g], pages_expected[g]) for g in groups_run
             if figs_per_group[g] < pages_expected[g]}
    print(f"{len(groups_run)} of {len(groups)} groups have stage-1 figures; "
          f"{len(short)} produced fewer figures than pages", flush=True)

    # ---- segments
    segs = sorted(args.run_root.glob("*/out/run_*/02_DIS_Segments/*.png"))
    print(f"{len(segs)} stage-2 segments under {args.run_root}", flush=True)
    if not segs:
        raise SystemExit("no segments found -- has the full arm produced output yet?")

    by_group = defaultdict(list)
    for s in segs:
        g = group_of(s.name, refs.keys())
        if g:
            by_group[g].append(s)

    rows, unmatched = [], 0
    for g, paths in sorted(by_group.items()):
        cands = refs.get(g, [])
        if not cands:
            unmatched += len(paths)
            continue
        scored = []
        for p in paths:
            d = descriptor(p)
            if d is None:
                continue
            for i, (m, rd) in enumerate(cands):
                scored.append((sim(d, rd), p, i, d))
        scored.sort(key=lambda x: -x[0])
        taken = set()
        for score, p, i, d in scored:
            if p in taken:
                continue
            taken.add(p)
            m, rd = cands[i]
            key = f"{g}/{m['number']}"
            ci = cell_ink.get(key, {})
            rows.append({
                "group": g, "number": m["number"], "name": m["name"],
                "stratum": m["stratum"], "render": m["render"],
                "per_page": m["per_page"], "bond_line_width": m["bond_line_width"],
                "heavy_atoms": m["heavy_atoms"], "size_bucket": m["size_bucket"],
                "arm": groups[g]["arm"],
                "segment": p.name, "match_score": round(score, 4),
                "ink_cell": ci.get("ink_px"), "ink_seg": d[0],
                "cell_bbox_w": ci.get("bbox_w"), "cell_bbox_h": ci.get("bbox_h"),
                "seg_bbox_w": d[1], "seg_bbox_h": d[2],
            })
        unmatched += len(paths) - len(taken)
    if not rows:
        raise SystemExit("no segment matched any drawing -- check --cells and --manifest")

    # ---- scale guard: a segment must be a crop of page pixels, not a resize.
    # Compare only the segments that kept most of their ink; a badly clipped
    # segment legitimately has a smaller bbox and would poison the median.
    good = [r for r in rows if r["ink_cell"] and r["ink_seg"] / r["ink_cell"] > 0.9]
    gd = [r["seg_bbox_w"] / r["cell_bbox_w"] for r in good if r["cell_bbox_w"]]
    med = float(np.median(gd)) if gd else 1.0
    print(f"scale check: median segment/cell bbox width on well-preserved segments "
          f"= {med:.4f} over n={len(gd)}")
    if abs(med - 1.0) > args.max_scale_drift:
        raise SystemExit(f"segments are not at page scale (median {med:.3f}); "
                         f"the ink ratio would be comparing two different rulers")

    # ---- per drawing
    per = defaultdict(lambda: {"ink_seg": 0, "n_seg": 0, "best": 0.0})
    meta = {}
    for r in rows:
        k = (r["group"], r["number"])
        per[k]["ink_seg"] += r["ink_seg"]
        per[k]["n_seg"] += 1
        per[k]["best"] = max(per[k]["best"], r["ink_seg"])
        meta[k] = r
    drawings = []
    for g, e in groups.items():
        if g not in groups_run:
            continue                     # never reached stage 1: not a measurement
        for m in e["molecules"]:
            k = (g, m["number"])
            ci = cell_ink.get(f"{g}/{m['number']}", {})
            if not ci.get("ink_px"):
                continue
            p = per.get(k, {"ink_seg": 0, "n_seg": 0, "best": 0.0})
            drawings.append({
                "group": g, "number": m["number"], "name": m["name"],
                "stratum": m["stratum"], "render": m["render"], "arm": e["arm"],
                "per_page": m["per_page"], "bond_line_width": m["bond_line_width"],
                "heavy_atoms": m["heavy_atoms"], "size_bucket": m["size_bucket"],
                "ink_cell": ci["ink_px"], "ink_seg": p["ink_seg"],
                "ink_best_segment": p["best"], "n_segments": p["n_seg"],
                "retention": round(p["ink_seg"] / ci["ink_px"], 4),
                "retention_best": round(p["best"] / ci["ink_px"], 4),
                # absolute loss as well as fractional: 200 px off a 30-atom
                # structure is one bond, and one bond is the whole mechanism.
                # A fraction alone hides that a big molecule can lose a bond and
                # still read as 0.99 retained.
                "ink_lost_px": ci["ink_px"] - p["ink_seg"],
            })

    # ---- join the outcome from score_cx, if it has been run
    agree = miss = 0
    if args.scored and (args.scored / "cx_molecules.csv").exists():
        out = {}
        with open(args.scored / "cx_molecules.csv") as f:
            for r in csv.DictReader(f):
                out[(r["group"], r["name"])] = r
        for d in drawings:
            r = out.get((d["group"], d["name"]))
            d["skeleton_ok"] = (r["skeleton_recovered"] == "True") if r else None
            d["letter"] = r["best_letter"] if r else None
        # matcher validation: on structures the scorer graded Y/YS the chemistry
        # assignment is not in doubt, so the pixel matcher should agree
        with open(args.scored / "cx_structures.csv") as f:
            for r in csv.DictReader(f):
                if r["letter"] not in ("Y", "YS"):
                    continue
                mrow = next((x for x in rows if x["segment"] == r["file_name"]), None)
                if mrow is None:
                    continue
                if mrow["name"] == r["assigned"]:
                    agree += 1
                else:
                    miss += 1

    args.out.mkdir(parents=True, exist_ok=True)
    with open(args.out / "ink_segments.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    with open(args.out / "ink_drawings.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(drawings[0].keys()))
        w.writeheader()
        w.writerows(drawings)

    # ---- report
    def stats(xs):
        if not len(xs):
            return {"n": 0}
        a = np.array(xs, float)
        return dict(n=len(a), mean=round(float(a.mean()), 4),
                    median=round(float(np.median(a)), 4),
                    p10=round(float(np.percentile(a, 10)), 4),
                    lost_gt_2pct=int((a < 0.98).sum()),
                    lost_gt_10pct=int((a < 0.90).sum()),
                    none=int((a == 0).sum()),
                    # a segment can also hold MORE ink than the drawing: the mask
                    # reached into a caption or a neighbour. That is a different
                    # failure from erasure and is counted apart from it.
                    gained_gt_2pct=int((a > 1.02).sum()))
    summary = {"segments": len(rows), "segments_unmatched_to_a_group": unmatched,
               "drawings": len(drawings), "scale_median_bbox_ratio": round(med, 4),
               "groups_in_manifest": len(groups), "groups_reaching_stage1": len(groups_run),
               "groups_with_fewer_figures_than_pages": {k: v for k, v in sorted(short.items())},
               "drawings_seen_but_never_segmented": sum(1 for d in drawings
                                                        if d["n_segments"] == 0),
               "matcher_agrees_with_scorer_on_YYS": agree,
               "matcher_disagrees_with_scorer_on_YYS": miss,
               "overall": stats([d["retention"] for d in drawings])}
    for key in ("render", "stratum", "size_bucket", "arm"):
        summary[f"by_{key}"] = {k: stats([d["retention"] for d in drawings if d[key] == k])
                                for k in sorted({d[key] for d in drawings})}
    have = [d for d in drawings if d.get("skeleton_ok") is not None]
    if have:
        ok = [d["retention"] for d in have if d["skeleton_ok"]]
        no = [d["retention"] for d in have if not d["skeleton_ok"]]
        x = np.array([d["retention"] for d in have], float)
        y = np.array([1.0 if d["skeleton_ok"] else 0.0 for d in have])
        r = float(np.corrcoef(x, y)[0, 1]) if x.std() and y.std() else float("nan")
        # Bins are dense at the TOP because that is where the data is and where
        # the mechanism lives: a single benzene double bond is ~1-2% of a
        # structure's ink, so the ibuprofen failure is a retention of ~0.98, not
        # of 0.5. Coarse bins would put every interesting case in one bucket.
        bins = [(0, .9), (.9, .95), (.95, .98), (.98, .99), (.99, .995),
                (.995, .999), (.999, 1.01)]
        lost_ok = [d["ink_lost_px"] for d in have if d["skeleton_ok"]]
        lost_no = [d["ink_lost_px"] for d in have if not d["skeleton_ok"]]
        summary["outcome"] = {
            "n": len(have),
            "ink_lost_px_when_correct": (round(float(np.median(lost_ok)), 1)
                                         if lost_ok else None),
            "ink_lost_px_when_wrong": (round(float(np.median(lost_no)), 1)
                                       if lost_no else None),
            "retention_when_skeleton_correct": stats(ok) if ok else None,
            "retention_when_skeleton_wrong": stats(no) if no else None,
            "point_biserial_r": round(r, 4),
            "by_retention_bin": {f"{a}-{b}": {
                "n": int(((x >= a) & (x < b)).sum()),
                "skeleton_correct": int(y[(x >= a) & (x < b)].sum()),
                "pct": (round(100 * float(y[(x >= a) & (x < b)].mean()), 1)
                        if ((x >= a) & (x < b)).sum() else None)} for a, b in bins},
        }
    (args.out / "ink_summary.json").write_text(json.dumps(summary, indent=1))
    print(json.dumps({k: v for k, v in summary.items()
                      if k in ("segments", "drawings", "overall", "outcome",
                               "matcher_agrees_with_scorer_on_YYS",
                               "matcher_disagrees_with_scorer_on_YYS")}, indent=1))
    print("by render:", json.dumps(summary["by_render"], indent=1))
    print(f"-> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
