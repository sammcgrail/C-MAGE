"""The arms table for the collapsed catalogue at the bottom of the wall.

Every number here is recomputed from the scored CSVs at build time rather than
copied from headline.json, because headline.json's per-arm figures were built on
different scopes and quoting them side by side is the exact comparison the old
page had to apologise for in a 45-word subtitle.

MATCHED SCOPE. Arms are compared only on compounds every listed arm covers. The
re-render arm covers 760 of the 1210, so that is the denominator for all of them.
An arm table whose rows have different denominators is not a comparison.
"""
import csv
from pathlib import Path

B = Path("/root/C-MAGE/benchmarks/scored")

ARMS = [
    ("RDKit 1500, fresh layout", ["pooled1010_corpus_rdkit_1500", "batch7_corpus_rdkit_1500"],
     "Draw it yourself at 1500 px. The arm the page reports.", True),
    ("RDKit 300", ["pooled1010_corpus_rdkit_300", "batch7_corpus_rdkit_300"],
     "Same layout, smaller canvas. Costs four points.", False),
    ("PubChem re-rendered 1500", ["pubchem_rerender", "batch7_corpus_rerender_1500"],
     "PubChem's own 2D coordinates, redrawn with stroke width scaled to the canvas.", False),
    ("PubChem 300 + white remap", ["pooled1010_corpus_300_white", "batch7_corpus_300_white"],
     "Near-white background forced to true white. Best result from repairing a supplied image.", False),
    ("PubChem white + upscaled 1200", ["img_corpus_white_up1200", "new250_corpus_white_up1200",
                                       "pharma200_corpus_white_up1200", "batch7_corpus_white_up1200"],
     "Remap, then resample to 1200 px. Resampling adds nothing.", False),
    ("PubChem 300 upscaled 1200", ["img_corpus_upscaled_1200", "new250_corpus_upscaled_1200",
                                   "pharma200_corpus_upscaled_1200", "batch7_corpus_upscaled_1200"],
     "Resample alone, no remap.", False),
    ("PubChem 300, as supplied", ["pooled1010_corpus_300", "batch7_corpus_300"],
     "What you get fetching PubChem at the default size.", False),
    ("PubChem 1500, as supplied", ["pooled1010_corpus_hires", "batch7_corpus_hires"],
     "PubChem's own large PNG. Zero correct, on all 1210, in four independent batches.", False),
]


def load(dirs):
    out = {}
    for d in dirs:
        p = B / d / "structures.csv"
        if p.exists():
            for r in csv.DictReader(open(p)):
                out[r["file_name"]] = r
    return out


def build(threshold: float = 0.8431) -> tuple[list[dict], str]:
    data = {name: load(dirs) for name, dirs, _n, _l in ARMS}
    common = set.intersection(*[set(v) for v in data.values() if v])
    n = len(common)
    rows = []
    for name, _dirs, note, lead in ARMS:
        v = data[name]
        ex = gr = hi = hiok = ph = 0
        for f in common:
            r = v[f]
            if r["verdict"] == "exact":
                ex += 1
            if r["grade"] in ("exact", "stereo", "tautomer", "charge", "salt"):
                gr += 1
            pf = (r.get("phantom_frags") or "").strip()
            if pf and pf not in ("0", "[]"):
                ph += 1
            if float(r.get("confidence") or 0) >= threshold:
                hi += 1
                if r["verdict"] == "exact":
                    hiok += 1
        rows.append({"name": name, "n": n, "lead": lead, "note": note,
                     "strict": round(ex / n * 100, 1), "graded": round(gr / n * 100, 1),
                     "high": round(hiok / hi * 100, 1) if hi else None,
                     "phantom": round(ph / n * 100, 1)})
    note = (f"All eight arms on the same {n} compounds — the largest set every arm covers. "
            f"Strict is the string as emitted, which is what you get pasting it into a "
            f"database. Graded allows a tautomer, a charge or a salt to differ. Phantom is "
            f"the share of predictions carrying a stray disconnected fragment welded on "
            f"beside an otherwise correct molecule.")
    return rows, note
