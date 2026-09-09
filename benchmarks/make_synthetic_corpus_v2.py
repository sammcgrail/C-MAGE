#!/usr/bin/env python3
"""Draw the v2 synthetic corpus from a plan. Ground truth known by construction.

THE MECHANISM (unchanged from v1, and the reason any of this is trustworthy)

    cond = rdAbbreviations.CondenseMolAbbreviations(mol, abbrevs, maxCoverage=0.8)
    cx   = Chem.MolToCXSmiles(cond)     # '*c1ccc(*)cc1 |$CF3;;;;;OMe;$|'
    draw(cond)                          # the picture and the string are ONE object

The drawing and the reference come from the same molecule, so they cannot
disagree. Everything v2 adds is about drawing that same molecule MORE THAN ONCE
under conditions that differ in exactly one variable.

WHAT V2 ADDS
------------
* render conditions (synthetic_compounds_v2.RENDER): grid density, bond line
  width and inter-structure spacing, so the stage-2 erasure effect has a
  gradient instead of a single point.
* a vocabulary arm: the same condensed molecule drawn with the label CXMolScribe
  knows and with the chemically identical MIRRORED label it does not. Both sides
  are drawn with PLAIN display labels, so `CO2Et` vs `EtO2C` differs in
  character order and in nothing else -- not in subscript typography.
* every cell's exact pixel rectangle is written into the manifest. v1's cropper
  recomputed the geometry from imported constants, which works only while there
  is one geometry; with seven layouts the rectangle has to be data.

UPPER BOUND, STATED HERE BECAUSE IT MUST TRAVEL WITH THE NUMBERS
----------------------------------------------------------------
RDKit line art on exactly white, one drawing convention, no scanner noise, no
overlapping labels, no hand-drawn bonds. Every figure this corpus produces is an
UPPER BOUND on the pipeline in anger, and `basic` is a control that should sit
near ceiling rather than a result.

  .venv-ms/bin/python benchmarks/make_synthetic_corpus_v2.py \
      --plan benchmarks/synth_v2_build/synthetic_plan_v2.json \
      --out-pdfs benchmarks/corpus_synth2 \
      --out-manifest benchmarks/ground_truth/synthetic_manifest_v2.json
"""
import argparse
import datetime as dt
import json
import math
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

from rdkit import Chem, RDLogger
from rdkit.Chem import AllChem, rdAbbreviations, rdMolDescriptors
from rdkit.Chem.Draw import rdMolDraw2D

sys.path.insert(0, str(Path(__file__).resolve().parent))
from synthetic_compounds_v2 import (DPI, FIXED_BOND_LENGTH, LAYOUTS,  # noqa: E402
                                    MIRRORS, PAGE_H, PAGE_W, RENDER,
                                    SIZE_BUCKETS, STEREO_BUCKETS, ABBREV_BUCKETS)
from select_synthetic_v2 import bucket_of, fused_max                  # noqa: E402

RDLogger.DisableLog("rdApp.*")
GRID_TOP = 170
TITLE_Y = 108
CAPTION_DROP = 44           # baseline below the drawing box, when captions are on
LABEL_PROPS = ("atomLabel", "_displayLabel", "_displayLabelW", "dummyLabel")

try:
    from molscribe.constants import ABBREVIATIONS as MS_ABBREV
except ImportError:                                                   # pragma: no cover
    MS_ABBREV = {}


# ------------------------------------------------------------------ geometry
def cells_for(layout):
    """Layout name -> [(x, y, w, h)] in page pixels, reading order."""
    L = LAYOUTS[layout]
    cw, ch = L["box_w"] + L["gut_x"], L["box_h"] + L["gut_y"]
    gw, gh = L["cols"] * cw - L["gut_x"], L["rows"] * ch - L["gut_y"]
    x0, y0 = (PAGE_W - gw) // 2, GRID_TOP
    if y0 + gh > PAGE_H - 100:
        raise SystemExit(f"layout {layout} does not fit the page: {gh} tall from {y0}")
    return [(x0 + c * cw, y0 + r * ch, L["box_w"], L["box_h"])
            for r in range(L["rows"]) for c in range(L["cols"])]


