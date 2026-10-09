#!/usr/bin/env python3
"""Tests for big_expand.merge_cx (run: .venv-ms/bin/python tools/superatoms/test_big_expand.py)."""
import json, sys, tempfile
from pathlib import Path
import pandas as pd
sys.path.insert(0, str(Path(__file__).parent))
import big_expand as E

COLS = ["File Path", "Predicted CXSMILES", "CXSMILES's Confidence Levels"]


def _pair(d, ids):
    d.mkdir(parents=True, exist_ok=True)
    for f, sub in (("High", ids[::2]), ("Low", ids[1::2])):
        pd.DataFrame([[f"/x/{k}.png", "C", 0.9] for k in sub], columns=COLS).to_excel(d / f"Completed_{f}Confidence_CMAGE.xlsx")


def main():
    E.log = lambda m: None
    with tempfile.TemporaryDirectory() as t:
        t = Path(t)
        sa, cxp, run = t / "sa", t / "sa/cxmolscribe", t / "run/03_CXMS_Results"
        for d, ids in (("big", ["rb_0001", "rb_0002"]), ("wavy", ["wv_0002"])):
            (sa / d).mkdir(parents=True)
            json.dump([{"id": k} for k in ids], open(sa / d / "set.json", "w"))
        _pair(cxp, ["rb_0001", "wv_0001", "wv_0002"])          # wv_0001: removed from its set, row still in the pair
        (cxp / "RUN.txt").write_text("")
        _pair(run, ["rb_0002"])
        E.merge_cx(t / "run", sa, cxp)                          # must not raise on the stale wv_0001
        got = set()
        for f in ("High", "Low"):
            got |= {Path(x).stem for x in pd.read_excel(cxp / f"Completed_{f}Confidence_CMAGE.xlsx")["File Path"]}
        assert got == {"rb_0001", "rb_0002", "wv_0001", "wv_0002"}, got
        for bad, why in ((["rb_9999"], "in no set.json"), (["rb_0001"], "twice")):
            _pair(run, bad)
            before = (cxp / "Completed_HighConfidence_CMAGE.xlsx").read_bytes()
            try:
                E.merge_cx(t / "run", sa, cxp)
                raise SystemExit(f"FAIL: {bad} accepted")
            except AssertionError as e:
                assert why in str(e), e
            assert (cxp / "Completed_HighConfidence_CMAGE.xlsx").read_bytes() == before, "partial write"
    print("TEST PASS")


if __name__ == "__main__":
    main()
