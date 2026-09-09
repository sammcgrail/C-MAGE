#!/usr/bin/env python3
"""Compact, chart-ready summaries of scored runs that are too big to publish whole.

WHY THIS EXISTS
---------------
`published_runs/` holds complete pipeline runs -- spreadsheets, crops, rendered
images -- so any number the site shows can be re-examined structure by structure.
That is the right default and it does not scale: the full 743-image depiction
corpus is thousands of PNGs, and the web app's `/api/benchmark` already ships
half a megabyte of JSON before adding it.

So for the arms that exist only to put ONE bar on ONE chart, this script commits
the scoring input instead of the run: `scored/<arm>/structures.csv`, written by
`score_run.py`, one row per emitted structure. Everything the charts show is
recomputed from those rows here -- verdicts, tier crosstab, fragment histogram --
using the same RDKit comparison and the same CXSMILES expansion as
`rescore_fragments.py`. Nothing is transcribed from a report.

Because it re-derives rather than transcribes, its verdict can be printed BESIDE
score_run.py's -- which is what `cross_check` in each arm does. That is not
ceremony: on its first run the comparison found a real bug here. This file took
the largest fragment unconditionally, so for every SALT it dropped the counter-ion
from the prediction and compared it against a reference that still had one,
guaranteeing a mismatch. 50 rows of the 1031-cell synthetic arm, 46 of them the
`salt` stratum and 49 of the 50 already strict-exact by score_run. Whole molecule
is now tried first and the largest-fragment hammer only fires as a fallback, which
is what it was always for -- stripping fragments the MODEL hallucinated.

    .venv-ms/bin/python benchmarks/build_headline.py            # writes headline.json

TWO DENOMINATORS, ALWAYS BOTH
-----------------------------
An emitted structure whose image has no reference SMILES cannot be right and
cannot be wrong. `rescore_fragments.py` charges those to the pipeline, which is
the conservative reading; dividing by the images that HAVE an answer is the
optimistic one. On the 743-image corpus the two differ by six points (62.2% vs
68.4%) and the gap is entirely the 68 images with no reference. Both are emitted
here (`emitted` / `scorable`) so a caption can never pair one denominator's
number with the other denominator's name -- which is exactly how "62.2% of the
675 images with an answer" got written down, when 62.2% is 462/743.
"""
from __future__ import annotations

import collections
import csv
import json
import os
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

try:
    from rdkit import Chem, RDLogger
except ImportError:                                              # pragma: no cover
    sys.exit("build_headline.py needs RDKit -- run it with the stage-3 interpreter "
             "(.venv-ms/bin/python), not whatever python3 is on PATH")
RDLogger.DisableLog("rdApp.*")

from cxsmiles import expand                                      # noqa: E402


