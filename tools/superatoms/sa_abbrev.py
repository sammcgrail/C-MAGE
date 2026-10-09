"""Superatom condensation for the superatom-heavy C-MAGE set.

RDKit's 37 default abbreviations plus the protecting groups and common superatoms the defaults lack.
Extensions go FIRST (larger groups before the smaller ones they contain). Attachment rules keep a label
chemically honest (Boc/Cbz/Fmoc only on N, so a tert-butyl ester reads CO2tBu, not Boc).
Truth is never derived from the condensed molecule: expand() rebuilds the full molecule from the
condensed one by molzip and must reproduce the original canonical isomeric SMILES exactly."""
from rdkit import Chem
from rdkit.Chem import rdAbbreviations
from rdkit.Chem.Draw import rdMolDraw2D

S2 = "<sub>2</sub>"
S3 = "<sub>3</sub>"
EXTRA = [  # label, SMILES with * at the attachment, label drawn pointing right, label drawn pointing left
    ("Fmoc", "*C(=O)OCC1c2ccccc2-c2ccccc21", "Fmoc", "Fmoc"),
    ("OTBDPS", "*O[Si](c1ccccc1)(c1ccccc1)C(C)(C)C", "OTBDPS", "TBDPSO"),
    ("TBDPS", "*[Si](c1ccccc1)(c1ccccc1)C(C)(C)C", "TBDPS", "TBDPS"),
    ("OTIPS", "*O[Si](C(C)C)(C(C)C)C(C)C", "OTIPS", "TIPSO"),
    ("TIPS", "*[Si](C(C)C)(C(C)C)C(C)C", "TIPS", "TIPS"),
    ("OTBS", "*O[Si](C)(C)C(C)(C)C", "OTBS", "TBSO"),
    ("TBS", "*[Si](C)(C)C(C)(C)C", "TBS", "TBS"),
    ("OTMS", "*O[Si](C)(C)C", "OTMS", "TMSO"),
    ("TMS", "*[Si](C)(C)C", "TMS", "TMS"),
    ("Cbz", "*C(=O)OCc1ccccc1", "Cbz", "Cbz"),
    ("CO2Bn", "*C(=O)OCc1ccccc1", f"CO{S2}Bn", f"BnO{S2}C"),
    ("Boc", "*C(=O)OC(C)(C)C", "Boc", "Boc"),
    ("CO2tBu", "*C(=O)OC(C)(C)C", f"CO{S2}tBu", f"tBuO{S2}C"),
    ("OTs", "*OS(=O)(=O)c1ccc(C)cc1", "OTs", "TsO"),
    ("Ts", "*S(=O)(=O)c1ccc(C)cc1", "Ts", "Ts"),
    ("OTf", "*OS(=O)(=O)C(F)(F)F", "OTf", "TfO"),
    ("Tf", "*S(=O)(=O)C(F)(F)F", "Tf", "Tf"),
    ("OMs", "*OS(=O)(=O)C", "OMs", "MsO"),
    ("SO2Me", "*S(=O)(=O)C", f"SO{S2}Me", f"MeO{S2}S"),
    ("OPMB", "*OCc1ccc(OC)cc1", "OPMB", "PMBO"),
    ("OBz", "*OC(=O)c1ccccc1", "OBz", "BzO"),
    ("Bz", "*C(=O)c1ccccc1", "Bz", "Bz"),
    ("OBn", "*OCc1ccccc1", "OBn", "BnO"),
    ("Bn", "*Cc1ccccc1", "Bn", "Bn"),
    ("Ph", "*c1ccccc1", "Ph", "Ph"),
    ("OCF3", "*OC(F)(F)F", f"OCF{S3}", f"F{S3}CO"),
    ("CO2Me", "*C(=O)OC", f"CO{S2}Me", f"MeO{S2}C"),
    ("NMe2", "*N(C)C", f"NMe{S2}", f"Me{S2}N"),
    ("NEt2", "*N(CC)CC", f"NEt{S2}", f"Et{S2}N"),
    # RDKit 2025.03 defaults that would MISLABEL the drawing, overridden: its "iBu" is *C(C)CC
    # (sec-butyl) and its "iPent" is *C(C)CCC (1-methylbutyl); its "NMe" (*NC) draws as "NMe".
    ("iBu", "*CC(C)C", "iBu", "iBu"),
    ("sBu", "*C(C)CC", "sBu", "sBu"),
    ("iPent", "*CCC(C)C", "iPent", "iPent"),
    ("NHMe", "*NC", "NHMe", "MeHN"),
]
DROP_DEFAULTS = {"NMe", "NCF3"}   # NMe replaced by NHMe; "NCF3" (NH-CF3) reads ambiguously
# label -> attachment elements allowed. Anything absent: any attachment.
ONLY_ON = {"Fmoc": {7}, "Cbz": {7}, "Boc": {7}, "CO2Bn": {6}, "CO2tBu": {6}, "Bn": {7, 8, 16},
           "TBS": {7, 6}, "TMS": {6, 7}, "TIPS": {6, 7}, "TBDPS": {6, 7}, "Ts": {7, 6}, "Tf": {7, 6},
           "SO2Me": {6, 7}, "Bz": {7, 6}}


def _restrict(d, elems):
    """Constrain the definition's attachment atom (query atom 0, any non-dummy by default)."""
    rw = Chem.RWMol(d.mol)
    rw.ReplaceAtom(0, Chem.MolFromSmarts("[" + ",".join(f"#{e}" for e in sorted(elems)) + "]").GetAtomWithIdx(0))
    d.mol = rw.GetMol()
    return d


