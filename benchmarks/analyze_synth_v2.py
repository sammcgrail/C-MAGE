#!/usr/bin/env python3
"""Cut the v2 result every way the corpus was designed to be cut.

score_cx.py reports by stratum and by group, which is right for the paper's
Table 3 and blind to everything v2 added. This joins its per-drawing verdicts
back to the manifest's recorded attributes -- size bucket, stereo depth,
abbreviation depth, render condition, arm -- and reports BOTH arms side by side,
because the gap between them is the finding and a single arm is not.

Every proportion carries a Wilson 95% interval. That is the whole point of
scaling from 100 compounds to 1031 drawings: an interval says whether a stratum
is different or merely small. Paired comparisons (the crossed render conditions,
the vocabulary mirror) use McNemar on the SAME compounds, which is the reason
they were drawn more than once.

  .venv-ms/bin/python benchmarks/analyze_synth_v2.py \
      --manifest benchmarks/ground_truth/synthetic_manifest_v2.json \
      --full benchmarks/scored/synthetic_v2_full \
      --stage3 benchmarks/scored/synthetic_v2_stage3only \
      --out benchmarks/scored/synthetic_v2_report
"""
import argparse
import csv
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path


def wilson(k, n, z=1.96):
    if not n:
        return (None, None)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    s = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (round(100 * (c - s) / d, 1), round(100 * (c + s) / d, 1))


def pct(k, n):
    return None if not n else round(100.0 * k / n, 1)