# Each arm: where its rows are, which manifest holds the answers, and the prose a
# chart axis cannot carry. `note` is the caveat; `tweak` marks an arm that is NOT
# stock C-MAGE, so the UI can never plot it as if it were.
ARMS = [
    {
        "key": "images_all675",
        "lead": True,          # the headline stat: real depictions, not line art
        "title": "743 PubChem depictions",
        "short": "743 depictions",
        "scored": "scored/images_all675",
        "manifest": "ground_truth/images_realworld_all.json",
        "stages": "stage 3 only — no figure extraction, no segmentation",
        "settings": "stock C-MAGE, pipeline defaults, DECIMER_BBOX_PAD unset",
        "tweak": None,
        "note": "The whole molecules_realworld corpus, not a stride sample. 675 of the "
                "743 images carry a reference SMILES; the other 68 are emitted and "
                "unscorable.",
    },
    {
        "key": "images97_stock",
        "title": "97-image stride sample",
        "short": "97 sample",
        "scored": "scored/images97_stock",
        "manifest": "ground_truth/images_realworld_every7.json",
        "stages": "stage 3 only — no figure extraction, no segmentation",
        "settings": "stock C-MAGE, pipeline defaults, DECIMER_BBOX_PAD unset",
        "tweak": None,
        "note": "Every 7th image of the 675 that carry an answer. Reproduces the "
                "published 97-image run exactly.",
    },
    {
        "key": "images97_remap245",
        "title": "The same 97, background remapped 245 → 255",
        "short": "97 sample, input normalised",
        "scored": "scored/images97_remap245",
        "manifest": "ground_truth/images_realworld_every7.json",
        "stages": "stage 3 only — no figure extraction, no segmentation",
        "settings": "stock C-MAGE, unchanged. The INPUT was changed, not the pipeline.",
        "baseline": "images97_stock",
        "tweak": "Pixels at 245,245,245 — the near-white page background these PNGs "
                 "ship with — were set to pure white before upload. Nothing in C-MAGE "
                 "was modified, and the same normalisation is one line of PIL in any "
                 "caller's own code.",
        "note": "A paired A/B against the row above: same 97 images, same weights, "
                "same settings, same scoring.",
    },
    {
        "key": "images97_cropwhite_tol15",
        "title": "The same 97, CropWhite tolerance loosened to 15",
        "short": "97 sample, segmenter loosened",
        "scored": "scored/images97_cropwhite_tol15",
        "manifest": "ground_truth/images_realworld_every7.json",
        "stages": "stage 3 only — no figure extraction, no segmentation",
        "settings": "C-MAGE MODIFIED: CropWhite's exact-white test relaxed to a "
                    "tolerance of 15.",
        "baseline": "images97_stock",
        "tweak": "The same near-white background, attacked inside the pipeline "
                 "instead of in the input.",
        "rejected": "Measured worse than stock and reverted. It is recorded here so "
                    "the claim 'we tried the other fix' is checkable, and it is not "
                    "offered as an option.",
        "note": "Third arm of the same A/B. Same 97 images, same weights, same "
                "scoring as the two rows above.",
    },
    {
        "key": "synth_stage3_1031",
        "upper_bound": True,   # RDKit line art on pure white -- a ceiling, not a result
        "title": "1031 synthetic cells",
        "short": "synthetic, stage 3 only",
        "scored": "scored/synth_stage3_1031",
        "manifest": "ground_truth/synthetic_manifest_v2.json",
        "stages": "stage 3 only \u2014 one already-cropped structure per image",
        "settings": "stock C-MAGE, pipeline defaults, DECIMER_BBOX_PAD unset",
        "tweak": None,
        "note": "Every cell of the synthetic v2 corpus, one structure per image, so "
                "recall and precision are the same number. RDKit line art on pure "
                "white: an upper bound, not a result. Sharded 4 ways round-robin "
                "over crop_order.txt, so every shard is an interleaved sample.",
    },
    {
        "key": "synth_full_matched",
        "upper_bound": True,
        "title": "The same corpus through the full pipeline",
        "short": "synthetic, full pipeline",
        "scored": "scored/synth_full_matched",
        "manifest": "ground_truth/synthetic_manifest_v2.json",
        "stages": "stages 1+2+3 \u2014 figure extraction, segmentation, then recognition",
        "settings": "stock C-MAGE, pipeline defaults, DECIMER_BBOX_PAD unset",
        "baseline": "synth_stage3_1031",
        "tweak": None,
        "note": "The segmentation A/B. Compare it to the row above ONLY over the 38 "
                "documents both arms cover (451 molecules): full 46.3% strict exact "
                "against 54.3%, 60.9% graded against 79.2%. Segmentation costs 8.6 "
                "points strict and 19.9 graded. Do not compare the raw totals \u2014 "
                "this arm covers 38 of the 87 documents and the gap between two arms "
                "over different corpora is not a finding about either.",
    },
    {
        "key": "docs_round34",
        "title": "Six real documents, patents and papers",
        "short": "6 real documents",
        "scored": "scored/docs_round34",
        "manifest": "ground_truth/pdf_manifest_round34.json",
        "stages": "stages 1+2+3 \u2014 the whole pipeline on real PDFs",
        "settings": "stock C-MAGE, pipeline defaults, DECIMER_BBOX_PAD unset",
        "tweak": None,
        "note": "Ground truth built from the documents themselves: 75 compounds, each "
                "needing a PubChem name match and a reading of the drawing to agree. "
                "43 further drawn compounds are recorded unresolved rather than "
                "guessed. PMC10180415 draws 84 and the manifest resolves 41, so its "
                "precision is a LOWER BOUND; over the other five, precision is 39.3% "
                "strict and 69.6% graded.",
    },
]


