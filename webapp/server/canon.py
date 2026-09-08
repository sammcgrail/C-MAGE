"""Canonicalise SMILES with RDKit. Runs under the stage-3 interpreter.

Reads a JSON list of SMILES strings on stdin, writes a JSON list of records on
stdout, in the same order:

  canonical       RDKit canonical isomeric SMILES of the WHOLE string
  flat            the same with all stereochemistry removed
  valid           RDKit parsed it
  largest         canonical isomeric SMILES of the largest fragment alone
  largest_flat    the same with stereochemistry removed
  fragments       how many disconnected fragments the string contains
  phantom         {fragment SMILES: count} for every fragment that is NOT the
                  largest one -- the material a "largest fragment" score drops

Comparing `canonical` tells you two strings are the same molecule including
stereo; comparing `flat` tells you they agree up to stereochemistry. String
equality on raw SMILES tells you nothing, which is why this exists.

WHY THE FRAGMENT FIELDS EXIST. On a real corpus this pipeline frequently
recovers the molecule and then appends phantom DISCONNECTED atoms -- almost
always `I` (an OH label read as iodine) or `[HH]`. Oxalic acid came back as
`I.I.I.O=C(O)C(=O)O.[HH].[HH]`: a correct core inside an unusable string. Both
numbers are needed to describe that honestly, so both are computed here rather
than being asserted in prose somewhere. Largest is by HEAVY atom count, not
total atoms: `[HH]` has two atoms and zero heavy atoms, and it is exactly the
phantom the split exists to isolate.

Kept dependency-free on purpose so the web layer never needs RDKit itself: it
shells out to the pipeline's own environment, so the comparison uses the exact
RDKit build the pipeline was run with.
"""
import json
import sys


def main() -> int:
    from rdkit import Chem, RDLogger
    RDLogger.DisableLog("rdApp.*")

    def canon(mol, stereo=True):
        m = Chem.Mol(mol)
        if not stereo:
            Chem.RemoveStereochemistry(m)
        return Chem.MolToSmiles(m, isomericSmiles=stereo)

    out = []
    for smi in json.load(sys.stdin):
        rec = {"canonical": None, "flat": None, "valid": False,
               "largest": None, "largest_flat": None, "fragments": 0, "phantom": {}}
        if isinstance(smi, str) and smi.strip() and smi != "<invalid>":
            # CXSMILES may carry a trailing " |...|" extension block; RDKit's
            # parser understands it, so pass the string through untouched.
            mol = Chem.MolFromSmiles(smi)
            if mol is not None:
                rec["canonical"] = canon(mol)
                rec["flat"] = canon(mol, stereo=False)
                rec["valid"] = True
                try:
                    frags = Chem.GetMolFrags(mol, asMols=True, sanitizeFrags=True)
                except Exception:                     # noqa: BLE001 - a weird fragment must not lose the whole record
                    frags = ()
                if frags:
                    rec["fragments"] = len(frags)
                    order = sorted(range(len(frags)), key=lambda i: -frags[i].GetNumHeavyAtoms())
                    best = frags[order[0]]
                    rec["largest"] = canon(best)
                    rec["largest_flat"] = canon(best, stereo=False)
                    for i in order[1:]:
                        key = Chem.MolToSmiles(frags[i])
                        rec["phantom"][key] = rec["phantom"].get(key, 0) + 1
        out.append(rec)
    json.dump(out, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