# ----------------------------------------------------------------- chemistry
def abbrevs():
    ab = rdAbbreviations.GetDefaultAbbreviations()
    for a in rdAbbreviations.ParseAbbreviations("Ph\t*c1ccccc1\n"):
        ab.append(a)
    return ab


def strip_labels(mol):
    m = Chem.Mol(mol)
    for a in m.GetAtoms():
        for p in LABEL_PROPS:
            if a.HasProp(p):
                a.ClearProp(p)
    return m


def plain_display(mol):
    """Force every superatom to draw as its literal label text.

    RDKit condenses `CO2Et` and also stores `CO<sub>2</sub>Et` in _displayLabel,
    which is what actually gets drawn. The vocabulary arm compares `CO2Et` with
    `EtO2C`, and a mirrored label has no subscript form -- so unless BOTH sides
    are forced to plain text the comparison silently includes a typography
    change as well as a vocabulary one.
    """
    m = Chem.Mol(mol)
    for a in m.GetAtoms():
        if a.HasProp("atomLabel"):
            lab = a.GetProp("atomLabel")
            a.SetProp("_displayLabel", lab)
            a.SetProp("_displayLabelW", lab)
    return m


def mirror_labels(mol):
    """Rewrite every mirrorable superatom to its mirrored spelling.

    The GRAPH is untouched: only the label string changes, so the skeleton
    ground truth of the mirrored drawing is identical to its twin's.
    """
    m = Chem.Mol(mol)
    n = 0
    for a in m.GetAtoms():
        if a.HasProp("atomLabel") and a.GetProp("atomLabel") in MIRRORS:
            lab = MIRRORS[a.GetProp("atomLabel")]
            a.SetProp("atomLabel", lab)
            a.SetProp("_displayLabel", lab)
            a.SetProp("_displayLabelW", lab)
            n += 1
    return m, n


def drawn_forms(mol):
    cx = Chem.MolToCXSmiles(mol)
    skel = Chem.MolToSmiles(strip_labels(mol))
    _, block = (cx.split(" |", 1) + [""])[:2]
    found = re.findall(r"\$([^$]*)\$", block)
    appendix = [x for x in found[0].split(";") if x] if found else []
    return cx, skel, appendix


def build_markush(smiles, labels):
    m = Chem.MolFromSmiles(smiles)
    if m is None:
        raise ValueError(f"markush scaffold will not parse: {smiles}")
    dummies = [a for a in m.GetAtoms() if a.GetAtomicNum() == 0]
    if len(dummies) != len(labels):
        raise ValueError(f"{smiles}: {len(dummies)} dummies, {len(labels)} labels")
    for a, lab in zip(dummies, labels):
        a.SetAtomMapNum(0)
        a.SetProp("atomLabel", lab)
        # `[*]` parsed from SMILES carries dummyLabel='*', which MolToCXSmiles
        # emits as atomProp:0.dummyLabel.* -- a reparse does not reproduce it and
        # the reference then fails its own idempotence check.
        if a.HasProp("dummyLabel"):
            a.ClearProp("dummyLabel")
    return m


