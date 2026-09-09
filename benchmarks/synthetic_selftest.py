#!/usr/bin/env python3
"""Standing gate on the synthetic corpus and on score_cx.py's grader.

Two halves, and the second matters more than the first.

INTEGRITY -- is the ground truth actually true?
  * every reference CXSMILES parses and is IDEMPOTENT under reparse
  * every non-Markush reference expands, through the scorer's own table, back to
    the molecule it claims to be
  * recorded formula and InChIKey recompute from the recorded SMILES, which is
    what catches a name that resolved to the wrong PubChem CID
  * every drawn superatom means the same thing in RDKit's abbreviation table
    (which DREW it) and CXMolScribe's (which is asked to NAME it). These two
    tables do disagree -- RDKit's `NC` is an isocyanide, CXMolScribe's is a
    nitrile facing the other way -- and a label they disagree about could never
    be graded fairly.
  * every molecule satisfies the predicate of the stratum it is filed under

DISCRIMINATION -- does the grader still say no?
  A grader that passes everything reports a flattering number and no error, which
  is worse than the strict metric it replaces. Each control below is a case the
  grader MUST fail, and the gate closes if any of them starts passing:
    self                  -> Y or YS      (a reference must grade as itself)
    synonym label         -> unchanged    (OMe and MeO are one superatom)
    different label       -> A            (skeleton right, appendix wrong)
    two labels swapped    -> A            (right labels, wrong positions)
    graded against another group's references -> N or NS, never Y

  .venv-ms/bin/python benchmarks/synthetic_selftest.py \
      --manifest ground_truth/synthetic_manifest.json
"""
import argparse
import json
import re
import sys
from pathlib import Path

from rdkit import Chem, RDLogger
from rdkit.Chem import rdAbbreviations, rdMolDescriptors

sys.path.insert(0, str(Path(__file__).resolve().parent))
import score_cx                                                   # noqa: E402
from cxsmiles import expand                                       # noqa: E402

RDLogger.DisableLog("rdApp.*")

try:
    from molscribe.constants import ABBREVIATIONS as MS_ABBREV
except ImportError:                                               # pragma: no cover
    sys.exit("run this with .venv-ms/bin/python -- it needs molscribe")


def attach_methyl(smi):
    """A substituent SMILES -> the molecule you get by capping it with CH3.

    RDKit writes an abbreviation's attachment point as a dummy `*OC`;
    CXMolScribe writes it as a radical `[O]C`. Capping both with a methyl is the
    only way to compare the two tables without arguing about that notation.
    """
    m = Chem.MolFromSmiles(smi)
    if m is None:
        return None
    rw = Chem.RWMol(m)
    anchor = None
    for a in rw.GetAtoms():
        if a.GetAtomicNum() == 0:
            anchor = a.GetIdx()
            break
        if a.GetNumRadicalElectrons() > 0:
            anchor = a.GetIdx()
            break
    if anchor is None:
        return None
    at = rw.GetAtomWithIdx(anchor)
    if at.GetAtomicNum() == 0:
        at.SetAtomicNum(6)                     # the dummy becomes the methyl
        at.SetNoImplicit(False)
        at.SetNumExplicitHs(0)
    else:
        at.SetNumRadicalElectrons(max(0, at.GetNumRadicalElectrons() - 1))
        c = rw.AddAtom(Chem.Atom(6))
        rw.AddBond(anchor, c, Chem.BondType.SINGLE)
    out = rw.GetMol()
    try:
        Chem.SanitizeMol(out)
    except Exception:                                             # noqa: BLE001
        return None
    return Chem.MolToSmiles(out)


def swap_labels(cx, a, b):
    """Replace label `a` with `b` inside a CXSMILES $-block only."""
    core, _, block = cx.partition(" |")
    parts = re.search(r"\$([^$]*)\$", block)
    if not parts:
        return None
    labs = parts.group(1).split(";")
    labs = [b if x == a else x for x in labs]
    return core + " |$" + ";".join(labs) + "$|"


