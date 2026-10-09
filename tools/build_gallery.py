#!/usr/bin/env python3
"""The "Gallery" tab: every image the LLM vs OCR tab scores, filterable by molecule type.

    build_gallery.py               rebuild wall/gallery.json from wall/llmocr.json + wall/llmocr_detail.json
    build_gallery.py show TYPE [N] print N random members of a type (name + reference SMILES), to hand-check
    build_gallery.py near TYPE [N] print N random NON-members (false-negative spot check)

Nothing is scored here. The verdict codes are copied from wall/llmocr.json, which build_llmocr.py writes
from every arm's ledger through sonnet_batch.verdict() (corpus, superatoms built/real, the big set: one row
per image, codes in arm order). So the Gallery's numbers are the LLM vs OCR tab's numbers, cut by type;
run this after build_llmocr.py, in the same publish step. The truth SMILES (llmocr_detail.json "t") is
used only to compute the types and the heavy-atom count; it is not shipped in this payload.

Types are multi-label, from RDKit on the reference molecule (the largest fragment for most tests; the
whole thing for "metal" and "multi-component"). A type ships only with >= MIN_N images.
"""
from __future__ import annotations

import json
import os
import random
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
WALL = REPO / "benchmarks" / "wall"
SRC = WALL / "llmocr.json"
DETAIL = WALL / "llmocr_detail.json"
OUT = WALL / "gallery.json"
MIN_N = 10

from rdkit import Chem, RDLogger  # noqa: E402
from rdkit.Chem import RDConfig  # noqa: E402
RDLogger.DisableLog("rdApp.*")

# The PROTAC E3-ligand motifs are the big set's own (tools/superatoms/big_index.py), so a PROTAC means the
# same thing on every tab.
sys.path.insert(0, str(HERE / "superatoms"))
_argv, sys.argv = sys.argv, sys.argv[:1]          # big_index reads sys.argv[1] at import
import big_index as BI  # noqa: E402
sys.argv = _argv

S = Chem.MolFromSmarts
METALS = {3, 4, 11, 12, 13, 19, 20, 37, 38, 55, 56, 87, 88} | set(range(21, 31)) | set(range(39, 49)) \
    | set(range(57, 81)) | {31, 49, 50, 81, 82, 83, 84} | set(range(89, 104))
IONS = {3, 11, 19, 37, 55, 4, 12, 20, 38, 56}     # Li Na K Rb Cs, Be Mg Ca Sr Ba

