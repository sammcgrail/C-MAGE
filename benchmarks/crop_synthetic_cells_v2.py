#!/usr/bin/env python3
"""Cut one clean image per drawn structure, and record how much ink it contains.

TWO JOBS, ONE PASS

1. The NO-SEGMENTATION arm. The corpus knows exactly where every structure sits
   (the manifest records `cell_px`, the drawing box in page pixels), so the crop
   comes from the page render itself instead of from DECIMER. Feed the crops to
   benchmarks/run_stage3_only.sh and the difference between that run and the full
   pipeline is what stage 2 costs, on the same drawings, with one variable moved.

2. The DENOMINATOR for the erasure measurement. Every crop's ink pixel count is
   written to cell_ink.json. Stage-2 segments are produced at PAGE SCALE -- a
   1700 px page gives a 1507 px figure and a 619 px segment of a 700 px cell,
   with no resampling anywhere -- so ink(segment) / ink(clean cell) is a ratio of
   two counts of the same pixels and needs no scale correction. Verified against
   the v1 run before this file was written; if a future stage 2 starts resizing,
   ink_loss_v2.py's bbox check fails loudly rather than silently rescaling.

v1's cropper recomputed the cell rectangle from imported layout constants. That
works while there is one layout. v2 has seven, so the rectangle is read from the
manifest -- the generator writes what it actually drew.

  .venv-ms/bin/python benchmarks/crop_synthetic_cells_v2.py \
      --manifest benchmarks/ground_truth/synthetic_manifest_v2.json \
      --pdfs benchmarks/corpus_synth2 --out /tmp/synth2_cells
"""
import argparse
import json
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

import numpy as np
from PIL import Image

INK = 250          # a pixel darker than this is ink; the page is exact white


def render_page(pdf, page, dpi):
    with tempfile.TemporaryDirectory() as td:
        stem = Path(td) / "p"
        subprocess.run(["pdftoppm", "-r", str(dpi), "-f", str(page), "-l", str(page),
                        "-png", str(pdf), str(stem)], check=True, capture_output=True)
        out = sorted(Path(td).glob("p-*.png"))
        if not out:
            raise SystemExit(f"pdftoppm produced nothing for {pdf} page {page}")
        return Image.open(out[0]).convert("RGB").copy()


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--pdfs", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--ink-json", type=Path, default=None)
    ap.add_argument("--pad", type=int, default=24, help="white margin in px around the ink")
    ap.add_argument("--only-arm", default=None, help="restrict to these arms (comma list)")
    args = ap.parse_args()

    man = json.loads(args.manifest.read_text())
    dpi = man.get("drawn_at", {}).get("page_dpi_units", 200)
    args.out.mkdir(parents=True, exist_ok=True)
    arms = set(args.only_arm.split(",")) if args.only_arm else None

    ink, sizes, n, empty = {}, [], 0, 0
    for g, entry in sorted(man["groups"].items()):
        if arms and entry.get("arm") not in arms:
            continue
        pdf = args.pdfs / entry["source"]
        cache = {}
        for m in entry["molecules"]:
            p = m["page"]
            if p not in cache:
                cache = {p: render_page(pdf, p, dpi)}     # one page held at a time
            page = cache[p]
            x, y, w, h = m["cell_px"]
            cell = page.crop((x, y, x + w, y + h))
            a = np.array(cell.convert("L"))
            nz = np.argwhere(a < INK)
            if nz.size == 0:
                print(f"WARNING no ink in the cell for {g}/{m['name']}", file=sys.stderr)
                empty += 1
                continue
            y0, x0 = nz.min(0)
            y1, x1 = nz.max(0)
            box = (max(0, x0 - args.pad), max(0, y0 - args.pad),
                   min(w, x1 + 1 + args.pad), min(h, y1 + 1 + args.pad))
            crop = cell.crop(box)
            # `_image_<k>` so score_run.group_key maps the file back to its group
            # exactly as it maps a stage-1 figure.
            crop.save(args.out / f"{g}_image_{m['number']}.png")
            ca = np.array(crop.convert("L"))
            ink[f"{g}/{m['number']}"] = {
                "group": g, "number": m["number"], "name": m["name"],
                "stratum": m["stratum"], "render": m["render"], "arm": entry["arm"],
                # ink measured on the CELL, not the padded crop: the pad is white
                # and would otherwise make the denominator depend on --pad
                "ink_px": int((a < INK).sum()),
                "bbox_w": int(x1 - x0 + 1), "bbox_h": int(y1 - y0 + 1),
                "crop_w": crop.size[0], "crop_h": crop.size[1],
                "ink_of_crop": int((ca < INK).sum()),
                "heavy_atoms": m["heavy_atoms"], "per_page": m["per_page"],
                "bond_line_width": m["bond_line_width"],
            }
            sizes.append(crop.size)
            n += 1
        cache.clear()
        print(f"  {g:26s} {len(entry['molecules']):3d}", flush=True)

    out_json = args.ink_json or (args.out.parent / f"{args.out.name}_cell_ink.json")
    Path(out_json).write_text(json.dumps(ink, indent=1))
    ws = [s[0] for s in sizes]
    hs = [s[1] for s in sizes]
    print(f"\n{n} cell crops -> {args.out}   ({empty} cells had no ink)")
    print(f"  width  min {min(ws)} max {max(ws)}   height min {min(hs)} max {max(hs)}")
    print(f"  ink per drawing: min {min(v['ink_px'] for v in ink.values())} "
          f"median {sorted(v['ink_px'] for v in ink.values())[len(ink) // 2]} "
          f"max {max(v['ink_px'] for v in ink.values())}")
    by = Counter(v["render"] for v in ink.values())
    print("  by render condition:", dict(by))
    print(f"  ink denominators -> {out_json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
