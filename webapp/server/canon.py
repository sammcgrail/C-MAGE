"""Canonicalise SMILES with RDKit. Runs under the stage-3 interpreter.

Reads a JSON list of SMILES strings on stdin, writes a JSON list of records on
stdout, in the same order:

  canonical         RDKit canonical isomeric SMILES of the WHOLE string
  flat              the same with all stereochemistry removed
  valid             RDKit parsed it
  largest           canonical isomeric SMILES of the largest fragment alone
  largest_flat      the same with stereochemistry removed
  fragments         how many disconnected fragments the string contains
  phantom           {fragment SMILES: count} for every fragment that is NOT the
                    largest one -- the material a "largest fragment" score drops
  cxsmiles          canonical CXSMILES: like `canonical` but KEEPS the abbreviation
                    labels. Never lossy; use this for storage and export.
  expanded          abbreviations substituted for their real fragments, so the
                    string is usable by any toolkit. None if nothing to expand.
  abbreviations     the labels found, e.g. ["OMe"] -- so a caller can say so
  unexpanded        labels present but NOT expanded, never guessed
  markush           of those, the ones that denote no single molecule (R1, X, OR2)
  missing           of those, the ones that denote a definite group absent from
                    CXMolScribe's vocabulary (OTBS, OTHP) -- a closable coverage gap
  failed            not labels: diagnostics from an expansion that could not be
                    completed. A defect in the expander, counted apart from both
  exp_canonical     canonical isomeric SMILES of the EXPANDED molecule
  exp_flat          the same with stereochemistry removed
  exp_largest       largest fragment of the expanded molecule
  exp_largest_flat  the same with stereochemistry removed
  expander          which expander produced the above, or why none did

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

WHY `cxsmiles` AND `expanded` BOTH EXIST -- and why `canonical` alone was a bug.
CXMolScribe emits CXSMILES on purpose: where a drawing says `OMe`, the prediction
is a dummy atom whose label lives in the `|$OMe;$|` extension block, because
C-MAGE's vendored MolScribe deliberately does not guess an expansion.
`Chem.MolToSmiles()` **silently drops that block**, so `*C |$Ph;$|` came out of
here as bare `*C` -- the abbreviation destroyed, with nothing to tell the user it
had been. That is worse than mis-scoring it: an exported SMILES no chemist can
use, and no warning.

So: `cxsmiles` (MolToCXSmiles) is the lossless form for storage and export,
`expanded` is the usable form for anyone feeding it to a toolkit, and
`abbreviations` lets the UI say which. Expansion never guesses -- a label that
cannot be expanded is reported in `unexpanded`, split into `markush` and
`missing`, with expander diagnostics kept apart again in `failed`. Three findings,
never summed: nobody's fault, a closable vocabulary gap, and our own bug.

WHY THE `exp_*` FIELDS ARE FILLED IN EVEN WHEN NOTHING WAS EXPANDED. They are set
to the plain values in that case, so a consumer comparing on them needs no
fallback branch. A fallback in the consumer is a fallback that gets written twice
and diverges; the semantics belong here, where RDKit is.

WHERE THE EXPANDER LIVES. `benchmarks/cxsmiles.py`, imported -- NOT reimplemented
here. It was reimplemented here once, and the copies then had to be fixed
separately: the join must be done with `Chem.molzip`, because `RWMol.RemoveAtom`
plus `AddBond` appends the new bond at the end of the anchor's bond list and
`@`/`@@` and `/`-`\\` are both defined relative to that order, so the naive join
silently emits the wrong stereoisomer. Two copies of that is two chances to have
it wrong and no way to tell which number came from which. If the import fails the
`exp_*` fields fall back to the unexpanded values and `expander` says so, which
the UI must render as "withheld" rather than as a result.

Kept dependency-free of the web layer on purpose: the web process never needs
RDKit, it shells out to the pipeline's own environment, so the comparison uses the
exact RDKit build the pipeline was run with.
"""
import json
import os
import re
import sys

# The expander is imported from the benchmark tree, which the deployment mounts.
# CMAGE_CXSMILES_DIR is set by chem.py; the two fallbacks cover a source checkout
# and an image that carries the repository at the app root.
_here = os.path.dirname(os.path.abspath(__file__))
for _cand in (os.environ.get("CMAGE_CXSMILES_DIR"),
              os.path.join(_here, "..", "..", "benchmarks"),
              "/benchmarks"):
    if _cand and os.path.isfile(os.path.join(_cand, "cxsmiles.py")):
        sys.path.insert(0, os.path.abspath(_cand))
        break

try:
    from cxsmiles import expand as _expand_cx, label_class as _label_class
    EXPANDER = "benchmarks/cxsmiles.py"
except ImportError as _exc:                                      # pragma: no cover
    _expand_cx = _label_class = None
    EXPANDER = f"unavailable: {_exc}"


def _labels(cx):
    """Per-atom abbreviation labels from a CXSMILES extension block, or []."""
    m = re.match(r"^\S+\s*\|(.*)\|\s*$", cx.strip())
    if not m:
        return []
    block = re.search(r"\$([^$]*)\$", m.group(1))
    if not block:
        return []
    # A label needs a letter: the block also carries coordinate and radical
    # fields, and a bare index is not an abbreviation.
    return [t for t in block.group(1).split(";") if t and any(c.isalpha() for c in t)]


