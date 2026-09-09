#!/usr/bin/env python3
"""Draw a benchmark corpus whose CXSMILES ground truth is known by construction.

THE PROBLEM THIS SOLVES (benchmarks/FINDINGS.md section 5)
----------------------------------------------------------
The C-MAGE paper grades each prediction against its own segment image, in two
parts: the SKELETON (the CXSMILES minus the appendix) and the APPENDIX
(CXMolScribe's translation of the drawn superatoms). Our document corpus is
scored against PubChem *SMILES*, which has no appendix at all, so 148 of 242
predictions there are unscoreable -- the reference cannot express what the
drawing says. The paper's authors hand-wrote a reference CXSMILES per segment
because "the novel datasets do not have established ground truths".

If we DRAW the structures ourselves the ground truth is not a judgement call:

    cond = rdAbbreviations.CondenseMolAbbreviations(mol, abbrevs, maxCoverage=0.8)
    cx   = Chem.MolToCXSmiles(cond)      # -> '*c1ccc(*)c(...)c1 |$CF3;;;;;OMe;...$|'
    draw(cond)                           # the picture and the string are the same object

The drawing and the reference come from one molecule object, so they cannot
disagree. That is the whole mechanism.

WHAT THIS BUYS, AND WHAT IT COSTS
---------------------------------
Buys: an appendix grade, per stratum, on 100 compounds -- the measurement the
document corpus cannot make at all.

Costs: RDKit line art is CLEANER than real literature figures. No scanner noise,
no overlapping labels, no hand-drawn bonds, one drawing convention throughout.
Every number this corpus produces is an UPPER BOUND on what the pipeline does in
anger, and the `basic` stratum is a control that should sit near ceiling rather
than a result. Say so wherever the numbers are quoted.

DRAWING DECISIONS THAT ARE NOT COSMETIC
---------------------------------------
* PURE WHITE background (255,255,255) everywhere. DECIMER's CropWhite tests for
  exact white; the near-white (#f5f5f5) panel behind PubChem's own depictions in
  the older test PDFs measurably costs accuracy.
* Stage 1 renders pages at pdf2image's DEFAULT 200 dpi -- see
  MERMaid/src/visualheist/methods_visualheist.py:_pdf_to_image, which calls
  convert_from_path(path) with no dpi. So structure size in PAGE INCHES is what
  matters, not the size of any PNG we might have made. Pages are laid out in
  units of 1/200 inch for that reason: one user unit is one pixel as stage 1
  will see it.
* fixedBondLength caps the scale of SMALL molecules. Without it RDKit blows
  aspirin up to fill a 700x560 box, giving it a bond length no journal would
  print and flattering the benchmark further.
* Vector PDF (SVG -> rsvg-convert), not a rasterised one: no JPEG ringing to
  turn the background off-white, and ~30 KB per file.

Run with the stage-3 interpreter, which is the only one with RDKit:

  .venv-ms/bin/python benchmarks/make_synthetic_corpus.py \
      --out-pdfs benchmarks/corpus_synth \
      --out-manifest benchmarks/ground_truth/synthetic_manifest.json

Rebuild the identical PDFs offline from an existing manifest (no PubChem):

  ... make_synthetic_corpus.py --from-manifest benchmarks/ground_truth/synthetic_manifest.json
"""
import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

from rdkit import Chem, RDLogger
from rdkit.Chem import AllChem, rdAbbreviations, rdMolDescriptors
from rdkit.Chem.Draw import rdMolDraw2D

sys.path.insert(0, str(Path(__file__).resolve().parent))
from synthetic_compounds import (BASIC, STEREO, ABBREVIATED, COMPLEX, SALT,  # noqa: E402
                                 MARKUSH_SCAFFOLDS, PDFS, STRATA)

RDLogger.DisableLog("rdApp.*")

PUBCHEM = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound"

# ---- page geometry, in units of 1/200 inch (= one stage-1 pixel)
DPI = 200
PAGE_W, PAGE_H = int(8.5 * DPI), int(11 * DPI)      # US Letter
MARGIN = 100
TITLE_Y = 108
GRID_TOP = 170
CELL_W = (PAGE_W - 2 * MARGIN) // 2                 # 750
CELL_H = 636
BOX_W, BOX_H = 700, 552                             # drawing box inside a cell
CAPTION_DY = 596                                    # label baseline within a cell
ROWS_PAGE = (3, 2)                                  # 6 structures then 4
FIXED_BOND_LENGTH = 80              # 0.40 inch at 200 dpi


