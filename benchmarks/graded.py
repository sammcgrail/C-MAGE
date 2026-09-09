#!/usr/bin/env python3
"""Graded verdicts: how close is a "wrong" prediction, really?

WHY THIS EXISTS
---------------
`score_run.py` grades every prediction exact / stereo / wrong / invalid by RDKit
canonical SMILES. That is the correct strict metric and this module does not
change it. But on both committed corpora most of the `wrong` pile is not a
different molecule -- it is the same molecule written differently, and the strict
metric cannot tell those apart:

    675 PubChem depictions   504 strict-wrong -> 426 (84.5%) are the same molecule
    11 published documents   212 strict-wrong ->  20 ( 9.4%) are the same molecule

Report the strict number AND the graded breakdown. Never merge them, and never
quote the graded number alone: a caller that pastes the SMILES straight out gets
the strict one.

THE LADDER, tightest first. Each rung permits everything above it plus one more
relaxation, so the grade names the LOOSEST relaxation that was needed:

  exact     canonical isomeric SMILES equal            (identical to score_run.py)
  stereo    equal after dropping stereochemistry       (identical to score_run.py)
  tautomer  equal after rdMolStandardize's canonical tautomer, both sides
  charge    equal after Uncharger, both sides. Protonation only -- NOT ONE FRAGMENT
            is removed from either side at this rung.
  salt      equal after SaltRemover's curated counter-ion/solvate list + Uncharger
  skeleton  InChIKey first block equal: same connectivity, differing in some mix of
            stereochemistry, protonation and isotope that no rung above caught
  near      Morgan-r2 Tanimoto >= NEAR_TANIMOTO. A DIAGNOSTIC, NEVER A PASS.
  wrong     none of the above
  invalid   RDKit will not parse it

WHERE THE LINES ARE DRAWN, AND WHY
----------------------------------
`near` is not a correctness bucket and must never be counted as one. Measured on
the 675-molecule manifest, Morgan-r2 puts 18 of 197,506 distinct pairs at >= 0.85
-- but SEVEN of those 18 sit at exactly 1.000 and are enantiomer pairs
(levomilnacipran/milnacipran, esketamine/ketamine, citalopram/escitalopram,
cetirizine/levocetirizine, bupivacaine/levobupivacaine, esomeprazole/omeprazole,
galactose/glucose). Morgan fingerprints are stereo-blind, so a Tanimoto of 1.000
is not evidence of identity. And the random-pair rate understates the real false
positive rate anyway, because a misread is the reference minus an atom, not a
random molecule: carboplatin-without-its-platinum scores 0.889 against
carboplatin. It is graded `near`, and `near` means "look at this", not "count it".

The threshold is 0.85 because that is where the two corpora separate cleanly:
nothing graded `wrong` on either corpus exceeds 0.845 (images) or 0.657 (PDFs),
so no genuine miss is being dressed up, while the near bucket stays small enough
(16 and 0) to read end to end -- which is the only way to know a bucket.

TWO PREDICTION-SIDE CONTENT NORMALISATIONS, reported as flags, never folded in:

  decoded    CXSMILES abbreviation labels expanded via cxsmiles.py. Lossless
             decoding of what the model actually emitted -- `*C |$CO2H;;;;$|` IS
             the carboxylic acid. Worth 19 of 212 on the document corpus.
  dephantom  neutral fragments made only of H and/or I removed, and identical
             duplicate fragments collapsed. Narrow on purpose, and evidence-based:
             FINDINGS.md 2 characterises this exact artifact. `[I-]` is a genuine
             counter-ion and survives; `CC`, `CCl`, `C` and every real substructure
             survive. Verified against both manifests: not one of the 709 reference
             molecules carries a neutral H/I-only fragment, so this step cannot
             fabricate a match against a reference that legitimately had one.

AND ONE MORE, WHICH GETS ITS OWN COLUMN BECAUSE IT DESTROYS CONTENT:

  grade_largest   the same ladder, but the prediction may also be reduced to its
                  largest fragment by heavy-atom count. This is what
                  rescore_fragments.py measures. It is reported beside `grade`,
                  exactly like whole-SMILES beside largest-fragment, because the
                  two answer different questions and neither replaces the other.

TRAPS THAT WERE LIVE IN THE FIRST DRAFT OF THIS FILE
----------------------------------------------------
Every one of these produced a WRONG ANSWER THAT LOOKED LIKE A BETTER SCORE.

* Comparing the prediction's largest fragment against the REFERENCE'S largest
  fragment graded carboplatin `exact` while the prediction had dropped the
  platinum. Reference-side fragment selection is gone; the reference is only ever
  normalised by rules that name what they remove.
* `rdMolStandardize.FragmentParent` is `LargestFragmentChooser` wearing a
  chemistry name. Using it for the `salt` rung silently reintroduced the hammer:
  33 image predictions reached `salt` only because it binned their phantom
  `I`/`[HH]`, and it strips `[Pt+2]` clean off carboplatin's reference.
  `SaltRemover`'s 15 curated patterns take a mesylate and an iodide and leave
  `[Pt+2]`, propylene glycol and succinic acid where they are.
* Even with SaltRemover, `salt` on a metal complex is a trap, so `metal_guard`
  refuses it two ways -- see that function.
* Ranking the grade above the normalisation cost let the largest-fragment hammer
  manufacture a TIGHTER-looking grade than an untouched comparison: clozapine
  scored "tautomer (after binning an iodide)" when plain "salt" was available with
  nothing removed. Hence two grades rather than one.

CONTROL, and it is not optional: every prediction score_run.py already grades
`exact` must come back `exact` here with no normalisation at all. If a
normalisation is improving a prediction that was already right, it is not
normalising, it is guessing. `graded_selftest.py` asserts this and the traps above.

    graded.py --scored SCORED_DIR --manifest MANIFEST [--json OUT]
"""
import argparse
import collections
import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from rdkit import Chem, DataStructs, RDLogger
    from rdkit.Chem import AllChem, rdMolDescriptors
    from rdkit.Chem.MolStandardize import rdMolStandardize
    from rdkit.Chem.SaltRemover import SaltRemover
