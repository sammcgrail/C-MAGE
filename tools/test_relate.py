"""Prove every branch of relate() can actually fire.

WHY THIS EXISTS. A sibling session found a stratification quota gated on
`len(cip_labels) >= 8` where cip_labels is `{"R": n, "S": m}` — len() maxes out
at 2, so the condition was unsatisfiable. It contributed +0 and printed +0, which
is indistinguishable from a stratum the data genuinely lacks. Nobody looked
because the output was plausible.

relate() has the same shape of risk: five branches, each of which reports "no
note" when it does not fire, and a missing note looks like a row that simply had
nothing to say. That already happened once here — the isotope branch never fired
at all, because zeroing an isotope does not remove it ([2H] is an explicit
hydrogen ATOM), and the note just quietly went missing.

So each branch is fed the case that must trigger it. A test that only ever sees
inputs which pass proves nothing.

    /root/C-MAGE/.venv-ms/bin/python tools/test_relate.py
"""
import sys

sys.path.insert(0, "/root/C-MAGE/tools")
from build_wall import relate                                   # noqa: E402

CASES = [
    # name,        predicted,             expected,                          wanted branch
    ("identical",  "CC(=O)Nc1ccc(O)cc1",  "CC(=O)NC1=CC=C(C=C1)O",           "identical"),
    ("stereo",     "CC(N)C(=O)O",         "C[C@H](N)C(=O)O",                 "close"),
    ("isotope",    "CC(C)=O",             "[2H]C([2H])([2H])C(=O)C([2H])([2H])[2H]", "close"),
    ("geometry",   "C(/C=C/C)C",          "C(/C=C\\\\C)C",                     "close"),
    ("different",  "c1ccccc1",            "CCO",                             "different"),
    ("unparseable", "not_a_smiles",       "CCO",                             None),
]


def main() -> int:
    bad = []
    for name, pred, truth, want in CASES:
        got = relate(pred, truth)
        how = got.get("how")
        if how != want:
            bad.append(f"{name}: wanted {want!r}, got {how!r} ({got})")
            continue
        # A branch that fires but attributes nothing is the failure this file exists
        # to catch: "close" with no reason is the isotope bug all over again.
        if how == "close" and not (got.get("stereo") or got.get("iso") or got.get("geom")):
            bad.append(f"{name}: reported 'close' but attributed no cause ({got})")
        print(f"  ok  {name:12s} -> {how or '(no note)'}")

    # And the arithmetic that produced "14 of 7 stereocentres disagree".
    for name, pred, truth, _ in CASES:
        st = (relate(pred, truth) or {}).get("stereo")
        if st and st[0] > st[1]:
            bad.append(f"{name}: impossible ratio {st[0]} of {st[1]}")

    if bad:
        print("\nFAIL")
        for b in bad:
            print("  " + b)
        return 1
    print("\nPASS — every branch fires on the case that must trigger it")
    return 0


if __name__ == "__main__":
    sys.exit(main())
