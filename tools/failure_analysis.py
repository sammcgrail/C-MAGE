#!/usr/bin/env python3
"""Why the readers miss: every non-exact reading of the paired corpus, classified by what differs
between the answer and the PubChem truth, with the molecule features that go with missing, the
three arms' overlap, a gallery of missed drawings with the difference highlighted, and the
fixes the data supports, each with the number of misses it would address.

Used by build_sonnet_report.py (payload key "failures"); importable on its own:

    failure_analysis.py --selftest        planted edits must land in the right class
    failure_analysis.py --sample N        print N classified misses per arm to hand-check

CLASSES, in the order they are tested (the first that applies wins):

    invalid     RDKit cannot parse the answer
    ez_added    stereo verdict, only double-bond E/Z differs, and every differing bond is one the
                truth leaves UNSPECIFIED (the answer wrote a geometry)
    ez_omitted  stereo verdict, only E/Z differs, and the truth specifies a bond the answer left
                out or flipped
    tet         stereo verdict, tetrahedral centres differ (or centres and bonds both)
    iso         same molecule once isotope labels are dropped (a stereo verdict's isotope case,
                or a wrong verdict that is only deuterium labels)
    fragment    the largest fragments agree once charges are neutralised: a counter-ion dropped
                or invented, a phantom fragment, a charge state
    bond        same heavy atoms, same wiring once every bond is single: bond order or aromaticity
    connect     same heavy atoms, different wiring (ring size, substituent moved, ring opened)
    element     same number of heavy atoms, different elements (N read as C, Cl as F)
    atoms       different number of heavy atoms (a methyl missed, a ring written one short)

The classifier is checked by --selftest on planted edits of one molecule (one edit per class)
and build_sonnet_report refuses to publish if it fails.
"""
import glob
import io
import json
import os
import sys
from collections import Counter
from pathlib import Path

from rdkit import Chem, RDLogger
from rdkit.Chem import rdDepictor, rdFMCS, rdMolDescriptors
from rdkit.Chem.Draw import rdMolDraw2D
from rdkit.Chem.MolStandardize import rdMolStandardize

RDLogger.DisableLog("rdApp.*")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

CATS = [  # key, label, one-line meaning
    ("ez_added", "E/Z added (truth unspecified)", "the answer gives a double bond a geometry the PubChem record leaves open"),
    ("ez_omitted", "E/Z omitted or flipped (truth specifies)", "a specified double-bond geometry left out or reversed"),
    ("tet", "Tetrahedral stereo", "one or more stereocentres differ (sometimes with a double bond too)"),
    ("iso", "Isotope labels", "the same molecule once deuterium or other labels are dropped"),
    ("fragment", "Fragment, charge or counter-ion", "largest fragments agree once neutralised: a counter-ion, phantom fragment or charge state"),
    ("bond", "Bond order or aromaticity", "same atoms and wiring; a double bond or aromatic ring differs"),
    ("connect", "Ring size or connectivity", "same atoms, different wiring"),
    ("element", "Wrong atom or element", "same atom count, an element swapped"),
    ("atoms", "Missing or extra atoms", "a different number of heavy atoms"),
    ("invalid", "Unparseable", "RDKit cannot read the answer"),
]
CAT_LABEL = {k: l for k, l, _ in CATS}
ARMS = [("s55", "Sonnet 5.5"), ("s5", "Sonnet 5"), ("cx", "CXMolScribe")]
METALS = set(list(range(3, 5)) + list(range(11, 14)) + list(range(19, 32)) + list(range(37, 51))
             + list(range(55, 84)) + list(range(87, 104)))   # alkali to post-transition, incl. B? no: 5 is boron, excluded
METALS -= {5, 14, 32, 33, 34, 51, 52}   # B, Si, Ge, As, Se, Sb, Te are not metals here
_EZ = {Chem.BondStereo.STEREOE: "E", Chem.BondStereo.STEREOZ: "Z",
       Chem.BondStereo.STEREOTRANS: "E", Chem.BondStereo.STEREOCIS: "Z"}


# ---------------------------------------------------------------- molecule helpers
def mol(s):
    return Chem.MolFromSmiles(s) if s else None


def canon(m, stereo=True):
    return Chem.MolToSmiles(m, isomericSmiles=stereo) if m is not None else None


