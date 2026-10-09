#!/usr/bin/env python3
"""Expansion of the built superatom set (2026-10-09): about 300 more drawings, sa_0176 onward.

Same method and gates as build_set.py, with the v2 abbreviation list (sa_abbrev.ALL_V2: + Trt, PMB on N,
MOM/OMOM, THP/OTHP, SEM/OSEM, Piv/OPiv, Alloc; RDKit's ambiguous "NC" isocyanide dropped).
Sources:
  - every new PubChem pick (pubchem_names2.txt -> more/pubchem2.json) with >= 2 labels;
  - corpus molecules with >= 2 labels NOT already in the set, read by the Sonnet 5.5 API corpus arm
    (so each has a paired plain reading), <= 60 heavy atoms, chosen greedily for label diversity
    until the expansion reaches TARGET built drawings.
A molecule already in the set (same canonical isomeric SMILES) is never drawn twice.
Gates per molecule (failure -> more/rejected2.json): >= 2 labels; expand(condensed) == original;
no overlapping labels (coordgen retry); each label drawn as its text (SVG atom text runs);
PNG re-saved pixels only and asserted free of text chunks (zTXt/tEXt/iTXt), PIL info and RDKit mol.
Writes the PNGs to the published run dir and APPENDS to synth/set.json and synth/run_set.json."""
import collections, csv, json, random, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import sa_abbrev as A
from build_set import assert_clean, label_clash, svg_labels, label_forms, ocr_text
from PIL import Image
from rdkit import Chem, RDLogger
from rdkit.Chem import rdDepictor
RDLogger.DisableLog("rdApp.*")

ROOT = Path("/root/cmage-work/superatoms")
REPO = Path("/root/C-MAGE")
RUN = REPO / "benchmarks/published_runs/sonnet55_api_superatoms/synth"
IMG = RUN / "images"
TARGET = 300
MAX_HEAVY = 60
SEED = 20261009
DEFS = A.ALL_V2


def gate(it):
    """-> (item with condensed mol, None) or (None, reason)."""
    m = Chem.MolFromSmiles(it["truth"])
    c = A.condense(m, defs=DEFS)
    labs = A.labels_of(c)
    if len(labs) < 2:
        return None, "fewer than 2 labels"
    if A.canon(A.expand(c)) != A.canon(m):
        return None, "expand != truth"
    layout = None
    if label_clash(c):
        rdDepictor.SetPreferCoordGen(True)
        rdDepictor.Compute2DCoords(c)
        rdDepictor.SetPreferCoordGen(False)
        if label_clash(c):
            return None, "labels overlap in the drawing"
        layout = "coordgen"
    drawn = svg_labels(c)
    bad = [a.GetProp("atomLabel") for a in c.GetAtoms() if a.HasProp("atomLabel")
           and drawn.get(a.GetIdx()) not in label_forms(a.GetProp("atomLabel"))]
    if bad:
        return None, f"label not drawn as text: {bad}"
    return dict(it, labels=labs, _c=c, layout=layout, heavy=m.GetNumHeavyAtoms()), None