except ImportError:                                              # pragma: no cover
    sys.exit("graded.py needs RDKit -- run it with the stage-3 interpreter "
             "(.venv-ms/bin/python)")
RDLogger.DisableLog("rdApp.*")

NEAR_TANIMOTO = 0.85
GRADES = ["exact", "stereo", "tautomer", "charge", "salt", "skeleton", "near", "wrong"]
RANK = {g: i for i, g in enumerate(GRADES)}
#     grades that mean "this IS the manifest molecule, written differently"
MATCHED = ("exact", "stereo", "tautomer", "charge", "salt")
ALL_GRADES = GRADES + ["invalid"]

# Anything not here (and not H) is a metal for metal_guard. B/Si/Ge/As/Sb/Te stay
# on the non-metal side: they occur inside real drug molecules (boronic acids,
# silyl protecting groups) and are never spectator counter-ions.
NONMETALS = {"H", "He", "B", "C", "N", "O", "F", "Ne", "Si", "P", "S", "Cl", "Ar",
             "Ge", "As", "Se", "Br", "Kr", "Sb", "Te", "I", "Xe", "At", "Rn"}

_TAUT = rdMolStandardize.TautomerEnumerator()
_TAUT.SetMaxTautomers(500)
_TAUT.SetMaxTransforms(500)
_UNC = rdMolStandardize.Uncharger()
_SALT = SaltRemover()
_cache = {}


# ---------------------------------------------------------------- primitives
def parse_mol(smiles):
    """RDKit mol or None. Accepts CXSMILES; falls back to the plain SMILES part.

    Deliberately the same logic as score_run.py:parse_mol, so `exact` here and
    `exact` there are the same predicate on the same input.
    """
    if smiles is None:
        return None
    s = str(smiles).strip()
    if not s or s == "<invalid>":
        return None
    m = Chem.MolFromSmiles(s)
    if m is None and "|" in s:
        m = Chem.MolFromSmiles(s.split("|", 1)[0].strip())
    return m