P = {
    "betalactam": S("[#8]=[#6;r4]1~[#6;r4]~[#6;r4]~[#7;r4]1"),
    "sulfonamide": S("[#6]-[SX4](=O)(=O)-[NX3]"),
    # 4-quinolone-3-carboxylic acid (or ester) with the 6-fluoro: cipro-, levo-, moxifloxacin...
    "fq": S("[#6](=O)(-[#8])-[#6]1=[#6]-[#7]-[#6]2=[#6]-[#6]=[#6](-F)-[#6]=[#6]-2-[#6]-1=O"),
    "fq_ar": S("[#6](=O)(-[#8])-[#6]1:[#6]:[#7]:[#6]2:[#6]:[#6]:[#6](-F):[#6]:[#6]:2:[#6]:1=O"),
    # 1,4- and 1,5-benzodiazepine: benzene fused to a 7-ring holding two N
    "bzd14": S("c12ccccc1~[#7]~[#6]~[#6;!a]~[#7]~[#6]2"),
    "bzd15": S("c12ccccc1~[#7]~[#6]~[#6;!a]~[#6]~[#7]2"),     # C3 not aromatic: drops the dibenzo-/thieno-
                                                              # benzodiazepines (clozapine, olanzapine, dibenzepin)
    "steroid": S("[#6]1~[#6]~[#6]~[#6]2~[#6](~[#6]~1)~[#6]~[#6]~[#6]1~[#6]~2~[#6]~[#6]~[#6]2~[#6]~[#6]~[#6]~[#6]~1~2"),
    # HMG-CoA mimic: the 3,5-dihydroxy acid (or ester / salt) or its delta-lactone
    # (acyclic, two carbons on to a ring, so the 1,3-polyol of a polyene macrolide does not count)
    "statin": S("[#8;X2H1,X1-,X2;!R]-[#6;!R](=O)-[CH2;!R]-[CH1;!R](-[OX2H1])-[CH2;!R]-[CH1;!R](-[OX2H1])-[#6;!R]~[#6;!R]-[#6,#7;R]"),
    "statin_l": S("O=C1-[CH2]-[CH1](-[OX2H1])-[CH2]-[CH1](-[CH2]-[CH2]-[#6;R])-O1"),
    "barbiturate": S("O=C1-[#7]-C(=O)-[#6]-C(=O)-[#7]-1"),
    "phenothiazine": S("c1cccc2c1[#7]c1ccccc1[#16]2"),
    # nucleoside: a nucleobase ring N on C1' of an oxolane (ribose, deoxyribose, 4'-thio / carbocyclic not counted)
    "nucleoside": S("[n;R]-[#6;R1]1-[#8,#16;R1]-[#6;R1]-[#6;R1]-[#6;R1]-1"),
    "phosphate": S("P(=O)(~[#8])~[#8]"),
    # pyranose: a 6-ring of 5 C + 1 O with >= 3 ring carbons bearing O; furanose: 5-ring with 2 ring C-O
    "pyranose": S("[#8;R1]1-[#6;R1](-[#8,#7])-[#6;R1](-[#8])-[#6;R1](-[#8])-[#6;R1]-[#6;R1]-1"),
    "pyranose2": S("[#8;R1]1-[#6;R1]-[#6;R1](-[#8])-[#6;R1](-[#8])-[#6;R1](-[#8])-[#6;R1]-1"),
    "furanose": S("[#8;R1]1-[#6;R1](-[#8,#7,n])-[#6;R1](-[#8])-[#6;R1](-[#8])-[#6;R1]-1"),
    "dhp": S("[#6]1(-[#6]=O)=[#6]-[#7H1]-[#6]=[#6](-[#6]=O)-[#6H1]-1-c"),
    # A residue N-Ca-C(=O)-N whose N is an amide N or a free amine (big_index.RES also takes a tertiary
    # amine, which made a DOTA-amide gadolinium agent a "peptide").
    "res": S("[NX3;!$(N=*);$(N-[#6]=O),$([NX3;!H0]),$([NX4+;!H0])][CX4;H1,H2][CX3](=O)[NX3]"),
}
MORPHINAN = Chem.MolFromSmiles("C1CCC23CCNC(C2C1)Cc1ccccc31")
_q = Chem.AdjustQueryParameters()
_q.makeBondsGeneric = True
_q.aromatizeIfPossible = False
_q.adjustDegree = False
_q.adjustRingCount = False
MORPHINAN = Chem.AdjustQueryProperties(MORPHINAN, _q)

_NP = None


def np_score(m):
    """RDKit Contrib NP-likeness (Ertl 2008): > ~1 reads as natural-product-like."""
    global _NP
    if _NP is None:
        sys.path.insert(0, os.path.join(RDConfig.RDContribDir, "NP_Score"))
        import npscorer
        _NP = (npscorer, npscorer.readNPModel())
    return _NP[0].scoreMol(m, _NP[1])