def strip(m, db=False, tet=False, iso=False):
    m = Chem.Mol(m)
    if iso:
        for a in m.GetAtoms():
            a.SetIsotope(0)
        m = Chem.RemoveHs(m)
    if tet:
        for a in m.GetAtoms():
            a.SetChiralTag(Chem.ChiralType.CHI_UNSPECIFIED)
    if db:
        for b in m.GetBonds():
            if b.GetBondType() == Chem.BondType.DOUBLE:
                b.SetStereo(Chem.BondStereo.STEREONONE)
            if b.GetBondDir() in (Chem.BondDir.ENDUPRIGHT, Chem.BondDir.ENDDOWNRIGHT):
                b.SetBondDir(Chem.BondDir.NONE)
    return Chem.MolToSmiles(m)


def largest_fragment(m):
    frags = Chem.GetMolFrags(m, asMols=True, sanitizeFrags=False)
    return max(frags, key=lambda f: f.GetNumHeavyAtoms()) if frags else m


_UNCHARGER = rdMolStandardize.Uncharger()


def neutral_core(m):
    """Largest fragment, charges neutralised, no stereo, no isotopes: the 'same molecule' test
    behind the fragment/charge class."""
    try:
        f = Chem.Mol(largest_fragment(m))
        f.UpdatePropertyCache(strict=False)
        Chem.SanitizeMol(f, catchErrors=True)
        f = _UNCHARGER.uncharge(f)
        return strip(f, db=True, tet=True, iso=True)
    except Exception:
        return None


def neutral_all(m):
    """Every fragment neutralised and stripped, sorted: catches a charge state written differently
    on an ionic solid (As2O3 as [O-2] vs [O-]) where no fragment is 'the' molecule."""
    try:
        out = []
        for f in Chem.GetMolFrags(m, asMols=True, sanitizeFrags=False):
            f = Chem.Mol(f)
            f.UpdatePropertyCache(strict=False)
            Chem.SanitizeMol(f, catchErrors=True)
            f = _UNCHARGER.uncharge(f)
            for a in f.GetAtoms():
                a.SetFormalCharge(0)
                a.SetNumExplicitHs(0)
                a.SetNoImplicit(False)
                a.SetNumRadicalElectrons(0)
            f.UpdatePropertyCache(strict=False)
            Chem.SanitizeMol(f, catchErrors=True)
            out.append(strip(f, db=True, tet=True, iso=True))
        return ".".join(sorted(out))
    except Exception:
        return None


def skeleton(m):
    """Every bond single, nothing aromatic, no charges, no stereo, no isotopes: the wiring alone."""
    rw = Chem.RWMol(m)
    for a in rw.GetAtoms():
        a.SetIsAromatic(False)
        a.SetFormalCharge(0)
        a.SetNumExplicitHs(0)
        a.SetNoImplicit(False)
        a.SetChiralTag(Chem.ChiralType.CHI_UNSPECIFIED)
        a.SetIsotope(0)
    for b in rw.GetBonds():
        b.SetBondType(Chem.BondType.SINGLE)
        b.SetIsAromatic(False)
        b.SetStereo(Chem.BondStereo.STEREONONE)
    m2 = rw.GetMol()
    try:
        m2.UpdatePropertyCache(strict=False)
        Chem.FastFindRings(m2)
        return Chem.MolToSmiles(m2)
    except Exception:
        return None


def heavy_counter(m):
    return Counter(a.GetSymbol() for a in m.GetAtoms() if a.GetAtomicNum() > 1)


def fmt_counter_diff(ct, cp):
    """'+C2 −N' style: what the answer has over the truth."""
    plus = [f"{k}{v if v > 1 else ''}" for k, v in sorted((cp - ct).items())]
    minus = [f"{k}{v if v > 1 else ''}" for k, v in sorted((ct - cp).items())]
    return (("+" + "".join(plus)) if plus else "") + ((" " if plus and minus else "") + ("−" + "".join(minus)) if minus else "")


def ez_diff(t, p):
    """Bond-by-bond E/Z comparison on identical stereo-free graphs. -> (added, omitted, flipped, bonds)
    where bonds lists (truth bond idx, pred bond idx, kind)."""
    match = p.GetSubstructMatch(t)
    out = []
    for b in t.GetBonds():
        if b.GetBondType() != Chem.BondType.DOUBLE:
            continue
        pb = p.GetBondBetweenAtoms(match[b.GetBeginAtomIdx()], match[b.GetEndAtomIdx()])
        lt, lp = _EZ.get(b.GetStereo()), _EZ.get(pb.GetStereo())
        if lt == lp:
            continue
        out.append((b.GetIdx(), pb.GetIdx(), "added" if lt is None else "omitted" if lp is None else "flipped"))
    kinds = Counter(k for _, _, k in out)
    return kinds["added"], kinds["omitted"], kinds["flipped"], out