def canon(mol, stereo=True):
    return Chem.MolToSmiles(mol, isomericSmiles=stereo) if mol is not None else None


def flat(mol):
    if mol is None:
        return None
    m = Chem.Mol(mol)
    Chem.RemoveStereochemistry(m)
    return Chem.MolToSmiles(m)


def _memo(key, fn):
    if key not in _cache:
        try:
            _cache[key] = fn()
        except Exception:                                        # noqa: BLE001
            _cache[key] = None
    return _cache[key]


def taut_canon(mol, key, stereo=True):
    def go():
        t = _TAUT.Canonicalize(mol)
        return None if t is None else (canon(t, True) if stereo else flat(t))
    return _memo(("taut", key, stereo), go)


def uncharged(mol, key, stereo=True):
    def go():
        m = _UNC.uncharge(Chem.Mol(mol))
        Chem.SanitizeMol(m)
        return canon(m, True) if stereo else flat(m)
    return _memo(("unc", key, stereo), go)


def salt_stripped(mol, key, stereo=True):
    """Curated counter-ions/solvates off, then uncharged. NOT FragmentParent."""
    def go():
        m = _UNC.uncharge(_SALT.StripMol(Chem.Mol(mol), dontRemoveEverything=True))
        Chem.SanitizeMol(m)
        return canon(m, True) if stereo else flat(m)
    return _memo(("salt", key, stereo), go)


def _taut_of_smiles(smiles, stereo=True):
    if not smiles:
        return None
    return _memo(("tsmi", smiles, stereo),
                 lambda: taut_canon(Chem.MolFromSmiles(smiles), smiles, stereo))


def skeleton(mol):
    """InChIKey first block: connectivity only, stereo/protonation/isotope stripped."""
    def go():
        k = Chem.MolToInchiKey(mol)
        return k[:14] if k else None
    return _memo(("skel", canon(mol)), go)


def morgan(mol):
    return AllChem.GetMorganFingerprintAsBitVect(mol, 2, 2048) if mol is not None else None


def elem_counts(mol):
    """Element -> count, implicit hydrogens included. Formal charge ignored."""
    d = {}
    for a in mol.GetAtoms():
        d[a.GetSymbol()] = d.get(a.GetSymbol(), 0) + 1
        h = a.GetTotalNumHs()
        if h:
            d["H"] = d.get("H", 0) + h
    return d


def elem_l1(a, b):
    """Atoms added plus atoms removed: 1 or 2 usually means one misread label."""
    return sum(abs(a.get(k, 0) - b.get(k, 0)) for k in set(a) | set(b))


def metals(mol):
    return {a.GetSymbol() for a in mol.GetAtoms()
            if a.GetSymbol() not in NONMETALS and a.GetAtomicNum() > 1}


def metal_guard(pmol, rmol):
    """True when the `salt` rung is safe to apply to this pair.

    R1  a metal on one side only. Carboplatin's reference carries `[Pt+2]` and the
        prediction lost it entirely; any rule that removes counter-ions makes the
        missing platinum disappear from the comparison instead of failing it.
    R2  a metal carrying any bond, on either side. Oxaliplatin's prediction draws
        the platinum covalently, and fragment-based normalisation then compares the
        diaminocyclohexane LIGAND on both sides -- a match on something that is not
        the compound.
    Both were live false passes before this guard existed.
    """
    if metals(pmol) != metals(rmol):
        return False
    for m in (pmol, rmol):
        if any(a.GetSymbol() not in NONMETALS and a.GetAtomicNum() > 1 and a.GetDegree() > 0
               for a in m.GetAtoms()):
            return False
    return True


