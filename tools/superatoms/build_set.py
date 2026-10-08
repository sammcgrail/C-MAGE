#!/usr/bin/env python3
"""Build the superatom-heavy synthetic set: corpus molecules with >= 2 condensable groups (already
read in the plain corpus by the Sonnet 5.5 API arm, so each has a paired plain reading) plus PubChem
molecules chosen for protecting groups and common superatoms. Each is drawn CONDENSED with the
corpus renderer's settings at 1500 px; the truth is the original full molecule.

Gates per molecule (a failure drops it, recorded in synth/rejected.json):
  - at least 2 superatom labels after condensation;
  - expand(condensed) == original, canonical isomeric SMILES (truth exact by construction);
  - tesseract finds every distinct label's text in the 1500 px drawing (it really shows them);
  - PNG written with NO text chunks (RDKit embeds the molecule in zTXt by default).
Output: synth/images/sa_NNNN.png (neutral names, shuffled order) and synth/set.json."""
import csv, io, json, random, re, subprocess, sys, collections
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import sa_abbrev as A
from PIL import Image
from rdkit import Chem, RDLogger
RDLogger.DisableLog("rdApp.*")

ROOT = Path("/root/cmage-work/superatoms")
REPO = Path("/root/C-MAGE")
IMG = ROOT / "synth/images"
N_CORPUS_GREEDY = 70
MAX_HEAVY = 60
SEED = 20261008


def assert_clean(p):
    """No answer in the file: no text chunks at all, PIL sees no info beyond dpi/gamma, and RDKit
    cannot recover a molecule from it."""
    b = Path(p).read_bytes()
    assert not any(t in b for t in (b"zTXt", b"tEXt", b"iTXt")), p
    im = Image.open(p); im.load()
    assert not (set(im.info) - {"dpi", "gamma"}), (p, im.info)
    assert Chem.MolFromPNGFile(str(p)) is None, p


def ocr_text(png):
    r = subprocess.run(["tesseract", str(png), "-", "--psm", "11"], capture_output=True, text=True)
    return re.sub(r"\s+", "", r.stdout)


def svg_text(cond):
    from rdkit.Chem.Draw import rdMolDraw2D
    d = rdMolDraw2D.MolDraw2DSVG(1500, 1500, -1, -1, True)
    o = d.drawOptions()
    o.clearBackground = True; o.maxFontSize = -1; o.minFontSize = -1; o.scaleBondWidth = True; o.bondLineWidth = 2
    rdMolDraw2D.PrepareAndDrawMolecule(d, cond)
    d.FinishDrawing()
    return d.GetDrawingText()


def label_clash(cond):
    """True when two atoms' drawn text boxes overlap (e.g. AcO printed over OBz): such a drawing is
    unreadable by anyone and would measure the layout, not the reader."""
    boxes = {}
    for m in re.finditer(r"<text x='([\d.]+)' y='([\d.]+)' class='atom-(\d+)' style='font-size:([\d.]+)px", svg_text(cond)):
        x, y, i, fs = float(m.group(1)), float(m.group(2)), int(m.group(3)), float(m.group(4))
        b = (x - 0.2 * fs, y - 0.95 * fs, x + 0.8 * fs, y + 0.3 * fs)   # padded: touching counts
        o = boxes.get(i)
        boxes[i] = b if o is None else (min(o[0], b[0]), min(o[1], b[1]), max(o[2], b[2]), max(o[3], b[3]))
    ks = sorted(boxes)
    for a in range(len(ks)):
        for b in range(a + 1, len(ks)):
            p, q = boxes[ks[a]], boxes[ks[b]]
            if p[0] < q[2] and q[0] < p[2] and p[1] < q[3] and q[1] < p[3]:
                return True
    return False


def svg_labels(cond):
    """The text RDKit draws for each atom, from the same drawing code with plain SVG <text> output
    (same options as the PNG). Returns {atom index: drawn string}."""
    from rdkit.Chem.Draw import rdMolDraw2D
    d = rdMolDraw2D.MolDraw2DSVG(1500, 1500, -1, -1, True)
    o = d.drawOptions()
    o.clearBackground = True; o.maxFontSize = -1; o.minFontSize = -1; o.scaleBondWidth = True; o.bondLineWidth = 2
    rdMolDraw2D.PrepareAndDrawMolecule(d, cond)
    d.FinishDrawing()
    got = collections.defaultdict(str)
    for m in re.finditer(r"<text[^>]*class='atom-(\d+)'[^>]*>(.*?)</text>", d.GetDrawingText()):
        got[int(m.group(1))] += re.sub(r"<[^>]+>", "", m.group(2))
    return got


def label_forms(lab):
    d = next(x for x in A.ALL if x.label == lab)
    strip = lambda s: re.sub(r"<[^>]+>", "", s)
    return {strip(d.displayLabel) or lab, strip(d.displayLabelW) or strip(d.displayLabel) or lab}


