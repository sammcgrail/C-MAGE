#!/usr/bin/env python3
"""Pick REAL drawings that show text superatoms, from the Haiku screen (real/classify.jsonl).

A screened label counts only when it maps to a known group AND that group is present in the
benchmark's ground-truth SMILES (so a hallucinated label, or a drawing whose truth disagrees with
it, cannot qualify an image). An image qualifies with >= 1 verified label and no unverifiable
claims of a known label. Truth must parse with RDKit and hold no dummy / R atoms.
Output: real/candidates.json (all qualifying) and the sampled set (see SAMPLE)."""
import json, random, re, collections
from pathlib import Path
from rdkit import Chem, RDLogger
RDLogger.DisableLog("rdApp.*")
ROOT = Path("/root/cmage-work/superatoms")
SRC = ROOT / "dl/molscribe_real"
# canonical label -> (aliases as written, SMARTS that must match the truth)
G = {
    "OMe": (["OMe", "MeO", "OCH3", "H3CO", "CH3O"], "[CH3][OX2]"),
    "OEt": (["OEt", "EtO", "OC2H5", "C2H5O", "OCH2CH3", "CH3CH2O"], "[CH3][CH2][OX2]"),
    "Me": ([], None),
    "Et": (["Et", "C2H5", "CH2CH3", "H5C2", "CH3CH2"], "[CH3][CH2]"),
    "nPr": (["Pr", "n-Pr", "nPr", "C3H7", "n-C3H7"], "[CH3][CH2][CH2]"),
    "iPr": (["iPr", "i-Pr", "iPr", "CH(CH3)2", "(CH3)2CH"], "[CH3][CH]([CH3])"),
    "Bu": (["Bu", "n-Bu", "nBu", "C4H9", "n-C4H9"], "[CH3][CH2][CH2][CH2]"),
    "tBu": (["tBu", "t-Bu", "tert-Bu", "But", "Bu-t", "C(CH3)3", "(CH3)3C", "tBuO", "t-BuO", "OtBu", "Ot-Bu"], "C([CH3])([CH3])[CH3]"),
    "iBu": (["iBu", "i-Bu"], "[CH2][CH]([CH3])[CH3]"),
    "Ph": (["Ph", "C6H5", "Phe"], "[cH]1[cH][cH][cH][cH]c1"),
    "Bn": (["Bn", "Bzl", "CH2Ph", "PhCH2", "BnO", "OBn", "OBzl", "BzlO", "CH2C6H5"], "[CH2]c1[cH][cH][cH][cH][cH]1"),
    "Bz": (["Bz", "OBz", "BzO", "COPh", "PhCO", "C(O)Ph"], "C(=O)c1[cH][cH][cH][cH][cH]1"),
    "Ac": (["Ac", "OAc", "AcO", "NHAc", "AcNH", "AcHN", "COCH3", "CH3CO", "C(O)CH3", "OCOCH3", "COMe", "MeCO"], "[CH3]C(=O)"),
    "Boc": (["Boc", "BOC", "NHBoc", "BocHN", "BocNH", "t-Boc"], "C(=O)OC([CH3])([CH3])[CH3]"),
    "Cbz": (["Cbz", "Z", "CBz", "CBZ", "NHCbz", "CbzHN"], "C(=O)O[CH2]c1ccccc1"),
    "Fmoc": (["Fmoc", "FMOC"], "C(=O)OCC1c2ccccc2-c2ccccc21"),
    "CF3": (["CF3", "F3C"], "C(F)(F)F"),
    "OCF3": (["OCF3", "F3CO"], "OC(F)(F)F"),
    "CN": (["CN", "NC", "C≡N"], "C#N"),
    "NO2": (["NO2", "O2N"], "[$([N+](=O)[O-]),$(N(=O)=O)]"),
    "CO2H": (["CO2H", "HO2C", "COOH", "HOOC", "C(O)OH"], "C(=O)[OH]"),
    "CO2Me": (["CO2Me", "MeO2C", "COOMe", "MeOOC", "CO2CH3", "H3CO2C", "COOCH3", "CH3OOC", "C(O)OMe", "C(O)OCH3"], "C(=O)O[CH3]"),
    "CO2Et": (["CO2Et", "EtO2C", "COOEt", "EtOOC", "CO2C2H5", "C2H5O2C", "COOC2H5", "C2H5OOC", "C(O)OEt"], "C(=O)O[CH2][CH3]"),
    "CO2tBu": (["CO2tBu", "tBuO2C", "CO2t-Bu", "t-BuO2C", "COOtBu", "CO2But"], "C(=O)OC([CH3])([CH3])[CH3]"),
    "CHO": (["CHO", "OHC"], "[CX3H1](=O)"),
    "NMe2": (["NMe2", "Me2N", "N(CH3)2", "(CH3)2N"], "[NX3]([CH3])[CH3]"),
    "NEt2": (["NEt2", "Et2N", "N(C2H5)2"], "[NX3]([CH2][CH3])[CH2][CH3]"),
    "NHMe": (["NHMe", "MeHN", "MeNH", "NHCH3", "CH3NH", "HNMe"], "[NX3;H1][CH3]"),
    "SMe": (["SMe", "MeS", "SCH3", "CH3S"], "[CH3][SX2]"),
    "SO2Me": (["SO2Me", "MeO2S", "MeSO2", "SO2CH3", "CH3SO2", "Ms", "OMs", "MsO", "MsHN", "NHMs"], "[CH3]S(=O)(=O)"),
    "Ts": (["Ts", "Tos", "OTs", "TsO", "NHTs", "TsHN", "TsNH", "Tosyl"], "S(=O)(=O)c1ccc([CH3])cc1"),
    "Tf": (["Tf", "OTf", "TfO", "NTf2", "Tf2N"], "S(=O)(=O)C(F)(F)F"),
    "SO3H": (["SO3H", "HO3S"], "S(=O)(=O)[OH]"),
    "TMS": (["TMS", "SiMe3", "Me3Si", "OTMS", "TMSO", "Si(CH3)3"], "[Si]([CH3])([CH3])[CH3]"),
    "TBS": (["TBS", "TBDMS", "OTBS", "TBSO", "OTBDMS", "TBDMSO"], "[Si]([CH3])([CH3])C([CH3])([CH3])[CH3]"),
    "TIPS": (["TIPS", "OTIPS", "TIPSO"], "[Si](C([CH3])[CH3])(C([CH3])[CH3])C([CH3])[CH3]"),
    "TBDPS": (["TBDPS", "OTBDPS", "TBDPSO"], "[Si](c1ccccc1)(c1ccccc1)C([CH3])([CH3])[CH3]"),
    "PMB": (["PMB", "OPMB", "PMBO"], "[CH2]c1ccc(O[CH3])cc1"),
    "SO2NH2": (["SO2NH2", "H2NO2S", "H2NSO2"], "S(=O)(=O)[NH2]"),
    "CONH2": (["CONH2", "H2NOC", "C(O)NH2", "H2NCO"], "C(=O)[NH2]"),
    "CH2OH": (["CH2OH", "HOCH2", "HOH2C"], "[CH2][OH]"),
}
ALIAS = {}
for k, (al, _) in G.items():
    for a in al:
        ALIAS[a.replace(" ", "")] = k
