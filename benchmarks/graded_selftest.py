#!/usr/bin/env python3
"""A gate on the graded verdicts: does a looser rung ever pass a wrong molecule?

WHY A GATE AND NOT A UNIT TEST
------------------------------
`graded.py` exists to show that most of the strict `wrong` pile is a
representation difference. A grading scheme loose enough to also pass genuinely
different molecules would produce a HIGHER, FRIENDLIER NUMBER and no error --
which is worse than the strict metric it was meant to improve on, and reads
exactly like a better pipeline. So the failure mode this file guards is not "the
grader crashed", it is "the grader got generous".

Every negative case below was a LIVE FALSE PASS during development, not an
invented worry:

  carboplatin  the prediction lost the platinum entirely. Comparing largest
               fragment to largest fragment, and later rdMolStandardize's
               FragmentParent, both reduced the two sides to cyclobutane-1,1-
               dicarboxylic acid and graded it `exact`.
  oxaliplatin  the prediction draws Pt covalently. Fragment-based normalisation
               kept the diaminocyclohexane LIGAND on both sides and graded a match
               on something that is not the compound.
  glucose /    Morgan fingerprints are stereo-blind, so two diastereomers score
  galactose    Tanimoto 1.000. If a Tanimoto rule could ever reach `exact`, every
               enantiomer pair in the corpus would silently pass.
  [I-]         a genuine iodide counter-ion has the same shape as the phantom
               iodine artifact and must NOT be swept up by the phantom rule.

AND THE POSITIVE CONTROL, which is the one people forget: a prediction the strict
scorer already calls `exact` must come back `exact` here with NO normalisation
applied. If a normalisation step is "improving" an answer that was already right,
it is not normalising, it is guessing.

TEETH
-----
A control whose failure looks like its success carries no information. Two of
these cases therefore assert BOTH directions: the guard blocks the match, AND the
same comparison with the guard bypassed WOULD have matched. If bypassing the
guard ever stops changing the answer, the guard has stopped being tested and this
file says so rather than reporting a pass.

    graded_selftest.py            # human-readable
    graded_selftest.py --json     # machine-readable
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import graded  # noqa: E402

MATCHED = graded.MATCHED

# name, predicted SMILES, reference SMILES, expected grade, expected normalisations
CASES = [
    # ---- positive: right answers must stay right, untouched
    ("control: exact stays exact", "CC(=O)Nc1ccc(O)cc1", "CC(=O)Nc1ccc(O)cc1",
     "exact", set()),
    ("control: a real match needs no normalisation",
     "Cc1nnc2n1-c1ccc(Cl)cc1C(c1ccccc1)=NC2", "Cc1nnc2n1-c1ccc(Cl)cc1C(c1ccccc1)=NC2",
     "exact", set()),
    # ---- positive: the representation differences this module exists to name
    ("phantom I/[HH] stripped", "CC(=O)Oc1ccccc1C(=O)O.I.I.[HH]",
     "CC(=O)Oc1ccccc1C(=O)O", "exact", {"dephantom"}),
    ("CXSMILES abbreviation decoded", "*C[C@@H](CN)CC(C)C |$CO2H;;;;;;;;$|",
     "CC(C)C[C@H](CN)CC(=O)O", "exact", {"decoded"}),
    ("tautomer (sildenafil, real prediction)",
     "CCCc1nn(C)c2c(=O)nc(-c3cc(S(=O)(=O)N4CCN(C)CC4)ccc3OCC)[nH]c12",
     "CCCc1nn(C)c2c(=O)[nH]c(-c3cc(S(=O)(=O)N4CCN(C)CC4)ccc3OCC)nc12",
     "tautomer", set()),
    ("protonation only (ciprofloxacin carboxylate)",
     "O=C([O-])c1cn(C2CC2)c2cc(N3CCNCC3)c(F)cc2c1=O",
     "O=C(O)c1cn(C2CC2)c2cc(N3CCNCC3)c(F)cc2c1=O", "charge", set()),
    ("counter-ion only (osimertinib free base vs mesylate)",
     "C=CC(=O)Nc1cc(Nc2nccc(-c3cn(C)c4ccccc34)n2)c(OC)cc1N(C)CCN(C)C",
     "C=CC(=O)Nc1cc(Nc2nccc(-c3cn(C)c4ccccc34)n2)c(OC)cc1N(C)CCN(C)C.CS(=O)(=O)O",
     "salt", set()),
    ("protonation the Uncharger cannot reach, permanent cation (thiamine PP)",
     "Cc1ncc(C[n+]2csc(CCOP(=O)(O)OP(=O)(O)O)c2C)c(N)n1",
     "Cc1ncc(C[n+]2csc(CCOP(=O)(O)OP(=O)([O-])O)c2C)c(N)n1", "skeleton", set()),
    # ---- negative: these must NOT reach a matched grade
    ("NEGATIVE metal lost: carboplatin without its platinum",
     "O=C([O-])C1(C(=O)[O-])CCC1.[HH].[HH].[H]N[HH]",
     "N.N.O=C([O-])C1(C(=O)[O-])CCC1.[Pt+2]", "near", None),
    ("NEGATIVE metal coordinated: oxaliplatin drawn covalently",
     "[H][N]1C2([H])CCCCC2([HH])[NH][Pt]12[O]C(=O)C(=O)[O]2",
     "O=C(O)C(=O)O.[NH-][C@@H]1CCCC[C@H]1[NH-].[Pt+2]", "wrong", None),
    ("NEGATIVE stereo-blind fingerprint: galactose vs glucose, Tanimoto 1.000",
     "OC[C@H]1OC(O)[C@H](O)[C@@H](O)[C@H]1O", "OC[C@H]1OC(O)[C@H](O)[C@@H](O)[C@@H]1O",
     "stereo", None),
    ("NEGATIVE genuine counter-ion: [I-] is not a phantom",
     "CN1CCN(C2=Nc3cc(Cl)ccc3Nc3ccccc32)CC1.[I-]",
     "CN1CCN(C2=Nc3cc(Cl)ccc3Nc3ccccc32)CC1", "salt", set()),
    ("NEGATIVE one carbon too many: strychnine homologue at Tanimoto 0.845",
     "[H][C@@]12N3C(=O)C[C@]4([H])OCC=C5CCN6CC[C@@]1(c1ccccc13)[C@]6([H])C[C@]5([H])[C@]24[H]",
     "O=C1C[C@H]2OCC=C3CN4CC[C@]56c7ccccc7N1[C@H]5[C@H]2[C@H]3C[C@H]46",
     "wrong", None),
]


def run():
    cases, failures = [], []
    for name, pred, ref, want, want_norm in CASES:
        rf = graded.ref_forms(ref)
        got = graded.grade_prediction(pred, [("reference", rf)])
        norm = {k for k in ("decoded", "dephantom", "dedup") if got[k]}
        ok = got["grade"] == want and (want_norm is None or norm == want_norm)
        # a negative case must additionally not be claimed as a match at all
        if name.startswith("NEGATIVE") and got["grade"] in MATCHED and want not in MATCHED:
            ok = False
        cases.append({"name": name, "pred": pred, "ref": ref, "want": want,
                      "grade": got["grade"], "grade_largest": got["grade_largest"],
                      "tanimoto": got["best_tanimoto"], "normalisations": sorted(norm),
                      "want_normalisations": None if want_norm is None else sorted(want_norm),
                      "ok": ok})
        if not ok:
            failures.append(name)

    # ---- teeth: the metal guard must still be capable of changing an answer.
    # It is exercised against the thing it guards, which is FRAGMENT-PARENT style
    # normalisation, not against the SaltRemover currently wired in. SaltRemover
    # leaves [Pt+2] alone, so with it the guard is a no-op on these two cases and a
    # test run that way would report a pass while testing nothing. Swapping the
    # stripper back to FragmentParent is precisely the regression the guard exists
    # to survive, so that is the condition under which it must demonstrably bite.
    teeth = []
    for label, pred, ref in [
            ("carboplatin (metal on one side only)",
             "O=C([O-])C1(C(=O)[O-])CCC1.[HH].[HH].[H]N[HH]",
             "N.N.O=C([O-])C1(C(=O)[O-])CCC1.[Pt+2]"),
            ("oxaliplatin (metal covalently bonded)",
             "[H][N]1C2([H])CCCCC2([HH])[NH][Pt]12[O]C(=O)C(=O)[O]2",
             "O=C(O)C(=O)O.[NH-][C@@H]1CCCC[C@H]1[NH-].[Pt+2]")]:
        saved_strip, saved_guard = graded.salt_stripped, graded.metal_guard

        def fragment_parent(mol, key, stereo=True, _g=graded):
            m = _g._UNC.uncharge(_g.rdMolStandardize.FragmentParent(_g.Chem.Mol(mol)))
            _g.Chem.SanitizeMol(m)
            return _g.canon(m, True) if stereo else _g.flat(m)

        try:
            graded.salt_stripped = fragment_parent
            graded._cache.clear()
            pf = graded.forms(graded.parse_mol(pred))
            rf2 = graded.forms(graded.parse_mol(ref))
            with_guard = graded.compare(pf, rf2)[0]
            graded.metal_guard = lambda a, b: True
            without_guard = graded.compare(pf, rf2)[0]
        finally:
            graded.salt_stripped, graded.metal_guard = saved_strip, saved_guard
            graded._cache.clear()
        # Without the guard the salt rung must reach a matched grade, or this case
        # has stopped exercising the guard and proves nothing.
        discriminates = without_guard in MATCHED and with_guard not in MATCHED
        teeth.append({"case": label, "with_guard": with_guard,
                      "without_guard": without_guard, "discriminates": discriminates})
        if not discriminates:
            failures.append(f"metal guard no longer discriminates on {label}")

    # ---- teeth: the phantom rule must be narrow, not "drop small fragments"
    narrow = []
    for smi, want_dropped in [("CC(=O)O.I.II.[HH].[H]", True), ("CC(=O)O.[I-]", False),
                              ("CC(=O)O.CC", False), ("CC(=O)O.Cl", False)]:
        mol = graded.parse_mol(smi)
        _m, phantoms, _d = graded.dephantom(mol)
        ok = bool(phantoms) == want_dropped
        narrow.append({"smiles": smi, "dropped": phantoms, "ok": ok})
        if not ok:
            failures.append(f"phantom rule wrong on {smi}")

    return {"ok": not failures, "failures": failures, "cases": cases,
            "metal_guard_teeth": teeth, "phantom_rule": narrow,
            "reason": "; ".join(failures) if failures else ""}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    res = run()
    if args.json:
        json.dump(res, sys.stdout, indent=1)
        print()
        return 0 if res["ok"] else 1
    for c in res["cases"]:
        print(f"[{'ok  ' if c['ok'] else 'FAIL'}] {c['name']}")
        print(f"        pred   {c['pred'][:96]}")
        print(f"        ref    {c['ref'][:96]}")
        print(f"        grade  {c['grade']} (want {c['want']}); +largest {c['grade_largest']}; "
              f"Tanimoto {c['tanimoto']}; normalisations {c['normalisations'] or 'none'}")
    print()
    for t in res["metal_guard_teeth"]:
        mark = "has teeth" if t["discriminates"] else "NO LONGER DISCRIMINATES"
        print(f"[{'ok  ' if t['discriminates'] else 'FAIL'}] metal guard, {t['case']}: "
              f"{t['with_guard']} with guard vs {t['without_guard']} without  <- {mark}")
    for p in res["phantom_rule"]:
        print(f"[{'ok  ' if p['ok'] else 'FAIL'}] phantom rule {p['smiles']} -> dropped {p['dropped'] or 'nothing'}")
    n = len(res["cases"])
    print(f"\n{n - sum(1 for c in res['cases'] if not c['ok'])}/{n} grading cases pass.")
    print("GATE: " + ("open — graded verdicts may be reported"
                      if res["ok"] else f"CLOSED — {res['reason']}"))
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
