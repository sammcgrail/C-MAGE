#!/usr/bin/env python3
"""Grade a run the way the C-MAGE paper does: SKELETON and APPENDIX, separately.

WHY A SECOND SCORER
-------------------
score_run.py compares whole molecules against a reference SMILES. That is the
right question for a caller who wants a structure out of a document, and it is
the WRONG question for CXMolScribe, which deliberately emits CXSMILES with the
drawn superatoms preserved as labelled dummy atoms. FINDINGS.md section 5 has
the detail: 148 of 242 predictions on the document corpus cannot be scored at
all against a PubChem SMILES, because the reference has no appendix to compare.

The paper (Table 3) grades each prediction against its own segment image in two
parts -- the skeleton (the CXSMILES minus the appendix) and the appendix (the
translation of the superatoms) -- against a hand-written reference CXSMILES.
This corpus is drawn by benchmarks/make_synthetic_corpus.py, so the reference
CXSMILES is not hand-written but generated from the same molecule object that
was drawn: the picture and the string cannot disagree.

THE FIVE LETTERS, AND WHICH PART IS INFERRED
--------------------------------------------
Given: `Y` = skeleton and appendix both correct; `YS` = skeleton correct with no
appendix present. The other three are the symmetric completion of that pair and
are OUR reading, not a quotation:

    Y   skeleton correct, appendix present and correct
    YS  skeleton correct, no appendix present (nothing to translate)
    A   skeleton correct, appendix present and WRONG
    N   skeleton wrong, appendix present
    NS  skeleton wrong, no appendix present

  skeletal accuracy = (Y + YS + A) / graded
  appendix accuracy =  Y / (Y + A)              -- only over structures that
                                                   HAVE an appendix to get right

"Appendix present" is decided by the REFERENCE, i.e. by what was drawn: a
drawing with no superatom cannot demand one. A prediction that invents an
appendix where none was drawn almost always fails the skeleton too (it has a
dummy where an atom belongs), and is graded N on that basis.

THREE COMPARISONS, REPORTED SIDE BY SIDE, NEVER MERGED
------------------------------------------------------
1. skeleton_strict    the dummy graphs must match. `Et` drawn and `CC` predicted
                      is a MISS here even though the molecule is right.
2. skeleton_expanded  both sides' appendices expanded through the same table,
                      then compared as molecules. This is the plain-SMILES
                      question, and the gap between 1 and 2 is the measurement
                      Sam asked for: how much of the difference between CXSMILES
                      scoring and SMILES scoring is representation.
3. appendix           labels compared by MEANING, not by string, through
                      CXMolScribe's OWN table: `MeO` and `OMe` both expand to
                      *OC and are one superatom drawn facing two ways, as are
                      `OHC`/`CHO` and `F3C`/`CF3`. Note that CXMolScribe reads
                      `NC` as a mirrored NITRILE where RDKit's table reads it as
                      an isocyanide -- the model's table is the right one to
                      grade the model's output with, and benchmarks/
                      synthetic_selftest.py refuses to let the corpus DRAW any
                      label the two tables disagree about.

ASSIGNMENT
----------
The paper's grader looks at the segment image. We cannot, so each prediction is
assigned to the reference in its group that it best matches, over both
representations. Any assignment procedure can mis-assign, so the summary reports
how many assignments were AMBIGUOUS (top two candidates within 0.05 with no
exact match) rather than pretending the question does not arise. A mis-assigned
prediction is graded N against either candidate unless it is exactly some other
drawn molecule, which is a real confusion and should be counted as one.

  .venv-ms/bin/python benchmarks/score_cx.py --run-dir RUN \
      --manifest ground_truth/synthetic_manifest.json --out SCORED_CX
"""
import argparse
import csv
import datetime as dt
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from rdkit import Chem, DataStructs, RDLogger
from rdkit.Chem import AllChem

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cxsmiles                                                   # noqa: E402
import graded as graded_mod                                       # noqa: E402
from score_run import HIGH, LOW, group_key, read_sheet            # noqa: E402

RDLogger.DisableLog("rdApp.*")

LETTERS = ["Y", "YS", "A", "N", "NS", "invalid"]
SKELETON_OK = ("Y", "YS", "A")
LABEL_PROPS = ("atomLabel", "_displayLabel", "_displayLabelW", "dummyLabel")