PAT = {k: Chem.MolFromSmarts(s) for k, (_, s) in G.items() if s}
SAMPLE = {"USPTO": 200, "CLEF": 70, "UOB": 30, "acs": 40}
SHOW = {"USPTO": True, "CLEF": True, "UOB": False, "acs": False}


def norm(l):
    l = re.sub(r"[\s–—-]", "", str(l)).replace("−", "")
    l = l.translate(str.maketrans("₀₁₂₃₄₅₆₇₈₉", "0123456789"))
    if l in ALIAS:
        return ALIAS[l]
    l2 = l.replace("-", "")
    return ALIAS.get(l2)


def main():
    recs = [json.loads(l) for l in open(ROOT / "real/classify.jsonl")]
    # a parsed re-screen (rescreen_real.py, 2026-10-09) replaces an unparsed original
    rp = ROOT / "real/classify_retry.jsonl"
    retry = {r["id"]: r for r in map(json.loads, open(rp)) if "labels" in r} if rp.exists() else {}
    recs = [retry.get(r["id"], r) if "labels" not in r else r for r in recs]
    cands, stats = [], collections.Counter()
    for r in recs:
        stats[(r["set"], "screened")] += 1
        labs = r.get("labels") or []
        if not labs:
            continue
        m = Chem.MolFromSmiles(r["truth"])
        if m is None or any(a.GetAtomicNum() == 0 for a in m.GetAtoms()) or "*" in r["truth"]:
            stats[(r["set"], "truth unusable")] += 1
            continue
        mapped = [(l, norm(l)) for l in labs]
        known = [(l, k) for l, k in mapped if k]
        ok = [(l, k) for l, k in known if k in PAT and m.HasSubstructMatch(PAT[k])]
        if not ok:
            stats[(r["set"], "no verified label")] += 1
            continue
        if len(ok) < len(known):
            stats[(r["set"], "a known label not in truth")] += 1
            continue
        stats[(r["set"], "qualifies")] += 1
        cands.append(dict(r, verified=[k for _, k in ok], written=[l for l, _ in ok],
                          unmapped=[l for l, k in mapped if not k], heavy=m.GetNumHeavyAtoms()))
    json.dump(cands, open(ROOT / "real/candidates.json", "w"), indent=0)
    for s in sorted({k[0] for k in stats}):
        print(s, {k[1]: v for k, v in stats.items() if k[0] == s})
    return cands


if __name__ == "__main__":
    main()
