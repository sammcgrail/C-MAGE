#!/usr/bin/env python3
"""Build the "Attachment-point fragments (wavy bond)" set from wavy_scan.py's candidates (USPTO ODP grants, CWU
TIF + the applicant's ChemDraw MOL).

Truth, from the MOL alone (wavy_truth): ChemDraw writes the wavy line as stereo-4 ('either') single bonds from the
point where it meets the attachment bond (the crossing atom X) to the line's end points (degree-1 carbons). Those end
points are deleted; X becomes the attachment `*`; if the bond is drawn running on THROUGH the wavy line, the stub
beyond it (the only other degree-1 neighbour of X) is deleted too. X must then have exactly one real neighbour
(else rejected). A drawing qualifies only when the MOL has nothing else open: no R/pseudo/alias atom, no R-group or
APO block, no Sgroup but SUP, one fragment, >= 3 real heavy atoms, sanitises, round-trips.

    wavy_build.py select [--n 60]     candidates -> spread picks -> /root/cmage-work/wavy/picked.json + review grids
    wavy_build.py write  ID ...        write the run set (only the ids that passed the visual check)"""
import collections, json, random, re, sys
from pathlib import Path
from rdkit import Chem, RDLogger
RDLogger.DisableLog("rdApp.*")
sys.path.insert(0, str(Path(__file__).parent))
import wavy_scan
WORK = Path("/root/cmage-work/wavy")
RUN = Path("/root/C-MAGE/benchmarks/published_runs/sonnet55_api_superatoms/wavy")
SEED = 20261009


def wavy_truth(txt):
    g = wavy_scan.wavy_glyph(txt)
    if not g:
        return None, "no wavy glyph"
    # sanitised parse: RDKit reads wedge chirality AND double-bond geometry from the 2D MOL here (an unsanitised
    # parse lost every E/Z); the wavy-line atoms are removed afterwards and stereo re-perceived
    m = Chem.MolFromMolBlock(txt, sanitize=True, removeHs=False)
    if m is None:
        return None, "MOL unreadable"
    rw = Chem.RWMol(m)
    glyph = {y - 1 for _, ys in g for y in ys}
    cross = [x - 1 for x, _ in g]
    drop = set(glyph)
    for x in cross:
        nb = [n.GetIdx() for n in rw.GetAtomWithIdx(x).GetNeighbors() if n.GetIdx() not in glyph]
        if len(nb) == 2:
            stubs = [n for n in nb if rw.GetAtomWithIdx(n).GetDegree() == 1 and rw.GetAtomWithIdx(n).GetAtomicNum() == 6]
            if len(stubs) != 1:
                return None, "crossing atom: cannot tell the stub from the fragment"
            # the wavy line must cut a STRAIGHT bond (fragment atom - X - stub within 15 degrees of collinear); at a
            # zigzag vertex X is itself a drawn carbon and the cut bond is the next one: ambiguous, rejected
            import math
            c = m.GetConformer()
            p0, px, ps = (c.GetAtomPosition(i) for i in ([n for n in nb if n != stubs[0]][0], x, stubs[0]))
            v1, v2 = (p0.x - px.x, p0.y - px.y), (ps.x - px.x, ps.y - px.y)
            ang = math.degrees(math.acos(max(-1, min(1, (v1[0] * v2[0] + v1[1] * v2[1]) /
                                                     (math.hypot(*v1) * math.hypot(*v2) or 1)))))
            if ang < 165:
                return None, "wavy line at a zigzag vertex (ambiguous)"
            drop.add(stubs[0])
            nb = [n for n in nb if n != stubs[0]]
        if len(nb) != 1:
            return None, f"crossing atom has {len(nb)} real neighbours"
        a = rw.GetAtomWithIdx(x)
        a.SetAtomicNum(0); a.SetFormalCharge(0); a.SetNoImplicit(True); a.SetNumExplicitHs(0)
    for b in rw.GetBonds():
        b.SetBondDir(Chem.BondDir.NONE)
    for i in sorted(drop, reverse=True):
        rw.RemoveAtom(i)
    m = rw.GetMol()
    try:
        Chem.SanitizeMol(m)
        # E/Z: the removed wavy-line atoms were often a double bond's reference atoms, so re-derive every
        # double bond's geometry from the 2D coordinates of the atoms that remain
        for b in m.GetBonds():
            if b.GetBondType() == Chem.BondType.DOUBLE:
                b.SetStereo(Chem.BondStereo.STEREONONE)
        Chem.DetectBondStereochemistry(m)
        Chem.AssignStereochemistry(m, cleanIt=True, force=True)
        m = Chem.RemoveHs(m)
    except Exception as e:
        return None, f"sanitize: {e}"[:80]
    smi = Chem.MolToSmiles(m)
    if "." in smi:
        return None, "more than one fragment"
    m2 = Chem.MolFromSmiles(smi)
    if m2 is None or Chem.MolToSmiles(m2) != smi:
        return None, "no round trip"
    real = sum(1 for a in m2.GetAtoms() if a.GetAtomicNum() > 0)
    if real < 3:
        return None, "fewer than 3 real atoms"
    return smi, None


