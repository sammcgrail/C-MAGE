#!/usr/bin/env python3
"""Standing gate on the v2 synthetic corpus and on score_cx.py's grader.

Same two halves as v1's gate, plus the checks the v2 arms make possible. The
second half still matters more than the first: a grader that passes everything
reports a flattering number and no error.

INTEGRITY -- is the ground truth actually true?
  * every reference CXSMILES parses and is IDEMPOTENT under reparse
  * every in-vocabulary condensation expands, through the SCORER's own table,
    back to the molecule it claims to be
  * recorded formula and InChIKey recompute from the recorded SMILES -- the
    check that catches a name resolved to the wrong PubChem record
  * every drawn superatom means the same thing in RDKit's table (which DREW it)
    and CXMolScribe's (which is asked to NAME it), for every label claimed to be
    in vocabulary
  * every molecule satisfies the predicate of the stratum it is filed under
  * NO drawn molecule may lose a stereocentre to condensation. RDKit's
    CondenseMolAbbreviations silently drops a chiral tag when a stereocentre's
    substituent is absorbed (valine -> `*C(*)N |$iPr;;CO2H;$|`), which would put
    a picture in the corpus that is not the compound the manifest names.

INTEGRITY, v2-specific
  * every Markush scaffold is a substructure of the parent drug it was cut from
  * every cell rectangle lies inside the page and no two overlap on a page --
    an overlap would mean two structures share ink and neither crop is clean
  * the vocabulary pair is EXACT: same members in the same order, identical
    skeleton and identical expanded SMILES, and every mirrored label is absent
    from CXMolScribe's vocabulary while its canonical twin is present. If the
    model ever ships a vocabulary containing `EtO2C`, this check fails and the
    arm is retired rather than quietly reporting a stale result.
  * every crossed-arm render condition carries the SAME compounds, so a
    difference between conditions cannot be a difference between samples
  * recorded buckets (size, stereo depth, abbreviation depth) recompute

DISCRIMINATION -- does the grader still say no?
    self                  -> Y or YS
    synonym label         -> unchanged (OMe and MeO are one superatom)
    different label       -> A
    two labels swapped    -> A
    a mirrored label      -> A, never Y (it is not in the model's table, so it
                             cannot mean the same thing to the model)
    other group's refs    -> N or NS, never Y

  .venv-ms/bin/python benchmarks/synthetic_selftest_v2.py \
      --manifest benchmarks/ground_truth/synthetic_manifest_v2.json
"""
import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from rdkit import Chem, RDLogger
from rdkit.Chem import rdAbbreviations, rdMolDescriptors

sys.path.insert(0, str(Path(__file__).resolve().parent))
import score_cx                                                          # noqa: E402
from cxsmiles import expand                                              # noqa: E402
from select_synthetic_v2 import bucket_of, fused_max                     # noqa: E402
from synthetic_compounds_v2 import (ABBREV_BUCKETS, LAYOUTS, MIRRORS,    # noqa: E402
                                    PAGE_H, PAGE_W, RENDER, SIZE_BUCKETS,
                                    STEREO_BUCKETS)
from synthetic_selftest import attach_methyl, swap_labels, swap_two      # noqa: E402

RDLogger.DisableLog("rdApp.*")

try:
    from molscribe.constants import ABBREVIATIONS as MS_ABBREV
except ImportError:                                                      # pragma: no cover
    sys.exit("run this with .venv-ms/bin/python -- it needs molscribe")


def _positional(cx):
    mol, labs = score_cx.parse_cx(cx)
    return score_cx.positional_key(mol, labs)