def canon(smiles, stereo=True):
    if not smiles:
        return None
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None
    if not stereo:
        Chem.RemoveStereochemistry(mol)
    return Chem.MolToSmiles(mol)


def largest_fragment(smiles):
    """(mol, n_fragments) for the fragment with the most HEAVY atoms.

    Heavy atoms, not atoms: `[HH]` has two atoms and no heavy ones, and it is the
    phantom this exists to discard.
    """
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None, 0
    frags = Chem.GetMolFrags(mol, asMols=True, sanitizeFrags=True)
    if not frags:
        return None, 0
    return max(frags, key=lambda f: f.GetNumHeavyAtoms()), len(frags)


def score(arm):
    path = os.path.join(HERE, arm["scored"], "structures.csv")
    manifest = os.path.join(HERE, arm["manifest"])
    rows = list(csv.DictReader(open(path)))
    if not rows:
        sys.exit(f"{path} has no rows")
    truth = {k: [m["smiles"] for m in g["molecules"]]
             for k, g in json.load(open(manifest))["groups"].items()}
    # The wrong-manifest trap: comparing against a corpus these rows never came
    # from prints a calm 0.0% that looks exactly like a real result.
    if not ({r["group"] for r in rows} & set(truth)):
        sys.exit(f"none of the groups in {path} appear in {arm['manifest']}")

    emitted = collections.Counter()      # over every emitted row
    scorable = collections.Counter()     # over rows whose image has a reference
    tiers = collections.defaultdict(collections.Counter)
    tiers_scorable = collections.defaultdict(collections.Counter)
    hist = collections.Counter()
    phantom_rows = 0
    # Seeded, not left to the Counter: an absent key renders as "None", which
    # reads as "not measured" when it means "zero disagreements".
    cross = collections.Counter({"n": 0, "disagree_on_exact": 0, "graded_available": 0})

    for row in rows:
        group = row["group"]
        expanded, _note = expand(row["smiles"])
        smiles = expanded or row["smiles"]
        mol, nfrag = largest_fragment(smiles)
        hist[nfrag] += 1
        if nfrag > 1:
            phantom_rows += 1
        expect = truth.get(group, [])
        exact_set = {canon(e) for e in expect} - {None}
        flat_set = {canon(e, stereo=False) for e in expect} - {None}
        # WHOLE FIRST, largest fragment only as a fallback.
        # Taking the largest fragment unconditionally is wrong for a SALT: the
        # reference is the whole salt, the prediction is the whole salt, and
        # dropping the counter-ion from one side only guarantees a mismatch. That
        # is not hypothetical -- it silently cost 50 rows on the 1031-cell
        # synthetic arm (46 of them the `salt` stratum, 49 of the 50 already
        # strict-exact by score_run.py), and it was invisible until this file's
        # verdict was printed next to score_run.py's. The largest-fragment hammer
        # exists to strip fragments the MODEL hallucinated, so it must only fire
        # when the whole molecule did not already match.
        whole = Chem.MolFromSmiles(smiles)
        if whole is None and mol is None:
            verdict = "invalid"
        else:
            verdict = "wrong"
            for cand in (whole, mol):
                if cand is None:
                    continue
                flat = Chem.Mol(cand)
                Chem.RemoveStereochemistry(flat)
                if Chem.MolToSmiles(cand) in exact_set:
                    verdict = "exact"
                    break
                if Chem.MolToSmiles(flat) in flat_set and verdict != "exact":
                    verdict = "stereo"
        emitted[verdict] += 1
        tiers[row["tier"]][verdict] += 1
        tiers[row["tier"]]["n"] += 1
        # R1 cross-check. score_run.py already graded this row and its verdict is
        # carried in the CSV. This function deliberately RE-DERIVES the comparison
        # rather than transcribing it, so the two are independent -- which only
        # buys anything if the disagreement is reported instead of hidden. On the
        # 1031-cell synthetic arm they differ on 50 rows (4.8%), all of them rows
        # this function calls `wrong` and score_run grades `exact`: score_run
        # applies prediction-side normalisations (`decoded`, `dephantom`) that this
        # one does not. Neither is the "right" number; they answer slightly
        # different questions, and a caption must never pair one with the other's
        # name.
        sr = row.get("verdict") or ""
        srg = row.get("grade") or ""
        cross["n"] += 1
        cross[f"headline_{verdict}"] += 1
        if sr:
            cross[f"score_run_strict_{sr}"] += 1
        if srg:
            cross[f"score_run_graded_{srg}"] += 1
            cross["graded_available"] += 1
        if srg and (srg == "exact") != (verdict == "exact"):
            cross["disagree_on_exact"] += 1

        if group in truth:
            scorable[verdict] += 1
            scorable["n"] += 1
            tiers_scorable[row["tier"]][verdict] += 1
            tiers_scorable[row["tier"]]["n"] += 1

    n_emitted = len(rows)
    out = dict(arm)
    out.pop("scored", None)
    out.pop("manifest", None)
    out.update({
        "source": arm["scored"] + "/structures.csv",
        "manifest_file": os.path.basename(arm["manifest"]),
        "emitted": {"n": n_emitted, **{v: emitted[v] for v in
                                       ("exact", "stereo", "wrong", "invalid")}},
        "scorable": {"n": scorable["n"], **{v: scorable[v] for v in
                                            ("exact", "stereo", "wrong", "invalid")}},
        # Over every emitted row. `tiers_scorable` drops the rows whose image has
        # no reference: they cannot be right and cannot be wrong, and charging them
        # to the tier is the conservative reading, not the only one.
        "tiers": {t: {k: c[k] for k in ("n", "exact", "stereo", "wrong", "invalid")}
                  for t, c in sorted(tiers.items())},
        "tiers_scorable": {t: {k: c[k] for k in ("n", "exact", "stereo", "wrong", "invalid")}
                           for t, c in sorted(tiers_scorable.items())},
        "phantom_rows": phantom_rows,
        "fragment_histogram": dict(sorted(hist.items())),
        # R1: this file's verdict beside score_run.py's, from the same rows. They
        # answer slightly different questions (score_run applies prediction-side
        # normalisations this does not), so they will not agree exactly -- and a
        # caption must never pair one number with the other's name. Reported, not
        # reconciled: a disagreement that is printed is information, one that is
        # averaged away is a bug waiting to be shipped.
        "cross_check": dict(cross),
    })
    return out