try:
    from molscribe.constants import ABBREVIATIONS as MS_ABBREV
except ImportError:                                               # pragma: no cover
    MS_ABBREV = {}


# ----------------------------------------------------------------- helpers
def strip_labels(mol):
    m = Chem.Mol(mol)
    for a in m.GetAtoms():
        for p in LABEL_PROPS:
            if a.HasProp(p):
                a.ClearProp(p)
    return m


def parse_cx(cx):
    """CXSMILES text -> (mol with labels, [label or '' per atom]) or (None, [])."""
    if not cx or str(cx).strip() in ("", "<invalid>"):
        return None, []
    s = str(cx).strip()
    m = Chem.MolFromSmiles(s)
    if m is None:                       # fall back to the SMILES part alone
        m = Chem.MolFromSmiles(s.split("|", 1)[0].strip())
        if m is None:
            return None, []
    labels = [a.GetProp("atomLabel") if a.HasProp("atomLabel") else "" for a in m.GetAtoms()]
    return m, labels


def skeleton_smiles(mol, stereo=True):
    """Canonical SMILES of the dummy graph. Labels never reach SMILES output,
    but they are cleared anyway so this cannot depend on a writer detail."""
    if mol is None:
        return None
    m = strip_labels(mol)
    if not stereo:
        Chem.RemoveStereochemistry(m)
    try:
        return Chem.MolToSmiles(m)
    except Exception:                                             # noqa: BLE001
        return None


def label_meaning(label):
    """A superatom's MEANING: its expansion, canonicalised.

    `OMe` and `MeO` are one superatom drawn facing two ways and must compare
    equal; `CN` (nitrile) and `NC` (isocyanide) must not. Only CXMolScribe's own
    table decides -- an unknown label falls back to its literal text, never to a
    guess, so an R-group stays an R-group and an unrecognised abbreviation is
    only ever equal to itself.
    """
    if not label:
        return ""
    smi = getattr(MS_ABBREV.get(label), "smiles", None)
    if isinstance(smi, str) and smi:
        m = Chem.MolFromSmiles(smi)
        if m is not None:
            return Chem.MolToSmiles(m)
    return f"<{label}>"


_MEANING_ID = {}


def positional_key(mol, labels, stereo=True):
    """Canonical SMILES with each dummy's label MEANING baked into its isotope.

    Two structures share this key only if the skeletons match AND each labelled
    position carries the same superatom. That is what "the appendix is correct"
    has to mean -- a multiset of labels would pass a prediction that put the
    right two labels on the wrong two atoms.
    """
    if mol is None:
        return None
    m = strip_labels(mol)
    for i, lab in enumerate(labels):
        if not lab or i >= m.GetNumAtoms():
            continue
        key = label_meaning(lab)
        _MEANING_ID.setdefault(key, len(_MEANING_ID) + 1)
        m.GetAtomWithIdx(i).SetIsotope(_MEANING_ID[key])
    if not stereo:
        Chem.RemoveStereochemistry(m)
    try:
        return Chem.MolToSmiles(m)
    except Exception:                                             # noqa: BLE001
        return None


def expanded_canon(cx, stereo=True):
    """Both sides through cxsmiles.expand -- the plain-SMILES question."""
    if not cx:
        return None, "empty"
    smi, note = cxsmiles.expand(str(cx))
    if smi is None:
        core = str(cx).split("|", 1)[0].strip()
        m = Chem.MolFromSmiles(core)
        smi = Chem.MolToSmiles(m) if m is not None else None
    if smi is None:
        return None, note
    m = Chem.MolFromSmiles(smi)
    if m is None:
        return None, note
    if not stereo:
        Chem.RemoveStereochemistry(m)
    return Chem.MolToSmiles(m), note


def fp(smi):
    m = Chem.MolFromSmiles(smi) if smi else None
    return AllChem.GetMorganFingerprintAsBitVect(m, 2, 2048) if m is not None else None


def tanimoto(a, b):
    return DataStructs.TanimotoSimilarity(a, b) if (a is not None and b is not None) else 0.0


