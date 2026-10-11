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


def test_step_carries_on(t):
    """Every phase failing with an ordinary error: the step still runs every later phase, does not halt, does
    not disable the timer. A spend-guard CapHit still halts."""
    calls, disabled = [], []
    E.STATE = t / "state.json"
    E.set_rows = lambda: []
    E.api_have = lambda: set()
    E.n_protac_read = lambda: 0
    E.run_spend = lambda d: 0.0

    def boom(name):
        def f(*a, **k):
            calls.append(name)
            raise RuntimeError(f"{name} broke")
        return f
    E.add_rows, E.run_cx, E.run_api, E.score, E.publish = (boom(x) for x in ("add", "cx", "api", "score", "publish"))
    E.signal = lambda *a, **k: calls.append("signal")
    E.disable_timer = lambda why: disabled.append(why)
    assert E.step(5, do_publish=True, do_signal=False) == 0
    assert calls == ["add", "cx", "api", "score", "publish", "signal"], calls
    assert not disabled and not E.load_state().get("halted"), (disabled, E.load_state())
    assert len(E.load_state()["steps"][-1]["errors"]) == 5

    def cap():
        raise E.CapHit("spend guard")
    E.run_api = cap
    assert E.step(5, do_publish=False, do_signal=False) == 1
    assert disabled and E.load_state()["halted"] == "spend guard"


def test_clean_truth(t):
    """New rows get the same stray-fragment cleaning as clean_truth.py apply: label/glyph artifacts dropped (raw kept
    in truth_raw), a drawn salt kept, an unknown fragment kept and logged for a look, a clean truth untouched."""
    from rdkit import Chem
    E.now = lambda: __import__("datetime").datetime(2026, 10, 11)
    lp = t / "truth_cleanup.json"
    parent = "COc1cc2nn(C3CCN(C(=O)C4CCN(Cc5ccc6c(c5)C(=O)N(C5CCC(=O)NC5=O)C6=O)CC4)CC3)cc2cc1NC(=O)c1cccc(C(F)(F)F)n1"
    cases = {      # raw truth -> expected clean truth
        parent + ".[I-27]": parent,                     # compound label "I-27" (rb_0605)
        parent + ".I[I-16]": parent,
        parent + ".S.S": parent,                        # "(S)" stereo descriptors
        parent + ".[HH]": parent,                       # split N-H
        parent + ".[2H-].[2H-]": parent,                # "D-" amino-acid labels
        parent + ".[C-3]BF": parent,                    # "(BFC-3)"
        parent + ".C": parent,                          # lone C glyph
        parent + ".O=CO": parent + ".O=CO",             # drawn formic acid salt: kept
        parent + ".[Cl-]": parent + ".[Cl-]",
        parent + ".O": parent + ".O",                   # hydrate: kept
        parent: parent,
    }
    for i, (raw, want) in enumerate(cases.items()):
        r = E.clean_truth_row(f"rb_t{i:03d}", {"truth": raw, "cls": "protac"}, log_path=lp)
        assert r["truth"] == want, (raw, r["truth"])
        assert r["changed"] == (raw != want)
        assert Chem.MolFromSmiles(r["truth"]) is not None
    r = E.clean_truth_row("rb_t100", {"truth": parent + ".CCCCc1ccccc1", "cls": "protac"}, log_path=lp)
    assert r["truth"] == parent + ".CCCCc1ccccc1" and r["undecided"], r          # unknown: kept, flagged
    log = json.load(open(lp))
    ids = {x["id"] for x in log["rows"]}
    assert "rb_t000" in ids and "rb_t100" in ids and "rb_t010" not in ids, ids    # clean truth: no entry
    assert any(x["id"] == "rb_t100" and x["undecided"] for x in log["rows"])


def main():
    E.log = lambda m: None
    with tempfile.TemporaryDirectory() as t:
        t = Path(t)
        E.QUAR = t / "quarantine.jsonl"
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
        # Sam 10 Oct: a bad NEW row is quarantined and skipped, never fatal; the good rows still merge
        _pair(run, ["rb_9999", "rb_0001", "wv_0002"][:2])           # unknown id + already-merged id
        E.merge_cx(t / "run", sa, cxp)
        q = [json.loads(l) for l in open(E.QUAR)]
        assert {(r["key"], r["stage"]) for r in q} == {("rb_9999", "cx-merge"), ("rb_0001", "cx-merge")}, q
        got2 = set()
        for f in ("High", "Low"):
            got2 |= {Path(x).stem for x in pd.read_excel(cxp / f"Completed_{f}Confidence_CMAGE.xlsx")["File Path"]}
        assert got2 == got, got2
        test_step_carries_on(t)
        test_clean_truth(t)
    print("TEST PASS")


if __name__ == "__main__":
    main()
