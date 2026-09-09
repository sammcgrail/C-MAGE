#!/usr/bin/env python3
"""Cut one clean image per drawn structure, straight from the PDF page.

This is the no-segmentation arm of the ablation. The synthetic corpus knows
exactly where every structure sits on its page (the manifest records page and
grid cell), so the crops can be made from the page render itself rather than by
asking DECIMER. Feed them to benchmarks/run_stage3_only.sh and the difference
between that run and the full pipeline is what stage 2 costs -- measured, on the
same 100 drawings, with one variable changed.

That difference is not hypothetical. On the full run, ibuprofen's benzene came
back as a cyclohexadiene; the stage-1 FIGURE has all three double bonds and the
stage-2 SEGMENT is missing the bottom one, because the instance mask clipped an
interior line. Stage 3 read the damaged image correctly. A whole-pipeline score
charges that to the recogniser, which is the wrong place to look for the fix.

Pages are rendered at 200 dpi because that is what stage 1 uses -- pdf2image's
default, see MERMaid/src/visualheist/methods_visualheist.py:_pdf_to_image.

  .venv-ms/bin/python benchmarks/crop_synthetic_cells.py \
      --manifest ground_truth/synthetic_manifest.json \
      --pdfs benchmarks/corpus_synth --out /tmp/synth_cells
"""
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

# Must match make_synthetic_corpus.py. Imported rather than copied so a layout
# change cannot silently desynchronise the two.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_synthetic_corpus import (BOX_H, BOX_W, CELL_H, CELL_W,  # noqa: E402
                                   DPI, GRID_TOP, MARGIN)


def render_page(pdf, page, dpi=DPI):
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
    ap.add_argument("--pad", type=int, default=24, help="white margin in px around the ink")
    args = ap.parse_args()

    man = json.loads(args.manifest.read_text())
    args.out.mkdir(parents=True, exist_ok=True)
    pages, n, sizes = {}, 0, []
    for g, entry in man["groups"].items():
        pdf = args.pdfs / entry["source"]
        for m in entry["molecules"]:
            key = (g, m["page"])
            if key not in pages:
                pages[key] = render_page(pdf, m["page"])
            page = pages[key]
            row, col = m["cell"]
            x = MARGIN + col * CELL_W + (CELL_W - BOX_W) // 2
            y = GRID_TOP + row * CELL_H
            cell = page.crop((x, y, x + BOX_W, y + BOX_H))
            a = np.array(cell.convert("L"))
            nz = np.argwhere(a < 250)
            if nz.size == 0:
                print(f"WARNING no ink in the cell for {m['name']}", file=sys.stderr)
                continue
            y0, x0 = nz.min(0)
            y1, x1 = nz.max(0)
            box = (max(0, x0 - args.pad), max(0, y0 - args.pad),
                   min(BOX_W, x1 + 1 + args.pad), min(BOX_H, y1 + 1 + args.pad))
            crop = cell.crop(box)
            # `_image_<k>` so score_run.group_key maps the file back to its group
            # exactly as it maps a stage-1 figure.
            crop.save(args.out / f"{g}_image_{m['number']}.png")
            sizes.append(crop.size)
            n += 1
    ws = [s[0] for s in sizes]
    hs = [s[1] for s in sizes]
    print(f"{n} cell crops -> {args.out}")
    print(f"  width  min {min(ws)} max {max(ws)}   height min {min(hs)} max {max(hs)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
