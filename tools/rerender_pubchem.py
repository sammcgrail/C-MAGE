"""Re-render PubChem compounds so they survive CXMolScribe's fixed 384 px resize.

WHY. PubChem's own 1500 px PNG scores 0 of 810 -- not one correct answer across two
independent compound sets -- and nine attempts to repair those images by resampling
all failed. PubChem cannot serve a usable large render either: its PUG SVG endpoint
400s, and the imgsrv service the website uses ignores width/height and always
returns 300x300.

So: re-render rather than resample, which is what every working arm already is.

WHAT MAKES THIS A RE-RENDER OF THE PUBCHEM DEPICTION AND NOT A FRESH DRAWING.
Each compound's 2D SDF carries the atom coordinates PubChem itself laid out. Drawing
from those keeps PubChem's depiction -- same layout, same orientation -- and changes
only the thing that was broken: stroke width, scaled to the canvas instead of held
constant in absolute pixels. `used_pubchem_coords` in the output records how many
actually got PubChem's coordinates rather than the SMILES fallback, because a run
where that number is low is a fresh RDKit layout wearing this script's name.
"""
import glob
import io
import json
import os
import sys

sys.path.insert(0, "<work>/cmage-img")
import pug                                                        # noqa: E402
from PIL import Image                                             # noqa: E402
from rdkit import Chem, RDLogger                                  # noqa: E402
from rdkit.Chem.Draw import rdMolDraw2D                           # noqa: E402

RDLogger.DisableLog("rdApp.*")

SIZE = 1500          # the exact size whose native PubChem render scores zero
OUT = "<work>/rerender/pubchem_rerender_1500/in"


def main() -> int:
    sel = json.load(open("<work>/cmage-img/selected.json"))
    os.makedirs(OUT, exist_ok=True)
    ok = fail = used_sdf = 0
    fails = []
    for i, c in enumerate(sel):
        cid = c["cid"]
        # Reuse the other arms' filename exactly, so the existing manifest scores
        # this arm with no edits and no chance of a silent key mismatch.
        g = glob.glob(f"<work>/cmage-img/corpus_300/*_cid{cid}.png")
        if not g:
            fails.append((cid, "no matching filename")); fail += 1; continue
        dst = os.path.join(OUT, os.path.basename(g[0]))
        if os.path.exists(dst):
            ok += 1; continue

        mol = None
        try:
            _st, data = pug.fetch(
                f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{cid}"
                f"/SDF?record_type=2d")
            mol = Chem.MolFromMolBlock(data.decode("utf8", "replace"))
            if mol is not None:
                used_sdf += 1
        except Exception:
            mol = None
        if mol is None:
            mol = Chem.MolFromSmiles(c["smiles"])
        if mol is None:
            fails.append((cid, "unrenderable")); fail += 1; continue

        try:
            dr = rdMolDraw2D.MolDraw2DCairo(SIZE, SIZE)
            o = dr.drawOptions()
            o.bondLineWidth = max(1, round(SIZE / 150))   # scales WITH the canvas
            o.fixedBondLength = -1
            o.padding = 0.06
            rdMolDraw2D.PrepareAndDrawMolecule(dr, mol)
            dr.FinishDrawing()
            Image.open(io.BytesIO(dr.GetDrawingText())).convert("RGB").save(dst)
            ok += 1
        except Exception as exc:
            fails.append((cid, str(exc)[:60])); fail += 1

        if (i + 1) % 50 == 0:
            print(f"  {i+1}/{len(sel)} ok={ok} fail={fail} sdf={used_sdf}", flush=True)

    print(f"DONE ok={ok} fail={fail} used_pubchem_coords={used_sdf}", flush=True)
    json.dump(fails, open("<work>/rerender/fails.json", "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
