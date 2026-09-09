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

    Never guesses: an abbreviation absent from ABBREVIATIONS is reported, not
    approximated. That is the property the CXSMILES representation buys.
    """
    core, labels = parse(cx)
    if not any(labels):
        mol = Chem.MolFromSmiles(core)
        return (Chem.MolToSmiles(mol), "no abbreviations") if mol else (None, "unparseable")

    mol = Chem.MolFromSmiles(core, sanitize=False)
    if mol is None:
        return None, "unparseable core"
    rw = Chem.RWMol(mol)
    unknown = []
    # Descending index: removing an atom renumbers everything above it.
    for i in range(rw.GetNumAtoms() - 1, -1, -1):
        label = labels[i] if i < len(labels) else ""
        if not label:
            continue
        entry = ABBREVIATIONS.get(label)
        smi = getattr(entry, "smiles", None)
        if smi is None:
            unknown.append(label)
            continue
        frag = Chem.MolFromSmiles(smi, sanitize=False)
        if frag is None:
            unknown.append(label)
            continue
        nbrs = [n.GetIdx() for n in rw.GetAtomWithIdx(i).GetNeighbors()]
        if len(nbrs) != 1:
            # A label on a bridging atom has no single attachment point; leaving
            # it alone is honest, substituting arbitrarily is not.
            unknown.append(f"{label}(attachments={len(nbrs)})")
            continue
        anchor, offset = nbrs[0], rw.GetNumAtoms()
        rw.InsertMol(frag)
        rw.AddBond(anchor, offset, Chem.BondType.SINGLE)
        rw.RemoveAtom(i)
    try:
        out = rw.GetMol()
        Chem.SanitizeMol(out)
    except Exception as e:                                       # noqa: BLE001
        return None, f"{type(e).__name__}: {e}"
    return Chem.MolToSmiles(out), (",".join(unknown) if unknown else "ok")


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
    return 0


if __name__ == "__main__":
    sys.exit(main())