def is_phantom_frag(frag):
    """A NEUTRAL fragment made only of H and/or I -- the artifact FINDINGS.md 2 names.

    `I` (hydrogen iodide), `II` (diiodine), `[HH]`, `[H]` qualify. `[I-]` does not:
    it carries a formal charge and is a genuine counter-ion, so it is left for the
    `salt` rung to deal with by name.
    """
    if any(a.GetFormalCharge() != 0 for a in frag.GetAtoms()):
        return False
    return all(a.GetSymbol() in ("H", "I") for a in frag.GetAtoms())


def dephantom(mol):
    """(mol, phantoms dropped, duplicates dropped) -- two lists, never one.

    Collapsing a duplicate is a different claim from discarding a phantom (one
    crop holding two copies of the same drawing, versus a misread label), so they
    are counted apart. Merging them once made `Cl` appear in a field labelled
    "phantoms dropped", which is exactly the kind of quiet mislabelling that turns
    into a wrong conclusion three steps later.
    """
    frags = list(Chem.GetMolFrags(mol, asMols=True, sanitizeFrags=True))
    if len(frags) <= 1:
        return mol, [], []
    keep, phantoms = [], []
    for f in frags:
        (phantoms if is_phantom_frag(f) else keep).append(f)
    phantoms = sorted(Chem.MolToSmiles(f) for f in phantoms)
    dupes = []
    if len(keep) > 1:
        seen, uniq = set(), []
        for f in keep:
            c = Chem.MolToSmiles(f)
            if c in seen:
                dupes.append(c)
                continue
            seen.add(c)
            uniq.append(f)
        keep = uniq
    if not keep:
        return mol, [], []
    out = keep[0]
    for f in keep[1:]:
        out = Chem.CombineMols(out, f)
    # CombineMols leaves RingInfo uninitialised; round-trip so fingerprints, InChI
    # and the tautomer enumerator all see a sanitised molecule.
    rt = Chem.MolFromSmiles(Chem.MolToSmiles(out))
    return (rt if rt is not None else out), phantoms, sorted(dupes)


def largest_fragment(mol):
    """(largest fragment by HEAVY atoms, n fragments). Heavy, because `[HH]` has
    two atoms and zero heavy atoms and is exactly what must lose."""
    frags = Chem.GetMolFrags(mol, asMols=True, sanitizeFrags=True)
    if not frags:
        return None, 0
    return max(frags, key=lambda f: f.GetNumHeavyAtoms()), len(frags)


def expand_cxsmiles(smiles):
    """(expanded SMILES or None, note) via cxsmiles.py. Never guesses a label."""
    try:
        from cxsmiles import expand
        return expand(str(smiles))
    except Exception as e:                                       # noqa: BLE001
        return None, f"{type(e).__name__}"


# ---------------------------------------------------------------- comparison
def forms(mol):
    """Every comparison form of one molecule, computed once."""
    key = canon(mol)
    unc_i, unc_f = uncharged(mol, key, True), uncharged(mol, key, False)
    salt_i, salt_f = salt_stripped(mol, key, True), salt_stripped(mol, key, False)
    return {
        "mol": mol, "iso": key, "flat": flat(mol),
        "taut_iso": taut_canon(mol, key, True), "taut_flat": taut_canon(mol, key, False),
        "unc_iso": unc_i, "unc_flat": unc_f,
        "salt_iso": salt_i, "salt_flat": salt_f,
        # The ladder is cumulative, so the charge and salt rungs must also permit
        # the tautomer relaxation above them. Without these a prediction that is
        # both a tautomer and a hydroiodide falls through every rung.
        "unc_taut": _taut_of_smiles(unc_i, True), "unc_taut_flat": _taut_of_smiles(unc_f, False),
        "salt_taut": _taut_of_smiles(salt_i, True), "salt_taut_flat": _taut_of_smiles(salt_f, False),
        "skel": skeleton(mol), "fp": morgan(mol),
        "elems": elem_counts(mol), "formula": rdMolDescriptors.CalcMolFormula(mol),
        "heavy": mol.GetNumHeavyAtoms(),
    }