# Display order and grouping. key -> (label, group). Groups: drug classes, structure, size, drawing.
TYPES = [
    ("protac", "PROTAC", "drug"),
    ("betalactam", "β-lactam", "drug"),
    ("steroid", "Steroid", "drug"),
    ("nucleoside", "Nucleoside / nucleotide", "drug"),
    ("fq", "Fluoroquinolone", "drug"),
    ("bzd", "Benzodiazepine", "drug"),
    ("morphinan", "Morphinan opioid", "drug"),
    ("statin", "Statin", "drug"),
    ("barbiturate", "Barbiturate", "drug"),
    ("phenothiazine", "Phenothiazine", "drug"),
    ("dhp", "Dihydropyridine", "drug"),
    ("sulfonamide", "Sulfonamide", "drug"),
    ("peptide", "Peptide", "struct"),
    ("cpeptide", "Cyclic peptide", "struct"),
    ("macrocycle", "Macrocycle (ring ≥12)", "struct"),
    ("np", "Natural-product-like", "struct"),
    ("sugar", "Glycoside / sugar", "struct"),
    ("metal", "Metal / organometallic", "struct"),
    ("salt", "Salt / multi-component", "struct"),
    ("stereo", "Has stereocentres", "struct"),
    ("sa", "Superatom labels", "struct"),
    ("h15", "≤15 atoms", "size"),
    ("h30", "16–30 atoms", "size"),
    ("h50", "31–50 atoms", "size"),
    ("h51", ">50 atoms", "size"),
]
GROUPS = [("drug", "Drug class"), ("struct", "Structure"), ("size", "Size")]


def classify(smiles: str, src: str) -> tuple[list[str], int | None]:
    """Types of one reference molecule, and its heavy-atom count (all fragments)."""
    t = ["sa"] if src in ("b", "r", "g") else []
    whole = Chem.MolFromSmiles(smiles or "")
    if whole is None:
        return t, None
    ha = whole.GetNumHeavyAtoms()
    t.append("h15" if ha <= 15 else "h30" if ha <= 30 else "h50" if ha <= 50 else "h51")
    frags = Chem.GetMolFrags(whole, asMols=True)
    if len(frags) > 1:
        t.append("salt")
    # A metal bonded to something (organometallic, coordination), or any metal other than a group 1/2
    # counter-ion: sodium and calcium salts are "salt", not "metal".
    if any(a.GetAtomicNum() in METALS and (a.GetDegree() or a.GetAtomicNum() not in IONS) for a in whole.GetAtoms()):
        t.append("metal")
    m = max(frags, key=lambda f: f.GetNumHeavyAtoms())
    h = lambda k: m.HasSubstructMatch(P[k])
    if ha >= 40 and (m.HasSubstructMatch(BI.IMID) or m.HasSubstructMatch(BI.IMID2) or m.HasSubstructMatch(BI.VHL)):
        t.append("protac")
    if h("betalactam"):
        t.append("betalactam")
    if h("steroid"):
        t.append("steroid")
    if h("nucleoside"):
        t.append("nucleoside")
    if h("fq") or h("fq_ar"):
        t.append("fq")
    if h("bzd14") or h("bzd15"):
        t.append("bzd")
    if m.HasSubstructMatch(MORPHINAN):
        t.append("morphinan")
    if h("statin") or h("statin_l"):
        t.append("statin")
    if h("barbiturate"):
        t.append("barbiturate")
    if h("phenothiazine"):
        t.append("phenothiazine")
    if h("dhp"):
        t.append("dhp")
    if h("sulfonamide"):
        t.append("sulfonamide")
    # Peptide: >= 3 distinct alpha carbons in an N-Ca-C(=O)-N residue (P["res"], a stricter big_index.RES;
    # the big set needs >= 4 for its own class, the tab asks for >= 3).
    res = {x[1] for x in m.GetSubstructMatches(P["res"])}
    rings = m.GetRingInfo().AtomRings()
    if len(res) >= 3:
        t.append("peptide")
        # Cyclic: some ring of >= 12 atoms runs through >= 3 of those alpha carbons (head-to-tail,
        # side-chain lactam, depsipeptide); a proline ring alone (5 atoms) never qualifies.
        if any(len(r) >= 12 and len(res & set(r)) >= 3 for r in rings):
            t.append("cpeptide")
    if any(len(r) >= 12 for r in rings):
        t.append("macrocycle")
    # Defined (assigned) tetrahedral centres only: an undrawn centre is not something a reader can miss.
    if Chem.FindMolChiralCenters(m, includeUnassigned=False, useLegacyImplementation=False):
        t.append("stereo")
    if h("pyranose") or h("pyranose2") or h("furanose"):
        t.append("sugar")
    if "metal" not in t:
        try:
            if np_score(m) >= 1.0:
                t.append("np")
        except Exception:
            pass
    return t, ha


