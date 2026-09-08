#!/usr/bin/env python3
"""Adopt an existing C-MAGE run into the web app's gallery.

Use it to seed the gallery with runs made before the web app existed, or made
on another machine. Nothing is re-run: the images and spreadsheets are copied
into a job directory in the standard layout and indexed.

    webapp/tools/import_run.py --results DIR [--segments DIR] [--figures DIR] \
        --filename test_page.pdf [--pages 1] [--label "..."] [--note "..."]

  --results   stage 3 output: Completed_*Confidence_CMAGE.xlsx + *confidence_images/
              (a whole run directory with 01_/02_/03_ subfolders is also accepted)
  --segments  stage 2 crops (Image_DIS_VH_File_*.png); default: taken from the
              paths recorded in the spreadsheets, if they still exist
  --figures   stage 1 figures; optional but lets the UI show the source figure
  --note      a caveat shown above the results (e.g. which structures are known
              to be wrong and why)
  --private   keep it out of the gallery listing
  --sample    make it the one run the "try the sample" button reuses

An imported run is LISTED by default, which is the opposite of an upload: it is
a curated exhibit the operator chose to publish, not a document a stranger
handed over. Uploads are unlisted unless the uploader asks otherwise.

Point CMAGE_DATA at the same data directory the server uses; the server picks
the new run up on its next start (or immediately, if you POST nothing: the
index is rebuilt from the job directories at start-up).
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import config, results  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--results", required=True, type=Path)
    ap.add_argument("--segments", type=Path)
    ap.add_argument("--figures", type=Path)
    ap.add_argument("--filename", required=True, help="display name of the document that was run")
    ap.add_argument("--kind", choices=["pdf", "image"], default="pdf")
    ap.add_argument("--pages", type=int, default=1)
    ap.add_argument("--label", default="")
    ap.add_argument("--note", default="")
    ap.add_argument("--finished", type=float, default=None, help="unix time; default: now")
    ap.add_argument("--private", action="store_true",
                    help="do not list it in the gallery (imports are listed by default: "
                         "an imported run is a curated exhibit, not somebody's upload)")
    ap.add_argument("--sample", action="store_true",
                    help="this is the canonical demo run that 'Try the one-page sample' reuses")
    args = ap.parse_args()

    src = args.results.resolve()
    res_dir = src / "03_CXMS_Results" if (src / "03_CXMS_Results").is_dir() else src
    if not (res_dir / results.HC_XLSX).is_file() and not (res_dir / results.LC_XLSX).is_file():
        sys.exit(f"no Completed_*Confidence_CMAGE.xlsx under {res_dir}")
    seg_dir = args.segments or (src / "02_DIS_Segments" if (src / "02_DIS_Segments").is_dir() else None)
    fig_dir = args.figures or (src / "01_VH_Figures" if (src / "01_VH_Figures").is_dir() else None)

    job_id = secrets.token_urlsafe(9)
    job_dir = config.JOBS_DIR / job_id
    run_dir = job_dir / "out" / "run_import"
    for sub in results.SUBDIRS.values():
        (run_dir / sub).mkdir(parents=True, exist_ok=True)

    # Stage 3 output: the two workbooks and the rendered images.
    for name in (results.HC_XLSX, results.LC_XLSX):
        if (res_dir / name).is_file():
            shutil.copy2(res_dir / name, run_dir / "03_CXMS_Results" / name)
    for tier in ("high", "low"):
        d = res_dir / f"{tier}confidence_images"
        if d.is_dir():
            for f in d.iterdir():
                if f.is_file():
                    shutil.copy2(f, run_dir / results.SUBDIRS[tier] / f.name)

    # Stage 2 crops: from --segments, else from the paths inside the workbooks.
    copied = 0
    if seg_dir and seg_dir.is_dir():
        for f in seg_dir.iterdir():
            if f.is_file() and f.suffix.lower() in results.IMAGE_SUFFIXES:
                shutil.copy2(f, run_dir / results.SUBDIRS["segment"] / f.name)
                copied += 1
    else:
        for name in (results.HC_XLSX, results.LC_XLSX):
            p = res_dir / name
            if p.is_file():
                for row in results._read_sheet(p, "x"):
                    sp = Path(row["segment_path"])
                    if sp.is_file():
                        shutil.copy2(sp, run_dir / results.SUBDIRS["segment"] / sp.name)
                        copied += 1
    if fig_dir and fig_dir.is_dir():
        for f in fig_dir.iterdir():
            if f.is_file() and f.suffix.lower() in results.IMAGE_SUFFIXES:
                shutil.copy2(f, run_dir / results.SUBDIRS["figure"] / f.name)

    parsed = results.parse_run(run_dir)
    finished = args.finished or time.time()
    record = {
        "id": job_id, "kind": args.kind, "filename": args.filename, "size": 0, "pages": args.pages,
        "created": finished, "origin": "import", "status": "done", "stage": 3, "stage_started": None,
        "started": finished, "finished": finished, "error": None, "client": "", "label": args.label,
        "run_dir": str(run_dir.relative_to(job_dir)), "results": parsed, "note": args.note,
        "public": not args.private, "sample": args.sample, "token": secrets.token_urlsafe(16),
    }
    tmp = job_dir / "job.json.tmp"
    tmp.write_text(json.dumps(record, indent=1, sort_keys=True))
    os.replace(tmp, job_dir / "job.json")
    c = parsed["counts"]
    print(f"imported {job_id}: {c['structures']} structures ({c['high']} high, {c['low']} low), "
          f"{copied} crops, {c['figures']} figures, "
          f"{'listed in the gallery' if record['public'] else 'unlisted'}"
          f"{', canonical sample' if args.sample else ''} -> {job_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
