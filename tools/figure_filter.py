#!/usr/bin/env python3
"""Decide whether a stage-1 figure contains a chemical drawing at all.

WHY. VisualHeist extracts page regions, and 44 of 139 real figures (32%) it hands
to stage 2 contain no chemistry: body text, data tables, IR and NMR spectra,
journal boilerplate, a bar chart. Stage 2 mostly filters them -- 75% produce no
segment -- but 11 of them DO produce segments, 15 in total, and every structure
stage 3 emits from those is a false positive by construction. A properties table
gave four. "medicaments." was read as `[*][Mn] |$PmAm;$|`.

WHAT IT KEYS ON. Text is the thing being separated out, and text has a signature
that a drawn structure does not: its ink lies in narrow horizontal bands of very
regular height, repeated down the page. A structure's ink is sparse, spread in
two dimensions, and its connected components vary wildly in size.

  rows_with_ink       fraction of pixel rows carrying any ink
  band_regularity     how uniform the heights of the ink bands are
  comp_height_cv      coefficient of variation of connected-component heights
  fill                ink pixels / bounding-box area
  aspect              width / height of the figure

Everything is computed from the figure alone. No model, no weights, ~15 ms.

CALIBRATION. Thresholds were fitted against 139 real figures classified by eye,
twice, independently, with the two passes agreeing exactly
(`benchmarks/figure_labels_real_documents.tsv`). Run this file directly to
re-evaluate against that file and print the confusion matrix -- do not change a
threshold without re-running it.

    tools/figure_filter.py --labels benchmarks/figure_labels_real_documents.tsv \\
                           --figures-json <work>/figclass/figures.json

BIAS. It is deliberately biased AGAINST dropping. A figure wrongly dropped is a
molecule that can never be recovered; a text block wrongly kept costs one junk
prediction that the confidence score already files low. So `looks_like_text`
returns True only on a clear case.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np
from PIL import Image

INK = 200          # matches benchmarks/ink_retention_real_documents.json


def features(path: str) -> dict:
    with Image.open(path) as im:
        a = np.asarray(im.convert("L"))
    mask = a < INK
    h, w = mask.shape
    total = int(mask.sum())
    if total == 0:
        return {"empty": True, "rows_with_ink": 0.0, "band_regularity": 0.0,
                "band_count": 0, "fill": 0.0, "aspect": w / max(h, 1), "ink": 0}

    rows = mask.any(axis=1)
    # Contiguous runs of inked rows are the "bands". Text lines are bands of very
    # similar height; a structure is one or two tall irregular ones.
    bands, run = [], 0
    for r in rows:
        if r:
            run += 1
        elif run:
            bands.append(run); run = 0
    if run:
        bands.append(run)
    bands = [b for b in bands if b >= 2]      # single-pixel rules are not text lines
    tall_ratio = 0.0
    if len(bands) >= 3:
        arr = np.array(bands, dtype=float)
        # Low CV == very uniform band heights == typeset lines.
        regularity = 1.0 - min(1.0, float(arr.std() / max(arr.mean(), 1e-6)))
        # A drawn structure makes ONE band far taller than the typeset lines around
        # it. Without this, a Markush formula with three lines of German legal text
        # under it counts as text and the molecule is thrown away.
        tall_ratio = float(arr.max() / max(np.median(arr), 1e-6))
    else:
        regularity = 0.0

    ys, xs = np.nonzero(mask)
    bbox = (ys.max() - ys.min() + 1) * (xs.max() - xs.min() + 1)
    return {
        "empty": False,
        "rows_with_ink": float(rows.mean()),
        "band_regularity": regularity,
        "band_count": len(bands),
        "tall_ratio": tall_ratio,
        "fill": total / max(bbox, 1),
        "aspect": w / max(h, 1),
        "ink": total,
    }


def looks_like_text(f: dict) -> bool:
    """True only for a clear text/table block. Biased against dropping."""
    if f["empty"]:
        return True
    # A thin horizontal strip -- a running head, a table-of-contents line. Checked
    # before the tall-band rule below, because a one-line strip has no "rest" for a
    # band to be taller than.
    if f["aspect"] > 8 and f["band_count"] <= 3:
        return True
    # One band far taller than the rest is a drawing sitting among text lines.
    # Keep it whatever else the figure looks like.
    if f.get("tall_ratio", 0.0) >= 2.5:
        return False
    # Many bands of very uniform height: typeset lines or table rows.
    if f["band_count"] >= 6 and f["band_regularity"] >= 0.62:
        return True
    return False


def evaluate(labels_path: str, figures_json: str) -> int:
    labels = {}
    for line in open(labels_path):
        parts = line.rstrip("\n").split("\t")
        if len(parts) == 3:
            labels[int(parts[0])] = parts[2]
    figs = json.load(open(figures_json))
    if len(figs) != len(labels):
        print(f"figure list ({len(figs)}) and label file ({len(labels)}) disagree",
              file=sys.stderr)
        return 2
    STRUCT = {"structure", "structure_in_diagram", "structure_generic"}
    tp = fp = tn = fn = 0
    wrong_drops = []
    for i, fig in enumerate(figs, start=1):
        truth_is_text = labels[i] not in STRUCT
        if not os.path.isfile(fig["path"]):
            print(f"missing {fig['path']}", file=sys.stderr)
            return 2
        pred_is_text = looks_like_text(features(fig["path"]))
        if pred_is_text and truth_is_text:
            tp += 1
        elif pred_is_text and not truth_is_text:
            fp += 1; wrong_drops.append((i, fig["stem"], labels[i]))
        elif not pred_is_text and truth_is_text:
            fn += 1
        else:
            tn += 1
    n = tp + fp + tn + fn
    print(f"figures: {n}   text by eye: {tp + fn}   structure by eye: {tn + fp}")
    print(f"  dropped and IS text        {tp}")
    print(f"  dropped but HAS A STRUCTURE {fp}   <- the only expensive error")
    print(f"  kept and is text            {fn}")
    print(f"  kept and has a structure    {tn}")
    if tp + fp:
        print(f"  precision of a drop: {tp}/{tp+fp} = {tp/(tp+fp):.1%}")
    print(f"  recall over text:    {tp}/{tp+fn} = {tp/max(tp+fn,1):.1%}")
    for i, stem, lab in wrong_drops:
        print(f"    WRONGLY DROPPED  {i} {stem} ({lab})")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--labels")
    ap.add_argument("--figures-json")
    ap.add_argument("figures", nargs="*", help="figure files to classify")
    args = ap.parse_args()
    if args.labels and args.figures_json:
        return evaluate(args.labels, args.figures_json)
    if not args.figures:
        ap.error("give figure files, or --labels with --figures-json")
    for p in args.figures:
        f = features(p)
        print(f"{'TEXT ' if looks_like_text(f) else 'KEEP '} {os.path.basename(p)}  "
              f"bands={f['band_count']} reg={f['band_regularity']:.2f} "
              f"rows={f['rows_with_ink']:.2f} aspect={f['aspect']:.1f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
