"""Read a finished C-MAGE run directory into plain records.

A run directory is what run_pipeline.py writes:

    <run>/01_VH_Figures/<pdf>_image_<n>.png                      stage 1
    <run>/02_DIS_Segments/Image_DIS_VH_File_<figure>_molecule_<m>.png   stage 2
    <run>/03_CXMS_Results/Completed_HighConfidence_CMAGE.xlsx    stage 3
    <run>/03_CXMS_Results/Completed_LowConfidence_CMAGE.xlsx
    <run>/03_CXMS_Results/{high,low}confidence_images/<figure>_molecule_<m>.png

The spreadsheets are the source of truth for SMILES and confidence (columns as
written by cxmolscribe-wd/folder_ms.py: B = segment path, F = predicted
CXSMILES, I = confidence). Images are matched back by file name, never by row
position, because folder_ms.py skips a row when RDKit cannot draw a SMILES.
"""
from __future__ import annotations

import re
from pathlib import Path

import openpyxl

DIS_PREFIX = "Image_DIS_VH_File_"
HC_XLSX = "Completed_HighConfidence_CMAGE.xlsx"
LC_XLSX = "Completed_LowConfidence_CMAGE.xlsx"
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}
INVALID = "<invalid>"

_MOL_RE = re.compile(r"^(?P<figure>.+)_molecule_(?P<n>\d+)$")
_FIG_RE = re.compile(r"^(?P<source>.+)_image_(?P<n>\d+)$")

SUBDIRS = {
    "figure": "01_VH_Figures",
    "segment": "02_DIS_Segments",
    "high": "03_CXMS_Results/highconfidence_images",
    "low": "03_CXMS_Results/lowconfidence_images",
}


def find_run_dir(root: Path) -> Path | None:
    """Accept either a run directory or the --out root that contains run_* dirs."""
    root = Path(root)
    if (root / "03_CXMS_Results").is_dir() or (root / "01_VH_Figures").is_dir():
        return root
    runs = sorted(p for p in root.glob("run_*") if p.is_dir())
    return runs[-1] if runs else None


def _images(directory: Path) -> list[str]:
    if not directory.is_dir():
        return []
    return sorted(p.name for p in directory.iterdir()
                  if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES and not p.name.startswith("."))


def natural_key(name: str):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", name)]


def progress(run_dir: Path | None) -> dict:
    """Live counts while a run is in flight, derived from what is on disk."""
    if run_dir is None:
        return {"figures": 0, "segments": 0, "read": 0}
    return {
        "figures": len(_images(run_dir / SUBDIRS["figure"])),
        "segments": len(_images(run_dir / SUBDIRS["segment"])),
        "read": len(_images(run_dir / SUBDIRS["high"])) + len(_images(run_dir / SUBDIRS["low"])),
    }


def split_names(segment_name: str) -> tuple[str, str, int | None, str]:
    """'Image_DIS_VH_File_doc_image_3_molecule_1.png' ->
    ('doc_image_3_molecule_1', 'doc_image_3', 1, 'doc')."""
    stem = Path(segment_name).stem
    base = stem[len(DIS_PREFIX):] if stem.startswith(DIS_PREFIX) else stem
    m = _MOL_RE.match(base)
    figure = m.group("figure") if m else base
    mol = int(m.group("n")) if m else None
    f = _FIG_RE.match(figure)
    source = f.group("source") if f else figure
    return base, figure, mol, source


def _read_sheet(path: Path, tier: str) -> list[dict]:
    rows = []
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        ws = wb.active
        for row in ws.iter_rows(min_row=2, values_only=True):
            cells = list(row) + [None] * 11
            seg = cells[1]
            if not seg:
                continue
            smiles = cells[5]
            conf = cells[8]
            try:
                conf = float(conf) if conf is not None else None
            except (TypeError, ValueError):
                conf = None
            rows.append({"tier": tier, "segment_path": str(seg),
                         "smiles": "" if smiles is None else str(smiles), "confidence": conf})
    finally:
        wb.close()
    return rows