def swap_two(cx):
    """Swap the first two DISTINCT labels with each other, positions kept."""
    core, _, block = cx.partition(" |")
    parts = re.search(r"\$([^$]*)\$", block)
    if not parts:
        return None
    labs = parts.group(1).split(";")
    idx = [i for i, x in enumerate(labs) if x]
    for i in idx:
        for j in idx:
            if i < j and labs[i] != labs[j]:
                labs[i], labs[j] = labs[j], labs[i]
                return core + " |$" + ";".join(labs) + "$|"
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifest", type=Path,
                    default=Path(__file__).resolve().parent / "ground_truth" / "synthetic_manifest.json")
    args = ap.parse_args()
    man = json.loads(args.manifest.read_text())
    fails, checks = [], 0

    def check(cond, msg):
        nonlocal checks
        checks += 1
        if not cond:
            fails.append(msg)

    mols = [(g, m) for g, e in man["groups"].items() for m in e["molecules"]]
    check(len(mols) == 100, f"expected 100 compounds, found {len(mols)}")

    # ---------------------------------------------------- 1. integrity
    for g, m in mols:
        cx = m["drawn_cxsmiles"]
        mol = Chem.MolFromSmiles(cx)
        check(mol is not None, f"{m['name']}: reference CXSMILES does not parse")
        if mol is None:
            continue
        check(Chem.MolToCXSmiles(mol) == cx,
              f"{m['name']}: reference CXSMILES is not idempotent")
        ref = Chem.MolFromSmiles(m["smiles"])
        check(ref is not None, f"{m['name']}: reference SMILES does not parse")
        if ref is None:
            continue
        if not m.get("markush"):
            check(rdMolDescriptors.CalcMolFormula(ref) == m["formula"],
                  f"{m['name']}: recorded formula {m['formula']} != "
                  f"{rdMolDescriptors.CalcMolFormula(ref)} from the recorded SMILES")
            check(Chem.MolToInchiKey(ref) == m["inchikey"],
                  f"{m['name']}: recorded InChIKey does not match the recorded SMILES "
                  f"(CID {m['cid']} may be the wrong record)")
            check(bool(m["cid"]), f"{m['name']}: no PubChem CID")
        if m["has_appendix"] and not m.get("markush"):
            back, note = expand(cx)
            check(back is not None and Chem.CanonSmiles(back) == Chem.CanonSmiles(m["smiles"]),
                  f"{m['name']}: appendix does not expand back to the molecule ({note})")

    # ------------------------------------- 2. the two tables agree on every label
    rd = {a.label: Chem.MolToSmiles(a.mol) for a in rdAbbreviations.GetDefaultAbbreviations()}
    rd["Ph"] = "*c1ccccc1"
    used = sorted({lab for _, m in mols for lab in m["appendix"] if not lab.startswith("R")})
    check(bool(used), "no superatom labels in the corpus at all -- nothing to grade")
    for lab in used:
        a, b = rd.get(lab), getattr(MS_ABBREV.get(lab), "smiles", None)
        check(a is not None, f"label {lab} was drawn but is not in RDKit's table")
        check(b is not None, f"label {lab} was drawn but CXMolScribe cannot emit it")
        if a and b:
            ca, cb = attach_methyl(a), attach_methyl(b)
            check(ca is not None and ca == cb,
                  f"label {lab}: RDKit drew {a} but CXMolScribe means {b} -- "
                  f"({ca} vs {cb}). Ungradeable; remove it from the corpus.")

    # ------------------------------------------------- 3. stratum predicates
    for g, m in mols:
        s, ha, nf = m["stratum"], m["heavy_atoms"], m["fragments"]
        nst, net = m["defined_stereocentres"], m["net_charge"]
        if s == "basic":
            check(nst == 0 and nf == 1 and net == 0 and not m["has_appendix"] and ha <= 26,
                  f"{m['name']}: filed basic but centres={nst} frags={nf} charge={net} "
                  f"heavy={ha} appendix={m['appendix']}")
        elif s == "stereo":
            check(nst >= 3 and not m["has_appendix"],
                  f"{m['name']}: filed stereo but centres={nst} appendix={m['appendix']}")
        elif s == "abbreviated":
            check(m["has_appendix"] and not m.get("markush"),
                  f"{m['name']}: filed abbreviated but appendix={m['appendix']}")
        elif s == "complex":
            # "complex" is an OR: 55+ heavy atoms OR a macrocycle. Erythromycin is
            # 51 atoms round a 14-membered lactone and belongs here; a size-only
            # test rejected it, which is the test being wrong about the stratum.
            check(ha >= 55 or m.get("largest_ring", 0) >= 13,
                  f"{m['name']}: filed complex but {ha} heavy atoms and largest "
                  f"ring {m.get('largest_ring')}")
        elif s == "salt":
            check(nf >= 2 or net != 0,
                  f"{m['name']}: filed salt but frags={nf} net charge={net}")
        elif s == "markush":
            check(m.get("markush") and any(l.startswith("R") for l in m["appendix"]),
                  f"{m['name']}: filed markush but appendix={m['appendix']}")

    # --------------------------------------------- 4. the grader discriminates
    groups = {g: [score_cx.build_reference(x) for x in e["molecules"]]
              for g, e in man["groups"].items()}
    # The probe must be one where swapping two labels actually CHANGES the
    # molecule. aspirin's condensed skeleton is an ortho-disubstituted benzene,
    # so exchanging its OAc and CO2H is a symmetry operation and grading it Y is
    # correct -- picking it as the negative control made the control agree with
    # the thing it controls for, which is how a gate stops being evidence.
    def swap_is_visible(m):
        sw = swap_two(m["drawn_cxsmiles"])
        if sw is None:
            return False
        a, la = score_cx.parse_cx(m["drawn_cxsmiles"])
        b, lb = score_cx.parse_cx(sw)
        return (a is not None and b is not None
                and score_cx.positional_key(a, la) != score_cx.positional_key(b, lb))

    probe = next((m for g, m in mols if m["stratum"] == "abbreviated"
                  and len(set(m["appendix"])) >= 2 and swap_is_visible(m)), None)
    check(probe is not None, "no abbreviated compound where swapping two labels is "
                             "even detectable -- the swap control would prove nothing")
    other = next(g for g in groups if all(x["name"] != (probe or {}).get("name")
                                          for x in groups[g]))
    if probe:
        home = next(g for g, m in mols if m["name"] == probe["name"])
        refs = groups[home]
        cx = probe["drawn_cxsmiles"]

        r = score_cx.grade_one(cx, refs)
        check(r["letter"] == "Y" and r["assigned"] == probe["name"],
              f"CONTROL self: {probe['name']} does not grade as itself "
              f"(letter={r['letter']} assigned={r['assigned']})")

        syn = {"OMe": "MeO", "CF3": "F3C", "CO2H": "HO2C", "NO2": "O2N", "CN": "NC"}
        did_syn = False
        for a, b in syn.items():
            if a in probe["appendix"]:
                r2 = score_cx.grade_one(swap_labels(cx, a, b), refs)
                check(r2["letter"] == "Y",
                      f"CONTROL synonym: {a}->{b} on {probe['name']} graded "
                      f"{r2['letter']}, but they are the same superatom mirrored")
                check(r2["appendix_labels_exact"] is False,
                      f"CONTROL synonym: {a}->{b} should still be flagged as a "
                      f"literal string difference")
                did_syn = True
                break
        check(did_syn, "CONTROL synonym never ran -- no mirrorable label on the probe")

        wrong = "CF3" if "CF3" not in probe["appendix"] else "NO2"
        r3 = score_cx.grade_one(swap_labels(cx, probe["appendix"][0], wrong), refs)
        check(r3["letter"] == "A",
              f"CONTROL wrong label: {probe['appendix'][0]}->{wrong} on "
              f"{probe['name']} graded {r3['letter']}, expected A")

        sw = swap_two(cx)
        check(sw is not None, "CONTROL swap: could not build a two-label swap")
        if sw:
            r4 = score_cx.grade_one(sw, refs)
            check(r4["letter"] == "A",
                  f"CONTROL swapped positions: {probe['name']} graded {r4['letter']}, "
                  f"expected A -- right labels on the wrong atoms must not pass")

        r5 = score_cx.grade_one(cx, groups[other])
        check(r5["letter"] in ("N", "NS"),
              f"CONTROL foreign group: {probe['name']} graded {r5['letter']} against "
              f"group {other}, which does not contain it")

    print(f"{checks} checks, {len(fails)} failures")
    for f in fails:
        print("  FAIL " + f)
    print("GATE: " + ("open" if not fails else "CLOSED"))
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