def main():
    old = json.load(open(RUN / "set.json"))
    have = {A.canon(x["truth"]) for x in old}
    used_keys = {x["key"] for x in old if x.get("key")}
    n0 = max(int(x["id"][3:]) for x in old)
    assert n0 == 175, n0
    man = list(csv.DictReader(open(REPO / "corpus_images/manifest.csv")))
    led = {json.loads(l)["k"] for l in open(REPO / "benchmarks/published_runs/sonnet55_api/ledger.jsonl")
           if json.loads(l)["status"] == "ok"}
    by_can, cands = {}, []
    for r in man:
        m = Chem.MolFromSmiles(r["truth_smiles"])
        if m is None:
            continue
        by_can[A.canon(m)] = r
        if r["key"] in used_keys or r["key"] not in led or m.GetNumHeavyAtoms() > MAX_HEAVY:
            continue
        labs = A.labels_of(A.condense(m, defs=DEFS))
        if len(labs) >= 2 and A.canon(m) not in have:
            cands.append(dict(src="corpus", key=r["key"], name=r["name"], cid=r["pubchem_cid"],
                              truth=r["truth_smiles"], labels=labs))
    rej, pubs, seen = [], [], set(have)
    pub = json.load(open(ROOT / "more/pubchem2.json"))
    for n, v in pub.items():
        if not v:
            continue
        m = Chem.MolFromSmiles(v["smiles"])
        if m is None:
            continue
        cn = A.canon(m)
        if cn in seen:
            rej.append(dict(name=n, cid=v["cid"], why="already in the set / duplicate pick")); continue
        seen.add(cn)
        r = by_can.get(cn)
        if r is not None:        # a list molecule that IS a corpus molecule: corpus record and truth
            if r["key"] in led and r["key"] not in used_keys:
                it = next((c for c in cands if c["key"] == r["key"]), None)
                if it:
                    it["forced"] = True
            else:
                rej.append(dict(name=n, cid=v["cid"], why="corpus molecule not readable as a pair")); continue
            continue
        if m.GetNumHeavyAtoms() > MAX_HEAVY:
            rej.append(dict(name=n, cid=v["cid"], why=f"> {MAX_HEAVY} heavy atoms")); continue
        it = dict(src="pubchem", key=None, name=n, cid=v["cid"], truth=v["smiles"])
        g, why = gate(it)
        if g:
            pubs.append(g)
        else:
            rej.append(dict(it, why=why))
    chosen = []
    for c in [c for c in cands if c.get("forced")]:
        g, why = gate(c)
        (chosen.append(g) if g else rej.append(dict(c, why=why)))
    freq = collections.Counter(l for c in pubs + chosen + old for l in set(c["labels"]))
    pool = sorted([c for c in cands if not c.get("forced")], key=lambda c: c["key"])
    while len(pubs) + len(chosen) < TARGET and pool:
        best = max(pool, key=lambda c: (sum(1 / (1 + freq[l]) for l in set(c["labels"])), len(c["labels"]), c["key"]))
        pool.remove(best)
        g, why = gate(best)
        if not g:
            rej.append(dict(best, why=why)); continue
        chosen.append(g)
        freq.update(set(g["labels"]))
    items = pubs + chosen
    random.Random(SEED).shuffle(items)
    out = []
    for i, it in enumerate(items, n0 + 1):
        sid = f"sa_{i:04d}"
        c = it.pop("_c")
        tmp = ROOT / "more/tmp.png"
        A.render(c, 1500, tmp)
        im = Image.open(tmp); im.load()
        png = IMG / f"{sid}.png"
        assert not png.exists(), png
        im.convert("RGB").save(png)            # re-encode: pixels only
        assert_clean(png)
        nd = lambda x: re.sub(r"[\d,._]", "", x).replace("0", "O")
        txt = nd(ocr_text(png))
        miss = [l for l in sorted(set(it["labels"])) if not any(nd(f) in txt for f in label_forms(l))]
        rec = dict(src=it["src"], key=it["key"], name=it["name"], cid=it["cid"], truth=it["truth"],
                   labels=it["labels"], id=sid, cx=Chem.MolToCXSmiles(c), heavy=it["heavy"],
                   n_labels=len(it["labels"]), ocr_missing=miss, plain_key=it["key"], png=str(png),
                   batch="2026-10-09", abbrev="v2", show=True)
        if it.get("layout"):
            rec["layout"] = it["layout"]
        out.append(rec)
    json.dump(out, open(ROOT / "more/synth_new.json", "w"), indent=1)
    json.dump(rej, open(ROOT / "more/rejected2.json", "w"), indent=1)
    # one write per file, after every gate passed
    json.dump(old + out, open(RUN / "set.json", "w"), indent=1)
    rs = json.load(open(RUN / "run_set.json"))
    assert [x["id"] for x in rs] == [x["id"] for x in old]
    json.dump(rs + [{"id": o["id"], "png": o["png"], "truth": o["truth"]} for o in out],
              open(RUN / "run_set.json", "w"), indent=0)
    print(f"{len(out)} built ({sum(o['src'] == 'corpus' for o in out)} corpus, "
          f"{sum(o['src'] == 'pubchem' for o in out)} PubChem), {len(rej)} rejected "
          f"{dict(collections.Counter(r['why'].split(':')[0] for r in rej))}; OCR missed a label on "
          f"{sum(1 for o in out if o['ocr_missing'])}")
    print(collections.Counter(l for o in out for l in set(o["labels"])).most_common())


if __name__ == "__main__":
    main()