def mcnemar(b, c):
    """Exact two-sided binomial p for b discordant one way, c the other."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tot = sum(math.comb(n, i) for i in range(k + 1))
    return min(1.0, 2 * tot / (2 ** n))


def groups_attempted(run_root, manifest_groups):
    """Which groups did an arm actually process?

    Needed for the same reason ink_loss_v2 needs it: score_cx walks the WHOLE
    manifest, so a drawing whose PDF has not been run yet appears in
    cx_molecules.csv as simply not recovered -- indistinguishable, in every
    table, from one the pipeline saw and got wrong. On partial data that turns
    unfinished batches into a fabricated failure rate, and the two arms progress
    at different speeds so it would corrupt the ARM GAP, which is the finding.

    Full arm: stage-1 figures. Stage-3-only arm: the stage-2 results workbook,
    which lists every image handed to stage 3 (the crops themselves).
    """
    if run_root is None:
        return None
    root = Path(run_root)
    names = [f.name for f in root.glob("*/out/run_*/01_VH_Figures/*.png")]
    if not names:
        try:
            import pandas as pd
            for x in root.glob("*/out/run_*/02_DIS_Segments/DIS_CMAGE_results.xlsx"):
                col = pd.read_excel(x)["DIS Result File Paths"].tolist()
                names += [Path(str(v)).name for v in col]
        except Exception:                                          # noqa: BLE001
            return None
    out = set()
    for n in names:
        stem = Path(n).stem
        if stem.startswith("Image_DIS_VH_File_"):
            stem = stem[len("Image_DIS_VH_File_"):]
        stem = stem.rsplit("_molecule_", 1)[0]
        for k in sorted(manifest_groups, key=len, reverse=True):
            if stem == k or stem.startswith(k + "_image_"):
                out.add(k)
                break
    return out or None


def load(scored):
    out = {}
    p = Path(scored) / "cx_molecules.csv"
    if not p.exists():
        return out
    with open(p) as f:
        for r in csv.DictReader(f):
            out[(r["group"], r["name"])] = {
                "skeleton": r["skeleton_recovered"] == "True",
                "full": r["full_recovered"] == "True",
                "expanded": r["expanded_recovered"] == "True",
                "fragment": r["fragment_recovered"] == "True",
                "letter": r["best_letter"],
                "assigned": int(r["structures_assigned"]),
            }
    return out


def table(rows, key, arms, want="skeleton"):
    by = defaultdict(list)
    for r in rows:
        k = r.get(key)
        if k is not None:
            by[k].append(r)
    out = {}
    for k, xs in sorted(by.items(), key=lambda kv: str(kv[0])):
        e = {"n": len(xs)}
        for arm in arms:
            got = [x for x in xs if x.get(arm) is not None]
            hit = sum(1 for x in got if x[arm][want])
            e[arm] = {"n": len(got), "k": hit, "pct": pct(hit, len(got)),
                      "ci": wilson(hit, len(got))}
        # appendix, over drawings that were DRAWN with one
        app = [x for x in xs if x["has_appendix"]]
        for arm in arms:
            got = [x for x in app if x.get(arm) is not None]
            hit = sum(1 for x in got if x[arm]["full"])
            e[f"{arm}_appendix"] = {"n": len(got), "k": hit, "pct": pct(hit, len(got)),
                                    "ci": wilson(hit, len(got))}
        out[str(k)] = e
    return out


def md_table(title, tab, arms, note=""):
    head = f"### {title}\n"
    if note:
        head += note + "\n\n"
    head += "| " + " | ".join(["bucket", "drawings"]
                              + [f"{a} skeleton" for a in arms]
                              + [f"{a} appendix" for a in arms]) + " |\n"
    head += "|" + "---|" * (2 + 2 * len(arms)) + "\n"
    for k, e in tab.items():
        cells = [k, str(e["n"])]
        for a in arms:
            v = e[a]
            cells.append(f"{v['k']}/{v['n']} = {v['pct']}% ({v['ci'][0]}-{v['ci'][1]})"
                         if v["n"] else "-")
        for a in arms:
            v = e[f"{a}_appendix"]
            cells.append(f"{v['k']}/{v['n']} = {v['pct']}%" if v["n"] else "-")
        head += "| " + " | ".join(cells) + " |\n"
    return head + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--full", type=Path, required=True)
    ap.add_argument("--stage3", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--ink", type=Path, default=None, help="ink_loss_v2.py output dir")
    ap.add_argument("--full-run-root", type=Path, default=None,
                    help="batch run root of the full arm; restricts its denominator "
                         "to groups that were actually processed")
    ap.add_argument("--stage3-run-root", type=Path, default=None,
                    help="batch run root of the stage-3-only arm, likewise")
    args = ap.parse_args()

    man = json.loads(args.manifest.read_text())
    full, s3 = load(args.full), load(args.stage3)
    arms = ["full", "stage3"]
    att = {"full": groups_attempted(args.full_run_root, man["groups"]),
           "stage3": groups_attempted(args.stage3_run_root, man["groups"])}
    rows = []
    for g, e in man["groups"].items():
        for m in e["molecules"]:
            k = (g, m["name"])
            rows.append({
                "group": g, "name": m["name"], "stratum": m["stratum"],
                "arm_of_pdf": e["arm"], "render": m["render"],
                "per_page": m["per_page"], "bond_line_width": m["bond_line_width"],
                "size_bucket": m["size_bucket"], "stereo_bucket": m["stereo_bucket"],
                "abbrev_bucket": m["abbrev_bucket"], "topology": m.get("topology"),
                "has_appendix": m["has_appendix"], "markush": bool(m.get("markush")),
                "heavy_atoms": m["heavy_atoms"], "number": m["number"],
                "in_vocab": all(m["appendix_in_vocab"]) if m["has_appendix"] else None,
                "full": (full.get(k) if (att["full"] is None or g in att["full"]) else None),
                "stage3": (s3.get(k) if (att["stage3"] is None or g in att["stage3"]) else None),
            })
    core = [r for r in rows if r["arm_of_pdf"] in ("core", "mixed")]
    crossed = [r for r in rows if r["arm_of_pdf"] == "crossed"]
    vin = [r for r in rows if r["arm_of_pdf"] == "vocab_in"]
    vout = [r for r in rows if r["arm_of_pdf"] == "vocab_out"]

    rep = {
        "drawings": len(rows), "scored_full": sum(1 for r in rows if r["full"]),
        "scored_stage3": sum(1 for r in rows if r["stage3"]),
        "groups_attempted_full": (len(att["full"]) if att["full"] else None),
        "groups_attempted_stage3": (len(att["stage3"]) if att["stage3"] else None),
        "groups_in_manifest": len(man["groups"]),
        "partial_note": ("Denominators are restricted to the groups each arm "
                         "actually processed. score_cx walks the whole manifest, so "
                         "without this an unrun PDF is reported as a failure and the "
                         "two arms -- which progress at different speeds -- would be "
                         "compared over different corpora."),
        "upper_bound_note": (
            "RDKit line art on exactly white, one drawing convention, no scanner "
            "noise and no overlapping labels. Every number here is an UPPER BOUND "
            "on the pipeline against real literature, and `basic` is a control "
            "that should sit near ceiling rather than a result."),
        "core_by_stratum": table(core, "stratum", arms),
        "core_by_size": table(core, "size_bucket", arms),
        "stereo_by_depth": table([r for r in core if r["stratum"] == "stereo"],
                                 "stereo_bucket", arms),
        "all_by_stereo_depth": table(core, "stereo_bucket", arms),
        "abbrev_by_depth": table([r for r in core if r["stratum"] == "abbreviated"],
                                 "abbrev_bucket", arms),
        "complex_by_topology": table([r for r in core if r["stratum"] == "complex"],
                                     "topology", arms),
        "crossed_by_render": table(crossed, "render", arms),
        "crossed_by_perpage": table(crossed, "per_page", arms),
        "crossed_by_linewidth": table(crossed, "bond_line_width", arms),
    }

    # ---- paired: vocabulary mirror, same molecule, same pixels but the label
    pair = {}
    byname = {r["name"]: r for r in vin}
    for arm in arms:
        b = c = both = neither = 0
        for r in vout:
            a = byname.get(r["name"])
            if not a or not a.get(arm) or not r.get(arm):
                continue
            x, y = a[arm]["skeleton"], r[arm]["skeleton"]
            both += x and y
            neither += (not x) and (not y)
            b += x and not y
            c += y and not x
        pair[f"{arm}_skeleton"] = {"in_only": b, "out_only": c, "both": both,
                                   "neither": neither, "p_mcnemar": round(mcnemar(b, c), 5)}
        b = c = both = neither = 0
        for r in vout:
            a = byname.get(r["name"])
            if not a or not a.get(arm) or not r.get(arm):
                continue
            x, y = a[arm]["full"], r[arm]["full"]
            both += x and y
            neither += (not x) and (not y)
            b += x and not y
            c += y and not x
        pair[f"{arm}_appendix_Y"] = {"in_only": b, "out_only": c, "both": both,
                                     "neither": neither, "p_mcnemar": round(mcnemar(b, c), 5)}
    rep["vocab_paired"] = pair
    rep["vocab_arms"] = {"in": table(vin, "stratum", arms), "out": table(vout, "stratum", arms)}

    # ---- paired: every crossed condition against dens_std, same compounds
    base = {r["name"]: r for r in crossed if r["render"] == "dens_std"}
    cross_pair = {}
    for cond in sorted({r["render"] for r in crossed}):
        if cond == "dens_std":
            continue
        d = {}
        for arm in arms:
            b = c = 0
            for r in [x for x in crossed if x["render"] == cond]:
                a = base.get(r["name"])
                if not a or not a.get(arm) or not r.get(arm):
                    continue
                x, y = a[arm]["skeleton"], r[arm]["skeleton"]
                b += x and not y
                c += y and not x
            d[arm] = {"std_only": b, "cond_only": c, "p_mcnemar": round(mcnemar(b, c), 5)}
        cross_pair[cond] = d
    rep["crossed_paired_vs_dens_std"] = cross_pair

    if args.ink and (args.ink / "ink_summary.json").exists():
        rep["ink"] = json.loads((args.ink / "ink_summary.json").read_text())

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "report.json").write_text(json.dumps(rep, indent=1))

    md = [f"# Synthetic corpus v2 -- {rep['drawings']} drawings, both arms", "",
          rep["upper_bound_note"], "",
          f"full pipeline scored {rep['scored_full']}, stage-3-only scored "
          f"{rep['scored_stage3']}. Percentages are per DRAWING recall (was this "
          f"structure recovered), with Wilson 95% intervals.", ""]
    md.append(md_table("Core corpus by stratum", rep["core_by_stratum"], arms))
    md.append(md_table("Core corpus by heavy-atom count", rep["core_by_size"], arms,
                       "Size is recorded for every drawing, so this cuts ACROSS strata "
                       "-- it is not the `complex` stratum under another name."))
    md.append(md_table("Stereo stratum by number of defined centres",
                       rep["stereo_by_depth"], arms))
    md.append(md_table("Whole core corpus by number of defined centres",
                       rep["all_by_stereo_depth"], arms))
    md.append(md_table("Abbreviated stratum by superatoms per structure",
                       rep["abbrev_by_depth"], arms))
    md.append(md_table("Complex stratum by ring topology", rep["complex_by_topology"], arms,
                       "v1's `complex` predicate was `heavy>=55 OR ring>=13`, a "
                       "disjunction of the two variables it needed to separate."))
    md.append(md_table("Crossed arm by render condition", rep["crossed_by_render"], arms,
                       "The SAME 48 compounds under every condition."))
    md.append(md_table("Crossed arm by structures per page", rep["crossed_by_perpage"], arms))
    md.append(md_table("Crossed arm by bond line width", rep["crossed_by_linewidth"], arms))
    md.append("### Vocabulary mirror, paired on the same molecule\n")
    md.append("| comparison | both | in-vocab only | mirrored only | neither | McNemar p |")
    md.append("|---|---|---|---|---|---|")
    for k, v in pair.items():
        md.append(f"| {k} | {v['both']} | {v['in_only']} | {v['out_only']} | "
                  f"{v['neither']} | {v['p_mcnemar']} |")
    md.append("")
    md.append("### Crossed conditions against dens_std, paired on the same molecule\n")
    md.append("| condition | arm | dens_std only | condition only | McNemar p |")
    md.append("|---|---|---|---|---|")
    for cond, d in cross_pair.items():
        for arm, v in d.items():
            md.append(f"| {cond} | {arm} | {v['std_only']} | {v['cond_only']} | "
                      f"{v['p_mcnemar']} |")
    md.append("")
    (args.out / "report.md").write_text("\n".join(md) + "\n")
    print("\n".join(md[:4]))
    print(md_table("Core corpus by stratum", rep["core_by_stratum"], arms))
    print(f"-> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