def ref_forms(smiles_or_mol):
    """Manifest SMILES (or a mol) -> comparison forms; None if it will not parse."""
    m = parse_mol(smiles_or_mol) if isinstance(smiles_or_mol, str) else smiles_or_mol
    return forms(m) if m is not None else None


def _eq(a, b):
    return a is not None and b is not None and a == b


def compare(p, r):
    """(grade, Tanimoto) for one prediction form against one reference form."""
    t = None
    if p["fp"] is not None and r["fp"] is not None:
        t = DataStructs.TanimotoSimilarity(p["fp"], r["fp"])
    if _eq(p["iso"], r["iso"]):
        return "exact", t
    if _eq(p["flat"], r["flat"]):
        return "stereo", t
    if _eq(p["taut_iso"], r["taut_iso"]) or _eq(p["taut_flat"], r["taut_flat"]):
        return "tautomer", t
    if (_eq(p["unc_iso"], r["unc_iso"]) or _eq(p["unc_flat"], r["unc_flat"])
            or _eq(p["unc_taut"], r["unc_taut"]) or _eq(p["unc_taut_flat"], r["unc_taut_flat"])):
        return "charge", t
    if metal_guard(p["mol"], r["mol"]) and (
            _eq(p["salt_iso"], r["salt_iso"]) or _eq(p["salt_flat"], r["salt_flat"])
            or _eq(p["salt_taut"], r["salt_taut"]) or _eq(p["salt_taut_flat"], r["salt_taut_flat"])):
        return "salt", t
    if _eq(p["skel"], r["skel"]):
        return "skeleton", t
    if t is not None and t >= NEAR_TANIMOTO:
        return "near", t
    return "wrong", t


# Field names are prefixed `graded_` where score_run.py already owns the plain
# name. `matched_name` and `closest_name` are STRICT columns over there, and an
# earlier version of this dict quietly overwrote both for all 426 rows that reached
# a matched grade -- the strict recall survived only because it also gates on
# `verdict`, which is luck, not design. score_run.py now asserts the key sets are
# disjoint so the next collision fails loudly instead of silently rewriting a
# column somebody is reading as the strict answer.
BLANK = {"grade": "invalid", "grade_largest": "invalid", "graded_match": None,
         "graded_match_largest": None, "graded_closest": None, "decoded": False,
         "dephantom": False, "dedup": False, "largest": False, "best_tanimoto": None,
         # `phantom_frags` / `duplicate_frags` are what this prediction CARRIES, not
         # what the winning variant dropped -- they are populated whether or not the
         # dephantom variant is the one selected. `dropped_by_largest` is the other
         # kind and is only set when the hammer actually won. Naming these
         # "dropped_*" once produced a row flagged dedup=False with a non-empty
         # "dropped_duplicates", which is a field lying about its own meaning.
         "n_fragments": None, "phantom_frags": "", "duplicate_frags": "",
         "dropped_by_largest": "", "formula_pred": None, "formula_ref": None,
         "formula_match": None, "elem_delta": None, "heavy_delta": None,
         "skeleton_match": False, "expansion_note": ""}


