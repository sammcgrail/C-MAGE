#!/usr/bin/env python3
"""A gate on the CXSMILES expander: does graph surgery preserve stereochemistry?

WHY A GATE AND NOT A UNIT TEST
------------------------------
Expansion sits between the recogniser and every number on the benchmark tab, so
an expander that quietly emits the wrong stereoisomer does not produce an error —
it produces a *plausible lower accuracy*, which is indistinguishable from the
pipeline being worse than it is. That is exactly the failure this corpus has
already produced three times (`FINDINGS.md` 3): the metric measured
representation rather than recognition, and every time the tell was a chemically
sensible answer scored wrong.

So the web app does not merely test the expander in CI; it **asks this module at
build time whether the expander may be trusted**, and withholds every expanded
figure if the answer is no. A withheld number looks different from a wrong one.

THE INVARIANT, AND WHY IT IS NOT CIRCULAR
-----------------------------------------
Substituting an abbreviation's SMILES into the prediction *as text*, at the
position the dummy atom occupied, cannot reorder any atom's bonds. `@`/`@@` and
`/`-`\\` are both defined relative to bond order, so the textual expansion is
necessarily stereochemically faithful. It is useless in general — it only works
when the label sits at a position where string substitution is well defined — but
that makes it an independent reference for the cases where it does work.

    predicted   */C=C/C=C/C |$COOH;;;;;$|
    textual     OC(=O)/C=C/C=C/C            <- same bonds, same order, by construction
    expanded    must canonicalise to the same molecule

Each case below is a REAL prediction taken from the 11-document benchmark corpus,
not an invented string, and each is paired with a textual equivalent worked out
by hand. Two of them also have an independent third check: the molecule is in the
corpus ground truth, so the expected SMILES came from PubChem rather than from
this file.

THE NEGATIVE CONTROL
--------------------
`naive_expand` is the SUPERSEDED algorithm — `RWMol.RemoveAtom` plus
`AddBond` — kept for one reason: a test whose failure looks like its success
carries no information. It appends the new bond at the END of the anchor's bond
list, which silently reassigns parity. If `naive_expand` ever agreed with the
real expander on every case, this file would have stopped testing anything, and
`run()` says so rather than reporting a pass.

    cxsmiles_selftest.py            # human-readable
    cxsmiles_selftest.py --json     # what the web app consumes
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rdkit import Chem, RDLogger  # noqa: E402

RDLogger.DisableLog("rdApp.*")

import cxsmiles  # noqa: E402


# (name, prediction as CXSMILES, textual expansion, ground-truth SMILES, discriminates)
#
# `textual` is the same string with the label written out where the `*` stood, so
# the bond order the parser sees is unchanged. `truth` is filled in only where the
# molecule is in the corpus manifest, in which case the expected value came from
# PubChem and not from this file.
#
# `discriminates` records whether the superseded algorithm is KNOWN to get this
# case wrong. Only those cases are evidence that the invariant is being enforced
# rather than merely satisfied; the rest are coverage. Both witnesses below are
# real predictions whose benchmark verdict the fix changed — sorbic acid lost a
# double-bond geometry at the attachment point, aglacin A had one tetrahedral
# centre inverted — and between them they are the whole 16 -> 18 difference.
CASES = [
    ("sorbic acid — E/Z at the attachment point",
     "*/C=C/C=C/C |$COOH;;;;;$|",
     "OC(=O)/C=C/C=C/C",
     "C/C=C/C=C/C(=O)O", True),
    ("aglacin A — four stereocentres, six labels, one centre inverted",
     "*c1cc([C@@H]2c3c(cc(*)c(*)c3*)[C@H](*)[C@]3([H])COC[C@@]23[H])cc(*)c1* "
     "|$OMe;;;;;;;;;MeO;;MeO;;MeO;;OAc;;;;;;;;;;MeO;;OMe$|",
     None,
     "COc1cc([C@@H]2c3c(cc(OC)c(OC)c3OC)[C@H](OC(C)=O)[C@@H]3COC[C@@H]23)cc(OC)c1OC", True),
    ("oxazolidinone — two tetrahedral centres beside the join",
     "*[C@@H]1OC(=O)N[C@@H]1C |$Ph;;;;;;;$|",
     "c1ccccc1[C@@H]1OC(=O)N[C@@H]1C",
     "C[C@H]1NC(=O)O[C@H]1c1ccccc1", False),
    ("6-bromopiperonal — a double bond INSIDE the abbreviation (CHO)",
     "*c1cc2c(cc1Br)OCO2 |$CHO;;;;;;;;;;$|",
     "O=Cc1cc2c(cc1Br)OCO2",
     "O=Cc1cc2c(cc1Br)OCO2", False),
    ("a chiral ether — parity with the label on the far side of O",
     "*O[C@@H](C)CC |$Me;;;;;$|",
     "CO[C@@H](C)CC",
     None, False),
    ("three labels on one ring — order must not matter",
     "*Nc1cc(*)cc(*)c1 |$Boc;;;;;OMe;;;MeO;$|",
     None,
     "COc1cc(NC(=O)OC(C)(C)C)cc(OC)c1", False),
]


def canon(smiles):
    """RDKit canonical isomeric SMILES, or None. Never string-compares raw input."""
    if not smiles:
        return None
    mol = Chem.MolFromSmiles(smiles)
    return Chem.MolToSmiles(mol) if mol is not None else None


def naive_expand(cx):
    """The SUPERSEDED expander, kept only as this file's negative control.

    `RemoveAtom` + `AddBond` appends the new bond at the end of the anchor's bond
    list. Both `@`/`@@` and `/`-`\\` are defined relative to that order, so the
    join silently reassigns parity and drops geometry — and produces a perfectly
    valid molecule while doing it. Do not call this for anything real.
    """
    try:
        from molscribe.constants import ABBREVIATIONS
    except ImportError:                                          # pragma: no cover
        return None
    core, labels = cxsmiles.parse(cx)
    mol = Chem.MolFromSmiles(core, sanitize=False)
    if mol is None:
        return None
    rw = Chem.RWMol(mol)
    for i in range(rw.GetNumAtoms() - 1, -1, -1):
        label = labels[i] if i < len(labels) else ""
        if not label or not any(c.isalpha() for c in label):
            continue
        smi = getattr(ABBREVIATIONS.get(label), "smiles", None)
        frag = Chem.MolFromSmiles(smi, sanitize=False) if isinstance(smi, str) and smi else None
        if frag is None:
            continue
        nbrs = [n.GetIdx() for n in rw.GetAtomWithIdx(i).GetNeighbors()]
        if len(nbrs) != 1:
            continue
        anchor, offset = nbrs[0], rw.GetNumAtoms()
        rw.InsertMol(frag)
        rw.AddBond(anchor, offset, Chem.BondType.SINGLE)
        rw.RemoveAtom(i)
    try:
        out = rw.GetMol()
        Chem.SanitizeMol(out)
    except Exception:                                            # noqa: BLE001
        return None
    return Chem.MolToSmiles(out)


def run():
    """-> {ok, cases, failures, naive_disagreements, control_meaningful, reason}.

    `ok` is the gate. It is False if any case fails, and ALSO False if a case
    marked `discriminates` has stopped disagreeing with the superseded algorithm —
    a control that agrees with the thing it controls for has stopped being
    evidence, and would let a silently reverted expander through as a pass.
    """
    cases, failures, blunted = [], [], []
    disagreements = 0
    for name, cx, textual, truth, discriminates in CASES:
        got, note = cxsmiles.expand(cx)
        got_c = canon(got)
        want_c = canon(textual) if textual else None
        truth_c = canon(truth) if truth else None
        # Every reference this case actually has must agree. A case with neither a
        # textual equivalent nor a ground truth would silently pass on anything, so
        # it is a failure of the case, not a pass.
        checks = [w for w in (want_c, truth_c) if w]
        ok = bool(got_c) and bool(checks) and all(got_c == w for w in checks)
        naive_c = canon(naive_expand(cx))
        differs = bool(naive_c) and naive_c != got_c
        disagreements += differs
        rec = {"name": name, "cxsmiles": cx, "expanded": got_c, "note": note,
               "textual": want_c, "truth": truth_c, "ok": ok,
               "naive": naive_c, "naive_differs": differs, "discriminates": discriminates}
        cases.append(rec)
        if not ok:
            failures.append(rec)
        if discriminates and not differs:
            blunted.append(rec)
    control = not blunted
    reason = ""
    if failures:
        reason = (f"{len(failures)} of {len(CASES)} stereo cases fail: "
                  + "; ".join(f["name"] for f in failures))
    elif blunted:
        reason = ("the superseded algorithm now agrees with the expander on "
                  + "; ".join(b["name"] for b in blunted)
                  + " — cases that exist to discriminate have stopped discriminating, so a pass "
                    "here would no longer be evidence of anything")
    return {"ok": not failures and control, "cases": cases,
            "failures": [f["name"] for f in failures],
            "blunted": [b["name"] for b in blunted],
            "naive_disagreements": disagreements,
            "control_meaningful": control, "reason": reason}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true", help="machine-readable, for the web app")
    args = ap.parse_args()
    res = run()
    if args.json:
        json.dump(res, sys.stdout, indent=1)
        print()
        return 0 if res["ok"] else 1
    for c in res["cases"]:
        print(f"[{'ok  ' if c['ok'] else 'FAIL'}] {c['name']}")
        print(f"        predicted   {c['cxsmiles']}")
        print(f"        expanded    {c['expanded']}    (note: {c['note']})")
        if c["textual"]:
            print(f"        textual     {c['textual']}")
        if c["truth"]:
            print(f"        ground truth{'':1s}{c['truth']}")
        tail = ("   <- DIFFERS, so this case has teeth" if c["naive_differs"]
                else "   <- agrees (expected)" if not c["discriminates"]
                else "   <- AGREES, but this case is supposed to discriminate")
        print(f"        superseded  {c['naive']}{tail}")
    n = len(res["cases"])
    disc = sum(1 for c in res["cases"] if c["discriminates"])
    print(f"\n{n - len(res['failures'])}/{n} stereo cases pass; the superseded algorithm "
          f"disagrees on {res['naive_disagreements']}, of which {disc} are the cases that must disagree.")
    print("GATE: " + ("open — expanded figures may be published"
                      if res["ok"] else f"CLOSED — {res['reason']}"))
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