# --------------------------------------------------------------- PubChem
def _get(url, tries=4):
    for i in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=45) as r:
                return json.loads(r.read().decode())
        except Exception:                                        # noqa: BLE001
            if i == tries - 1:
                return None
            time.sleep(1.5 * (i + 1))
    return None


def pubchem_by_name(name, cache):
    """name -> {cid, smiles, formula, inchikey} using PubChem's own record.

    Asks for both SMILES and ConnectivitySMILES: PubChem renamed IsomericSMILES
    to SMILES, and a client that asks for the old name gets the new field back
    silently, so read whichever arrives rather than trusting either name.
    """
    if name in cache:
        return cache[name]
    q = urllib.parse.quote(name)
    props = "SMILES,IsomericSMILES,ConnectivitySMILES,MolecularFormula,InChIKey"
    d = _get(f"{PUBCHEM}/name/{q}/property/{props}/JSON")
    rec = None
    if d and d.get("PropertyTable", {}).get("Properties"):
        p = d["PropertyTable"]["Properties"][0]
        smi = p.get("IsomericSMILES") or p.get("SMILES") or p.get("ConnectivitySMILES")
        rec = {"cid": p.get("CID"), "smiles": smi,
               "formula": p.get("MolecularFormula"), "inchikey": p.get("InChIKey")}
    cache[name] = rec
    time.sleep(0.25)                                  # PubChem asks for <= 5/s
    return rec


# --------------------------------------------------------------- chemistry
def _abbrevs():
    """RDKit's 37 defaults plus Ph, which CXMolScribe knows and RDKit omits."""
    ab = rdAbbreviations.GetDefaultAbbreviations()
    extra = rdAbbreviations.ParseAbbreviations("Ph\t*c1ccccc1\n")
    for a in extra:
        ab.append(a)
    return ab


def strip_labels(mol):
    """Copy of `mol` with every atomLabel removed -- the SKELETON as a graph."""
    m = Chem.Mol(mol)
    for a in m.GetAtoms():
        for p in ("atomLabel", "_displayLabel", "_displayLabelW", "dummyLabel"):
            if a.HasProp(p):
                a.ClearProp(p)
    return m


def labels_of(mol):
    return [a.GetProp("atomLabel") for a in mol.GetAtoms() if a.HasProp("atomLabel")]


def build_markush(smiles, labels):
    """`[*:n]` dummies -> dummies carrying atomLabel R1/R2 (what RDKit draws)."""
    m = Chem.MolFromSmiles(smiles)
    if m is None:
        raise ValueError(f"markush scaffold will not parse: {smiles}")
    dummies = sorted((a for a in m.GetAtoms() if a.GetAtomicNum() == 0),
                     key=lambda a: a.GetAtomMapNum())
    if len(dummies) != len(labels):
        raise ValueError(f"{smiles}: {len(dummies)} dummies but {len(labels)} labels")
    for a, lab in zip(dummies, labels):
        a.SetAtomMapNum(0)
        a.SetProp("atomLabel", lab)
        # RDKit sets dummyLabel="*" when it parses `[*:n]`, and MolToCXSmiles
        # then emits `atomProp:0.dummyLabel.*` -- which a reparse does NOT
        # reproduce, so the reference CXSMILES fails its own round-trip check.
        # The property carries no information here; the atomLabel is the label.
        a.ClearProp("dummyLabel")
    return m


def markush_query(smiles):
    """Substructure query where `*` is a wildcard, with SMILES aromaticity.

    Built from SMILES rather than SMARTS so the scaffold and the drug it claims
    to generalise go through the SAME aromaticity perception; a SMARTS written
    by hand can silently disagree with RDKit about a purinone ring and turn a
    correct scaffold into a rejection.
    """
    m = Chem.MolFromSmiles(smiles)
    if m is None:
        return None
    p = Chem.AdjustQueryParameters.NoAdjustments()
    p.makeDummiesQueries = True
    return Chem.AdjustQueryProperties(m, p)


def drawn_forms(mol):
    """(cxsmiles, skeleton SMILES, appendix labels) for the molecule as drawn."""
    cx = Chem.MolToCXSmiles(mol)
    skel = Chem.MolToSmiles(strip_labels(mol))
    # Labels in canonical OUTPUT order, which is what the $-block records.
    core, block = (cx.split(" |", 1) + [""])[:2]
    ordered = [x for x in re.findall(r"\$([^$]*)\$", block)[0].split(";")] if "$" in block else []
    appendix = [x for x in ordered if x]
    return cx, skel, appendix


