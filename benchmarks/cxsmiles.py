#!/usr/bin/env python3
"""Expand CXSMILES abbreviation labels into full structures, for scoring.

WHY THIS EXISTS — and why the pipeline is right not to do it itself
-------------------------------------------------------------------
CXMolScribe emits **CXSMILES**, not plain SMILES, and that is the point of it.
Where a drawing says `OMe`, the prediction is a dummy atom carrying the label
`OMe` in the CXSMILES extension block:

    *c1cc2c(cc1-c1cc(O)c3cc4c(cc3c1)OCO4)OCO2 |$OMe;;;;;;;;;;;;;;;;;$|

This fork's MolScribe deliberately does NOT expand that at prediction time —
`chemistry.py:_expand_abbreviation` has its `ABBREVIATIONS` lookup commented out
so the label survives verbatim, where upstream MolScribe would have substituted a
guess. Preserving it is strictly more information: the abbreviation as drawn is
recoverable, and an abbreviation the vocabulary does not know is *visible* rather
than silently wrong.

The consequence for benchmarking is easy to get wrong, and was: comparing a
CXSMILES against a fully-expanded reference SMILES can only ever fail, because
the two are different representations of the same molecule. 162 of 242
predictions on the expanded PDF corpus were scored "wrong" for this reason alone,
with nothing wrong with the recognition. **Expansion belongs here, at comparison
time**, using the same `ABBREVIATIONS` table the model was trained against.

    cxsmiles.py --smiles '*C |$Ph;$|'        # -> Cc1ccccc1
    cxsmiles.py --csv structures.csv         # add expanded + verdict columns
"""
import argparse
import csv
import re
import sys

from rdkit import Chem, RDLogger

RDLogger.DisableLog("rdApp.*")
try:
    from molscribe.constants import ABBREVIATIONS
except ImportError:                                              # pragma: no cover
    sys.exit("cxsmiles.py needs molscribe — run it with the stage-3 interpreter "
             "(.venv-ms/bin/python)")


# Two kinds of label cannot be expanded, and lumping them together misreads the
# result. A MARKUSH VARIABLE denotes no single molecule — nobody can expand `R1`,
# and a scorer should not be marked down for it. A MISSING ABBREVIATION does
# denote a definite group (OTBS is tert-butyldimethylsilyl) that simply is not in
# MolScribe's 75-entry vocabulary; that one is a coverage gap worth closing.
_MARKUSH = re.compile(r"^(R\d*|X|Y|Z|Ar|Alk|SR\d*|OR\d*|NR\d*|R[a-z]+|OR[a-z]+)$")


def label_class(label):
    """'markush' | 'missing' — why a label could not be expanded."""
    return "markush" if _MARKUSH.match(label or "") else "missing"


def parse(cx):
    """Split a CXSMILES into (core SMILES, [per-atom label]).

    Returns an empty label list for a plain SMILES, so callers need no special
    case for predictions that happen to carry no abbreviation.
    """
    m = re.match(r"^(\S+)\s*\|(.*)\|\s*$", cx.strip())
    if not m:
        return cx.strip(), []
    core, ext = m.group(1), m.group(2)
    labels = re.search(r"\$([^$]*)\$", ext)
    return core, (labels.group(1).split(";") if labels else [])


