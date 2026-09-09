#!/usr/bin/env python3
"""Merge several single-document C-MAGE runs into ONE benchmark run directory.

Why this exists. A corpus of N documents is cheapest to run as N separate
pipeline invocations -- each one can fail, be retried, or be re-run at a
different setting without touching the others. But the benchmark tab treats one
run directory as one measurement, and a corpus split across N run directories
appears as N unrelated results with N headline numbers. Worse, the honest way to
score N single-document runs is against N single-document manifests; score each
one against the whole-corpus manifest instead and every denominator silently
becomes the corpus total (34 rather than 5, 9, 1 ...), which is how a 9/34 recall
turns into 9/374.

Merging first removes the choice: one run directory, one manifest, and the
per-document attribution the tab already does by file-name stem.

    ../.venv-ms/bin/python benchmarks/merge_runs.py \
        --runs-root /tmp/cmage-pdfs/runs --dest benchmarks/published_runs/x/run

  --runs-root DIR   every <DIR>/*/out/run_* is a source run (newest per document)
  --run-dir DIR     an explicit source run; repeatable; combines with --runs-root
  --dest DIR        the merged run directory to create (must not exist unless --force)

RDKit is not needed; openpyxl is, so run this with the stage-3 interpreter
(`.venv-ms/bin/python`) exactly as for the scoring scripts.

What it does with each part of a run:

  01_VH_Figures/            copied; names already carry the document stem
  02_DIS_Segments/*.png     copied; likewise
  03_CXMS_Results/
      {high,low}confidence_images/   copied
      Completed_*Confidence_CMAGE.xlsx
                            REBUILT, not concatenated as files: one workbook per
                            tier holding every source row, with the segment path
                            rewritten relative to the run directory so the
                            merged run does not pin the machine it was made on.
      per_document/         the original workbooks, one pair per document, so
                            nothing is lost by the rebuild -- they still carry the
                            embedded depiction images a fresh openpyxl workbook
                            cannot reproduce. Only their absolute segment paths are
                            rewritten, at the zip level, for the same reason.
      merge.json            what came from where, and how many rows each gave.

Two guards, because both failures look exactly like success:

  * A name collision between two source runs is fatal, never a silent
    overwrite. Documents are supposed to have distinct stems; if two do not,
    the merged run would quietly hold one document's crop under another's name.
  * The merged workbooks are re-opened and re-parsed after writing, and the row
    count must equal the number of rows read from the sources. An empty
    spreadsheet parses fine and scores 0 structures, which reads like a real
    null result rather than a broken merge.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

import openpyxl

sys.path.insert(0, str(Path(__file__).resolve().parent))
from copy_run import rewrite_xlsx  # noqa: E402  -- zip-level path rewrite that keeps embedded images

# Column layout written by cxmolscribe-wd/folder_ms.py, 0-based. Exact
# positions, never a header substring search: 'Image From Predicted CXSMILES'
# also contains 'smiles' and sits at a LOWER index than the real column.
COL_INDEX, COL_PATH, COL_SMILES, COL_CONF, COL_CLASS = 0, 1, 5, 8, 9
TIERS = {"high": "Completed_HighConfidence_CMAGE.xlsx", "low": "Completed_LowConfidence_CMAGE.xlsx"}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}
COPY_DIRS = ("01_VH_Figures", "02_DIS_Segments",
             "03_CXMS_Results/highconfidence_images", "03_CXMS_Results/lowconfidence_images")


def newest_runs(root: Path) -> list[Path]:
    """<root>/<document>/out/run_* -> the newest run per document, sorted by name."""
    out = []
    for doc in sorted(p for p in root.iterdir() if p.is_dir()):
        runs = sorted(p for p in doc.glob("out/run_*") if (p / "03_CXMS_Results").is_dir())
        if runs:
            out.append(runs[-1])
    return out


def read_rows(xlsx: Path) -> list[list]:
    """Every data row of a Completed_*Confidence workbook, as plain cell lists."""
    wb = openpyxl.load_workbook(xlsx, read_only=True, data_only=True)
    try:
        rows = []
        for row in wb.active.iter_rows(min_row=2, values_only=True):
            cells = list(row) + [None] * 12
            if not cells[COL_PATH]:
                continue
            rows.append(cells)
        return rows
    finally:
        wb.close()


def header_of(xlsx: Path) -> list:
    wb = openpyxl.load_workbook(xlsx, read_only=True, data_only=True)
    try:
        return list(next(wb.active.iter_rows(min_row=1, max_row=1, values_only=True)))
    finally:
        wb.close()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--runs-root", type=Path)
    ap.add_argument("--run-dir", type=Path, action="append", default=[])
    ap.add_argument("--dest", type=Path, required=True)
    ap.add_argument("--force", action="store_true", help="replace --dest if it exists")
    args = ap.parse_args()

    sources = list(args.run_dir)
    if args.runs_root:
        sources += newest_runs(args.runs_root)
    sources = [p.resolve() for p in sources]
    if not sources:
        sys.exit("no source runs: pass --runs-root and/or --run-dir")
    for p in sources:
        if not (p / "03_CXMS_Results").is_dir():
            sys.exit(f"not a run directory (no 03_CXMS_Results): {p}")

    dest = args.dest
    if dest.exists():
        if not args.force:
            sys.exit(f"{dest} already exists; pass --force to replace it")
        shutil.rmtree(dest)
    for sub in COPY_DIRS:
        (dest / sub).mkdir(parents=True, exist_ok=True)
    (dest / "03_CXMS_Results" / "per_document").mkdir(parents=True, exist_ok=True)

    owner: dict[str, Path] = {}          # relative path -> the run that supplied it
    copied = {sub: 0 for sub in COPY_DIRS}
    rows_by_tier: dict[str, list[list]] = {t: [] for t in TIERS}
    header: dict[str, list] = {}
    report = []

    for src in sources:
        stem = src.parent.parent.name     # <document>/out/run_* -> <document>
        # The run's own name, not its path: an absolute source path would pin the
        # merged artifact to the machine it was assembled on.
        entry = {"run": src.name, "document": stem, "rows": {}, "images": {}}
        for sub in COPY_DIRS:
            d = src / sub
            if not d.is_dir():
                continue
            n = 0
            for f in sorted(d.iterdir()):
                if not f.is_file() or f.suffix.lower() not in IMAGE_SUFFIXES:
                    continue
                rel = f"{sub}/{f.name}"
                if rel in owner:
                    sys.exit(f"name collision on {rel}: {owner[rel]} and {src} both supply it. "
                             f"Two documents share a file-name stem; merging would hide one of them.")
                owner[rel] = src
                shutil.copy2(f, dest / sub / f.name)
                n += 1
            copied[sub] += n
            entry["images"][sub] = n
        for tier, name in TIERS.items():
            xlsx = src / "03_CXMS_Results" / name
            if not xlsx.is_file():
                entry["rows"][tier] = 0
                continue
            kept = dest / "03_CXMS_Results" / "per_document" / f"{stem}_{name}"
            shutil.copy2(xlsx, kept)
            # The kept originals still hold the absolute paths of the machine the run
            # happened on. Rewritten at the zip level rather than through openpyxl,
            # because a load/save round-trip drops the embedded depiction images that
            # are the only reason these copies are kept at all.
            rewrite_xlsx(kept, src)
            rows = read_rows(xlsx)
            if tier not in header:
                header[tier] = header_of(xlsx)
            for cells in rows:
                # Absolute paths pin the machine the run happened on. Only the file
                # name is ever trusted downstream, so rewrite to a run-relative one.
                cells[COL_PATH] = f"02_DIS_Segments/{Path(str(cells[COL_PATH])).name}"
                rows_by_tier[tier].append(cells)
            entry["rows"][tier] = len(rows)
        report.append(entry)

    written = {}
    for tier, name in TIERS.items():
        rows = rows_by_tier[tier]
        if not rows:
            written[tier] = 0
            continue
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(header.get(tier) or [None, "File Path", None, None, None, "Predicted CXSMILES",
                                       None, None, "CXSMILES's Confidence Levels", "Confidence Classification"])
        for i, cells in enumerate(rows):
            out = [None] * (max(COL_CLASS, COL_CONF) + 1)
            out[COL_INDEX] = str(i)
            for c in (COL_PATH, COL_SMILES, COL_CONF, COL_CLASS):
                out[c] = cells[c]
            ws.append(out)
        wb.save(dest / "03_CXMS_Results" / name)
        wb.close()
        written[tier] = len(rows)

    # Re-parse what was written. An empty or truncated workbook loads without
    # error and simply scores zero structures, which is indistinguishable from a
    # genuine null result -- so the count is checked, not assumed.
    for tier, name in TIERS.items():
        expect = written[tier]
        got = len(read_rows(dest / "03_CXMS_Results" / name)) if expect else 0
        if got != expect:
            sys.exit(f"merged {name} re-parsed to {got} rows, expected {expect}")
    total = sum(written.values())
    if total == 0:
        sys.exit("merged 0 structure rows from the sources; nothing would be scored")

    (dest / "03_CXMS_Results" / "merge.json").write_text(json.dumps(
        {"sources": len(sources), "rows": written, "documents": report}, indent=1))
    print(f"merged {len(sources)} runs -> {dest}")
    print("  rows: " + ", ".join(f"{t} {written[t]}" for t in TIERS) + f" (total {total})")
    for sub in COPY_DIRS:
        print(f"  {sub}: {copied[sub]} images")
    return 0


if __name__ == "__main__":
    sys.exit(main())
