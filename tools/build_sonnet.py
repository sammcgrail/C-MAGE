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


PROMPT_TEXT = """Read ten chemical structure drawings and give the SMILES for each.

Images (use the Read tool on each — they render as images):
/tmp/blind_<slot>/img01.png … img10.png

For each, write the SMILES for the structure depicted. Stereochemistry where the
drawing shows it (wedge/hash, E/Z). All fragments if more than one is drawn
(salts, counter-ions), dot-separated.

RULES:
- Work from the DRAWING. If you recognise the molecule you may cross-check, but
  the drawing is the authority — say so if they conflict.
- COUNT THE ATOMS EXPLICITLY before writing. An earlier batch read a chain with
  one extra CH2, turning lactic acid into 3-hydroxybutyric acid, at high stated
  confidence. Count ring vertices and chain carbons.
- Exactly one SMILES per image. UNREADABLE rather than a guess, with a reason.
- Do NOT use RDKit or any cheminformatics tool to canonicalise or improve your
  answer. I want your reading.

OUTPUT — a JSON array:
[{"img": "img01", "smiles": "...", "name_if_recognised": "...",
  "confidence": "high|medium|low"}, ...]
All ten, in order."""

PROMPT_NOTE = ("The file paths are anonymised before the model sees them. The corpus names "
               "images after their compounds — lactic_acid_cid612.png — so a model handed the "
               "real path can answer from the string without looking at the drawing, and would "
               "score well for entirely the wrong reason.")


def main() -> int:
    # Read the append-only results file, not a snapshot. The batch harness appends
    # to it, so the tab reflects every batch scored so far with no separate step to
    # forget.
    src = Path("/root/cmage-work/sonnet/results.jsonl")
    rows_in = [json.loads(l) for l in open(src) if l.strip()]
    img = WALL / "sonnet"
    pred = WALL / "sonnet_pred"
    img.mkdir(parents=True, exist_ok=True)
    pred.mkdir(parents=True, exist_ok=True)

    import glob
    idx = {}
    for dd in sorted(glob.glob("/root/cmage-work/cmage-img*/corpus_rdkit_1500")):
        for pth in glob.glob(dd + "/*.png"):
            idx.setdefault(os.path.basename(pth), pth)

    rows = []
    for r in rows_in:
        k = r["k"]
        src_img = idx.get(k + ".png")
        if not src_img:
            continue
        thumb(Path(src_img), img / f"{k}.png")
        has = render_pred(r.get("sonnet_smiles") or "", pred / f"{k}.png")
        # The tile's colour is the OUTCOME, not Sonnet's verdict alone. "Sonnet was
        # wrong" and "Sonnet was wrong where the pipeline was right" are different
        # facts, and the second is the one this tab exists to show.
        sv = r["sonnet_verdict"] == "exact"
        ov = r["ocr_verdict"] == "exact"
        outcome = ("both" if sv and ov else
                   "sonnet" if sv else
                   "cxms" if ov else "neither")
        rows.append({
            "k": k, "n": r["name"], "v": r["sonnet_verdict"], "g": r["sonnet_verdict"],
            "o": outcome,
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
    corpus_n = len(json.load(open(WALL / "images.json"))["rows"])
    d = {
        "arm": "Sonnet", "dir": "sonnet", "rows": rows,
        # Two readers, one denominator, shown at the same size. A single big
        # percentage with the other reader's score in prose underneath reads as a
        # headline plus a footnote; the point here is that they are comparable.
        "compare": {
            "n": n, "corpus": corpus_n,
            "sides": [
                {"label": "Sonnet", "exact": s_ex, "pct": round(s_ex / n * 100, 1)},
                {"label": "CXMolScribe", "exact": o_ex, "pct": round(o_ex / n * 100, 1)},
            ],
            "agree": both, "either": either,
            # Ordered worst-understood to best so the stacked bar reads left to
            # right as "who got it": both, then each alone, then neither.
            "breakdown": [
                {"key": "both", "label": "Both right",
                 "n": sum(1 for r in rows if r["o"] == "both")},
                {"key": "sonnet", "label": "Sonnet only",
                 "n": sum(1 for r in rows if r["o"] == "sonnet")},
                {"key": "cxms", "label": "CXMolScribe only",
                 "n": sum(1 for r in rows if r["o"] == "cxms")},
                {"key": "neither", "label": "Neither",
                 "n": sum(1 for r in rows if r["o"] == "neither")},
            ],
        },
        "prompt": PROMPT_TEXT, "promptNote": PROMPT_NOTE,
        "stats": {"n": n, "exact": s_ex, "strict_pct": round(s_ex / n * 100, 1)},
        "heroLabel": f"of {n} — against CXMolScribe's {o_ex} on the same {n}",
        "threshold": round(THRESHOLD * 100),
        "headline": ("A general vision model reading the same drawings, scored by the "
                     "same rule as the pipeline."),
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
