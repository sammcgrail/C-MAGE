#!/usr/bin/env python3
"""Fill CXMolScribe's reading of the novel set into benchmarks/novel_set.json (fields s, v, c).

    novel_cx.py <stage-3 run dir>

The run is benchmarks/run_stage3_only.sh on /root/cmage-work/novel/corpus_rdkit_1500, the same
stage-3-only arm the corpus's CXMolScribe column comes from. Scored with sonnet_batch.verdict, the
one scoring function. c is the model's confidence x 100, as in images.json. CXMolScribe is not
deterministic (see the skill), so this is one run, stamped with its directory.
"""
import json
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import sonnet_batch as B  # noqa: E402
from novel_set import OUT  # noqa: E402


def main(run: str) -> int:
    res = Path(run) / "03_CXMS_Results"
    pred = {}
    for f in ("Completed_HighConfidence_CMAGE.xlsx", "Completed_LowConfidence_CMAGE.xlsx"):
        for r in pd.read_excel(res / f).to_dict("records"):
            k = Path(r["File Path"]).stem
            if k in pred:
                raise SystemExit(f"{k} predicted twice")
            s = r["Predicted CXSMILES"]
            pred[k] = (s if isinstance(s, str) else None, float(r["CXSMILES's Confidence Levels"]),
                       "high" if f.startswith("Completed_High") else "low")
    d = json.load(open(OUT))
    for row in d["rows"]:
        s, c, tier = pred.get(row["k"], (None, None, None))
        row.update(s=s, v=B.verdict(s, row["t"]), c=None if c is None else round(c * 100),
                   cx_tier=tier, cx_run=Path(run).name)
        if row["kind"] == "A":
            row["cx_parent"] = B.verdict(s, row["parent_t"]) == "exact"
    OUT.write_text(json.dumps(d, indent=1) + "\n")
    for kind in "AB":
        xs = [r for r in d["rows"] if r["kind"] == kind]
        print(f"kind {kind}: CXMolScribe {sum(r['v'] == 'exact' for r in xs)}/{len(xs)} exact"
              + (f", {sum(r['cx_parent'] for r in xs)} equal the parent" if kind == "A" else ""))
    for r in d["rows"]:
        print(f"  {r['k']} {r['v']:<8} c={r['c']} {r['cx_tier']}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    sys.exit(main(sys.argv[1]))