def tet_diff(t, p):
    """Atoms (truth idx, pred idx) whose CIP label or chirality differs, on identical stereo-free graphs."""
    match = p.GetSubstructMatch(strip_mol(t))
    if not match:
        return []
    Chem.AssignStereochemistry(t, cleanIt=True, force=True)
    Chem.AssignStereochemistry(p, cleanIt=True, force=True)
    lab = lambda m, i: m.GetAtomWithIdx(i).GetPropsAsDict().get("_CIPCode")
    out = []
    for i, j in enumerate(match):
        if lab(t, i) != lab(p, j):
            out.append((i, j))
    return out


def strip_mol(m):
    m = Chem.Mol(m)
    for a in m.GetAtoms():
        a.SetChiralTag(Chem.ChiralType.CHI_UNSPECIFIED)
    for b in m.GetBonds():
        b.SetStereo(Chem.BondStereo.STEREONONE)
    return m


# ---------------------------------------------------------------- the classifier
def classify(pred: str, truth: str, verdict: str) -> dict:
    """One miss -> {cat, line, ...numbers}. `verdict` is sonnet_batch.verdict()'s word."""
    t = mol(truth)
    p = mol(pred)
    if verdict == "invalid" or p is None:
        return {"cat": "invalid", "line": "RDKit cannot parse the answer"}
    if verdict == "stereo":
        if strip(t, db=True) == strip(p, db=True):
            added, omitted, flipped, bonds = ez_diff(t, p)
            if added and not omitted and not flipped:
                return {"cat": "ez_added", "line": f"E/Z written on {added} double bond{'s' if added > 1 else ''} the truth leaves unspecified",
                        "added": added, "omitted": 0, "flipped": 0}
            parts = []
            if omitted:
                parts.append(f"{omitted} omitted")
            if flipped:
                parts.append(f"{flipped} flipped")
            if added:
                parts.append(f"{added} added")
            return {"cat": "ez_omitted", "line": "E/Z " + ", ".join(parts) + " (truth specifies)",
                    "added": added, "omitted": omitted, "flipped": flipped}
        if strip(t, tet=True) == strip(p, tet=True):
            d = tet_diff(t, p)
            n = len([a for a in t.GetAtoms() if a.GetChiralTag() != Chem.ChiralType.CHI_UNSPECIFIED])
            return {"cat": "tet", "line": f"{len(d)} of {n} stereocentres differ", "centres": len(d), "of": n}
        if strip(t, iso=True) == strip(p, iso=True):
            nt = sum(1 for a in t.GetAtoms() if a.GetIsotope())
            npp = sum(1 for a in p.GetAtoms() if a.GetIsotope())
            return {"cat": "iso", "line": f"isotope labels: {npp} read, {nt} in the truth", "read": npp, "truth": nt}
        d = tet_diff(t, p)
        return {"cat": "tet", "line": f"stereocentres and double bonds both differ ({len(d)} centres)", "centres": len(d)}
    # verdict == "wrong"
    nt, npp = neutral_core(t), neutral_core(p)
    if nt is not None and nt == npp:
        ft = Chem.GetMolFrags(t)
        fp = Chem.GetMolFrags(p)
        if len(fp) > len(ft):
            extra = [Chem.MolToSmiles(f) for f in sorted(Chem.GetMolFrags(p, asMols=True), key=lambda f: -f.GetNumHeavyAtoms())[1:]]
            return {"cat": "fragment", "line": f"extra fragment{'s' if len(fp) - len(ft) > 1 else ''}: {', '.join(extra[:3])}", "frags": [len(ft), len(fp)]}
        if len(fp) < len(ft):
            missing = [Chem.MolToSmiles(f) for f in sorted(Chem.GetMolFrags(t, asMols=True), key=lambda f: -f.GetNumHeavyAtoms())[1:]]
            return {"cat": "fragment", "line": f"counter-ion or fragment dropped: {', '.join(missing[:3])}", "frags": [len(ft), len(fp)]}
        return {"cat": "fragment", "line": "same molecule, different charge state or fragment written", "frags": [len(ft), len(fp)]}
    na_t = neutral_all(t)
    if na_t is not None and na_t == neutral_all(p):
        return {"cat": "fragment", "line": "same atoms and fragments, charges written differently"}
    if strip(t, db=True, tet=True, iso=True) == strip(p, db=True, tet=True, iso=True):
        return {"cat": "iso", "line": "isotope labels differ"}
    ct, cp = heavy_counter(t), heavy_counter(p)
    if ct == cp:
        if skeleton(t) == skeleton(p):
            return {"cat": "bond", "line": "same atoms and wiring; bond order or aromaticity differs"}
        rt, rp = rdMolDescriptors.CalcNumRings(t), rdMolDescriptors.CalcNumRings(p)
        return {"cat": "connect", "line": f"same atoms, different wiring (rings {rt} → {rp})", "rings": [rt, rp]}
    if sum(ct.values()) == sum(cp.values()):
        return {"cat": "element", "line": f"element swapped: {fmt_counter_diff(ct, cp)}", "diff": fmt_counter_diff(ct, cp)}
    d = sum(cp.values()) - sum(ct.values())
    return {"cat": "atoms", "line": f"{d:+d} heavy atom{'s' if abs(d) != 1 else ''} ({fmt_counter_diff(ct, cp)})".replace("+-", "−"), "delta": d, "diff": fmt_counter_diff(ct, cp)}