def main():
    arms = [score(a) for a in ARMS]
    doc = {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "scoring": "whole molecule first, then largest fragment by heavy-atom count "
                   "as a fallback, after CXSMILES abbreviation expansion; RDKit "
                   "canonical SMILES on both sides, never string equality. Largest-"
                   "fragment-only is wrong for salts: it drops a counter-ion the "
                   "reference has.",
        "built_by": "benchmarks/build_headline.py",
        "arms": arms,
    }
    dest = os.path.join(HERE, "headline.json")
    with open(dest, "w") as fh:
        json.dump(doc, fh, indent=1)
        fh.write("\n")
    for a in arms:
        e, s = a["emitted"], a["scorable"]
        print(f"{a['key']:20s} emitted {e['exact']}/{e['n']} = {e['exact']/e['n']:.1%}"
              f"   scorable {s['exact']}/{s['n']} = {s['exact']/s['n']:.1%}"
              f"   phantom {a['phantom_rows']}/{e['n']}")
        for t, c in a["tiers"].items():
            print(f"    tier {t:5s} n={c['n']:4d} exact {c['exact']:4d} "
                  f"= {c['exact']/c['n']:.1%}  (+stereo {(c['exact']+c['stereo'])/c['n']:.1%})")
    print(f"\nwrote {dest}")


if __name__ == "__main__":
    main()