def parse_run(run_dir: Path) -> dict:
    """Everything the UI needs about a completed run, with image *names* only.

    Paths inside the spreadsheets are absolute paths from wherever the run
    happened; only the file name is trusted, and it is resolved against this
    run directory.
    """
    run_dir = Path(run_dir)
    res = run_dir / "03_CXMS_Results"
    figures = _images(run_dir / SUBDIRS["figure"])
    segments = _images(run_dir / SUBDIRS["segment"])
    renders = {"high": set(_images(run_dir / SUBDIRS["high"])),
               "low": set(_images(run_dir / SUBDIRS["low"]))}

    structures = []
    seen = set()
    for tier, xlsx in (("high", HC_XLSX), ("low", LC_XLSX)):
        path = res / xlsx
        if not path.is_file():
            continue
        for row in _read_sheet(path, tier):
            seg_name = Path(row["segment_path"]).name
            if seg_name in seen:
                continue
            seen.add(seg_name)
            base, figure, mol, source = split_names(seg_name)
            render = f"{base}.png"
            fig_img = next((f for f in figures if Path(f).stem == figure), None)
            structures.append({
                "tier": tier,
                "smiles": row["smiles"],
                "confidence": row["confidence"],
                "valid": bool(row["smiles"]) and row["smiles"] != INVALID,
                "source": source,
                "figure": figure,
                "molecule": mol,
                "segment_image": seg_name if seg_name in segments else None,
                "rendered_image": render if render in renders[tier] else None,
                "figure_image": fig_img,
            })

    # Segments the spreadsheet never mentions (folder_ms.py hit an exception
    # before writing the row) still deserve a card, marked as unread.
    for seg_name in segments:
        if seg_name in seen:
            continue
        base, figure, mol, source = split_names(seg_name)
        structures.append({
            "tier": "low", "smiles": "", "confidence": None, "valid": False,
            "source": source, "figure": figure, "molecule": mol,
            "segment_image": seg_name, "rendered_image": None,
            "figure_image": next((f for f in figures if Path(f).stem == figure), None),
        })

    structures.sort(key=lambda s: (natural_key(s["figure"]), s["molecule"] if s["molecule"] is not None else -1))

    # EXPAND ABBREVIATIONS for every uploaded result, not just for benchmark runs.
    #
    # CXMolScribe emits CXSMILES on purpose: a drawing that says `OMe` becomes a
    # dummy atom whose label lives in the `|$OMe;$|` extension block, because
    # C-MAGE's vendored MolScribe deliberately declines to guess an expansion. That is more
    # information, not less -- but it means the string a user copies out contains a
    # bare `*` that no toolkit can resolve, and `Chem.MolToSmiles()` silently drops
    # the label entirely. Uploads previously got no expansion at all: only the
    # benchmark path ever called canonicalize().
    #
    # So attach all three forms here. Never a guess: an abbreviation outside
    # CXMolScribe's own vocabulary lands in `unexpanded` and the user is told -- split
    # into `markush` and `missing`, because "R1 stands for a set of groups" and "OTBS
    # is missing from the vocabulary" are different facts and the UI says which.
    try:
        from . import chem
        recs = chem.canonicalize([s["smiles"] for s in structures])
        for st, rec in zip(structures, recs):
            st["plain_smiles"] = rec.get("canonical")
            st["cxsmiles"] = rec.get("cxsmiles") or st["smiles"]
            st["expanded"] = rec.get("expanded")
            st["abbreviations"] = rec.get("abbreviations") or []
            st["unexpanded"] = rec.get("unexpanded") or []
            st["markush"] = rec.get("markush") or []
            st["missing"] = rec.get("missing") or []
            st["failed"] = rec.get("failed") or []
            st["fragments"] = rec.get("fragments") or 0
    except Exception:                                 # noqa: BLE001
        # RDKit unavailable must degrade to "no expansion", never to no results.
        for st in structures:
            st.setdefault("cxsmiles", st["smiles"])
            st.setdefault("expanded", None)
            st.setdefault("abbreviations", [])
            st.setdefault("markush", [])
            st.setdefault("missing", [])

    high = sum(1 for s in structures if s["tier"] == "high")
    return {
        "structures": structures,
        "figures": figures,
        "counts": {"figures": len(figures), "segments": len(segments),
                   "structures": len(structures), "high": high, "low": len(structures) - high,
                   "invalid": sum(1 for s in structures if not s["valid"])},
    }


def image_path(run_dir: Path, kind: str, name: str) -> Path | None:
    """Resolve an image name inside a run dir. Returns None unless it is a real
    file in the expected sub-directory (no traversal, no symlink escapes)."""
    if kind not in SUBDIRS and kind != "render":
        return None
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._ -]{0,200}\.(png|jpg|jpeg|tif|tiff|bmp)", name, re.IGNORECASE):
        return None
    if ".." in name:
        return None
    kinds = ("high", "low") if kind == "render" else (kind,)
    for k in kinds:
        base = (run_dir / SUBDIRS[k]).resolve()
        candidate = (base / name).resolve()
        if candidate.parent == base and candidate.is_file():
            return candidate
    return None