def selftest() -> list[str]:
    """Planted single edits of one molecule, each of which must land in its own class."""
    base = "C/C=C/C(=O)N[C@@H](C)c1ccnc(Cl)c1"     # E crotonamide, one centre, chloropyridine
    cases = [
        ("ez_added", "CC=CC(=O)N[C@@H](C)c1ccnc(Cl)c1", "C/C=C/C(=O)N[C@@H](C)c1ccnc(Cl)c1", "stereo"),   # truth unspecified, pred E
        ("ez_omitted", base, "CC=CC(=O)N[C@@H](C)c1ccnc(Cl)c1", "stereo"),
        ("ez_omitted", base, "C/C=C\\C(=O)N[C@@H](C)c1ccnc(Cl)c1", "stereo"),                               # flipped
        ("tet", base, "C/C=C/C(=O)N[C@H](C)c1ccnc(Cl)c1", "stereo"),
        ("iso", "[2H]C([2H])([2H])C(=O)O", "CC(=O)O", "stereo"),
        ("fragment", base, base + ".Cl", "wrong"),
        ("fragment", base + ".[Na+].[Cl-]", base, "wrong"),
        ("fragment", "CC(=O)[O-].[Na+]", "CC(=O)O", "wrong"),
        ("bond", base, "C/C=C/C(=O)N[C@@H](C)C1CCNC(Cl)C1", "wrong"),                                       # ring saturated
        ("connect", base, "C/C=C/C(=O)N[C@@H](C)c1cncc(Cl)c1", "wrong"),                                    # Cl moved
        ("element", base, "C/C=C/C(=O)N[C@@H](C)c1ccnc(F)c1", "wrong"),
        ("atoms", base, "C/C=C/C(=O)N[C@@H](CC)c1ccnc(Cl)c1", "wrong"),
        ("atoms", "c1ccc2ccccc2c1", "c1ccccc1", "wrong"),
        ("fragment", "[O-2].[O-2].[O-2].[As+3].[As+3]", "[As+3].[As+3].[O-2].[O-].[O-]", "wrong"),
        ("invalid", base, "C/C=C/C(=O)N[C@@H](C)c1ccnc(Cl)c", "invalid"),
    ]
    bad = []
    for want, truth, pred, v in cases:
        got = classify(pred, truth, v)
        if got["cat"] != want:
            bad.append(f"{want}: got {got['cat']} ({got['line']}) for {pred} vs {truth}")
    return bad


# ---------------------------------------------------------------- features (drivers)
def features(truth: str) -> dict:
    m = mol(truth)
    ha = m.GetNumHeavyAtoms()
    ri = m.GetRingInfo()
    rings = ri.NumRings()
    macro = any(len(r) >= 12 for r in ri.AtomRings())
    centres = len(Chem.FindMolChiralCenters(m, includeUnassigned=False, useLegacyImplementation=False))
    dbs = sum(1 for b in m.GetBonds() if b.GetStereo() in _EZ)
    metal = any(a.GetAtomicNum() in METALS for a in m.GetAtoms())
    frags = len(Chem.GetMolFrags(m))
    charged = any(a.GetFormalCharge() for a in m.GetAtoms())
    iso = any(a.GetIsotope() for a in m.GetAtoms())
    # drawing density: the corpus image scales the 2D layout to fit, so atoms per (longest side)^2
    # of RDKit's own layout says how crowded the picture is
    try:
        m2 = Chem.Mol(m)
        rdDepictor.Compute2DCoords(m2)
        conf = m2.GetConformer()
        xs = [conf.GetAtomPosition(i).x for i in range(m2.GetNumAtoms())]
        ys = [conf.GetAtomPosition(i).y for i in range(m2.GetNumAtoms())]
        side = max(max(xs) - min(xs), max(ys) - min(ys), 1.0)
        density = ha / (side * side)
    except Exception:
        density = None
    return {"heavy": ha, "rings": rings, "macro": macro, "stereo": centres + dbs, "metal": metal,
            "frags": frags, "charged": charged, "iso": iso, "density": density}


