#!/usr/bin/env python3
"""Attachment-point normalisation for the "Attachment-point fragments (wavy bond)" section.

The truth writes every open valence as a bare `*`. A reader may legitimately write the same thing as `[*]`, `*`,
`[1*]` / `[2*]` (isotope-numbered), `[*:1]` (atom-mapped), `R`, `R1`, `[R]`, `[R1]` or `[R']`. Unnormalised,
sonnet_batch.verdict() scores `[*]` and `*` exact, but `[1*]` as "stereo" (it drops isotopes only in its stereo-free
pass), `[*:1]` as wrong, and `R` / `[R]` as invalid SMILES. All of those deflate a correct reading.

norm(smiles) -> SMILES or None:
  1. text: `[R]`, `[R12]`, `[R']`, `[R1']` -> `[*]`; a bare `R`/`R12` outside brackets -> `*` (digits after a bare R
     are read as the label, as a chemist writes R1; a ring-closure digit right after R is therefore not supported).
     Bracketed elements starting with R ([Rb] [Re] [Rf] [Rg] [Rh] [Rn] [Ru] [Ra]) are never touched; bare `Rb`, `Rn`
     etc. are not valid SMILES anyway, so a bare R is always the attachment (`Rn1ccnc1` = R on an aromatic n).
  2. RDKit: every atom with atomic number 0 loses its isotope, atom-map number and query/label.
It never adds, removes or moves an attachment and never changes a real atom, so the count and position of `*` still
have to match the truth exactly: it cannot inflate a score. Both the prediction and the truth go through it, and the
result is scored with the unchanged verdict()."""
import re
from rdkit import Chem, RDLogger
RDLogger.DisableLog("rdApp.*")

_BR = re.compile(r"\[R\d*'*\]")


def _text(s: str) -> str:
    s = _BR.sub("[*]", s)
    out, depth = [], 0          # bare R only outside brackets
    i = 0
    while i < len(s):
        c = s[i]
        if c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
        if depth == 0 and c == "R":
            j = i + 1
            while j < len(s) and s[j].isdigit():
                j += 1
            out.append("*")
            i = j
            continue
        out.append(c)
        i += 1
    return "".join(out)


_LINE = re.compile(r"^[ \t]*(\*\*)?[ \t]*SMILES[ \t]*(\*\*)?[ \t]*:[ \t]*(.*?)[ \t]*$", re.M)


def parse_answer(text):
    """The last `SMILES:` line's value, WITHOUT eating attachment stars. api_reader.parse_smiles tolerates markdown
    bold by stripping every `*` around the value (`:\\s*\\**` and a trailing `\\**`), which deletes a leading or
    trailing attachment point: "SMILES: *C1CC2(C1)CCN(*)CC2" came back as "C1CC2(C1)CCN(*)CC2". Here only markdown
    is removed: a `**` that closes a bold label (`**SMILES:** x`), a `**x**` wrapper, backticks and <smiles> tags."""
    ms = _LINE.findall(text or "")
    if not ms:
        return None
    open_b, close_b, v = ms[-1]
    v = v.strip()
    if open_b and not close_b and v.startswith("**"):          # **SMILES:** value
        v = v[2:].strip()
    if len(v) > 4 and v.startswith("**") and v.endswith("**") and " " not in v[2:-2]:   # **value**
        v = v[2:-2]
    v = v.strip("`").strip()
    t = re.match(r"^<smiles>(.*)</smiles>$", v, re.I)
    if t:
        v = t.group(1)
    return v.split()[0] if v else None


def norm(smiles):
    if not smiles:
        return None
    m = Chem.MolFromSmiles(_text(smiles.strip()))
    if m is None:
        return None
    for a in m.GetAtoms():
        if a.GetAtomicNum() == 0:
            a.SetIsotope(0)
            a.SetAtomMapNum(0)
            for p in ("molAtomMapNumber", "dummyLabel", "_MolFileRLabel", "atomLabel"):
                if a.HasProp(p):
                    a.ClearProp(p)
    return Chem.MolToSmiles(m)


def selftest():
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from sonnet_batch import verdict
    t = norm("*C1(CF)CC1")
    ok = {"[*]C1(CF)CC1": "exact", "FCC1(*)CC1": "exact", "[1*]C1(CF)CC1": "exact", "[*:1]C1(CF)CC1": "exact",
          "RC1(CF)CC1": "exact", "[R]C1(CF)CC1": "exact", "[R1]C1(CF)CC1": "exact", "R1C1(CF)CC1": "exact",
          "CC1(CF)CC1": "wrong", "C1(CF)CC1": "wrong", "*C1(CCl)CC1": "wrong", "**C1(CF)CC1": "wrong",
          "[Rb]C1(CF)CC1": "wrong", "[Ru]": "wrong"}
    bad = []
    for p, want in ok.items():
        got = verdict(norm(p) or "", t)
        if got != want:
            bad.append((p, want, got))
    two = norm("*c1ccc(*)cc1")
    for p in ("[1*]c1ccc([2*])cc1", "Rc1ccc(R)cc1", "[*:1]c1ccc([*:2])cc1"):
        if verdict(norm(p), two) != "exact":
            bad.append((p, "exact", verdict(norm(p), two)))
    if verdict(norm("*c1ccccc1"), two) != "wrong":
        bad.append(("one attachment vs two", "wrong", verdict(norm("*c1ccccc1"), two)))
    for txt, want in (("SMILES: *C1CC2(C1)CCN(*)CC2", "*C1CC2(C1)CCN(*)CC2"), ("**SMILES:** *OC1CC1", "*OC1CC1"),
                      ("SMILES: **CCO**", "CCO"), ("**SMILES**: `*C(=O)CCl`", "*C(=O)CCl"),
                      ("x\nSMILES: CC\nSMILES: *CC*", "*CC*"), ("SMILES: <smiles>*CC</smiles>", "*CC")):
        if parse_answer(txt) != want:
            bad.append(("parse", txt, want, parse_answer(txt)))
    print("SELFTEST", "PASS" if not bad else f"FAIL {bad}")
    return not bad


if __name__ == "__main__":
    raise SystemExit(0 if selftest() else 1)
