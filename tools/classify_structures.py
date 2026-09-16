#!/usr/bin/env python3
"""Bucket the scored Sonnet rows by objective features of the REFERENCE structure, and report
how each reader does per bucket. Feeds the "By structure type" section of the Sonnet tab.

The buckets are computed from the reference SMILES with RDKit — size, rings, stereocentres,
macrocycles, peptides, metals, and so on — never from the compound's name or class, so nothing
here depends on recognising the molecule. A structure can fall in several buckets; each bucket
is a separate lens answering "on structures like this, who reads them right more often". Only
buckets with at least MIN_N members are reported, and each row states its own denominator.

    classify_structures.py            print the table
    classes(rows) -> list[dict]       for build_sonnet
"""
import json
import sys
from pathlib import Path

WORK = Path("/root/cmage-work/sonnet/results.jsonl")
MIN_N = 12

try:
    from rdkit import Chem, RDLogger
    from rdkit.Chem import Descriptors
    RDLogger.DisableLog("rdApp.*")
except ImportError:
    Chem = None

METALS = {3, 4, 11, 12, 13, 19, 20, 26, 27, 28, 29, 30, 45, 47, 48, 78, 79, 80, 83}  # Li..Bi, common ones
AMIDE = Chem.MolFromSmarts("[NX3][CX3](=[OX1])") if Chem else None


def features(truth: str) -> set[str]:
    """The buckets a reference structure belongs to. Empty if it will not parse."""
    if not Chem or not truth:
        return set()
    mol = Chem.MolFromSmiles(truth)
    if mol is None:
        return set()
    frags = Chem.GetMolFrags(mol, asMols=True, sanitizeFrags=False)
    heavy = mol.GetNumHeavyAtoms()
    ri = mol.GetRingInfo()
    ring_sizes = [len(r) for r in ri.AtomRings()]
    n_rings = len(ring_sizes)
    arom_rings = sum(1 for r in ri.AtomRings()
                     if all(mol.GetAtomWithIdx(i).GetIsAromatic() for i in r))
    stereo = len(Chem.FindMolChiralCenters(mol, useLegacyImplementation=False, includeUnassigned=True))
    amides = len(mol.GetSubstructMatches(AMIDE)) if AMIDE else 0
    has_metal = any(a.GetAtomicNum() in METALS for a in mol.GetAtoms())
    carbons = sum(1 for a in mol.GetAtoms() if a.GetAtomicNum() == 6)
    charged = any(a.GetFormalCharge() for a in mol.GetAtoms())
    halogens = sum(1 for a in mol.GetAtoms() if a.GetAtomicNum() in (9, 17, 35, 53))

    f = set()
    f.add("size:small" if heavy <= 15 else "size:medium" if heavy <= 30
          else "size:large" if heavy <= 50 else "size:huge")
    f.add("rings:acyclic" if n_rings == 0 else "rings:few" if n_rings <= 2 else "rings:poly")
    f.add("stereo:none" if stereo == 0 else "stereo:some" if stereo <= 2
          else "stereo:several" if stereo <= 5 else "stereo:many")
    if any(s > 12 for s in ring_sizes):
        f.add("macrocycle")
    if amides >= 4 and heavy >= 30:
        f.add("peptide")
    if arom_rings >= 3:
        f.add("aromatic-rich")
    if len(frags) >= 2:
        f.add("multi-fragment")
    if has_metal or carbons <= 2:
        f.add("inorganic")
    if charged:
        f.add("charged")
    if halogens >= 3:
        f.add("halogen-rich")
    return f


# label + a short human description, in display order (roughly small→large, simple→hard)
BUCKETS = [
    ("size:small", "Small (≤15 heavy atoms)"),
    ("size:medium", "Medium (16–30)"),
    ("size:large", "Large (31–50)"),
    ("size:huge", "Very large (>50)"),
    ("rings:acyclic", "Acyclic (no rings)"),
    ("rings:few", "1–2 rings"),
    ("rings:poly", "Polycyclic (3+ rings)"),
    ("aromatic-rich", "Aromatic-rich (3+ aromatic rings)"),
    ("stereo:none", "No stereocentres"),
    ("stereo:some", "1–2 stereocentres"),
    ("stereo:several", "3–5 stereocentres"),
    ("stereo:many", "6+ stereocentres"),
    ("macrocycle", "Macrocycles (ring >12)"),
    ("peptide", "Peptide-like (4+ amide bonds)"),
    ("halogen-rich", "Halogen-rich (3+ halogens)"),
    ("charged", "Charged / zwitterionic"),
    ("multi-fragment", "Salts / multi-fragment"),
    ("inorganic", "Inorganic / organometallic"),
]


def classes(rows: list[dict]) -> list[dict]:
    tally = {key: {"n": 0, "s": 0, "o": 0} for key, _ in BUCKETS}
    for r in rows:
        feats = features(r.get("truth"))
        for key in feats:
            if key in tally:
                t = tally[key]
                t["n"] += 1
                t["s"] += r.get("sonnet_verdict") == "exact"
                t["o"] += r.get("ocr_verdict") == "exact"
    out = []
    for key, label in BUCKETS:
        t = tally[key]
        if t["n"] < MIN_N:
            continue
        sp, op = round(100 * t["s"] / t["n"]), round(100 * t["o"] / t["n"])
        lead = "sonnet" if sp - op >= 6 else "cxms" if op - sp >= 6 else "tie"
        out.append({"key": key, "label": label, "n": t["n"],
                    "sonnet": sp, "cxms": op, "lead": lead})
    return out


def main() -> int:
    rows = [json.loads(l) for l in open(WORK) if l.strip()]
    cs = classes(rows)
    print(f"{len(rows)} scored rows; buckets with n>={MIN_N}:\n")
    print(f"  {'bucket':34} {'n':>4}  {'Sonnet':>7} {'CXMS':>6}  lead")
    for c in cs:
        print(f"  {c['label']:34} {c['n']:>4}  {c['sonnet']:>6}% {c['cxms']:>5}%  {c['lead']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