def feature_bins(feats: dict) -> list[tuple]:
    """(feature key, label, bin labelling function) in display order."""
    dens = sorted(f["density"] for f in feats.values() if f["density"] is not None)
    t1, t2 = dens[len(dens) // 3], dens[2 * len(dens) // 3]
    def heavy(f): return "under 25" if f["heavy"] < 25 else "25–44" if f["heavy"] < 45 else "45 or more"
    def rings(f): return "0" if f["rings"] == 0 else "1–2" if f["rings"] <= 2 else "3–4" if f["rings"] <= 4 else "5 or more"
    def stereo(f): return "0" if f["stereo"] == 0 else "1–2" if f["stereo"] <= 2 else "3–5" if f["stereo"] <= 5 else "6 or more"
    def dense(f): return "sparse" if f["density"] is None or f["density"] < t1 else "medium" if f["density"] < t2 else "dense"
    yn = lambda key: (lambda f: "yes" if f[key] else "no")
    return [
        ("heavy", "Heavy atoms", heavy, ["under 25", "25–44", "45 or more"]),
        ("rings", "Rings", rings, ["0", "1–2", "3–4", "5 or more"]),
        ("stereo", "Stereo elements (centres + E/Z bonds)", stereo, ["0", "1–2", "3–5", "6 or more"]),
        ("macro", "Macrocycle (ring of 12+)", yn("macro"), ["no", "yes"]),
        ("metal", "Metal present", yn("metal"), ["no", "yes"]),
        ("frags", "Salt or multi-component", lambda f: "yes" if f["frags"] > 1 else "no", ["no", "yes"]),
        ("charged", "Formal charges", yn("charged"), ["no", "yes"]),
        ("iso", "Isotope labels", yn("iso"), ["no", "yes"]),
        ("density", "Drawing density (atoms per area, tertiles)", dense, ["sparse", "medium", "dense"]),
    ]


# ---------------------------------------------------------------- drawing
def draw(m, dst: Path, hl_atoms=(), hl_bonds=(), size=480) -> bool:
    if dst.exists():
        return True
    try:
        from PIL import Image
        d = rdMolDraw2D.MolDraw2DCairo(size, size)
        o = d.drawOptions()
        o.bondLineWidth = 3
        o.padding = 0.06
        o.highlightBondWidthMultiplier = 10
        col = (1.0, 0.42, 0.42)
        ac = {i: col for i in hl_atoms}
        bc = {i: col for i in hl_bonds}
        mm = rdMolDraw2D.PrepareMolForDrawing(m)
        d.DrawMolecule(mm, highlightAtoms=list(hl_atoms), highlightBonds=list(hl_bonds),
                       highlightAtomColors=ac, highlightBondColors=bc)
        d.FinishDrawing()
        dst.parent.mkdir(parents=True, exist_ok=True)
        Image.open(io.BytesIO(d.GetDrawingText())).convert("RGB").quantize(colors=64, method=Image.MEDIANCUT).save(dst, optimize=True)
        return True
    except Exception:
        return False


def thumb(src: Path, dst: Path, size=480) -> bool:
    if dst.exists():
        return True
    try:
        from PIL import Image
        im = Image.open(src).convert("RGB")
        im.thumbnail((size, size), Image.LANCZOS)
        flat = Image.new("RGB", (size, size), "white")
        flat.paste(im, ((size - im.width) // 2, (size - im.height) // 2))
        dst.parent.mkdir(parents=True, exist_ok=True)
        flat.quantize(colors=32, method=Image.MEDIANCUT).save(dst, optimize=True)
        return True
    except Exception:
        return False


def highlights(t, p, cat):
    """(truth atoms, truth bonds, pred atoms, pred bonds) to colour: what differs."""
    if cat in ("ez_added", "ez_omitted"):
        try:
            _a, _o, _f, bonds = ez_diff(t, p)
            ta = [i for bi, _, _ in bonds for i in (t.GetBondWithIdx(bi).GetBeginAtomIdx(), t.GetBondWithIdx(bi).GetEndAtomIdx())]
            pa = [i for _, pi, _ in bonds for i in (p.GetBondWithIdx(pi).GetBeginAtomIdx(), p.GetBondWithIdx(pi).GetEndAtomIdx())]
            return ta, [b for b, _, _ in bonds], pa, [b for _, b, _ in bonds]
        except Exception:
            return [], [], [], []
    if cat == "tet":
        d = tet_diff(Chem.Mol(t), Chem.Mol(p))
        return [i for i, _ in d], [], [j for _, j in d], []
    if cat == "iso":
        return ([a.GetIdx() for a in t.GetAtoms() if a.GetIsotope()], [],
                [a.GetIdx() for a in p.GetAtoms() if a.GetIsotope()], [])
    # atom-level difference: maximum common substructure, highlight what is NOT shared
    try:
        res = rdFMCS.FindMCS([t, p], timeout=4, matchValences=False, ringMatchesRingOnly=True,
                             completeRingsOnly=False, bondCompare=rdFMCS.BondCompare.CompareOrder,
                             atomCompare=rdFMCS.AtomCompare.CompareElements)
        q = Chem.MolFromSmarts(res.smartsString) if res.smartsString else None
        if q is None:
            return [], [], [], []
        mt, mp = t.GetSubstructMatch(q), p.GetSubstructMatch(q)
        bt = {t.GetBondBetweenAtoms(mt[b.GetBeginAtomIdx()], mt[b.GetEndAtomIdx()]).GetIdx() for b in q.GetBonds()} if mt else set()
        bp = {p.GetBondBetweenAtoms(mp[b.GetBeginAtomIdx()], mp[b.GetEndAtomIdx()]).GetIdx() for b in q.GetBonds()} if mp else set()
        return ([a.GetIdx() for a in t.GetAtoms() if a.GetIdx() not in set(mt)],
                [b.GetIdx() for b in t.GetBonds() if b.GetIdx() not in bt],
                [a.GetIdx() for a in p.GetAtoms() if a.GetIdx() not in set(mp)],
                [b.GetIdx() for b in p.GetBonds() if b.GetIdx() not in bp])
    except Exception:
        return [], [], [], []


# ---------------------------------------------------------------- the analysis
def analyse(xs: list[dict], s5: dict, out_dir: Path, img_index: dict, max_cards: int = 44) -> dict:
    """xs: paired lane rows (5.5 + CX), s5: Sonnet 5 rows by key. out_dir: wall/report/fail.
    Only rows the Sonnet 5 arm also read are analysed, whatever the caller passes: the three arms'
    miss counts, overlap, drivers and fixes are a comparison and must share one denominator."""
    xs = [r for r in xs if r["k"] in s5]
    answers = {"s55": lambda r: (r["sonnet_smiles"], r["sonnet_verdict"], r.get("sonnet_conf")),
               "s5": lambda r: (s5[r["k"]]["sonnet_smiles"], s5[r["k"]]["sonnet_verdict"], s5[r["k"]].get("sonnet_conf")),
               "cx": lambda r: (r["ocr_smiles"], r["ocr_verdict"], r["ocr_conf"])}
    misses = {a: {} for a, _ in ARMS}
    for r in xs:
        for arm, _ in ARMS:
            smi, v, conf = answers[arm](r)
            if v != "exact":
                c = classify(smi, r["truth"], v)
                c["conf"] = conf
                c["smiles"] = smi
                misses[arm][r["k"]] = c
    taxonomy = {}
    for arm, label in ARMS:
        cnt = Counter(c["cat"] for c in misses[arm].values())
        taxonomy[arm] = {"label": label, "misses": len(misses[arm]), "n": len(xs),
                         "cats": {k: cnt.get(k, 0) for k, _, _ in CATS}}
    # the E/Z split by bond, for the figure's caption
    ez = {}
    for arm, _ in ARMS:
        ms = misses[arm].values()
        ez[arm] = {"added_rows": sum(1 for c in ms if c["cat"] == "ez_added"),
                   "omitted_rows": sum(1 for c in ms if c["cat"] == "ez_omitted"),
                   "added_bonds": sum(c.get("added", 0) for c in ms if c["cat"].startswith("ez")),
                   "omitted_bonds": sum(c.get("omitted", 0) for c in ms if c["cat"].startswith("ez")),
                   "flipped_bonds": sum(c.get("flipped", 0) for c in ms if c["cat"].startswith("ez"))}
    # overlap of the three miss sets
    M = {a: set(misses[a]) for a, _ in ARMS}
    combos = [("only_s55", "only 5.5", M["s55"] - M["s5"] - M["cx"]), ("only_s5", "only Sonnet 5", M["s5"] - M["s55"] - M["cx"]),
              ("only_cx", "only CXMolScribe", M["cx"] - M["s55"] - M["s5"]),
              ("s5_cx", "Sonnet 5 and CXMolScribe", (M["s5"] & M["cx"]) - M["s55"]),
              ("s55_s5", "5.5 and Sonnet 5", (M["s55"] & M["s5"]) - M["cx"]), ("s55_cx", "5.5 and CXMolScribe", (M["s55"] & M["cx"]) - M["s5"]),
              ("all", "all three", M["s55"] & M["s5"] & M["cx"])]
    overlap = [{"key": k, "label": l, "n": len(s), "names": sorted({r["name"] for r in xs if r["k"] in s})[:6]} for k, l, s in combos]
    overlap_none = len(xs) - len(M["s55"] | M["s5"] | M["cx"])
    # drivers
    feats = {r["k"]: features(r["truth"]) for r in xs}
    drivers = []
    for key, label, fn, order in feature_bins(feats):
        bins = []
        for b in order:
            ks = [r["k"] for r in xs if fn(feats[r["k"]]) == b]
            if not ks:
                continue
            bins.append({"label": b, "n": len(ks), **{a: sum(1 for k in ks if k in M[a]) for a, _ in ARMS}})
        drivers.append({"key": key, "label": label, "bins": bins})
    # gallery: every 5.5 miss, then up to 3 per (arm, class) for the other two, the smallest
    # drawings first so the highlight is legible, preferring images the other arms read right
    by_k = {r["k"]: r for r in xs}
    chosen = []
    seen = set()
    for k in sorted(M["s55"], key=lambda k: feats[k]["heavy"]):
        chosen.append((k, "s55", misses["s55"][k]["cat"]))
        seen.add(k)
    for arm in ("cx", "s5"):
        for cat, _, _ in CATS:
            ks = [k for k, c in misses[arm].items() if c["cat"] == cat and k not in seen]
            ks.sort(key=lambda k: (sum(1 for a in M if k in M[a]), feats[k]["heavy"]))
            take = 3 if cat != "invalid" else 2
            for k in ks[:take]:
                chosen.append((k, arm, cat))
                seen.add(k)
    chosen = chosen[:max_cards]
    cards = []
    for k, lead_arm, lead_cat in chosen:
        r = by_k[k]
        t = mol(r["truth"])
        card = {"k": k, "n": r["name"], "lead": lead_arm, "cat": lead_cat, "heavy": feats[k]["heavy"], "arms": {}, "img": {}}
        src = img_index.get(k + ".png")
        if src and thumb(Path(src), out_dir / "src" / f"{k}.png"):
            card["img"]["src"] = f"/wall/report/fail/src/{k}.png"
        truth_hl = (set(), set())
        for arm, _ in ARMS:
            if k not in misses[arm]:
                card["arms"][arm] = {"ok": True}
                continue
            c = misses[arm][k]
            entry = {"ok": False, "cat": c["cat"], "line": c["line"], "conf": c.get("conf")}
            p = mol(c["smiles"])
            if p is not None:
                ta, tb, pa, pb = highlights(Chem.Mol(t), Chem.Mol(p), c["cat"])
                truth_hl[0].update(ta)
                truth_hl[1].update(tb)
                if draw(p, out_dir / arm / f"{k}.png", pa, pb):
                    entry["img"] = f"/wall/report/fail/{arm}/{k}.png"
            card["arms"][arm] = entry
        if draw(t, out_dir / "truth" / f"{k}.png", sorted(truth_hl[0]), sorted(truth_hl[1])):
            card["img"]["truth"] = f"/wall/report/fail/truth/{k}.png"
        cards.append(card)
    # fixes, each with the misses it addresses, counted from the classes above
    def n_feat(arm, key):
        return sum(1 for k in M[arm] if feats[k][key])
    cx_salt = {k for k, c in misses["cx"].items() if c["cat"] == "fragment"}
    cx_metal = {k for k in M["cx"] if feats[k]["metal"]}
    either_55_cx = len(xs) - len(M["s55"] & M["cx"])
    either_5_cx = len(xs) - len(M["s5"] & M["cx"])
    fixes = [
        {"key": "ez_score", "label": "Score E/Z only where the truth specifies it (or draw unspecified double bonds wavy/crossed in the corpus)",
         "per_arm": {a: {"fixes": taxonomy[a]["cats"]["ez_added"], "of": taxonomy[a]["misses"]} for a, _ in ARMS}},
        {"key": "cx_salt", "label": "CXMolScribe: neutralise and strip counter-ions before scoring; route metal-containing drawings to a Sonnet reader",
         "per_arm": {"cx": {"fixes": len(cx_salt | cx_metal), "of": taxonomy["cx"]["misses"]}},
         "note": f"{len(cx_salt)} fragment/charge misses, {len(cx_metal)} on drawings with a metal ({len(cx_salt & cx_metal)} both)"},
        {"key": "s5_stereo", "label": "Sonnet 5: a stereo checklist (molfile from the drawn wedges, RDKit assigns R/S; never reason it by hand)",
         "per_arm": {"s5": {"fixes": taxonomy["s5"]["cats"]["tet"], "of": taxonomy["s5"]["misses"]},
                     "cx": {"fixes": taxonomy["cx"]["cats"]["tet"], "of": taxonomy["cx"]["misses"]}}},
        {"key": "s5_count", "label": "Sonnet 5: count ring vertices and chain atoms one at a time and re-render to compare (missing/extra atoms, connectivity)",
         "per_arm": {"s5": {"fixes": taxonomy["s5"]["cats"]["atoms"] + taxonomy["s5"]["cats"]["connect"], "of": taxonomy["s5"]["misses"]}}},
        {"key": "hybrid", "label": "Hybrid: CXMolScribe reads, Sonnet 5.5 adjudicates when they disagree (ceiling: either right)",
         "per_arm": {"cx": {"fixes": taxonomy["cx"]["misses"] - (len(xs) - either_55_cx), "of": taxonomy["cx"]["misses"]}},
         "note": f"either 5.5 or CXMolScribe right on {either_55_cx} of {len(xs)}; either Sonnet 5 or CXMolScribe on {either_5_cx}"},
        {"key": "cx_retry", "label": "CXMolScribe: retry or fall back when the output does not parse",
         "per_arm": {"cx": {"fixes": taxonomy["cx"]["cats"]["invalid"], "of": taxonomy["cx"]["misses"]}},
         "note": "an upper bound: these produced no usable SMILES at all"},
        {"key": "iso", "label": "Re-score isotope labels as their own class, apart from stereo",
         "per_arm": {a: {"fixes": taxonomy[a]["cats"]["iso"], "of": taxonomy[a]["misses"]} for a, _ in ARMS if taxonomy[a]["cats"]["iso"]}},
    ]
    return {"cats": [{"key": k, "label": l, "meaning": m} for k, l, m in CATS],
            "taxonomy": taxonomy, "ez": ez, "overlap": overlap, "overlap_none": overlap_none,
            "drivers": drivers, "cards": cards, "fixes": fixes,
            "misses": {a: [{"k": k, "n": by_k[k]["name"], "cat": c["cat"], "line": c["line"], "conf": c.get("conf")}
                           for k, c in misses[a].items()] for a, _ in ARMS}}


def corpus_images() -> dict:
    idx = {}
    for dd in sorted(glob.glob("/root/cmage-work/cmage-img*/corpus_rdkit_1500")):
        for p in glob.glob(dd + "/*.png"):
            idx.setdefault(os.path.basename(p), p)
    return idx


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["--selftest"]:
        bad = selftest()
        print("\n".join(bad) if bad else "SELFTEST PASS")
        sys.exit(1 if bad else 0)
    if a[:1] == ["--sample"]:
        n = int(a[1]) if len(a) > 1 else 8
        lane = [json.loads(l) for l in open("/root/cmage-work/sonnet-s55c/results.jsonl")]
        s5 = {r["k"]: r for r in map(json.loads, open("/root/cmage-work/sonnet/results.jsonl"))}
        xs = [r for r in lane if r["k"] in s5]
        import random
        random.seed(7)
        for arm, label in ARMS:
            print(f"== {label}")
            rows = []
            for r in xs:
                smi, v = {"s55": (r["sonnet_smiles"], r["sonnet_verdict"]), "s5": (s5[r["k"]]["sonnet_smiles"], s5[r["k"]]["sonnet_verdict"]),
                          "cx": (r["ocr_smiles"], r["ocr_verdict"])}[arm]
                if v != "exact":
                    rows.append((r["name"], smi, r["truth"], v))
            for name, smi, truth, v in random.sample(rows, min(n, len(rows))):
                c = classify(smi, truth, v)
                print(f"  [{c['cat']:10}] {name[:40]:40} | {c['line']}\n      truth {truth[:110]}\n      pred  {(smi or '')[:110]}")
        sys.exit(0)
    raise SystemExit(__doc__)