def grade_prediction(raw_smiles, refs):
    """refs: [(name, ref_forms(...)), ...] for the group. -> a dict of graded fields."""
    out = dict(BLANK)
    mol0 = parse_mol(raw_smiles)
    s = str(raw_smiles or "")
    exp_smi, note = (expand_cxsmiles(s) if ("|" in s and "$" in s) else (None, ""))
    out["expansion_note"] = note

    bases = []
    if mol0 is not None:
        bases.append((False, mol0))
    mol_e = parse_mol(exp_smi) if exp_smi else None
    if mol_e is not None and (mol0 is None or canon(mol_e) != canon(mol0)):
        bases.append((True, mol_e))
    if not bases:
        return out

    # (cost, decoded, dephantom, dedup, largest, mol, dropped-by-largest)
    variants = []
    for dec, m in bases:
        c0 = 1 if dec else 0
        variants.append((c0, dec, False, False, False, m, []))
        dp, phantoms, dupes = dephantom(m)
        if phantoms or dupes:
            variants.append((c0 + 1, dec, bool(phantoms), bool(dupes), False, dp, []))
            out["phantom_frags"] = ".".join(phantoms)
            out["duplicate_frags"] = ".".join(dupes)
        src = dp if (phantoms or dupes) else m
        lf, nf = largest_fragment(src)
        if nf > 1 and lf is not None:
            kept = Chem.MolToSmiles(lf)
            gone = sorted(Chem.MolToSmiles(f) for f in Chem.GetMolFrags(src, asMols=True, sanitizeFrags=True)
                          if Chem.MolToSmiles(f) != kept)
            variants.append((c0 + 3, dec, bool(phantoms), bool(dupes), True, lf, gone))

    out["n_fragments"] = len(Chem.GetMolFrags(mol0)) if mol0 is not None else 0

    def pick(vs):
        best = None
        for cost, dec, dph, ddup, lg, m, gone in vs:
            pf = forms(m)
            for name, r in refs:
                g, t = compare(pf, r)
                cand = (RANK[g], cost, -(t or 0.0), g, name, dec, dph, ddup, lg, t, r, gone)
                if best is None or cand[:3] < best[:3]:
                    best = cand
        return best

    best = pick([v for v in variants if not v[4]])          # no largest-fragment hammer
    best_lg = pick(variants)                                # hammer allowed
    _, _, _, g, name, dec, dph, ddup, _lg, t, r, _gone = best
    out.update(grade=g, decoded=dec, dephantom=dph, dedup=ddup, graded_closest=name,
               best_tanimoto=None if t is None else round(t, 3),
               graded_match=name if g in MATCHED else None)
    out["grade_largest"] = best_lg[3]
    out["graded_match_largest"] = best_lg[4] if best_lg[3] in MATCHED else None
    out["largest"] = bool(best_lg[8])
    if best_lg[8]:
        out["dropped_by_largest"] = ".".join(best_lg[11])
    whole = forms(mol0) if mol0 is not None else forms(bases[0][1])
    out["formula_pred"], out["formula_ref"] = whole["formula"], r["formula"]
    out["formula_match"] = whole["formula"] == r["formula"]
    out["elem_delta"] = elem_l1(whole["elems"], r["elems"])
    out["heavy_delta"] = whole["heavy"] - r["heavy"]
    out["skeleton_match"] = bool(_eq(whole["skel"], r["skel"]))
    return out


def load_refs(manifest):
    """{group: [(name, forms), ...]} from a score_run.py-shaped manifest."""
    out = {}
    for g, entry in manifest["groups"].items():
        lst = []
        for m in entry["molecules"]:
            rf = ref_forms(m["smiles"])
            if rf is None:
                raise SystemExit(f"manifest SMILES for {g}/{m.get('name')} does not parse")
            lst.append((m.get("name") or m.get("label"), rf))
        out[g] = lst
    return out