def rdkit_table():
    ab = rdAbbreviations.GetDefaultAbbreviations()
    for a in rdAbbreviations.ParseAbbreviations("Ph\t*c1ccccc1\n"):
        ab.append(a)
    return {a.label: Chem.MolToSmiles(a.mol) for a in ab}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifest", type=Path,
                    default=Path(__file__).resolve().parent / "ground_truth"
                    / "synthetic_manifest_v2.json")
    ap.add_argument("--max-report", type=int, default=25)
    args = ap.parse_args()
    man = json.loads(args.manifest.read_text())
    RD = rdkit_table()
    fails, checks = [], 0

    def check(cond, msg):
        nonlocal checks
        checks += 1
        if not cond:
            fails.append(msg)

    groups = man["groups"]
    mols = [(g, m) for g, e in groups.items() for m in e["molecules"]]
    check(len(mols) > 900, f"expected >900 drawings, found {len(mols)}")
    names = {m["name"] for _, m in mols}
    check(len(names) >= 480, f"expected >=480 distinct compounds, found {len(names)}")

    # ------------------------------------------------------- per drawing
    for g, m in mols:
        tag = f"{g}/{m['name']}"
        cx = m["drawn_cxsmiles"]
        mol = Chem.MolFromSmiles(cx)
        check(mol is not None, f"{tag}: reference CXSMILES does not parse")
        if mol is None:
            continue
        check(Chem.MolToCXSmiles(mol) == cx, f"{tag}: reference CXSMILES is not idempotent")
        check(score_cx.skeleton_smiles(mol) == m["skeleton"],
              f"{tag}: recorded skeleton is not the CXSMILES skeleton")

        mirrored = groups[g]["arm"] == "vocab_out"
        if not m.get("markush"):
            ref = Chem.MolFromSmiles(m["smiles"])
            check(ref is not None, f"{tag}: recorded SMILES does not parse")
            if ref is not None:
                check(rdMolDescriptors.CalcMolFormula(ref) == m["formula"],
                      f"{tag}: formula {m['formula']} != {rdMolDescriptors.CalcMolFormula(ref)}")
                if m.get("inchikey"):
                    check(Chem.MolToInchiKey(ref) == m["inchikey"],
                          f"{tag}: InChIKey does not recompute from the recorded SMILES")
                check(ref.GetNumHeavyAtoms() == m["heavy_atoms"], f"{tag}: heavy atom count")
                check(bucket_of(m["heavy_atoms"], SIZE_BUCKETS) == m["size_bucket"],
                      f"{tag}: size bucket {m['size_bucket']} does not match "
                      f"{m['heavy_atoms']} heavy atoms")
                nst = len(Chem.FindMolChiralCenters(ref, useLegacyImplementation=False,
                                                    includeUnassigned=False))
                check(nst == m["defined_stereocentres"], f"{tag}: stereocentre count")
                check(bucket_of(nst, STEREO_BUCKETS) == m["stereo_bucket"],
                      f"{tag}: stereo bucket")
                # the drawn molecule must still carry every centre the compound has,
                # unless it was drawn uncondensed (then it trivially does)
                if m["has_appendix"]:
                    try:
                        dn = len(Chem.FindMolChiralCenters(mol, useLegacyImplementation=False,
                                                           includeUnassigned=False))
                    except Exception:                             # noqa: BLE001
                        dn = -1
                    check(dn == nst,
                          f"{tag}: condensation changed the stereocentre count {nst} -> {dn}")
            if m["has_appendix"] and not mirrored:
                back, note = expand(cx)
                check(bool(back) and Chem.CanonSmiles(back) == Chem.CanonSmiles(m["smiles"]),
                      f"{tag}: appendix does not expand back to the compound ({note})")
        else:
            pm = Chem.MolFromSmiles(m["parent_smiles"])
            q = Chem.MolFromSmiles(m["skeleton"])
            if q is not None:
                p = Chem.AdjustQueryParameters.NoAdjustments()
                p.makeDummiesQueries = True
                q = Chem.AdjustQueryProperties(q, p)
            check(pm is not None and q is not None and pm.HasSubstructMatch(q),
                  f"{tag}: scaffold is not a substructure of {m.get('parent_name')}")

        # labels: meaning must agree between the table that drew it and the table
        # asked to name it, for every label claimed to be in vocabulary
        for lab, in_vocab in zip(m["appendix"], m["appendix_in_vocab"]):
            if m.get("markush"):
                continue
            check(in_vocab == (lab in MS_ABBREV),
                  f"{tag}: recorded vocabulary flag for {lab} is wrong")
            if not in_vocab or lab not in RD:
                continue
            ms = getattr(MS_ABBREV.get(lab), "smiles", None)
            a, b = attach_methyl(RD[lab]), attach_methyl(ms) if ms else None
            check(a is not None and a == b,
                  f"{tag}: label {lab} means {RD[lab]} to RDKit and {ms} to CXMolScribe")

        # stratum predicate, on the molecule as recorded
        s = m["stratum"]
        if not m.get("markush"):
            ref = Chem.MolFromSmiles(m["smiles"])
            if ref is not None:
                if s == "basic":
                    check(m["defined_stereocentres"] == 0 and m["fragments"] == 1
                          and m["net_charge"] == 0 and m["heavy_atoms"] <= 26
                          and not m["has_appendix"], f"{tag}: fails the basic predicate")
                elif s == "stereo":
                    check(m["defined_stereocentres"] >= 1 and not m["has_appendix"],
                          f"{tag}: fails the stereo predicate")
                elif s == "abbreviated":
                    check(m["has_appendix"], f"{tag}: abbreviated but nothing condensed")
                    check(bucket_of(m["n_superatoms"], ABBREV_BUCKETS) == m["abbrev_bucket"],
                          f"{tag}: abbreviation-depth bucket")
                elif s == "complex":
                    check(m["largest_ring"] >= 12 or m["heavy_atoms"] >= 51
                          or m["fused_max"] >= 4, f"{tag}: fails the complex predicate")
                elif s == "salt":
                    check(m["fragments"] >= 2 or m["net_charge"] != 0,
                          f"{tag}: fails the salt predicate")
        else:
            check(s == "markush" and m["has_appendix"], f"{tag}: markush with no R labels")

    # -------------------------------------------------- geometry, per page
    for g, e in groups.items():
        by_page = defaultdict(list)
        for m in e["molecules"]:
            by_page[m["page"]].append(m)
        L = LAYOUTS[e["layout"]]
        for p, ms in by_page.items():
            check(len(ms) <= L["rows"] * L["cols"],
                  f"{g} page {p}: {len(ms)} structures in a {L['rows']}x{L['cols']} grid")
            for m in ms:
                x, y, w, h = m["cell_px"]
                check(0 <= x and 0 <= y and x + w <= PAGE_W and y + h <= PAGE_H,
                      f"{g}/{m['name']}: cell {m['cell_px']} leaves the page")
            for i in range(len(ms)):
                for j in range(i + 1, len(ms)):
                    ax, ay, aw, ah = ms[i]["cell_px"]
                    bx, by_, bw, bh = ms[j]["cell_px"]
                    overlap = not (ax + aw <= bx or bx + bw <= ax
                                   or ay + ah <= by_ or by_ + bh <= ay)
                    check(not overlap,
                          f"{g} page {p}: cells of {ms[i]['name']} and {ms[j]['name']} overlap")

    # ------------------------------------------------- the vocabulary arm
    ins = sorted(k for k, v in groups.items() if v["arm"] == "vocab_in")
    check(len(ins) > 0, "no vocab_in groups in the manifest")
    n_mirror = 0
    for k in ins:
        ko = k.replace("vocab_in", "vocab_out")
        check(ko in groups, f"{k} has no mirrored twin")
        if ko not in groups:
            continue
        a, b = groups[k]["molecules"], groups[ko]["molecules"]
        check([x["name"] for x in a] == [x["name"] for x in b],
              f"{k}: the mirrored twin does not hold the same compounds in the same order")
        for x, y in zip(a, b):
            check(x["skeleton"] == y["skeleton"],
                  f"{k}/{x['name']}: mirroring changed the skeleton -- it must change ONLY the label")
            check(x["smiles"] == y["smiles"], f"{k}/{x['name']}: mirroring changed the molecule")
            check(len(x["appendix"]) == len(y["appendix"]),
                  f"{k}/{x['name']}: mirroring changed the number of superatoms")
            for la, lb in zip(x["appendix"], y["appendix"]):
                if la == lb:
                    check(la not in MIRRORS, f"{k}/{x['name']}: {la} has a mirror but was not applied")
                    continue
                n_mirror += 1
                check(MIRRORS.get(la) == lb, f"{k}/{x['name']}: {la} mirrored to {lb}, expected "
                                             f"{MIRRORS.get(la)}")
                check(la in MS_ABBREV, f"{k}/{x['name']}: canonical label {la} is NOT in the "
                                       f"model vocabulary, so the pair proves nothing")
                check(lb not in MS_ABBREV,
                      f"{k}/{x['name']}: mirrored label {lb} IS in the model vocabulary now -- "
                      f"the vocabulary arm is stale and must be retired")
    check(n_mirror > 50, f"only {n_mirror} labels were mirrored; the arm is too small to read")

    # ------------------------------------------------- the crossed arms
    crossed = defaultdict(set)
    for g, e in groups.items():
        if e["arm"] == "crossed":
            crossed[e["render"]] |= {m["name"] for m in e["molecules"]}
    check(len(crossed) >= 8, f"expected >=8 crossed render conditions, found {len(crossed)}")
    base = None
    for cond, s in sorted(crossed.items()):
        if base is None:
            base = s
        check(s == base, f"crossed condition {cond} holds a different compound set "
                         f"({len(s ^ base)} differ) -- the comparison would be between samples")
        check(RENDER[cond][0] in LAYOUTS, f"{cond}: unknown layout")

    # -------------------------------------------- DISCRIMINATION controls
    refs = {g: [score_cx.build_reference(m) for m in e["molecules"]]
            for g, e in groups.items()}
    letters = Counter()
    gnames = sorted(groups)
    skel_in_group = {g: {r["skeleton"] for r in rs} for g, rs in refs.items()}
    for gi, g in enumerate(gnames):
        for m in groups[g]["molecules"]:
            other = next((refs[h] for h in gnames
                          if h != g and m["skeleton"] not in skel_in_group[h]), None)
            cx = m["drawn_cxsmiles"]
            v = score_cx.grade_one(cx, refs[g])
            letters[v["letter"]] += 1
            check(v["letter"] in ("Y", "YS"),
                  f"{g}/{m['name']}: a reference does not grade as itself ({v['letter']})")
            if not m["has_appendix"]:
                continue
            # a synonym must not change the grade; a different label must cost it
            lab = m["appendix"][0]
            syn = {"OMe": "MeO", "MeO": "OMe", "CHO": "OHC", "OHC": "CHO",
                   "CF3": "F3C", "F3C": "CF3", "NO2": "O2N", "O2N": "NO2",
                   "CO2H": "HO2C", "HO2C": "CO2H", "SMe": "MeS", "MeS": "SMe"}.get(lab)
            if syn:
                alt = swap_labels(cx, lab, syn)
                if alt:
                    check(score_cx.grade_one(alt, refs[g])["letter"] == v["letter"],
                          f"{g}/{m['name']}: synonym {lab}->{syn} changed the grade")
            wrong = swap_labels(cx, lab, "CCl3" if lab != "CCl3" else "CF3")
            if wrong:
                check(score_cx.grade_one(wrong, refs[g])["letter"] == "A",
                      f"{g}/{m['name']}: a WRONG label still graded "
                      f"{score_cx.grade_one(wrong, refs[g])['letter']}, expected A")
            two = swap_two(cx)
            # A swap between two positions that are EQUIVALENT by symmetry is
            # not a wrong answer -- valproic acid's two nPr groups sit on one
            # carbon, and exchanging a label with CO2H there produces the same
            # molecule. Assert only where the swap actually changed something.
            if two and _positional(two) != _positional(cx):
                check(score_cx.grade_one(two, refs[g])["letter"] == "A",
                      f"{g}/{m['name']}: two labels swapped still graded "
                      f"{score_cx.grade_one(two, refs[g])['letter']}, expected A")
            mir = MIRRORS.get(lab)
            if mir:
                alt = swap_labels(cx, lab, mir)
                if alt:
                    check(score_cx.grade_one(alt, refs[g])["letter"] == "A",
                          f"{g}/{m['name']}: mirrored {lab}->{mir} graded Y -- the scorer is "
                          f"resolving a label the model has no entry for")
            # The negative control needs a group that does not CONTAIN this
            # molecule. v2 draws the same compound in several groups on purpose
            # (the crossed arms), so "the next group" is not automatically a
            # stranger, and asserting against one that holds the same skeleton
            # would be asserting that a correct answer is wrong.
            if other is not None:
                check(score_cx.grade_one(cx, other)["letter"] in ("N", "NS"),
                      f"{g}/{m['name']}: graded against a group that does not contain it "
                      f"and still scored {score_cx.grade_one(cx, other)['letter']}")

    print(f"{checks} checks, {len(fails)} failures")
    print(f"  self-grade letters {dict(letters)}   mirrored labels checked {n_mirror}")
    if fails:
        for f in fails[:args.max_report]:
            print("  FAIL " + f)
        if len(fails) > args.max_report:
            print(f"  ... and {len(fails) - args.max_report} more")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
