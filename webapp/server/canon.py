"""Canonicalise SMILES with RDKit. Runs under the stage-3 interpreter.

Reads a JSON list of SMILES strings on stdin, writes a JSON list of
{"canonical": ..., "flat": ..., "valid": bool} on stdout, in the same order.

  canonical  RDKit canonical isomeric SMILES (stereo kept)
  flat       canonical SMILES with all stereochemistry removed

Comparing `canonical` tells you two strings are the same molecule including
stereo; comparing `flat` tells you they agree up to stereochemistry. String
equality on raw SMILES tells you nothing, which is why this exists.

Kept dependency-free on purpose so the web layer never needs RDKit itself: it
shells out to the pipeline's own environment, so the comparison uses the exact
RDKit build the pipeline was run with.
"""
import json
import sys


def main() -> int:
    from rdkit import Chem, RDLogger
    RDLogger.DisableLog("rdApp.*")

    out = []
    for smi in json.load(sys.stdin):
        rec = {"canonical": None, "flat": None, "valid": False}
        if isinstance(smi, str) and smi.strip() and smi != "<invalid>":
            # CXSMILES may carry a trailing " |...|" extension block; RDKit's
            # parser understands it, so pass the string through untouched.
            mol = Chem.MolFromSmiles(smi)
            if mol is not None:
                rec["canonical"] = Chem.MolToSmiles(mol, isomericSmiles=True)
                flat = Chem.Mol(mol)
                Chem.RemoveStereochemistry(flat)
                rec["flat"] = Chem.MolToSmiles(flat, isomericSmiles=False)
                rec["valid"] = True
        out.append(rec)
    json.dump(out, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