def _split_unexpanded(note):
    """A note from expand() -> ([markush], [missing], [failed]).

    `note` is 'ok', 'no abbreviations', or a comma-joined list of what could not be
    expanded. THREE different things end up in that list and they are three
    different findings, so they are not summed:

      markush  the label denotes no single molecule -- `R1`, `X`, `OR2`. Nobody can
               expand it and no scorer should be marked down for it.
      missing  the label denotes a definite group (`OTBS` is tert-butyldimethyl-
               silyl) that is simply absent from CXMolScribe's 75-entry vocabulary.
               A closable coverage gap.
      failed   not a label at all: an RDKit diagnostic that the expander could not
               complete the join. A defect in the expander, not in the model or the
               vocabulary, and it must not be displayed as if `RuntimeError:
               Invariant Violation ...` were an abbreviation a chemist wrote.

    The third bucket exists because the diagnostics DID appear in the vocabulary
    list once, where a multi-line RDKit traceback sat among OMe and Ph as though it
    were the fourth most common abbreviation in the corpus.
    """
    if not note or note in ("ok", "no abbreviations"):
        return [], [], []
    markush, missing, failed = [], [], []
    for part in note.split(","):
        label = part.strip()
        if not label:
            continue
        # A label is short, single-line, and has no colon in it. Anything else is a
        # diagnostic. Checked by SHAPE rather than against a list of exception names,
        # because the next RDKit release may raise something not on the list.
        if ":" in label or "\n" in label or len(label) > 24:
            failed.append(" ".join(label.split())[:120])
            continue
        # Strip ONLY the expander's own diagnostic suffixes. Splitting on "(" would
        # cut `OPO(OEt)2` down to `OPO`, which is not a group anybody drew -- the
        # parenthesis there is chemistry, not annotation.
        base = re.sub(r"\((?:attachments=|on )[^)]*\)\s*$", "", label).strip()
        if not base:
            failed.append(label)
        elif _label_class and _label_class(base) == "markush":
            markush.append(base)
        else:
            missing.append(base)
    return markush, missing, failed


def main():
    from rdkit import Chem, RDLogger
    RDLogger.DisableLog("rdApp.*")

    def canon(mol, stereo=True):
        m = Chem.Mol(mol)
        if not stereo:
            Chem.RemoveStereochemistry(m)
        return Chem.MolToSmiles(m, isomericSmiles=stereo)

    def forms(smiles):
        """(canonical, flat, largest, largest_flat) for a plain SMILES, or 4 Nones."""
        mol = Chem.MolFromSmiles(smiles) if smiles else None
        if mol is None:
            return None, None, None, None
        try:
            frags = Chem.GetMolFrags(mol, asMols=True, sanitizeFrags=True)
        except Exception:                                        # noqa: BLE001
            frags = ()
        best = max(frags, key=lambda f: f.GetNumHeavyAtoms()) if frags else None
        return (canon(mol), canon(mol, stereo=False),
                canon(best) if best is not None else None,
                canon(best, stereo=False) if best is not None else None)

    out = []
    for smi in json.load(sys.stdin):
        rec = {"canonical": None, "flat": None, "valid": False,
               "largest": None, "largest_flat": None, "fragments": 0, "phantom": {},
               "cxsmiles": None, "expanded": None, "abbreviations": [],
               "unexpanded": [], "markush": [], "missing": [], "failed": [],
               "exp_canonical": None, "exp_flat": None,
               "exp_largest": None, "exp_largest_flat": None, "expander": EXPANDER}
        if isinstance(smi, str) and smi.strip() and smi != "<invalid>":
            # The labels are read from the STRING, before and independently of
            # parsing. A prediction RDKit cannot parse can still visibly carry
            # `OMe`, and reading the labels only on the parseable branch under-
            # reported this corpus by 7 of 148 -- an undercount that looks exactly
            # like a corpus with fewer abbreviations in it.
            rec["abbreviations"] = _labels(smi)
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
                except Exception:                                # noqa: BLE001
                    rec["cxsmiles"] = None
                rec["valid"] = True
                try:
                    frags = Chem.GetMolFrags(mol, asMols=True, sanitizeFrags=True)
                except Exception:                                # noqa: BLE001 - a weird fragment must not lose the whole record
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
                labels = rec["abbreviations"]
                if labels and _expand_cx is not None:
                    expanded, note = _expand_cx(smi)
                    rec["expanded"] = expanded
                    rec["markush"], rec["missing"], rec["failed"] = _split_unexpanded(note)
                    rec["unexpanded"] = rec["markush"] + rec["missing"]
                    if expanded:
                        (rec["exp_canonical"], rec["exp_flat"],
                         rec["exp_largest"], rec["exp_largest_flat"]) = forms(expanded)
                elif labels:
                    rec["missing"] = ["expander unavailable"]
                    rec["unexpanded"] = list(rec["missing"])
                # Nothing to expand, or expansion failed: the expanded comparison
                # is the plain one. Set here rather than in the consumer so the
                # fallback exists once.
                for exp_key, plain in (("exp_canonical", "canonical"), ("exp_flat", "flat"),
                                       ("exp_largest", "largest"), ("exp_largest_flat", "largest_flat")):
                    if rec[exp_key] is None:
                        rec[exp_key] = rec[plain]
        out.append(rec)
    json.dump(out, sys.stdout)
    return 0


def selftest():
    """Print the expander's stereo gate as JSON. Consumed by chem.expander_status()."""
    try:
        import cxsmiles_selftest
    except ImportError as exc:
        json.dump({"ok": False, "cases": [], "failures": [], "reason":
                   f"the expander's stereo gate could not be imported ({exc}), so nothing "
                   f"vouches for the expansion; expanded figures must be withheld"},
                  sys.stdout)
        return 1
    res = cxsmiles_selftest.run()
    res["expander"] = EXPANDER
    json.dump(res, sys.stdout)
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(selftest() if "--selftest" in sys.argv[1:] else main())
