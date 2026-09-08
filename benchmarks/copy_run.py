#!/usr/bin/env python3
"""Copy a C-MAGE run directory into the benchmark results with relative paths.

The stage-2 and stage-3 spreadsheets record every segment by absolute path, so
a raw run directory pins the machine it was made on. This copies the run and
rewrites those paths to be relative to the run directory (e.g.
`02_DIS_Segments/Image_DIS_VH_File_x_molecule_0.png`), by editing the shared
strings inside the .xlsx zip in place -- openpyxl is not used for the rewrite
because a load/save round-trip can drop the embedded check-images.

Everything else (figures, segments, rendered structures, logs) is copied as is.
Use --no-figures / --no-segments to leave the large image folders out.

  copy_run.py --run-dir /path/to/run_X --dest results/pdf_corpus/run
"""
import argparse
import re
import shutil
import zipfile
from pathlib import Path


def rewrite_xlsx(xlsx, run_root):
    """Replace '<run_root>/' with '' in every shared string and inline string of the workbook."""
    tmp = xlsx.with_suffix(".xlsx.tmp")
    root = str(run_root.resolve()).rstrip("/") + "/"
    count = 0
    with zipfile.ZipFile(xlsx) as zin, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename.startswith("xl/") and item.filename.endswith(".xml"):
                text = data.decode("utf-8")
                new, n = re.subn(re.escape(root), "", text)
                count += n
                data = new.encode("utf-8")
            zout.writestr(item, data)
    tmp.replace(xlsx)
    return count


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run-dir", type=Path, required=True)
    ap.add_argument("--dest", type=Path, required=True)
    ap.add_argument("--no-figures", action="store_true")
    ap.add_argument("--no-segments", action="store_true")
    args = ap.parse_args()

    src = args.run_dir.resolve()
    dest = args.dest
    if dest.exists():
        shutil.rmtree(dest)
    ignore = []
    if args.no_figures:
        ignore.append("01_VH_Figures")
    if args.no_segments:
        ignore.append("02_DIS_Segments")

    def _ignore(d, names):
        return [n for n in names if n in ignore and Path(d) == src]

    shutil.copytree(src, dest, ignore=_ignore)
    if args.no_segments:
        # keep the spreadsheet stage 3 consumed, just not the images
        (dest / "02_DIS_Segments").mkdir(exist_ok=True)
        for x in (src / "02_DIS_Segments").glob("*.xlsx"):
            shutil.copy(x, dest / "02_DIS_Segments" / x.name)
    total = 0
    for xlsx in dest.rglob("*.xlsx"):
        total += rewrite_xlsx(xlsx, src)
    # logs may echo absolute paths too
    for log in (dest / "logs").glob("*.log") if (dest / "logs").exists() else []:
        text = log.read_text(errors="replace")
        log.write_text(text.replace(str(src) + "/", "").replace(str(src), "<run>"))
    print(f"copied {src.name} -> {dest}; rewrote {total} absolute path strings in spreadsheets")


if __name__ == "__main__":
    main()
