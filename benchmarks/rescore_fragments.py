#!/usr/bin/env python3
"""Re-score a scored run counting only the LARGEST fragment of each prediction.

WHY THIS EXISTS
---------------
`score_run.py` compares whole predicted SMILES against ground truth, which is
the correct strict metric. But on a real corpus that metric turned out to be
dominated by ONE artifact rather than by recognition quality, and reporting it
alone was actively misleading.

Measured on 97 PubChem-verified depictions (300x300 PNG), stage 3 only:

    whole-SMILES     14.4% exact   -- and "high confidence" looked 58% wrong
    largest fragment 66.0% exact   -- and "high confidence" is 96.2% correct

The gap is not a scoring trick. Hand-checking the individual predictions shows
the model recovered the molecule and then appended phantom DISCONNECTED atoms:

    oxalic acid   I.I.I.O=C(O)C(=O)O.[HH].[HH]                  core exact
    proline       I.I.I.O=C(O)[C@@H]1CCCN1                      core exact
    melatonin     COc1ccc2[nH]cc(CCNC(C)=O)c2c1.[HH].[HH]       core exact
    epinephrine   CNC[C@H](O)c1ccc(O)c(O)c1 + 105 x I           core exact

63 of 97 predictions carried at least one phantom fragment; almost every one is
`I` or `[HH]`. That is the same signature as the well-known "OH read as iodine"
failure, i.e. a tiny heteroatom LABEL being read as an unbonded atom.

USE BOTH NUMBERS. Neither replaces the other:
  * the strict number is what a caller gets if it pastes the SMILES straight out
  * the fragment number is what the recogniser actually achieved, and therefore
    what a one-line post-process could deliver

USAGE
    rescore_fragments.py --scored DIR [--manifest FILE] [--json OUT]

    --scored    a score_run.py output directory (must contain structures.csv)
"""
import argparse
import collections
import csv
import json
import os
import sys

try:
    from rdkit import Chem, RDLogger
except ImportError:                                              # pragma: no cover
    sys.exit("rescore_fragments.py needs RDKit -- run it with the stage-3 interpreter")
RDLogger.DisableLog("rdApp.*")

DEFAULT_MANIFEST = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "ground_truth", "images_realworld_every7.json")


def canon(smiles, stereo=True):
    """Canonical SMILES, or None if RDKit will not parse it."""
    if not smiles:
        return None
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None
    if not stereo:
        Chem.RemoveStereochemistry(mol)
    return Chem.MolToSmiles(mol)


def expand_cx(smiles):
    """Expand CXSMILES abbreviation labels, or return the string unchanged.

    The second representation axis, and the one that cost the most to find.
    CXMolScribe deliberately preserves `OMe` as a labelled dummy atom rather than
    guessing an expansion, so a raw prediction can never equal a fully-expanded
    reference. Expanding here — never at prediction time — is what makes the
    comparison meaningful. See benchmarks/cxsmiles.py for the detail.
    """
    try:
        from cxsmiles import expand
    except ImportError:
        import os, sys as _s
        _s.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from cxsmiles import expand
    out, _note = expand(smiles)
    return out or smiles