# ----------------------------------------------------------------- grading
def fragments_of(smi):
    """Canonical SMILES of each disconnected fragment, largest first."""
    m = Chem.MolFromSmiles(smi) if smi else None
    if m is None:
        return []
    fs = Chem.GetMolFrags(m, asMols=True, sanitizeFrags=True)
    return [Chem.MolToSmiles(f) for f in
            sorted(fs, key=lambda f: -f.GetNumHeavyAtoms())]


def build_reference(entry):
    """One manifest molecule -> every form the grader compares against."""
    cx = entry["drawn_cxsmiles"]
    mol, labels = parse_cx(cx)
    exp, _ = expanded_canon(cx)
    if entry.get("markush"):
        # No molecule exists; the "expanded" form is the skeleton itself so the
        # assignment step still has something to work with. Graded on the
        # skeleton only -- see summary["markush_note"].
        exp = skeleton_smiles(mol)
    return {
        "name": entry["name"], "stratum": entry["stratum"], "markush": bool(entry.get("markush")),
        "cid": entry.get("cid"), "cx": cx,
        "skeleton": skeleton_smiles(mol), "skeleton_flat": skeleton_smiles(mol, False),
        "positional": positional_key(mol, labels), "positional_flat": positional_key(mol, labels, False),
        "labels": [x for x in labels if x], "has_appendix": bool([x for x in labels if x]),
        "expanded": exp, "expanded_flat": (expanded_canon(cx, False)[0] if not entry.get("markush")
                                           else skeleton_smiles(mol, False)),
        "skel_fp": fp(skeleton_smiles(mol)), "exp_fp": fp(exp),
        "smiles": entry["smiles"],
        # A drawn salt is one species; stage 2 hands stage 3 its fragments as
        # separate segments, so no segment can ever contain the whole reference.
        # Grading those against the whole species measures SEGMENTATION, not
        # recognition, and reports it in the recogniser's column.
        "frags": fragments_of(entry["smiles"]),
    }


def grade_one(pred_cx, refs):
    """Grade one prediction against the references drawn in its group."""
    out = {"letter": "invalid", "assigned": None, "assigned_stratum": None,
           "fragment_of_reference": False, "fragment_matched": "",
           "reference_fragments": None,
           "skeleton_strict": False, "skeleton_strict_flat": False,
           "skeleton_expanded": False, "skeleton_expanded_flat": False,
           "appendix_correct": None, "appendix_labels_exact": None,
           "pred_labels": "", "ref_labels": "", "ref_has_appendix": None,
           "pred_has_appendix": None, "assign_score": None, "assign_margin": None,
           "ambiguous": False, "expansion_note": "", "n_fragments": None}
    mol, labels = parse_cx(pred_cx)
    if mol is None:
        return out
    p_skel, p_skel_f = skeleton_smiles(mol), skeleton_smiles(mol, False)
    p_pos, p_pos_f = positional_key(mol, labels), positional_key(mol, labels, False)
    p_exp, note = expanded_canon(pred_cx)
    p_exp_f, _ = expanded_canon(pred_cx, False)
    p_labels = [x for x in labels if x]
    out.update({"pred_labels": ";".join(p_labels), "pred_has_appendix": bool(p_labels),
                "expansion_note": note, "n_fragments": len(Chem.GetMolFrags(mol))})
    p_skel_fp, p_exp_fp = fp(p_skel), fp(p_exp)

    scored = []
    for r in refs:
        s1 = 1.0 if (p_skel and p_skel == r["skeleton"]) else 0.0
        s2 = 1.0 if (p_exp and p_exp == r["expanded"]) else 0.0
        t = max(tanimoto(p_skel_fp, r["skel_fp"]), tanimoto(p_exp_fp, r["exp_fp"]))
        scored.append((2 * s1 + 2 * s2 + t, r))
    scored.sort(key=lambda x: -x[0])
    best, r = scored[0]
    runner = scored[1][0] if len(scored) > 1 else 0.0
    out["assign_score"], out["assign_margin"] = round(best, 3), round(best - runner, 3)
    out["ambiguous"] = best < 2.0 and (best - runner) < 0.05
    out["assigned"], out["assigned_stratum"] = r["name"], r["stratum"]
    out["ref_labels"] = ";".join(r["labels"])
    out["ref_has_appendix"] = r["has_appendix"]

    out["reference_fragments"] = len(r["frags"])
    if len(r["frags"]) > 1 and p_exp:
        hit = next((f for f in r["frags"] if f == p_exp), None)
        if hit:
            out["fragment_of_reference"] = True
            out["fragment_matched"] = hit

    out["skeleton_strict"] = bool(p_skel and p_skel == r["skeleton"])
    out["skeleton_strict_flat"] = bool(p_skel_f and p_skel_f == r["skeleton_flat"])
    out["skeleton_expanded"] = bool(p_exp and p_exp == r["expanded"])
    out["skeleton_expanded_flat"] = bool(p_exp_f and p_exp_f == r["expanded_flat"])

    # Appendix: only meaningful once the skeleton is right, which is also the
    # only case the paper's `A` covers.
    if out["skeleton_strict"]:
        if not r["has_appendix"]:
            out["letter"] = "YS"
            out["appendix_correct"] = None
        else:
            ok = bool(p_pos and p_pos == r["positional"])
            out["appendix_correct"] = ok
            out["appendix_labels_exact"] = sorted(p_labels) == sorted(r["labels"])
            out["letter"] = "Y" if ok else "A"
    else:
        out["letter"] = "N" if r["has_appendix"] else "NS"
    return out