def load():
    lo = json.load(open(SRC))
    det = json.load(open(DETAIL))
    return lo, det


def build() -> int:
    import fcntl
    with open("/tmp/cmage-wall-build.lock", "w") as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        return _build()


def _build() -> int:
    lo, det = load()
    ids = [a["id"] for a in lo["arms"]]
    rows, cnt, nohit = [], {k: 0 for k, _, _ in TYPES}, 0
    for k, name, code, src in lo["rows"]:
        tr = (det.get(k) or {}).get("t")
        if not tr:
            nohit += 1
        types, ha = classify(tr, src)
        for x in types:
            cnt[x] += 1
        rows.append([k, name, code, src, ha, types])
    keep = [(k, lab, g) for k, lab, g in TYPES if cnt[k] >= MIN_N]
    kept = {k for k, _, _ in keep}
    idx = {k: i for i, (k, _, _) in enumerate(keep)}
    # Ship each row's types as indices into the payload's type list (compact), dropped types removed.
    out_rows = [[k, name, code, src, ha, [idx[x] for x in types if x in kept]] for k, name, code, src, ha, types in rows]
    srcs = [("c", "Corpus"), ("b", "Superatoms, built"), ("r", "Superatoms, real"), ("g", "Big (≥50 atoms)")]
    out = {
        "built": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "from": lo["built"],
        "arms": [{x: a[x] for x in ("id", "label", "short", "tag", "kind", "color")} for a in lo["arms"]],
        "types": [{"k": k, "label": lab, "g": g, "n": cnt[k]} for k, lab, g in keep],
        "groups": [{"k": g, "label": lab} for g, lab in GROUPS],
        "dropped": [{"k": k, "label": lab, "n": cnt[k]} for k, lab, g in TYPES if k not in kept],
        "sources": [{"k": s, "label": lab, "n": sum(1 for r in rows if r[3] == s)} for s, lab in srcs
                    if any(r[3] == s for r in rows)],
        "note": "Exact = the reference molecule after RDKit canonicalisation, stereo included. Each reader is "
                "scored on the images it read in the current filter; the scores are the LLM vs OCR tab's, "
                "cut by molecule type. Types are computed with RDKit from the reference structure and overlap.",
        "rows": out_rows,
    }
    tmp = OUT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(out, separators=(",", ":"), ensure_ascii=False))
    os.replace(tmp, OUT)
    print(f"wrote {OUT.name} ({OUT.stat().st_size / 1e3:.0f} KB): {len(out_rows)} images, "
          f"{len(keep)} types shipped; rows without a reference: {nohit}")
    for k, lab, g in TYPES:
        sel = [r for r in rows if k in r[5]]
        per = []
        for i, a in enumerate(ids):
            rd = [r for r in sel if r[2][i] in "eswi"]
            ex = sum(1 for r in rd if r[2][i] == "e")
            per.append(f"{a} {ex}/{len(rd)}" + (f"={ex / len(rd) * 100:.0f}%" if rd else ""))
        print(f"  {'+' if k in kept else '-'} {lab:28s} n={cnt[k]:5d}  " + "  ".join(per))
    return 0


def show(kind: str, n: int, near: bool = False):
    lo, det = load()
    rows = lo["rows"][:]
    random.seed(7)
    random.shuffle(rows)
    got = 0
    for k, name, code, src in rows:
        tr = (det.get(k) or {}).get("t")
        types, ha = classify(tr, src)
        if (kind in types) != near:
            print(f"{k:50s} {name[:40]:40s} ha={ha} {','.join(types)}\n    {tr}")
            got += 1
            if got >= n:
                break


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        sys.exit(build())
    if a[0] in ("show", "near") and len(a) >= 2:
        show(a[1], int(a[2]) if len(a) > 2 else 12, near=a[0] == "near")
    else:
        raise SystemExit(__doc__)