# ---------------------------------------------------------------- validation
def stratum_ok(stratum, parent, appendix):
    nf = len(Chem.GetMolFrags(parent))
    ha = parent.GetNumHeavyAtoms()
    nst = len(Chem.FindMolChiralCenters(parent, useLegacyImplementation=False,
                                        includeUnassigned=False))
    net = Chem.GetFormalCharge(parent)
    macro = max([len(r) for r in parent.GetRingInfo().AtomRings()], default=0)
    if stratum == "basic":
        if nst or nf > 1 or net or ha > 26 or appendix:
            return f"basic but centres={nst} frags={nf} charge={net} heavy={ha} app={appendix}"
    elif stratum == "stereo":
        if nst < 1:
            return f"stereo but {nst} defined centres"
        if appendix:
            return f"stereo but drawn with an appendix {appendix}"
    elif stratum == "abbreviated":
        if not appendix:
            return "abbreviated but nothing condensed"
    elif stratum == "complex":
        if macro < 12 and ha < 51 and fused_max(parent) < 4:
            return f"complex but heavy={ha} ring={macro} fused={fused_max(parent)}"
    elif stratum == "salt":
        if nf < 2 and net == 0:
            return f"salt but frags={nf} charge={net}"
    elif stratum == "markush":
        if not appendix:
            return "markush but no R labels"
    return ""


def roundtrip_ok(cx):
    m = Chem.MolFromSmiles(cx)
    if m is None:
        return "reference CXSMILES does not parse"
    again = Chem.MolToCXSmiles(m)
    if again != cx:
        return f"CXSMILES not idempotent:\n  {cx}\n  {again}"
    return ""


# ------------------------------------------------------------------- drawing
def mol_svg(mol, w, h, line_width):
    m = Chem.Mol(mol)
    AllChem.Compute2DCoords(m)
    d = rdMolDraw2D.MolDraw2DSVG(w, h)
    o = d.drawOptions()
    o.clearBackground = False               # the page rect underneath is exact white
    o.bondLineWidth = line_width
    o.fixedBondLength = FIXED_BOND_LENGTH
    rdMolDraw2D.PrepareAndDrawMolecule(d, m)
    d.FinishDrawing()
    svg = d.GetDrawingText()
    return svg.split("<!-- END OF HEADER -->", 1)[1].rsplit("</svg>", 1)[0]


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def page_svg(title, caption, items, show_caption):
    parts = [f'<rect x="0" y="0" width="{PAGE_W}" height="{PAGE_H}" fill="#ffffff" stroke="none"/>',
             f'<text x="100" y="{TITLE_Y}" font-family="DejaVu Sans" font-size="34" '
             f'font-weight="bold" fill="#000000">{esc(title)}</text>']
    for (x, y, w, h), body, label in items:
        parts.append(f'<g transform="translate({x},{y})">{body}</g>')
        if show_caption:
            parts.append(
                f'<text x="{x + w // 2}" y="{y + h + CAPTION_DROP}" font-family="DejaVu Sans" '
                f'font-size="26" fill="#000000" text-anchor="middle">{esc(label)}</text>')
    parts.append(f'<text x="100" y="{PAGE_H - 70}" font-family="DejaVu Sans" font-size="26" '
                 f'fill="#000000">{esc(caption)}</text>')
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<svg xmlns="http://www.w3.org/2000/svg" width="8.5in" height="11in" '
            f'viewBox="0 0 {PAGE_W} {PAGE_H}">\n' + "\n".join(parts) + "\n</svg>\n")


def svgs_to_pdf(svg_paths, pdf_path):
    subprocess.run(["rsvg-convert", "-f", "pdf", "-o", str(pdf_path)]
                   + [str(p) for p in svg_paths], check=True, capture_output=True)


