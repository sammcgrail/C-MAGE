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
    print("TEST PASS")


if __name__ == "__main__":
    main()