# ----------------------------------------------------------------- report
def pct(a, b):
    return None if not b else round(100.0 * a / b, 1)


def stratum_table(rows, key="stratum"):
    by = defaultdict(list)
    for x in rows:
        by[x[key]].append(x)
    out = {}
    for s, xs in sorted(by.items()):
        c = Counter(x["letter"] for x in xs)
        n = len(xs)
        skel = sum(c[k] for k in SKELETON_OK)
        with_app = c["Y"] + c["A"]
        out[s] = {
            "structures": n, "Y": c["Y"], "YS": c["YS"], "A": c["A"], "N": c["N"],
            "NS": c["NS"], "invalid": c["invalid"],
            "skeleton_correct": skel, "skeleton_pct": pct(skel, n),
            "with_appendix": with_app, "appendix_correct": c["Y"],
            "appendix_pct": pct(c["Y"], with_app),
            "skeleton_expanded": sum(1 for x in xs if x["skeleton_expanded"]),
            "skeleton_expanded_pct": pct(sum(1 for x in xs if x["skeleton_expanded"]), n),
            "skeleton_strict_stereo_relaxed":
                sum(1 for x in xs if x["skeleton_strict_flat"]),
            "ambiguous_assignments": sum(1 for x in xs if x["ambiguous"]),
        }
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run-dir", type=Path, required=True)
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--label", default=None)
    args = ap.parse_args()

    manifest = json.loads(args.manifest.read_text())
    refs, ref_index = {}, {}
    for g, entry in manifest["groups"].items():
        refs[g] = [build_reference(m) for m in entry["molecules"]]
        for r, m in zip(refs[g], entry["molecules"]):
            ref_index[(g, r["name"])] = m

    res = args.run_dir / "03_CXMS_Results"
    rows = read_sheet(res / "Completed_HighConfidence_CMAGE.xlsx", HIGH) + \
        read_sheet(res / "Completed_LowConfidence_CMAGE.xlsx", LOW)
    if not rows:
        raise SystemExit(f"no stage-3 rows found under {res}")

    # The plain-SMILES side comes from graded.py, unmodified, so the two columns
    # are produced by two independent code paths and can be argued with apart.
    gref = {g: [(r["name"], graded_mod.ref_forms(r["smiles"])) for r in rs]
            for g, rs in refs.items()}

    out_rows, no_truth = [], 0
    for r in rows:
        g, fig, seg = group_key(r["file"], refs)
        if g not in refs:
            no_truth += 1
            continue
        rec = {"group": g, "figure": fig, "segment": seg,
               "file_name": Path(r["file"]).name, "tier": r["tier"],
               "confidence": r["confidence"], "smiles": r["smiles"]}
        rec.update(grade_one(r["smiles"], refs[g]))
        # group stratum, which is unambiguous wherever the group is pure
        strata_in_group = {x["stratum"] for x in refs[g]}
        rec["group_pure"] = len(strata_in_group) == 1
        rec["stratum"] = (next(iter(strata_in_group)) if rec["group_pure"]
                          else rec["assigned_stratum"])
        gr = graded_mod.grade_prediction(r["smiles"], gref[g])
        rec["plain_grade"] = gr["grade"]
        rec["plain_match"] = gr["graded_match"]
        rec["plain_exact"] = gr["grade"] == "exact"
        rec["plain_matched"] = gr["grade"] in graded_mod.MATCHED
        out_rows.append(rec)

    # ---- recall: per drawn molecule, was it recovered
    mol_rows = []
    for g, rs in refs.items():
        in_group = [x for x in out_rows if x["group"] == g]
        for r in rs:
            hits = [x for x in in_group if x["assigned"] == r["name"]]
            best = "no"
            for want in ("Y", "YS", "A"):
                if any(x["letter"] == want for x in hits):
                    best = want
                    break
            mol_rows.append({
                "group": g, "name": r["name"], "stratum": r["stratum"],
                "markush": r["markush"], "cid": r["cid"],
                "has_appendix": r["has_appendix"],
                "structures_assigned": len(hits),
                "skeleton_recovered": any(x["skeleton_strict"] for x in hits),
                "full_recovered": any(x["letter"] == "Y" for x in hits),
                "expanded_recovered": any(x["skeleton_expanded"] for x in hits),
                "plain_recovered": any(x["plain_exact"] for x in hits),
                "fragment_recovered": any(x["fragment_of_reference"] for x in hits),
                "best_letter": best,
            })

    nonmk = [x for x in out_rows if not any(
        r["markush"] and r["name"] == x["assigned"] for r in refs[x["group"]])]
    c = Counter(x["letter"] for x in out_rows)
    n = len(out_rows)
    skel = sum(c[k] for k in SKELETON_OK)
    with_app = c["Y"] + c["A"]
    summary = {
        "label": args.label, "run_dir_name": args.run_dir.name,
        "manifest": args.manifest.name, "corpus": manifest.get("corpus"),
        "generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "letters_note": ("Y/YS given by the paper; A/N/NS are the symmetric "
                         "completion and are this scorer's reading, not a quotation."),
        "upper_bound_note": ("RDKit line art on pure white: cleaner than any real "
                             "figure. Every figure here is an UPPER BOUND, and the "
                             "`basic` stratum is a control that should sit near "
                             "ceiling rather than a result."),
        "markush_note": ("markush structures have no single molecule. Their skeleton "
                         "grade is meaningful; their plain-SMILES column is not, and "
                         "the plain-SMILES headline excludes them."),
        "structures_graded": n,
        "structures_without_ground_truth": no_truth,
        "letters": {k: c[k] for k in LETTERS},
        "skeleton_correct": skel, "skeleton_pct": pct(skel, n),
        "appendix_denominator": with_app, "appendix_correct": c["Y"],
        "appendix_pct": pct(c["Y"], with_app),
        "skeleton_expanded_correct": sum(1 for x in out_rows if x["skeleton_expanded"]),
        "skeleton_expanded_pct": pct(sum(1 for x in out_rows if x["skeleton_expanded"]), n),
        "plain_exact": sum(1 for x in out_rows if x["plain_exact"]),
        "plain_exact_pct": pct(sum(1 for x in out_rows if x["plain_exact"]), n),
        "plain_exact_no_markush": sum(1 for x in nonmk if x["plain_exact"]),
        "plain_denominator_no_markush": len(nonmk),
        "plain_matched_graded": sum(1 for x in out_rows if x["plain_matched"]),
        "ambiguous_assignments": sum(1 for x in out_rows if x["ambiguous"]),
        "predictions_matching_one_drawn_fragment": sum(
            1 for x in out_rows if x["fragment_of_reference"]),
        "multi_fragment_references_seen": sum(
            1 for x in out_rows if (x["reference_fragments"] or 0) > 1),
        "predictions_carrying_an_appendix": sum(1 for x in out_rows if x["pred_has_appendix"]),
        "references_carrying_an_appendix": sum(1 for x in out_rows if x["ref_has_appendix"]),
        "by_stratum": stratum_table(out_rows),
        "by_group": stratum_table(out_rows, key="group"),
        "by_tier": stratum_table(out_rows, key="tier"),
        "recall": {
            "denominator": len(mol_rows),
            "skeleton_recovered": sum(1 for m in mol_rows if m["skeleton_recovered"]),
            "full_recovered": sum(1 for m in mol_rows if m["full_recovered"]),
            "expanded_recovered": sum(1 for m in mol_rows if m["expanded_recovered"]),
            "plain_recovered": sum(1 for m in mol_rows if m["plain_recovered"]),
            "by_stratum": {},
        },
    }
    by = defaultdict(list)
    for m in mol_rows:
        by[m["stratum"]].append(m)
    for s, ms in sorted(by.items()):
        summary["recall"]["by_stratum"][s] = {
            "drawn": len(ms),
            "skeleton_recovered": sum(1 for m in ms if m["skeleton_recovered"]),
            "full_recovered": sum(1 for m in ms if m["full_recovered"]),
            "expanded_recovered": sum(1 for m in ms if m["expanded_recovered"]),
            "plain_recovered": sum(1 for m in ms if m["plain_recovered"]),
            "fragment_recovered": sum(1 for m in ms if m["fragment_recovered"]),
            "never_assigned": sum(1 for m in ms if m["structures_assigned"] == 0),
        }

    args.out.mkdir(parents=True, exist_ok=True)
    fields = ["group", "stratum", "group_pure", "figure", "segment", "file_name", "tier",
              "confidence", "letter", "assigned", "assigned_stratum", "skeleton_strict",
              "skeleton_strict_flat", "skeleton_expanded", "skeleton_expanded_flat",
              "appendix_correct", "appendix_labels_exact", "ref_has_appendix",
              "pred_has_appendix", "ref_labels", "pred_labels", "plain_grade",
              "plain_match", "plain_exact", "plain_matched", "assign_score",
              "assign_margin", "ambiguous", "n_fragments", "reference_fragments",
              "fragment_of_reference", "fragment_matched", "expansion_note", "smiles"]
    with open(args.out / "cx_structures.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for x in sorted(out_rows, key=lambda r: (r["group"], r["figure"] or 0, r["segment"] or 0)):
            w.writerow(x)
    with open(args.out / "cx_molecules.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(mol_rows[0].keys()))
        w.writeheader()
        w.writerows(mol_rows)
    (args.out / "cx_summary.json").write_text(json.dumps(summary, indent=1))

    md = [f"# CXSMILES grade (paper Table 3 style) -- {args.label or args.run_dir.name}", "",
          summary["upper_bound_note"], "", summary["letters_note"], "",
          f"{n} structures graded, {no_truth} with no ground truth.", "",
          "| stratum | n | Y | YS | A | N | NS | skeleton | appendix | expanded-skeleton |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for s, t in summary["by_stratum"].items():
        md.append(f"| {s} | {t['structures']} | {t['Y']} | {t['YS']} | {t['A']} | {t['N']} | "
                  f"{t['NS']} | {t['skeleton_correct']}/{t['structures']} = {t['skeleton_pct']}% | "
                  f"{t['appendix_correct']}/{t['with_appendix']} = {t['appendix_pct']}% | "
                  f"{t['skeleton_expanded']}/{t['structures']} = {t['skeleton_expanded_pct']}% |")
    md += ["", f"| ALL | {n} | {c['Y']} | {c['YS']} | {c['A']} | {c['N']} | {c['NS']} | "
               f"{skel}/{n} = {summary['skeleton_pct']}% | {c['Y']}/{with_app} = "
               f"{summary['appendix_pct']}% | {summary['skeleton_expanded_correct']}/{n} = "
               f"{summary['skeleton_expanded_pct']}% |", ""]
    (args.out / "cx_summary.md").write_text("\n".join(md) + "\n")

    print(f"{n} structures graded  ->  {args.out}")
    print(f"  skeleton {skel}/{n} = {summary['skeleton_pct']}%   "
          f"appendix {c['Y']}/{with_app} = {summary['appendix_pct']}%")
    print(f"  expanded-skeleton (the plain-SMILES question) "
          f"{summary['skeleton_expanded_correct']}/{n} = {summary['skeleton_expanded_pct']}%")
    print(f"  letters {dict(c)}   ambiguous assignments {summary['ambiguous_assignments']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