def largest_fragment(smiles):
    """The fragment with the most heavy atoms. (mol, n_fragments) or (None, 0).

    Heavy atoms, not total atoms: `[HH]` has two atoms and zero heavy atoms, and
    it is exactly the phantom this function exists to discard.
    """
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None, 0
    frags = Chem.GetMolFrags(mol, asMols=True, sanitizeFrags=True)
    if not frags:
        return None, 0
    return max(frags, key=lambda f: f.GetNumHeavyAtoms()), len(frags)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scored", required=True, help="a score_run.py output directory")
    ap.add_argument("--manifest", default=DEFAULT_MANIFEST)
    ap.add_argument("--json", help="also write the summary here")
    ap.add_argument("--no-expand-cxsmiles", action="store_true",
                    help="do NOT expand CXSMILES abbreviations first (shows what the "
                         "unexpanded comparison scores, which is misleadingly low)")
    args = ap.parse_args()

    structures = os.path.join(args.scored, "structures.csv")
    if not os.path.exists(structures):
        sys.exit(f"no structures.csv in {args.scored} -- run score_run.py first")

    truth = {k: [m["smiles"] for m in g["molecules"]]
             for k, g in json.load(open(args.manifest))["groups"].items()}

    rows = list(csv.DictReader(open(structures)))
    if not rows:
        sys.exit(f"{structures} has no rows -- nothing to score")

    # --manifest DEFAULTS to the images corpus, so pointing --scored at a PDF run
    # and forgetting it compares 242 predictions against 97 unrelated molecules
    # and prints a calm "0 exact, 0.0%" -- a wrong answer that looks exactly like
    # a real one. Refuse instead: if not one scored group is in this manifest, the
    # manifest is the wrong one.
    scored_groups = {r["group"] for r in rows}
    if not (scored_groups & set(truth)):
        sys.exit(f"none of the {len(scored_groups)} groups in {structures} appear in "
                 f"{os.path.basename(args.manifest)} -- wrong manifest for this run.\n"
                 f"  scored:   {', '.join(sorted(scored_groups)[:3])} ...\n"
                 f"  manifest: {', '.join(sorted(truth)[:3])} ...\n"
                 f"  pass --manifest for the corpus this run was scored against.")

    verdicts = collections.Counter()
    by_tier = collections.Counter()
    frag_hist = collections.Counter()
    changed = []

    for row in rows:
        group, smiles, tier = row["group"], row["smiles"], row["tier"]
        expected = truth.get(group, [])
        exact_set = {canon(e) for e in expected} - {None}
        flat_set = {canon(e, stereo=False) for e in expected} - {None}

        if not args.no_expand_cxsmiles:
            smiles = expand_cx(smiles)
        mol, nfrag = largest_fragment(smiles)
        frag_hist[nfrag] += 1
        if mol is None:
            verdict = "invalid"
        else:
            got = Chem.MolToSmiles(mol)
            flat = Chem.Mol(mol)
            Chem.RemoveStereochemistry(flat)
            if got in exact_set:
                verdict = "exact"
            elif Chem.MolToSmiles(flat) in flat_set:
                verdict = "stereo"
            else:
                verdict = "wrong"
        verdicts[verdict] += 1
        by_tier[(tier, verdict)] += 1
        # A row the fragment strip RESCUED: strict scoring called it wrong or
        # invalid, the core structure was right all along.
        if verdict in ("exact", "stereo") and row["verdict"] not in ("exact", "stereo"):
            changed.append({"group": group, "strict": row["verdict"], "fragment": verdict,
                            "n_fragments": nfrag, "confidence": float(row["confidence"]),
                            "smiles": smiles})

    n = len(rows)
    right = verdicts["exact"]
    right_flat = verdicts["exact"] + verdicts["stereo"]
    multi = sum(c for k, c in frag_hist.items() if k > 1)

    out = {
        "scored_dir": os.path.abspath(args.scored),
        "denominator_emitted_structures": n,
        "verdicts": dict(verdicts),
        "accuracy_stereo_required": round(right / n, 4),
        "accuracy_stereo_relaxed": round(right_flat / n, 4),
        "predictions_with_phantom_fragments": multi,
        "fragment_count_histogram": dict(sorted(frag_hist.items())),
        "rescued_by_fragment_strip": len(changed),
        "rescued": sorted(changed, key=lambda r: -r["n_fragments"]),
        "confidence_crosstab": {},
    }
    print(f"LARGEST-FRAGMENT SCORING   denominator = {n} emitted structures")
    for v in ("exact", "stereo", "wrong", "invalid"):
        print(f"  {v:8s} {verdicts[v]:4d}   {verdicts[v] / n:6.1%}")
    print(f"  accuracy, stereo required : {right}/{n} = {right / n:.1%}")
    print(f"  accuracy, stereo relaxed  : {right_flat}/{n} = {right_flat / n:.1%}")
    print(f"\nphantom fragments: {multi}/{n} predictions ({multi / n:.1%}) "
          f"had more than one fragment")
    print(f"histogram (n_fragments: count): {out['fragment_count_histogram']}")
    print(f"rescued by stripping them: {len(changed)} predictions the strict "
          f"metric scored wrong/invalid but whose core structure was right")

    print("\nCONFIDENCE CROSSTAB (largest fragment)")
    for tier in ("high", "low"):
        total = sum(c for (t, _), c in by_tier.items() if t == tier)
        if not total:
            continue
        e, s = by_tier[(tier, "exact")], by_tier[(tier, "stereo")]
        w, i = by_tier[(tier, "wrong")], by_tier[(tier, "invalid")]
        out["confidence_crosstab"][tier] = {
            "n": total, "exact": e, "stereo": s, "wrong": w, "invalid": i,
            "fraction_correct": round((e + s) / total, 4),
        }
        print(f"  {tier:5s} n={total:4d}  exact={e:4d} stereo={s:3d} wrong={w:4d} "
              f"invalid={i:3d}   correct={(e + s) / total:6.1%}")

    if args.json:
        with open(args.json, "w") as fh:
            json.dump(out, fh, indent=2)
        print(f"\nwrote {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