def tally(records):
    """Grade counts, the normalisation cross-tab, and the strict-wrong breakdown.

    Everything is kept apart on purpose. There is no combined "accuracy" key here
    and there should not be one: the strict figure and the graded figures answer
    different questions and a single number would hide whichever is inconvenient.
    """
    n = len(records)
    by = collections.Counter(r["grade"] for r in records)
    by_lg = collections.Counter(r["grade_largest"] for r in records)
    strict_wrong = [r for r in records if r.get("verdict") == "wrong"]
    ww = collections.Counter(r["grade"] for r in strict_wrong)
    ww_lg = collections.Counter(r["grade_largest"] for r in strict_wrong)
    out = {
        "denominator": n,
        "near_tanimoto_threshold": NEAR_TANIMOTO,
        "grade": {g: by[g] for g in ALL_GRADES},
        "grade_with_largest_fragment": {g: by_lg[g] for g in ALL_GRADES},
        "normalisation_needed": {
            g: {"none": sum(1 for r in records if r["grade"] == g
                            and not (r["decoded"] or r["dephantom"] or r["dedup"])),
                "decoded": sum(1 for r in records if r["grade"] == g and r["decoded"]),
                "dephantom": sum(1 for r in records if r["grade"] == g and r["dephantom"]),
                "dedup": sum(1 for r in records if r["grade"] == g and r["dedup"])}
            for g in ALL_GRADES if by[g]},
        "strict_wrong": {
            "denominator": len(strict_wrong),
            "grade": {g: ww[g] for g in ALL_GRADES if ww[g]},
            "grade_with_largest_fragment": {g: ww_lg[g] for g in ALL_GRADES if ww_lg[g]},
            "same_molecule_different_representation": sum(ww[g] for g in MATCHED),
            "near_miss_skeleton_or_tanimoto": ww["skeleton"] + ww["near"],
            "genuinely_different_molecule": ww["wrong"],
            "unparseable": ww["invalid"],
        },
    }
    sw = out["strict_wrong"]
    if sw["denominator"]:
        sw["fraction_same_molecule"] = round(
            sw["same_molecule_different_representation"] / sw["denominator"], 4)
    return out


# ---------------------------------------------------------------- standalone
def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scored", required=True, help="a score_run.py output directory")
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--json", help="write the per-structure records here")
    args = ap.parse_args()

    path = os.path.join(args.scored, "structures.csv")
    if not os.path.exists(path):
        sys.exit(f"no structures.csv in {args.scored} -- run score_run.py first")
    rows = list(csv.DictReader(open(path)))
    if not rows:
        sys.exit(f"{path} has no rows")
    refs = load_refs(json.load(open(args.manifest)))
    unknown = sorted({r["group"] for r in rows} - set(refs))
    if len(unknown) == len({r["group"] for r in rows}):
        sys.exit(f"no group in {path} appears in {args.manifest} -- wrong manifest?\n"
                 f"  structures: {sorted({r['group'] for r in rows})[:4]}\n"
                 f"  manifest:   {sorted(refs)[:4]}")

    records = []
    for r in rows:
        rec = dict(r)
        if r["verdict"] == "no-truth" or r["group"] not in refs:
            rec.update(dict(BLANK, grade="no-truth", grade_largest="no-truth"))
        else:
            rec.update(grade_prediction(r["smiles"], refs[r["group"]]))
        records.append(rec)
    scored = [r for r in records if r["grade"] != "no-truth"]
    t = tally(scored)

    print(f"GRADED VERDICTS   denominator = {t['denominator']} structures with ground truth")
    print(f"  strict (score_run.py, unchanged): " +
          ", ".join(f"{k} {v}" for k, v in sorted(
              collections.Counter(r["verdict"] for r in scored).items())))
    print(f"  {'grade':10} {'n':>5} {'%':>7}   |  + largest fragment")
    for g in ALL_GRADES:
        if t["grade"][g] or t["grade_with_largest_fragment"][g]:
            print(f"  {g:10} {t['grade'][g]:5} {t['grade'][g]/t['denominator']*100:6.1f}%"
                  f"   |  {t['grade_with_largest_fragment'][g]:5}")
    sw = t["strict_wrong"]
    print(f"\n  of the {sw['denominator']} the strict metric calls WRONG:")
    print(f"    same molecule, different representation : {sw['same_molecule_different_representation']}"
          f" ({sw.get('fraction_same_molecule', 0)*100:.1f}%)")
    print(f"    near-miss (skeleton or Tanimoto >= {NEAR_TANIMOTO})  : {sw['near_miss_skeleton_or_tanimoto']}")
    print(f"    genuinely different molecule            : {sw['genuinely_different_molecule']}")
    if args.json:
        with open(args.json, "w") as f:
            json.dump({"tally": t, "structures": records}, f, indent=1)
        print(f"\nwrote {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