# --------------------------------------------------------------- drawing
def mol_svg(mol, w, h):
    AllChem.Compute2DCoords(mol)
    d = rdMolDraw2D.MolDraw2DSVG(w, h)
    o = d.drawOptions()
    o.clearBackground = False          # the page rect underneath is pure white
    o.bondLineWidth = 2
    o.fixedBondLength = FIXED_BOND_LENGTH
    rdMolDraw2D.PrepareAndDrawMolecule(d, mol)
    d.FinishDrawing()
    svg = d.GetDrawingText()
    return svg.split("<!-- END OF HEADER -->", 1)[1].rsplit("</svg>", 1)[0]


def esc(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def page_svg(title, caption, cells):
    """cells: [(row, col, mol_body_svg, label)] -> one page of SVG."""
    parts = [f'<rect x="0" y="0" width="{PAGE_W}" height="{PAGE_H}" fill="#ffffff" stroke="none"/>',
             f'<text x="{MARGIN}" y="{TITLE_Y}" font-family="DejaVu Sans" font-size="34" '
             f'font-weight="bold" fill="#000000">{esc(title)}</text>']
    for row, col, body, label in cells:
        x = MARGIN + col * CELL_W + (CELL_W - BOX_W) // 2
        y = GRID_TOP + row * CELL_H
        parts.append(f'<g transform="translate({x},{y})">{body}</g>')
        parts.append(f'<text x="{x + BOX_W // 2}" y="{y + CAPTION_DY}" font-family="DejaVu Sans" '
                     f'font-size="26" fill="#000000" text-anchor="middle">{esc(label)}</text>')
    parts.append(f'<text x="{MARGIN}" y="{PAGE_H - 70}" font-family="DejaVu Sans" font-size="26" '
                 f'fill="#000000">{esc(caption)}</text>')
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<svg xmlns="http://www.w3.org/2000/svg" width="8.5in" height="11in" '
            f'viewBox="0 0 {PAGE_W} {PAGE_H}">\n' + "\n".join(parts) + "\n</svg>\n")


def svgs_to_pdf(svg_paths, pdf_path):
    """rsvg-convert makes one multi-page PDF from several SVGs, losslessly."""
    cmd = ["rsvg-convert", "-f", "pdf", "-o", str(pdf_path)] + [str(p) for p in svg_paths]
    subprocess.run(cmd, check=True, capture_output=True)


# --------------------------------------------------------------- validation
def stratum_ok(stratum, parent, drawn, appendix):
    """Why a compound does NOT belong in the stratum it was filed under, or ''.

    A stratum whose members do not actually have the property it names produces
    a per-stratum table that means nothing, and nothing in the pipeline would
    ever complain -- so the check is here, before a single pixel is drawn.
    """
    nf = len(Chem.GetMolFrags(parent))
    ha = parent.GetNumHeavyAtoms()
    nst = len(Chem.FindMolChiralCenters(parent, useLegacyImplementation=False,
                                        includeUnassigned=False))
    net = Chem.GetFormalCharge(parent)
    macro = max([len(r) for r in parent.GetRingInfo().AtomRings()], default=0)
    if stratum == "basic":
        if nst or nf > 1 or net or ha > 26 or appendix:
            return f"basic but centres={nst} frags={nf} charge={net} heavy={ha} appendix={appendix}"
    elif stratum == "stereo":
        if nst < 3:
            return f"stereo but only {nst} defined centres"
        if appendix:
            return f"stereo but drawn with an appendix {appendix}"
    elif stratum == "abbreviated":
        if not appendix:
            return "abbreviated but nothing condensed"
    elif stratum == "complex":
        if ha < 55 and macro < 13:
            return f"complex but heavy={ha} largest ring={macro}"
    elif stratum == "salt":
        if nf < 2 and net == 0:
            return f"salt but frags={nf} net charge={net}"
    elif stratum == "markush":
        if not appendix:
            return "markush but no R labels"
    return ""


def roundtrip_ok(cx, drawn):
    """The reference CXSMILES must survive RDKit, or it is not a reference."""
    m = Chem.MolFromSmiles(cx)
    if m is None:
        return "reference CXSMILES does not parse"
    again = Chem.MolToCXSmiles(m)
    if again != cx:
        return f"CXSMILES not idempotent:\n  {cx}\n  {again}"
    return ""


