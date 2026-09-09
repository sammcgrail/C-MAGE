#!/usr/bin/env python3
"""Measure what stage 2 removes before stage 3 ever sees it -- and, optionally, put it back.

WHAT THIS MEASURES
------------------
Stage 2 (DECIMER segmentation) turns each stage-1 figure into zero or more
segment images and writes the segment paths into the spreadsheet stage 3 reads.
A figure that produces NO segments is simply absent from that spreadsheet: stage
3 never runs on it and nothing downstream records it existed. Across 139 figures
in 20 real-document runs that is 37 figures (26.6%), and the ink stage 3 sees
falls to 30.1% of the ink present in the figures.

THE FINDING THAT SHOULD STOP YOU ACTING ON THOSE NUMBERS
--------------------------------------------------------
Those are counts of INK, not of chemistry, and on real documents most of the
missing ink is not chemistry. All 26 zero-segment figures in the ground-truthed
subset were inspected by eye. Three carried a drawn structure -- two of them
Markush generics with R groups, which have no reference SMILES by construction.
The other 23 were body text, data tables, journal headers, licence boilerplate,
a bar chart, culture-medium recipes and an IR spectrum. Stage 1 (VisualHeist)
extracts them as "figures"; stage 2 is RIGHT to return no segments for them.

So the zero-segment count is mostly evidence of stage 1 over-extracting, not of
stage 2 destroying structures, and any retention figure computed over all
stage-1 figures has a denominator full of text. Fix the denominator before
quoting it: classify figures as structure-bearing first.

Feeding those figures to stage 3 anyway was measured, on the 11 ground-truthed
documents, against a matched baseline (identical segments in both arms, only the
26 whole-figure rows added):

    recall   9/34 strict, 18/34 graded   -- IDENTICAL in both arms
    precision      14/242 = 5.79%  ->  14/268 = 5.22%
    the 26 recovered figures produced   22 wrong + 4 invalid, all low-confidence,
                                        median closest-Tanimoto 0.000

It recovers ink and recovers nothing. That is why every rewrite in this tool is
now opt-in and the default is report-only. The whole-figure fallback DOES work
for an image upload -- one already-cropped structure, shipped and verified -- and
does not transfer to a document figure, which is a multi-panel page region.

WHAT IT DOES
------------
By default: measures and reports, changes nothing.

  1. Groups segment rows by source figure with an ANCHORED match on
     `Image_DIS_VH_File_<figure>_molecule_<n>.png`. A bare prefix match is wrong
     and has already produced retentions above 1.0 on this project (`image_1`
     claiming the segments of `image_10..19`).
  2. Measures ink retention per figure (segment ink / figure ink) into a JSON
     report, whether or not anything is rewritten -- because a figure stage 1
     never produced and a figure stage 2 erased are otherwise indistinguishable
     downstream, both contributing nothing.
  3. --enable-zerosegment-fallback appends the whole figure for figures with no
     segments. OFF: measured above to add noise, not signal.
  4. --enable-lowretention-fallback replaces a SINGLE low-retention segment with
     its whole figure. OFF: on a real figure some lost ink is a caption the
     segmenter correctly dropped, so a threshold over raw retention would fire on
     well-behaved figures. Waiting on the real-document ink-location measurement.

INK
---
"Ink" is pixels darker than --ink-threshold (default 200, matching
benchmarks/ink_retention_real_documents.json). benchmarks/ink_loss_v2.py uses
250. The report records which value was used and, with --both-thresholds, the
retention at both, so a reader can see how much the choice moves the answer
(measured: 0.232 vs 0.260 on the same figure -- small).
Do not reuse upstream's 0.72 binarisation here: that constant
(complete_structure.py:282) is the cause of the loss, and measuring the loss
with the ruler that caused it hides it.

USAGE
-----
    retention_guard.py --results-excel RUN/02_DIS_Segments/DIS_CMAGE_results.xlsx \
                       --figures RUN/01_VH_Figures \
                       --report RUN/logs/retention.json

Writes nothing unless a fallback flag is given. Exit status is 0 even when it
changes nothing; non-zero means the guard itself failed and the caller should
not proceed as though stage 2 output were intact.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import defaultdict

import numpy as np
import pandas as pd
from PIL import Image

COLUMN = "DIS Result File Paths"

# Anchored. The figure stem is greedy up to the LAST "_molecule_<digits>.png",
# because figure stems themselves contain underscores and digits
# (e.g. ntp_roc_pahs_image_2).
SEGMENT_RE = re.compile(r"^Image_DIS_VH_File_(?P<fig>.+)_molecule_(?P<n>\d+)\.png$")

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}


def ink(path: str, threshold: int) -> int:
    """Count of pixels darker than `threshold` in the 8-bit grey image."""
    with Image.open(path) as im:
        a = np.asarray(im.convert("L"))
    return int((a < threshold).sum())


def figure_stem(name: str) -> str:
    return os.path.splitext(os.path.basename(name))[0]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--results-excel", required=True,
                    help="stage 2's spreadsheet -- the file stage 3 reads")
    ap.add_argument("--figures", required=True,
                    help="the stage-1 figure directory stage 2 was given")
    ap.add_argument("--out-excel", default=None,
                    help="write here instead of rewriting --results-excel in place")
    ap.add_argument("--report", default=None, help="write the per-figure JSON report here")
    ap.add_argument("--ink-threshold", type=int, default=200,
                    help="pixels darker than this are ink (default 200)")
    ap.add_argument("--both-thresholds", action="store_true",
                    help="also report retention at 250, to show threshold sensitivity")
    ap.add_argument("--enable-zerosegment-fallback", action="store_true",
                    help="feed the whole figure to stage 3 for figures stage 2 left "
                         "with no segments (OFF by default -- measured to add noise, "
                         "see the module docstring)")
    ap.add_argument("--enable-lowretention-fallback", action="store_true",
                    help="also replace a SINGLE low-retention segment with its whole "
                         "figure (off by default -- see the module docstring)")
    ap.add_argument("--retention-threshold", type=float, default=0.90,
                    help="with --enable-lowretention-fallback, the retention below "
                         "which a single-segment figure falls back (default 0.90)")
    ap.add_argument("--dry-run", action="store_true",
                    help="report only; never write the spreadsheet")
    args = ap.parse_args()

    if not os.path.isdir(args.figures):
        print(f"retention_guard: figure directory does not exist: {args.figures}",
              file=sys.stderr)
        return 2
    if not os.path.isfile(args.results_excel):
        print(f"retention_guard: no stage-2 spreadsheet at {args.results_excel}",
              file=sys.stderr)
        return 2

    figures = sorted(f for f in os.listdir(args.figures)
                     if os.path.splitext(f)[1].lower() in IMAGE_EXTS
                     and os.path.isfile(os.path.join(args.figures, f)))
    if not figures:
        # A zero-figure directory would make every check below pass vacuously.
        print(f"retention_guard: no figures in {args.figures} -- refusing to report "
              f"'nothing lost' on an empty input", file=sys.stderr)
        return 2

    df = pd.read_excel(args.results_excel)
    if COLUMN not in df.columns:
        print(f"retention_guard: {args.results_excel} has no {COLUMN!r} column "
              f"(has {list(df.columns)})", file=sys.stderr)
        return 2

    rows = [str(p) for p in df[COLUMN].tolist() if isinstance(p, str) and p.strip()]

    # --- group segments by figure, anchored ------------------------------------
    by_fig: dict[str, list[str]] = defaultdict(list)
    unmatched: list[str] = []
    for p in rows:
        m = SEGMENT_RE.match(os.path.basename(p))
        if m:
            by_fig[m.group("fig")].append(p)
        else:
            unmatched.append(p)

    matched = sum(len(v) for v in by_fig.values())
    # R1: the partition must account for every row. Printed, not assumed.
    print(f"rows in spreadsheet: {len(rows)}  matched to a figure: {matched}  "
          f"unmatched: {len(unmatched)}")
    if matched + len(unmatched) != len(rows):
        print("retention_guard: row partition does not sum -- refusing to continue",
              file=sys.stderr)
        return 3
    if unmatched:
        print(f"  (unmatched rows are passed through untouched, e.g. "
              f"{os.path.basename(unmatched[0])})")

    stems = {figure_stem(f): f for f in figures}
    orphan_figs = sorted(set(by_fig) - set(stems))
    if orphan_figs:
        # Segments whose figure is not in --figures: usually the wrong directory
        # was passed. Loud, because every retention below would silently be None.
        print(f"retention_guard: {len(orphan_figs)} figure(s) referenced by segments "
              f"are not in {args.figures}: {orphan_figs[:3]}", file=sys.stderr)
        return 3

    # --- measure ---------------------------------------------------------------
    per_figure = {}
    zero_segment = []
    low_single = []
    for stem, fname in stems.items():
        fpath = os.path.join(args.figures, fname)
        try:
            fig_ink = ink(fpath, args.ink_threshold)
        except Exception as e:  # a figure we cannot read is not a figure with no ink
            print(f"retention_guard: cannot read figure {fname}: {e}", file=sys.stderr)
            return 3
        segs = by_fig.get(stem, [])
        seg_ink = 0
        missing = []
        for s in segs:
            if os.path.isfile(s):
                seg_ink += ink(s, args.ink_threshold)
            else:
                missing.append(s)
        entry = {
            "figure": fname,
            "figure_ink": fig_ink,
            "segments": len(segs),
            "segment_ink": seg_ink,
            "retained": (seg_ink / fig_ink) if fig_ink else None,
            "segments_missing_on_disk": len(missing),
        }
        if args.both_thresholds:
            f250 = ink(fpath, 250)
            s250 = sum(ink(s, 250) for s in segs if os.path.isfile(s))
            entry["retained_at_250"] = (s250 / f250) if f250 else None
        per_figure[stem] = entry

        if not segs:
            zero_segment.append(stem)
        elif (len(segs) == 1 and entry["retained"] is not None
              and entry["retained"] < args.retention_threshold):
            low_single.append(stem)

    # --- rewrite ---------------------------------------------------------------
    added, replaced = [], []
    new_rows = list(rows)

    if args.enable_zerosegment_fallback:
        for stem in zero_segment:
            new_rows.append(os.path.abspath(os.path.join(args.figures, stems[stem])))
            added.append(stem)

    if args.enable_lowretention_fallback:
        for stem in low_single:
            seg = by_fig[stem][0]
            whole = os.path.abspath(os.path.join(args.figures, stems[stem]))
            new_rows = [whole if r == seg else r for r in new_rows]
            replaced.append(stem)

    retentions = [e["retained"] for e in per_figure.values() if e["retained"] is not None]
    report = {
        "generated": __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc).isoformat(timespec="seconds"),
        "results_excel": os.path.abspath(args.results_excel),
        "figures_dir": os.path.abspath(args.figures),
        "ink_threshold": args.ink_threshold,
        "figures": len(stems),
        "segment_rows_in": len(rows),
        "segment_rows_matched": matched,
        "segment_rows_unmatched": len(unmatched),
        "figures_with_zero_segments": len(zero_segment),
        "zerosegment_fallback_enabled": bool(args.enable_zerosegment_fallback),
        "zero_segment_figures": sorted(zero_segment),
        "mean_retained": (float(np.mean(retentions)) if retentions else None),
        "median_retained": (float(np.median(retentions)) if retentions else None),
        "rows_added_whole_figure": sorted(added),
        "lowretention_fallback_enabled": bool(args.enable_lowretention_fallback),
        "retention_threshold": args.retention_threshold,
        "single_segment_below_threshold": sorted(low_single),
        "rows_replaced_with_whole_figure": sorted(replaced),
        "rows_out": len(new_rows),
        "per_figure": per_figure,
    }

    if args.report:
        os.makedirs(os.path.dirname(os.path.abspath(args.report)), exist_ok=True)
        with open(args.report, "w") as fh:
            json.dump(report, fh, indent=2)
        print(f"report: {args.report}")

    med = (f"{report['median_retained']:.3f}" if retentions else "n/a")
    print(f"figures: {len(stems)}  zero-segment: {len(zero_segment)}  "
          f"median retention: {med}")
    if added:
        print(f"added {len(added)} whole-figure row(s) for figures stage 2 erased: "
              f"{added[:5]}{'...' if len(added) > 5 else ''}")
    if replaced:
        print(f"replaced {len(replaced)} single low-retention segment(s) with the "
              f"whole figure: {replaced[:5]}{'...' if len(replaced) > 5 else ''}")
    if not added and not replaced:
        if zero_segment or low_single:
            # Never say "nothing to do" when there IS something and the flag is
            # simply off -- that reads exactly like a clean run.
            print(f"no rewrite: {len(zero_segment)} zero-segment and {len(low_single)} "
                  f"low-retention single-segment figure(s) found, but the "
                  f"corresponding fallback flag is off (report-only)")
        else:
            print("no rewrite needed -- every figure produced at least one segment")

    if args.dry_run:
        print("dry run: spreadsheet not written")
        return 0

    if added or replaced:
        out = args.out_excel or args.results_excel
        pd.DataFrame(new_rows, columns=[COLUMN]).to_excel(out)
        # Read back and assert, because "wrote the file" and "the file says what
        # I meant" are different claims.
        check = pd.read_excel(out)
        got = [str(p) for p in check[COLUMN].tolist() if isinstance(p, str) and p.strip()]
        if len(got) != len(new_rows):
            print(f"retention_guard: wrote {len(new_rows)} rows but read back "
                  f"{len(got)} -- not proceeding", file=sys.stderr)
            return 3
        print(f"wrote {out}: {len(rows)} -> {len(got)} rows")
    elif args.out_excel:
        pd.DataFrame(new_rows, columns=[COLUMN]).to_excel(args.out_excel)
        print(f"wrote {args.out_excel}: {len(new_rows)} rows (unchanged)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
