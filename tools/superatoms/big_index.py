#!/usr/bin/env python3
"""Index MolScribe's uspto_mol.zip (USPTO grant chemical drawings, 2001-2009 weeks: each TIF ships with the
patent's own MOL file) for the big-molecule superatom set. Truth = the MOL file, read by RDKit; never a model.

Kept: >= MIN_HEAVY heavy atoms, the MOL parses and sanitises, round-trips through SMILES, and has no R-group /
alias / query / dummy atom, no Sgroup it cannot interpret (only SUP abbreviations, which RDKit expands), no O-O-O
chain (a known MOL export artefact). Each kept row gets a class:
  protac      a full E3-ligase ligand: IMiD (glutarimide on a phthalimide / isoindolinone: thalidomide,
              lenalidomide, pomalidomide) or the VHL ligand (Hyp amide of a 4-(4-methylthiazol-5-yl)benzylamine).
              Strict on purpose: a bare glutarimide or any hydroxyproline amide matched echinocandins and HCV
              protease inhibitors. PROTACs postdate most of this well (2001-2009 grants), so expect very few.
  peptide     >= 4 amide-linked alpha-amino-acid residues (linear, cyclic, stapled, lipidated all count);
  macrocycle  a ring of >= 12 atoms;
  other       everything else that is big.
A drawing whose MOL holds a second molecule of > 12 heavy atoms (two compounds, a reaction) is dropped; small
counter-ions stay in the truth.
Output /root/cmage-work/bigsa/pool.jsonl (one row per kept drawing). Parallel, deterministic.

    big_index.py [ZIP]"""
import json, re, sys, zipfile
from multiprocessing import Pool
from pathlib import Path
from rdkit import Chem, RDLogger
RDLogger.DisableLog("rdApp.*")
ZIP = Path(sys.argv[1] if len(sys.argv) > 1 else "/root/cmage-work/bigsa/dl/uspto_mol.zip")
OUT = Path("/root/cmage-work/bigsa/pool.jsonl")
MIN_HEAVY = 50
IMID = Chem.MolFromSmarts("O=C1CCC(N2C(=O)c3ccccc3C2=O)C(=O)N1")
IMID2 = Chem.MolFromSmarts("O=C1CCC(N2[CH2]c3ccccc3C2=O)C(=O)N1")
VHL = Chem.MolFromSmarts("[OX2H1][CH1]1[CH2][CH1](C(=O)N[CX4]c2ccc(-c3scnc3)cc2)N(C1)C(=O)")   # VH032 and its alpha-methyl (VH101-type) benzylamines
RES = Chem.MolFromSmarts("[NX3;!$(N=*)][CX4;H1,H2][CX3](=O)[NX3]")
OOO = Chem.MolFromSmarts("[#8]~[#8]~[#8]")
BAD_LINE = re.compile(r"^(M  (ALS|RGP|LIN|RAD.*|SAP)|A  |G  |V  )", re.M)


def classify(m):
    if m.HasSubstructMatch(IMID) or m.HasSubstructMatch(IMID2) or m.HasSubstructMatch(VHL):
        return "protac", 0
    n = len({t[1] for t in m.GetSubstructMatches(RES)})
    if n >= 4:
        return "peptide", n
    if any(len(r) >= 12 for r in m.GetRingInfo().AtomRings()):
        return "macrocycle", n
    return "other", n


def one(args):
    name, txt = args
    if BAD_LINE.search(txt) or "R#" in txt:
        return None
    # Sgroups: allow only SUP (abbreviation; RDKit keeps the expanded atoms)
    for l in txt.splitlines():
        if l.startswith("M  STY"):
            if any(tok != "SUP" for tok in l.split()[3:][1::2]):
                return None
    m = Chem.MolFromMolBlock(txt, sanitize=True, removeHs=True)
    if m is None or m.GetNumHeavyAtoms() < MIN_HEAVY:
        return None
    if any(a.GetAtomicNum() == 0 or a.HasQuery() or a.HasProp("molFileAlias") for a in m.GetAtoms()):
        return None
    if m.HasSubstructMatch(OOO):
        return None
    fr = sorted((f.GetNumHeavyAtoms() for f in Chem.GetMolFrags(m, asMols=True)), reverse=True)
    if fr[0] < MIN_HEAVY or (len(fr) > 1 and fr[1] > 12):
        return None
    smi = Chem.MolToSmiles(m)
    m2 = Chem.MolFromSmiles(smi)
    if m2 is None or Chem.MolToSmiles(m2) != smi:
        return None
    cls, n = classify(m2)
    return {"mol": name, "tif": name[:-4] + ".TIF", "patent": name.split("/")[-2], "id": Path(name).stem,
            "heavy": m2.GetNumHeavyAtoms(), "smiles": smi, "inchikey": Chem.MolToInchiKey(m2), "cls": cls,
            "n_res": n, "frags": smi.count(".") + 1}


def feed(z, names):
    for n in names:
        yield n, z.read(n).decode("latin-1")


def main():
    z = zipfile.ZipFile(ZIP)
    names = sorted(n for n in z.namelist() if n.endswith(".MOL"))
    tifs = {n for n in z.namelist() if n.endswith(".TIF")}
    names = [n for n in names if n[:-4] + ".TIF" in tifs]
    print(len(names), "MOL files with a TIF", flush=True)
    kept = 0
    with Pool(12) as p, open(OUT.with_suffix(".tmp"), "w") as fh:
        for i, r in enumerate(p.imap(one, feed(z, names), chunksize=200)):
            if r:
                fh.write(json.dumps(r) + "\n"); kept += 1
            if i % 50000 == 0:
                print(i, "read,", kept, "kept", flush=True)
    OUT.with_suffix(".tmp").rename(OUT)
    print("DONE", kept, "kept", flush=True)


if __name__ == "__main__":
    main()