# --------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out-pdfs", type=Path, default=Path("benchmarks/corpus_synth"))
    ap.add_argument("--out-manifest", type=Path,
                    default=Path("benchmarks/ground_truth/synthetic_manifest.json"))
    ap.add_argument("--cache", type=Path, default=Path(".pubchem_synth_cache.json"))
    ap.add_argument("--from-manifest", type=Path, default=None,
                    help="rebuild the same PDFs from a manifest, with no network")
    ap.add_argument("--only", default=None, help="build only these PDF stems (comma list)")
    ap.add_argument("--keep-svg", action="store_true")
    args = ap.parse_args()

    ab = _abbrevs()
    scaffolds = {s[0]: s for s in MARKUSH_SCAFFOLDS}
    prior = {}
    if args.from_manifest:
        man = json.loads(args.from_manifest.read_text())
        for g in man["groups"].values():
            for m in g["molecules"]:
                prior[m["name"]] = m
    cache = json.loads(args.cache.read_text()) if args.cache.exists() else {}

    args.out_pdfs.mkdir(parents=True, exist_ok=True)
    args.out_manifest.parent.mkdir(parents=True, exist_ok=True)
    only = set(args.only.split(",")) if args.only else None

    groups, problems, n = {}, [], 0
    for stem, title, members in PDFS:
        if only and stem not in only:
            continue
        mols_meta, cells_by_page = [], {0: [], 1: []}
        for idx, (stratum, name) in enumerate(members):
            page = 0 if idx < ROWS_PAGE[0] * 2 else 1
            slot = idx if page == 0 else idx - ROWS_PAGE[0] * 2
            row, col = slot // 2, slot % 2

            if stratum == "markush":
                _, smi, labels, parent_name = scaffolds[name]
                drawn = build_markush(smi, labels)
                # The scaffold must actually be inside the drug it claims to
                # generalise; a SMARTS query is used so `*` is a wildcard.
                pinfo = prior.get(name) or {}
                parent_rec = (pinfo.get("parent_smiles") and {"smiles": pinfo["parent_smiles"],
                                                              "cid": pinfo.get("parent_cid")}) \
                    or pubchem_by_name(parent_name, cache)
                if not parent_rec or not parent_rec.get("smiles"):
                    problems.append(f"{name}: cannot resolve parent {parent_name}")
                    continue
                pmol = Chem.MolFromSmiles(parent_rec["smiles"])
                q = markush_query(smi)
                if q is None or pmol is None or not pmol.HasSubstructMatch(q):
                    problems.append(f"{name}: scaffold is not a substructure of {parent_name}")
                    continue
                parent = drawn                                  # no single molecule exists
                cid = inchikey = None
                formula = rdMolDescriptors.CalcMolFormula(strip_labels(drawn))
                ref_smiles = Chem.MolToSmiles(strip_labels(drawn))
                extra = {"markush": True, "parent_name": parent_name,
                         "parent_cid": parent_rec.get("cid"),
                         "parent_inchikey": parent_rec.get("inchikey"),
                         "parent_smiles": parent_rec["smiles"]}
            else:
                rec = prior.get(name)
                if rec:
                    # `source_smiles` is PubChem's string VERBATIM, not our
                    # canonical rewrite of it. Rebuilding from the canonical form
                    # gives the same molecule in a different atom order, and
                    # Compute2DCoords is order-dependent -- so --from-manifest
                    # reproduced the ground truth exactly and the PIXELS not at
                    # all, on 18 of 20 pages. Measured, not assumed.
                    src = {"cid": rec["cid"],
                           "smiles": rec.get("source_smiles") or rec["smiles"],
                           "formula": rec["formula"], "inchikey": rec["inchikey"]}
                else:
                    src = pubchem_by_name(name, cache)
                if not src or not src.get("smiles"):
                    problems.append(f"{name}: PubChem returned nothing")
                    continue
                parent = Chem.MolFromSmiles(src["smiles"])
                if parent is None:
                    problems.append(f"{name}: PubChem SMILES will not parse")
                    continue
                drawn = (rdAbbreviations.CondenseMolAbbreviations(parent, ab, maxCoverage=0.8)
                         if stratum == "abbreviated" else Chem.Mol(parent))
                ref_smiles = Chem.MolToSmiles(parent)
                cid, formula = src.get("cid"), src.get("formula")
                inchikey = src.get("inchikey") or Chem.MolToInchiKey(parent)
                extra = {"markush": False}

            cx, skel, appendix = drawn_forms(drawn)
            why = stratum_ok(stratum, parent, drawn, appendix) or roundtrip_ok(cx, drawn)
            if why:
                problems.append(f"{stem}/{name}: {why}")
                continue
            # For the abbreviated stratum the drawn condensation must expand
            # back to the parent through the SAME table the scorer uses. If it
            # does not, either the drawing or the scorer is wrong and we would
            # not be able to tell which from the score.
            expand_note = ""
            if appendix and not extra["markush"]:
                sys.path.insert(0, str(Path(__file__).resolve().parent))
                from cxsmiles import expand
                back, note = expand(cx)
                expand_note = note
                if not back or Chem.CanonSmiles(back) != Chem.CanonSmiles(ref_smiles):
                    problems.append(f"{stem}/{name}: condensation does not expand back "
                                    f"({note}) {back} != {ref_smiles}")
                    continue

            n += 1
            label = f"{n}  {name}"
            cells_by_page[page].append((row, col, mol_svg(drawn, BOX_W, BOX_H), label))
            mols_meta.append(dict({
                "index": idx, "number": n, "name": name, "label": label,
                "stratum": stratum, "cid": cid, "inchikey": inchikey, "formula": formula,
                "smiles": ref_smiles,                       # score_run.py reads this
                "source_smiles": (src["smiles"] if not extra["markush"] else None),
                "drawn_cxsmiles": cx, "skeleton": skel, "appendix": appendix,
                "has_appendix": bool(appendix),
                "heavy_atoms": parent.GetNumHeavyAtoms(),
                "largest_ring": max([len(r) for r in parent.GetRingInfo().AtomRings()], default=0),
                "fragments": len(Chem.GetMolFrags(parent)),
                "defined_stereocentres": len(Chem.FindMolChiralCenters(
                    parent, useLegacyImplementation=False, includeUnassigned=False)),
                "net_charge": Chem.GetFormalCharge(parent),
                "expansion_note": expand_note,
                "page": page + 1, "cell": [row, col],
            }, **extra))

        if not mols_meta:
            continue
        svg_paths = []
        for p in (0, 1):
            if not cells_by_page[p]:
                continue
            lo = mols_meta[0]["number"]
            hi = mols_meta[-1]["number"]
            cap = (f"Figure {p + 1}. Structures {lo}-{hi} of the synthetic benchmark corpus "
                   f"(page {p + 1} of 2).")
            sp = args.out_pdfs / f".{stem}_p{p + 1}.svg"
            sp.write_text(page_svg(title, cap, cells_by_page[p]))
            svg_paths.append(sp)
        pdf = args.out_pdfs / f"{stem}.pdf"
        svgs_to_pdf(svg_paths, pdf)
        if not args.keep_svg:
            for sp in svg_paths:
                sp.unlink()
        groups[stem] = {"source": f"{stem}.pdf", "title": title,
                        "pages": len(svg_paths), "molecules": mols_meta}
        print(f"{pdf}  {len(mols_meta)} structures, {len(svg_paths)} pages, "
              f"{pdf.stat().st_size // 1024} KB")

    args.cache.write_text(json.dumps(cache, indent=1))
    if problems:
        print("\nREJECTED (not drawn, not in the manifest):", file=sys.stderr)
        for p in problems:
            print("  " + p, file=sys.stderr)

    counts = {}
    for g in groups.values():
        for m in g["molecules"]:
            counts[m["stratum"]] = counts.get(m["stratum"], 0) + 1
    manifest = {
        "corpus": "synthetic_cx",
        "generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "generator": "benchmarks/make_synthetic_corpus.py",
        "note": ("RDKit-drawn corpus with CXSMILES ground truth known by construction: "
                 "every structure was drawn from the same molecule object whose "
                 "MolToCXSmiles is recorded as `drawn_cxsmiles`, so the picture and the "
                 "reference cannot disagree. `smiles` is the fully expanded molecule and "
                 "exists so score_run.py can produce the plain-SMILES comparison; "
                 "`drawn_cxsmiles`/`skeleton`/`appendix` are what score_cx.py grades. "
                 "Markush entries have no single molecule -- grade the skeleton only. "
                 "This is CLEANER than real literature figures and every number from it "
                 "is an upper bound."),
        "strata": counts,
        "drawn_at": {"page_dpi_units": DPI, "fixed_bond_length": FIXED_BOND_LENGTH,
                     "background": "#ffffff exact", "renderer": "RDKit MolDraw2DSVG -> rsvg-convert"},
        "groups": groups,
    }
    args.out_manifest.write_text(json.dumps(manifest, indent=1))
    print(f"\n{sum(len(g['molecules']) for g in groups.values())} compounds in "
          f"{len(groups)} PDFs -> {args.out_manifest}")
    print("strata:", counts)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
