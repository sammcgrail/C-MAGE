"""The Sonnet arm: a general vision model reading the same drawings, scored the same way.

The comparison is only worth anything if it is fair, so three things are fixed:

  * The SAMPLE is a deterministic stride over the sorted corpus, not a hand-pick.
    A curated ten is a claim about the curator.
  * The FILENAMES are anonymised. The corpus names images `testosterone_cid6013`,
    so a model given the path could answer from the string without looking at the
    picture at all, and would score well for the wrong reason.
  * The SCORING is identical: RDKit canonical isomeric SMILES equality for exact,
    equality after dropping stereochemistry for stereo. Same function, same
    references, no separate leniency for either reader.
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, "/root/C-MAGE/tools")
from build_wall import WALL, THRESHOLD, render_pred, thumb, relate     # noqa: E402


def main() -> int:
    rows_in = json.load(open("/tmp/sonnet10_scored.json"))
    img = WALL / "sonnet"
    pred = WALL / "sonnet_pred"
    img.mkdir(parents=True, exist_ok=True)
    pred.mkdir(parents=True, exist_ok=True)

    rows = []
    for r in rows_in:
        k = r["k"]
        thumb(Path(r["path"]), img / f"{k}.png")
        has = render_pred(r.get("sonnet_smiles") or "", pred / f"{k}.png")
        rows.append({
            "k": k, "n": r["name"], "v": r["sonnet_verdict"], "g": r["sonnet_verdict"],
            "c": None, "s": r.get("sonnet_smiles") or "", "t": r["truth"],
            "p": 1 if has else 0,
            "r": relate(r.get("sonnet_smiles") or "", r["truth"]),
            # Both readings travel with the row so the sheet can show them together.
            "ocr": r["ocr_smiles"], "ocrv": r["ocr_verdict"], "ocrc": r["ocr_conf"],
            "sconf": r.get("sonnet_conf"),
        })

    n = len(rows)
    s_ex = sum(1 for r in rows if r["v"] == "exact")
    o_ex = sum(1 for r in rows if r["ocrv"] == "exact")
    both = sum(1 for r in rows if r["v"] == "exact" and r["ocrv"] == "exact")
    either = sum(1 for r in rows if r["v"] == "exact" or r["ocrv"] == "exact")
    d = {
        "arm": "Sonnet", "dir": "sonnet", "rows": rows,
        "stats": {"n": n, "exact": s_ex, "strict_pct": round(s_ex / n * 100, 1)},
        "heroLabel": f"of {n} — against CXMolScribe's {o_ex} on the same {n}",
        "threshold": round(THRESHOLD * 100),
        "headline": (
            f"A general vision model reading the same drawings, scored by the same rule. "
            f"Sonnet {s_ex} of {n}, the pipeline {o_ex} of {n}. They agree on {both} and "
            f"between them get {either} — they fail on DIFFERENT molecules, which is the "
            f"result worth having from a sample this small."),
        "footer": (
            "Sample is a deterministic stride over the sorted corpus, not a hand-pick. "
            "Filenames were anonymised before the model saw them, because the corpus names "
            "images after their compounds and a model given the path could answer without "
            "looking. Scored with the same RDKit canonical comparison as every other arm. "
            f"n={n}: this is a probe, not a benchmark, and no percentage from it should be "
            "quoted as if it were one."),
    }
    json.dump(d, open(WALL / "sonnet.json", "w"), separators=(",", ":"))
    print(f"  sonnet {s_ex}/{n}  cxmolscribe {o_ex}/{n}  both {both}  either {either}")
    print(f"  payload {os.path.getsize(WALL/'sonnet.json')/1e3:.0f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