# ---------------------------------------------------------------------- main
def prepare(entry, ab, mirrored=False, plain=False):
    """Plan entry -> (parent mol, drawn mol, reference smiles, extra fields)."""
    if entry.get("markush"):
        drawn = build_markush(entry["scaffold_smiles"], entry["r_labels"])
        parent = drawn
        ref = Chem.MolToSmiles(strip_labels(drawn))
        extra = {"markush": True, "parent_name": entry["parent_name"],
                 "parent_cid": entry["parent_cid"], "parent_smiles": entry["parent_smiles"],
                 "parent_inchikey": entry["parent_inchikey"]}
        return parent, drawn, ref, extra
    parent = Chem.MolFromSmiles(entry["source_smiles"])
    if parent is None:
        raise ValueError("source SMILES will not parse")
    if entry["stratum"] == "abbreviated" or mirrored or plain:
        drawn = rdAbbreviations.CondenseMolAbbreviations(parent, ab, maxCoverage=0.8)
    else:
        drawn = Chem.Mol(parent)
    if plain:
        drawn = plain_display(drawn)
    n_mirrored = 0
    if mirrored:
        drawn, n_mirrored = mirror_labels(drawn)
    return parent, drawn, Chem.MolToSmiles(parent), {"markush": False,
                                                     "mirrored_labels": n_mirrored}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--plan", type=Path, required=True)
    ap.add_argument("--out-pdfs", type=Path, required=True)
    ap.add_argument("--out-manifest", type=Path, required=True)
    ap.add_argument("--only", default=None, help="build only these group stems (comma list)")
    ap.add_argument("--keep-svg", action="store_true")
    args = ap.parse_args()

    ab = abbrevs()
    plan = json.loads(args.plan.read_text())
    groups, problems, n = {}, [], 0
    only = set(args.only.split(",")) if args.only else None
    args.out_pdfs.mkdir(parents=True, exist_ok=True)
    args.out_manifest.parent.mkdir(parents=True, exist_ok=True)

    for job in plan["pdfs"]:
        stem = job["stem"]
        if only and stem not in only:
            continue
        cond = job["render"]
        layout, lw = RENDER[cond]
        rects = cells_for(layout)
        per_page = len(rects)
        show_cap = LAYOUTS[layout]["caption"]
        members = job["members"]
        pages, cells = {}, {}
        metas = []
        for idx, entry in enumerate(members):
            page, slot = idx // per_page, idx % per_page
            try:
                parent, drawn, ref, extra = prepare(
                    entry, ab, mirrored=job.get("mirrored", False),
                    plain=job.get("plain_labels", False))
            except Exception as e:                                # noqa: BLE001
                problems.append(f"{stem}/{entry['name']}: {e}")
                continue
            cx, skel, appendix = drawn_forms(drawn)
            why = stratum_ok(entry["stratum"], parent, appendix) or roundtrip_ok(cx)
            if why:
                problems.append(f"{stem}/{entry['name']}: {why}")
                continue
            # An in-vocabulary condensation must expand back to the parent
            # through the SAME table the scorer uses; if it does not, the drawing
            # or the scorer is wrong and the score could not say which.
            note = ""
            if appendix and not extra["markush"] and not job.get("mirrored"):
                from cxsmiles import expand
                back, note = expand(cx)
                if not back or Chem.CanonSmiles(back) != Chem.CanonSmiles(ref):
                    problems.append(f"{stem}/{entry['name']}: condensation does not "
                                    f"expand back ({note}) {back} != {ref}")
                    continue
            n += 1
            rect = rects[slot]
            label = f"{n}  {entry['name']}"
            pages.setdefault(page, []).append(
                (rect, mol_svg(drawn, rect[2], rect[3], lw), label))
            ha = parent.GetNumHeavyAtoms()
            nst = len(Chem.FindMolChiralCenters(parent, useLegacyImplementation=False,
                                                includeUnassigned=False))
            meta = dict({
                "index": idx, "number": n, "name": entry["name"], "label": label,
                "stratum": entry["stratum"],
                "cid": entry.get("cid"), "inchikey": entry.get("inchikey"),
                "formula": entry.get("formula"),
                "smiles": ref, "source_smiles": entry.get("source_smiles"),
                "drawn_cxsmiles": cx, "skeleton": skel, "appendix": appendix,
                "has_appendix": bool(appendix),
                "appendix_in_vocab": [a in MS_ABBREV for a in appendix],
                "heavy_atoms": ha,
                "size_bucket": bucket_of(ha, SIZE_BUCKETS),
                "defined_stereocentres": nst,
                "stereo_bucket": bucket_of(nst, STEREO_BUCKETS),
                "n_superatoms": len(appendix),
                "abbrev_bucket": (bucket_of(len(appendix), ABBREV_BUCKETS)
                                  if appendix else None),
                "largest_ring": max([len(r) for r in parent.GetRingInfo().AtomRings()],
                                    default=0),
                "fused_max": fused_max(parent),
                "fragments": len(Chem.GetMolFrags(parent)),
                "net_charge": Chem.GetFormalCharge(parent),
                "topology": entry.get("topology"),
                "expansion_note": note,
                "render": cond, "layout": layout, "bond_line_width": lw,
                "per_page": per_page, "page": page + 1, "cell": [slot // LAYOUTS[layout]["cols"],
                                                                 slot % LAYOUTS[layout]["cols"]],
                "cell_px": list(rect),
                "arm": job["arm"], "panel_id": entry.get("panel_id"),
            }, **extra)
            metas.append(meta)
        if not metas:
            continue
        svg_paths = []
        for p in sorted(pages):
            cap = (f"Figure {p + 1}. {job['title']} "
                   f"({per_page} per page, line width {lw}).")
            sp = args.out_pdfs / f".{stem}_p{p + 1}.svg"
            sp.write_text(page_svg(job["title"], cap, pages[p], show_cap))
            svg_paths.append(sp)
        pdf = args.out_pdfs / f"{stem}.pdf"
        svgs_to_pdf(svg_paths, pdf)
        if not args.keep_svg:
            for sp in svg_paths:
                sp.unlink()
        groups[stem] = {"source": f"{stem}.pdf", "title": job["title"],
                        "pages": len(svg_paths), "render": cond, "layout": layout,
                        "bond_line_width": lw, "per_page": per_page, "arm": job["arm"],
                        "molecules": metas}
        print(f"{pdf.name:28s} {len(metas):3d} structures  {len(svg_paths)} pages  "
              f"{pdf.stat().st_size // 1024:4d} KB  [{cond}]", flush=True)

    counts = Counter()
    for g in groups.values():
        for m in g["molecules"]:
            counts[m["stratum"]] += 1
    manifest = {
        "corpus": "synthetic_cx_v2",
        "generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "generator": "benchmarks/make_synthetic_corpus_v2.py",
        "plan": str(args.plan.name),
        "note": ("RDKit-drawn corpus with CXSMILES ground truth known by construction: "
                 "each structure was drawn from the same molecule object whose "
                 "MolToCXSmiles is recorded as `drawn_cxsmiles`, so the picture and the "
                 "reference cannot disagree. `smiles` is the fully expanded molecule, for "
                 "score_run.py's plain-SMILES comparison; `drawn_cxsmiles`/`skeleton`/"
                 "`appendix` are what score_cx.py grades. Markush entries have no single "
                 "molecule -- grade the skeleton only. v2 draws the SAME compounds under "
                 "several render conditions (see `render`/`arm`); compare across "
                 "conditions only within one arm. CLEANER than real literature: every "
                 "number from it is an UPPER BOUND and `basic` is a control, not a result."),
        "strata": dict(counts),
        "drawn_at": {"page_dpi_units": DPI, "fixed_bond_length": FIXED_BOND_LENGTH,
                     "background": "#ffffff exact",
                     "renderer": "RDKit MolDraw2DSVG -> rsvg-convert"},
        "render_conditions": {k: {"layout": v[0], "bond_line_width": v[1],
                                  "per_page": LAYOUTS[v[0]]["rows"] * LAYOUTS[v[0]]["cols"]}
                              for k, v in RENDER.items()},
        "groups": groups,
    }
    args.out_manifest.write_text(json.dumps(manifest, indent=1))
    if problems:
        print(f"\nREJECTED ({len(problems)}, not drawn, not in the manifest):", file=sys.stderr)
        for p in problems[:60]:
            print("  " + p, file=sys.stderr)
    print(f"\n{n} drawings in {len(groups)} PDFs -> {args.out_manifest}")
    print("strata:", dict(counts))
    print("arms:", dict(Counter(g["arm"] for g in groups.values())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