def expand(cx):
    """(expanded_smiles, note). note is 'ok', or names what could not be expanded.

    Joins with **Chem.molzip**, not RWMol surgery, and that choice is the whole
    correctness story. An earlier version did `RemoveAtom` + `AddBond`, which
    appends the new bond at the END of the anchor's bond list — and `@`/`@@` is
    defined relative to bond order, so 5 of 7 tetrahedral centres FLIPPED and 4 of
    5 alkene E/Z assignments were lost. It also silently downgraded a double bond
    to the dummy into a single bond. It produced wrong stereoisomers that parsed
    cleanly, which is the worst kind of wrong. `molzip` keeps the anchor's own bond
    object, so parity, E/Z and bond order all survive.

    Never guesses: an abbreviation absent from ABBREVIATIONS is reported, not
    approximated. A label on an atom that is not a dummy is also refused — deleting
    a real atom because it carried a label is not an expansion.
    """
    core, labels = parse(cx)
    if not any(labels):
        mol = Chem.MolFromSmiles(core)
        return (Chem.MolToSmiles(mol), "no abbreviations") if mol else (None, "unparseable")

    # removeHs=False keeps explicit [H] atoms, so the label list stays aligned with
    # atom indices. Sanitising here would silently drop them and misalign everything.
    params = Chem.SmilesParserParams()
    params.removeHs = False
    params.sanitize = False
    mol = Chem.MolFromSmiles(core, params)
    if mol is None:
        return None, "unparseable core"

    rw = Chem.RWMol(mol)
    unknown = []
    frags = []
    tag = 1
    for i in range(rw.GetNumAtoms()):
        label = labels[i] if i < len(labels) else ""
        if not label or not any(c.isalpha() for c in label):
            continue
        atom = rw.GetAtomWithIdx(i)
        if atom.GetSymbol() != "*":
            # A label on a real atom is not an attachment point.
            unknown.append(f"{label}(on {atom.GetSymbol()})")
            continue
        smi = getattr(ABBREVIATIONS.get(label), "smiles", None)
        # Belt and braces: a table entry can be absent, None, or a string RDKit
        # refuses — and RDKit raises TypeError rather than returning None for some
        # of those. Any failure here means "unknown", never a guess.
        frag = None
        if isinstance(smi, str) and smi:
            try:
                frag = Chem.MolFromSmiles(smi, params)
            except Exception:                                    # noqa: BLE001
                frag = None
        if frag is None:
            unknown.append(label)
            continue
        # The abbreviation's radical atom is its attachment point; every entry in
        # the table has exactly one and it is atom 0.
        fw = Chem.RWMol(frag)
        star = fw.AddAtom(Chem.Atom(0))
        fw.GetAtomWithIdx(star).SetAtomMapNum(tag)
        fw.AddBond(0, star, Chem.BondType.SINGLE)
        # Radical electron consumed by the new bond.
        a0 = fw.GetAtomWithIdx(0)
        a0.SetNumRadicalElectrons(max(0, a0.GetNumRadicalElectrons() - 1))
        frags.append(fw.GetMol())
        atom.SetAtomMapNum(tag)
        tag += 1

    if not frags:
        try:
            out = rw.GetMol()
            Chem.SanitizeMol(out)
            return Chem.MolToSmiles(out), (",".join(unknown) if unknown else "ok")
        except Exception as e:                                   # noqa: BLE001
            return None, f"{type(e).__name__}"

    combined = rw.GetMol()
    for f in frags:
        combined = Chem.CombineMols(combined, f)
    try:
        zipped = Chem.molzip(combined)
        Chem.SanitizeMol(zipped)
        Chem.AssignStereochemistry(zipped, cleanIt=True, force=True)
        return Chem.MolToSmiles(zipped), (",".join(unknown) if unknown else "ok")
    except Exception as e:                                       # noqa: BLE001
        return None, f"{type(e).__name__}: {e}"


def canon(smi, stereo=True):
    if not smi:
        return None
    mol = Chem.MolFromSmiles(smi)
    if mol is None:
        return None
    if not stereo:
        Chem.RemoveStereochemistry(mol)
    return Chem.MolToSmiles(mol)


def largest_fragment(smi):
    """Discard the phantom disconnected atoms characterised in FINDINGS.md 2."""
    mol = Chem.MolFromSmiles(smi) if smi else None
    if mol is None:
        return None
    frags = Chem.GetMolFrags(mol, asMols=True, sanitizeFrags=True)
    return Chem.MolToSmiles(max(frags, key=lambda f: f.GetNumHeavyAtoms())) if frags else None


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--smiles", help="expand one CXSMILES and print it")
    g.add_argument("--csv", help="a score_run.py structures.csv to expand")
    ap.add_argument("--out", help="write the augmented CSV here")
    args = ap.parse_args()

    if args.smiles:
        smi, note = expand(args.smiles)
        print(f"expanded: {smi}\nnote:     {note}")
        return 0 if smi else 1

    rows = list(csv.DictReader(open(args.csv)))
    if not rows:
        sys.exit(f"{args.csv} has no rows")
    stats = {"expanded": 0, "no_abbrev": 0, "unknown": 0, "failed": 0}
    for r in rows:
        smi, note = expand(r["smiles"])
        r["expanded_smiles"] = smi or ""
        r["expansion_note"] = note
        r["expanded_largest_fragment"] = largest_fragment(smi) or ""
        if smi is None:
            stats["failed"] += 1
        elif note == "ok":
            stats["expanded"] += 1
        elif note == "no abbreviations":
            stats["no_abbrev"] += 1
        else:
            stats["unknown"] += 1
    if args.out:
        with open(args.out, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
    n = len(rows)
    print(f"{n} predictions: {stats['expanded']} abbreviations expanded, "
          f"{stats['no_abbrev']} had none, {stats['unknown']} had an unknown label, "
          f"{stats['failed']} unparseable")

    # Split the unexpandable, because the two classes mean different things.
    markush, missing = {}, {}
    for r in rows:
        for lab in (r.get("expansion_note") or "").split(","):
            lab = lab.split("(")[0].strip()
            if not lab or lab in ("ok", "no abbreviations"):
                continue
            d = markush if label_class(lab) == "markush" else missing
            d[lab] = d.get(lab, 0) + 1
    if markush:
        print(f"  Markush variables, not expandable by anyone ({sum(markush.values())} "
              f"occurrences): {', '.join(sorted(markush))}")
    if missing:
        print(f"  real abbreviations missing from the vocabulary ({sum(missing.values())} "
              f"occurrences): {', '.join(sorted(missing))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
