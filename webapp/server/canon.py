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
  cxsmiles        canonical CXSMILES: like `canonical` but KEEPS the abbreviation
                  labels. Never lossy; use this for storage and export.
  expanded        abbreviations substituted for their real fragments, so the
                  string is usable by any toolkit. None if nothing to expand.
  abbreviations   the labels found, e.g. ["OMe"] -- so a caller can say so
  unexpanded      labels present but NOT in the vocabulary, never guessed

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

WHY `cxsmiles` AND `expanded` BOTH EXIST — and why `canonical` alone was a bug.
CXMolScribe emits CXSMILES on purpose: where a drawing says `OMe`, the prediction
is a dummy atom whose label lives in the `|$OMe;$|` extension block, because this
fork's MolScribe deliberately does not guess an expansion. `Chem.MolToSmiles()`
**silently drops that block**, so `*C |$Ph;$|` came out of here as bare `*C` --
the abbreviation destroyed, with nothing to tell the user it had been. That is
worse than mis-scoring it: an exported SMILES no chemist can use, and no warning.

So: `cxsmiles` (MolToCXSmiles) is the lossless form for storage and export,
`expanded` is the usable form for anyone feeding it to a toolkit, and
`abbreviations` lets the UI say which. Expansion never guesses -- a label absent
from MolScribe's own vocabulary is reported in `unexpanded` instead.

Kept dependency-free on purpose so the web layer never needs RDKit itself: it
shells out to the pipeline's own environment, so the comparison uses the exact
RDKit build the pipeline was run with.
"""
import json
import sys


def _labels(cx):
    """Per-atom abbreviation labels from a CXSMILES extension block, or []."""
    import re
    m = re.match(r"^\S+\s*\|(.*)\|\s*$", cx.strip())
    if not m:
        return []
    block = re.search(r"\$([^$]*)\$", m.group(1))
    if not block:
        return []
    # A label needs a letter: the block also carries coordinate and radical
    # fields, and a bare index is not an abbreviation.
    return [t for t in block.group(1).split(";") if t and any(c.isalpha() for c in t)]


def _expand(cx):
    """(expanded SMILES or None, [labels it could not expand]).

    Uses MolScribe's OWN abbreviation vocabulary -- the same table the model was
    trained against -- and never approximates: an unknown label is returned in
    the second element rather than replaced with a guess. That is the property
    CXSMILES buys, and throwing it away is what made `canonical` lossy.
    """
    import re
    from rdkit import Chem
    try:
        from molscribe.constants import ABBREVIATIONS
    except ImportError:
        return None, ["molscribe vocabulary unavailable"]

    m = re.match(r"^(\S+)\s*\|(.*)\|\s*$", cx.strip())
    if not m:
        return None, []
    core = m.group(1)
    block = re.search(r"\$([^$]*)\$", m.group(2))
    labels = block.group(1).split(";") if block else []
    mol = Chem.MolFromSmiles(core, sanitize=False)
    if mol is None:
        return None, ["unparseable core"]
    rw = Chem.RWMol(mol)
    unknown = []
    # Descending: removing an atom renumbers every index above it.
    for i in range(rw.GetNumAtoms() - 1, -1, -1):
        label = labels[i] if i < len(labels) else ""
        if not label or not any(c.isalpha() for c in label):
            continue
        smi = getattr(ABBREVIATIONS.get(label), "smiles", None)
        frag = Chem.MolFromSmiles(smi, sanitize=False) if smi else None
        if frag is None:
            unknown.append(label)
            continue
        nbrs = [n.GetIdx() for n in rw.GetAtomWithIdx(i).GetNeighbors()]
        if len(nbrs) != 1:
            # No single attachment point; substituting arbitrarily would be a guess.
            unknown.append(f"{label}(attachments={len(nbrs)})")
            continue
        anchor, offset = nbrs[0], rw.GetNumAtoms()
        rw.InsertMol(frag)
        rw.AddBond(anchor, offset, Chem.BondType.SINGLE)
        rw.RemoveAtom(i)
    try:
        out = rw.GetMol()
        Chem.SanitizeMol(out)
    except Exception as e:                            # noqa: BLE001
        return None, unknown + [f"{type(e).__name__}"]
    return Chem.MolToSmiles(out), unknown


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
               "largest": None, "largest_flat": None, "fragments": 0, "phantom": {},
               "cxsmiles": None, "expanded": None, "abbreviations": [],
               "unexpanded": []}
        if isinstance(smi, str) and smi.strip() and smi != "<invalid>":
            # CXSMILES may carry a trailing " |...|" extension block; RDKit's
            # parser understands it, so pass the string through untouched.
            mol = Chem.MolFromSmiles(smi)
            if mol is not None:
                rec["canonical"] = canon(mol)
                rec["flat"] = canon(mol, stereo=False)
                # LOSSLESS: MolToSmiles drops the |$...$| block, MolToCXSmiles
                # keeps it. Anything stored or exported must use this one.
                try:
                    rec["cxsmiles"] = Chem.MolToCXSmiles(mol)
                except Exception:                     # noqa: BLE001
                    rec["cxsmiles"] = None
                labels = _labels(smi)
                rec["abbreviations"] = labels
                if labels:
                    rec["expanded"], rec["unexpanded"] = _expand(smi)
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