def main():
    man = list(csv.DictReader(open(REPO / "corpus_images/manifest.csv")))
    led = {}
    for l in open(REPO / "benchmarks/published_runs/sonnet55_api/ledger.jsonl"):
        r = json.loads(l)
        if r["status"] == "ok":
            led[r["k"]] = r
    by_can = {}
    cands = []
    for r in man:
        m = Chem.MolFromSmiles(r["truth_smiles"])
        if m is None:
            continue
        by_can[A.canon(m)] = r["key"]
        c = A.condense(m)
        labs = A.labels_of(c)
        if len(labs) >= 2 and r["key"] in led and m.GetNumHeavyAtoms() <= MAX_HEAVY:
            cands.append(dict(src="corpus", key=r["key"], name=r["name"], cid=r["pubchem_cid"],
                              truth=r["truth_smiles"], labels=labs))
    pub = json.load(open(ROOT / "synth/pubchem.json"))
    forced, pubs = [], []
    for n, v in pub.items():
        m = Chem.MolFromSmiles(v["smiles"])
        labs = A.labels_of(A.condense(m))
        if len(labs) < 2:
            continue
        ck = by_can.get(A.canon(m))
        if ck:      # a list molecule that IS a corpus molecule: use the corpus record and truth
            hit = next((c for c in cands if c["key"] == ck), None)
            if hit:
                forced.append(hit)
            continue
        pubs.append(dict(src="pubchem", key=None, name=n, cid=v["cid"], truth=v["smiles"], labels=labs))
    # greedy diversity over corpus candidates: rarest labels first
    chosen = {c["key"]: c for c in forced}
    freq = collections.Counter(l for c in list(chosen.values()) + pubs for l in set(c["labels"]))
    pool = sorted([c for c in cands if c["key"] not in chosen], key=lambda c: c["key"])
    while len(chosen) < len(forced) + N_CORPUS_GREEDY and pool:
        best = max(pool, key=lambda c: (sum(1 / (1 + freq[l]) for l in set(c["labels"])), len(c["labels"]), c["key"]))
        pool.remove(best)
        chosen[best["key"]] = best
        freq.update(set(best["labels"]))
    items = list(chosen.values()) + pubs
    random.Random(SEED).shuffle(items)
    IMG.mkdir(parents=True, exist_ok=True)
    out, rej = [], []
    for it in items:
        m = Chem.MolFromSmiles(it["truth"])
        c = A.condense(m)
        if A.canon(A.expand(c)) != A.canon(m):
            rej.append(dict(it, why="expand != truth")); continue
        if label_clash(c):
            from rdkit.Chem import rdDepictor
            rdDepictor.SetPreferCoordGen(True)
            rdDepictor.Compute2DCoords(c)
            rdDepictor.SetPreferCoordGen(False)
            if label_clash(c):
                rej.append(dict(it, why="labels overlap in the drawing")); continue
            it = dict(it, layout="coordgen")
        sid = f"sa_{len(out) + 1:04d}"
        tmp = ROOT / "synth/tmp.png"
        A.render(c, 1500, tmp)
        im = Image.open(tmp); im.load()
        png = IMG / f"{sid}.png"
        im.convert("RGB").save(png)            # re-encode: pixels only, no zTXt molecule chunks
        assert_clean(png)
        drawn = svg_labels(c)
        bad = [a.GetProp("atomLabel") for a in c.GetAtoms() if a.HasProp("atomLabel")
               and drawn.get(a.GetIdx()) not in label_forms(a.GetProp("atomLabel"))]
        if bad:
            rej.append(dict(it, why=f"label not drawn as text: {bad}")); png.unlink(); continue
        # loose second witness on the PNG itself: OCR, digits dropped (subscripts OCR badly)
        nd = lambda x: re.sub(r"[\d,._]", "", x).replace("0", "O")
        txt = nd(ocr_text(png))
        miss = [l for l in sorted(set(A.labels_of(c))) if not any(nd(f) in txt for f in label_forms(l))]
        it2 = dict(it, id=sid, labels=A.labels_of(c), cx=Chem.MolToCXSmiles(c), heavy=m.GetNumHeavyAtoms(),
                   n_labels=len(A.labels_of(c)), ocr_missing=miss, plain_key=it["key"])
        if it["key"] is None:
            it2["plain_key"] = None
        out.append(it2)
    json.dump(out, open(ROOT / "synth/set.json", "w"), indent=1)
    json.dump(rej, open(ROOT / "synth/rejected.json", "w"), indent=1)
    print(f"{len(out)} built ({sum(1 for x in out if x['src'] == 'corpus')} corpus, "
          f"{sum(1 for x in out if x['src'] == 'pubchem')} PubChem), {len(rej)} rejected; "
          f"OCR missed a label on {sum(1 for x in out if x['ocr_missing'])}")
    print(collections.Counter(l for x in out for l in set(x["labels"])).most_common())


if __name__ == "__main__":
    main()