def kind(smi):
    m = Chem.MolFromSmiles(smi)
    n_att = sum(1 for a in m.GetAtoms() if a.GetAtomicNum() == 0)
    if n_att >= 2:
        return "multi-attachment"
    arom = [a for a in m.GetAtoms() if a.GetIsAromatic()]
    if arom:
        return "heteroaryl" if any(a.GetAtomicNum() not in (6,) for a in arom) else "aryl"
    if m.GetRingInfo().NumRings():
        return "ring"
    return "alkyl/acyclic"


def select(n):
    rows = [json.loads(l) for l in open(WORK / "scan2.jsonl")]
    # alias blocks are tested on the MOL text itself: ChemDraw writes CRLF, so the scan's `\n`-anchored alias
    # regex missed them, and a stacked "H/N" label (alias "H\r\nN") was exported as a bare C (5 rows caught late)
    rows = [r for r in rows if not r["pseudo"] and not r["alias"] and not r["rgp"] and not r["apo"]
            and all("SUP" in s for s in r["sgroup"])
            and not re.search(r"^A  ", Path(r["mol"]).read_text(encoding="latin-1"), re.M)]
    ok, why = [], collections.Counter()
    seen = set()
    for r in rows:
        txt = Path(r["mol"]).read_text(encoding="latin-1")
        smi, w = wavy_truth(txt)
        if not smi:
            why[w] += 1; continue
        if smi in seen:
            why["duplicate"] += 1; continue
        seen.add(smi)
        ok.append(dict(r, truth=smi, kind=kind(smi), patent=r["id"].rsplit("-", 1)[0]))
    print(len(rows), "clean candidates;", len(ok), "with a truth;", dict(why))
    print(collections.Counter(o["kind"] for o in ok))
    rng = random.Random(SEED)
    by = collections.defaultdict(list)
    for o in sorted(ok, key=lambda o: o["id"]):
        by[o["kind"]].append(o)
    picks, pp = [], collections.Counter()
    order = ["alkyl/acyclic", "ring", "heteroaryl", "aryl", "multi-attachment"]
    for b in by.values():
        rng.shuffle(b)
    while len(picks) < n and any(by.values()):
        for k in order:
            while by[k]:
                o = by[k].pop()
                if pp[o["patent"]] < 3:
                    picks.append(o); pp[o["patent"]] += 1
                    break
            if len(picks) >= n:
                break
    json.dump(picks, open(WORK / "picked.json", "w"), indent=1)
    from PIL import Image, ImageDraw
    for gi in range(0, len(picks), 12):
        ims = []
        for o in picks[gi:gi + 12]:
            im = Image.open(o["tif"]).convert("L")
            im.thumbnail((380, 300))
            c = Image.new("L", (400, 340), 255)
            c.paste(im, (10, 10))
            ImageDraw.Draw(c).text((10, 318), f"{picks.index(o)} {o['truth'][:52]}", fill=0)
            ims.append(c)
        G = Image.new("L", (1600, 340 * ((len(ims) + 3) // 4)), 255)
        for k, c in enumerate(ims):
            G.paste(c, ((k % 4) * 400, (k // 4) * 340))
        G.save(WORK / f"review_{gi // 12}.png")
    print(len(picks), "picked", collections.Counter(o["kind"] for o in picks))


def write(idx):
    picks = json.load(open(WORK / "picked.json"))
    sys.path.insert(0, str(Path(__file__).parent))
    from big_expand import clean_png
    RUN.mkdir(parents=True, exist_ok=True)
    img = WORK / "images"
    img.mkdir(exist_ok=True)
    rows = []
    sel = [picks[i] for i in idx]
    random.Random(SEED).shuffle(sel)
    for i, o in enumerate(sel, 1):
        rid = f"wv_{i:04d}"
        t, why = wavy_truth(Path(o["mol"]).read_text(encoding="latin-1"))      # always re-derived from the MOL
        assert t, (o["id"], why)
        o = dict(o, truth=t, kind=kind(t))
        p = img / f"{rid}.png"
        clean_png(o["tif"], p)
        rows.append({"id": rid, "src": "USPTO-ODP", "orig_id": o["id"], "orig_file": o["tif"], "orig_mol": o["mol"],
                     "patent": o["patent"], "week": o["week"], "png": str(p), "truth": o["truth"], "labels": [],
                     "kind": o["kind"], "n_attach": o["truth"].count("*"), "show": True,
                     "heavy": Chem.MolFromSmiles(o["truth"]).GetNumHeavyAtoms(), "score": "attach_norm"})
    json.dump(rows, open(RUN / "set.json", "w"), indent=1)
    json.dump([{"id": r["id"], "png": r["png"], "truth": r["truth"]} for r in rows], open(RUN / "run_set.json", "w"), indent=0)
    print(len(rows), "written", collections.Counter(r["kind"] for r in rows))


if __name__ == "__main__":
    if sys.argv[1] == "select":
        select(int(sys.argv[3]) if len(sys.argv) > 3 else 60)
    else:
        write([int(x) for x in sys.argv[2:]])