# v2 (2026-10-09 expansion, sa_0176 on): more protecting groups, placed BEFORE the v1 list (larger
# groups first: Trt before Ph, PMB before Bn/OMe, Piv/OPiv before tBu, OMOM/OSEM/OTHP before OMe).
EXTRA2 = [
    ("Trt", "*C(c1ccccc1)(c1ccccc1)c1ccccc1", "Trt", "Trt"),
    ("OSEM", "*OCOCC[Si](C)(C)C", "OSEM", "SEMO"),
    ("SEM", "*COCC[Si](C)(C)C", "SEM", "SEM"),
    ("OTHP", "*OC1CCCCO1", "OTHP", "THPO"),
    ("THP", "*C1CCCCO1", "THP", "THP"),
    ("OMOM", "*OCOC", "OMOM", "MOMO"),
    ("MOM", "*COC", "MOM", "MOM"),
    ("PMB", "*Cc1ccc(OC)cc1", "PMB", "PMB"),
    ("OPiv", "*OC(=O)C(C)(C)C", "OPiv", "PivO"),
    ("Piv", "*C(=O)C(C)(C)C", "Piv", "Piv"),
    ("Alloc", "*C(=O)OCC=C", "Alloc", "Alloc"),
]
ONLY_ON.update({"Trt": {7, 8, 16}, "SEM": {7}, "THP": {7}, "MOM": {7}, "PMB": {7}, "Piv": {7}, "Alloc": {7}})
# v2 also drops RDKit's "NC" (isocyanide drawn "NC"/"CN": the same letters as a left-pointing nitrile,
# so the drawing would not determine the molecule; sa_0034 was excluded for exactly this).
DROP_DEFAULTS_V2 = DROP_DEFAULTS | {"NC"}


def _defs(extra=EXTRA, drop=DROP_DEFAULTS):
    txt = "".join(f"{l}\t{s}\t{d}\t{w}\n" for l, s, d, w in extra)
    defs = [(_restrict(d, ONLY_ON[d.label]) if d.label in ONLY_ON else d)
            for d in rdAbbreviations.ParseAbbreviations(txt)]
    have = {d.label for d in defs}
    defs += [d for d in rdAbbreviations.GetDefaultAbbreviations() if d.label not in have | drop]
    return defs


ALL_V1 = _defs()                                    # the first 175 (build_set.py)
ALL_V2 = _defs(EXTRA2 + EXTRA, DROP_DEFAULTS_V2)    # the 2026-10-09 expansion (build_more.py)
# ALL: every label any built drawing can carry (lookup of display forms, CX label expansion); never
# used to condense.
ALL = ALL_V1 + [d for d in ALL_V2 if d.label not in {x.label for x in ALL_V1}]
DEF_SMILES = {d.label: Chem.MolToSmiles(d.mol) for d in rdAbbreviations.GetDefaultAbbreviations()}
DEF_SMILES.update({e[0]: e[1] for e in EXTRA + EXTRA2})


def labels_of(m):
    return [a.GetProp("atomLabel") for a in m.GetAtoms() if a.HasProp("atomLabel")]


def condense(mol, max_cov=0.8, defs=None):
    c = rdAbbreviations.CondenseMolAbbreviations(mol, ALL_V1 if defs is None else defs, maxCoverage=max_cov)
    for a in c.GetAtoms():      # belt and braces: the attachment rule must hold on every label
        if a.HasProp("atomLabel") and a.GetProp("atomLabel") in ONLY_ON:
            nb = a.GetNeighbors()
            assert len(nb) == 1 and nb[0].GetAtomicNum() in ONLY_ON[a.GetProp("atomLabel")], a.GetProp("atomLabel")
    return c


def expand(cond):
    """Rebuild the full molecule from a condensed one: each labelled dummy is zipped to its
    definition's fragment. Independent of how the original was condensed."""
    rw = Chem.RWMol(cond)
    frags, n = [], 0
    for a in rw.GetAtoms():
        if a.HasProp("atomLabel"):
            n += 1
            a.SetAtomMapNum(n)
            f = Chem.MolFromSmiles(DEF_SMILES[a.GetProp("atomLabel")])
            # the definition's own dummy becomes the partner of this dummy
            for fa in f.GetAtoms():
                if fa.GetAtomicNum() == 0:
                    fa.SetAtomMapNum(n)
            frags.append(f)
    m = rw.GetMol()
    for f in frags:
        m = Chem.CombineMols(m, f)
    z = Chem.molzip(m)
    Chem.SanitizeMol(z)
    return z


def canon(smi_or_mol):
    m = Chem.MolFromSmiles(smi_or_mol) if isinstance(smi_or_mol, str) else smi_or_mol
    return Chem.MolToSmiles(m) if m is not None else None


def render(cond, S, out):
    """Verbatim corpus renderer settings (cmage-img*/build_corpus*.py render_rdkit), drawing the
    CONDENSED molecule so the labels are real text superatoms."""
    d = rdMolDraw2D.MolDraw2DCairo(S, S)
    o = d.drawOptions()
    o.clearBackground = True
    o.maxFontSize = -1
    o.minFontSize = -1
    o.scaleBondWidth = True
    o.bondLineWidth = 2
    o.includeMetadata = False      # pixels only: RDKit embeds the molecule in zTXt by default
    rdMolDraw2D.PrepareAndDrawMolecule(d, cond)
    d.FinishDrawing()
    open(out, "wb").write(d.GetDrawingText())
