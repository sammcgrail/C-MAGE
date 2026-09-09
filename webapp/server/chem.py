"""SMILES comparison for the web layer, via the pipeline's own RDKit.

The web process deliberately has no RDKit dependency. canon.py is executed by
the stage-3 interpreter (the one that produced the predictions), and results
are memoised per SMILES string for the life of the process.

Comparison happens on FOUR key pairs, not one, and which pair a number came from
has to travel with the number:

  raw               the CXSMILES exactly as predicted
  raw_largest       the same, largest fragment only
  expanded          abbreviations substituted for the groups they name
  expanded_largest  both

`expanded` is the one that means what a reader thinks an accuracy means, and
`raw` is the one a naive harness computes. On this pipeline they differ by a
factor of two, because CXMolScribe preserves `OMe` as a labelled dummy atom and a
reference SMILES spells it out -- so the raw comparison is between two different
representations of the same molecule and can only fail. Keeping all four means the
page can show WHICH step moved a number rather than asserting it.
"""
from __future__ import annotations

import json
import os
import subprocess
import threading
from pathlib import Path

from . import config

_CANON_SCRIPT = Path(__file__).with_name("canon.py")
_cache: dict[str, dict] = {}
_lock = threading.Lock()
_expander: dict | None = None

# Which canonical forms each comparison uses. The ladder the benchmark tab renders
# is exactly this dict, in this order, so a row cannot be labelled with a scoring
# it was not computed under.
KEYS = {
    "raw": ("canonical", "flat"),
    "raw_largest": ("largest", "largest_flat"),
    "expanded": ("exp_canonical", "exp_flat"),
    "expanded_largest": ("exp_largest", "exp_largest_flat"),
}


def stage3_python() -> Path | None:
    for root in (config.CMAGE_ROOT / ".venvs" / "cmage-cxmolscribe", config.CMAGE_ROOT / ".venv-ms"):
        py = root / "bin" / "python"
        if py.exists():
            return py
    return None


def canonicalize(smiles: list[str]) -> list[dict]:
    """[{'canonical','flat','valid'}] aligned with the input; never raises."""
    todo = []
    with _lock:
        for s in smiles:
            if s not in _cache and s not in todo:
                todo.append(s)
    if todo:
        fresh = _run(todo)
        with _lock:
            for s, rec in zip(todo, fresh):
                _cache[s] = rec
    with _lock:
        return [dict(_cache.get(s) or {"canonical": None, "flat": None, "valid": False}) for s in smiles]


def _env() -> dict:
    """Environment for the stage-3 subprocess.

    CMAGE_CXSMILES_DIR tells canon.py where the ONE expander lives. It is imported
    rather than reimplemented: the stereo-preserving join is subtle enough that two
    copies means two chances to have it wrong, with no way to tell from a number
    which copy produced it.
    """
    return {**os.environ, "CMAGE_CXSMILES_DIR": str(config.BENCHMARK_DIR)}


def expander_status() -> dict:
    """Has the CXSMILES expander passed its stereo gate? Cached for the process.

    Every expanded figure on the benchmark tab depends on this being true, and an
    expander that emits the wrong stereoisomer does not raise -- it reports a
    plausibly lower accuracy, which is indistinguishable from the pipeline being
    worse. So the answer is asked for, and a False answer withholds the figures
    instead of publishing them.
    """
    global _expander
    with _lock:
        if _expander is not None:
            return _expander
    py = stage3_python()
    if py is None:
        res = {"ok": False, "reason": "the stage-3 interpreter is not present, so no "
                                      "expansion or comparison can be done at all", "cases": []}
    else:
        try:
            proc = subprocess.run([str(py), str(_CANON_SCRIPT), "--selftest"], capture_output=True,
                                  text=True, timeout=300, cwd=str(config.CMAGE_ROOT), env=_env())
            res = json.loads(proc.stdout)
            if not isinstance(res, dict):
                raise ValueError("selftest did not return an object")
        except Exception as exc:  # noqa: BLE001 - a gate that errors is a gate that is CLOSED
            res = {"ok": False, "cases": [],
                   "reason": f"the expander's stereo gate did not run ({str(exc)[:200]}), so nothing "
                             f"vouches for the expansion"}
    with _lock:
        _expander = res
    return res


def _run(smiles: list[str]) -> list[dict]:
    py = stage3_python()
    empty = [{"canonical": None, "flat": None, "valid": False, "error": "rdkit unavailable"} for _ in smiles]
    if py is None:
        return empty
    try:
        proc = subprocess.run([str(py), str(_CANON_SCRIPT)], input=json.dumps(smiles), capture_output=True,
                              text=True, timeout=300, cwd=str(config.CMAGE_ROOT), env=_env())
        if proc.returncode != 0:
            return [dict(e, error=proc.stderr[-300:]) for e in empty]
        out = json.loads(proc.stdout)
        if len(out) != len(smiles):
            return empty
        return out
    except Exception as exc:  # noqa: BLE001 - a comparison failure must never take the app down
        return [dict(e, error=str(exc)[:300]) for e in empty]


def verdict(pred: dict, truths: list[dict], *, mode: str = "expanded") -> tuple[str, int | None]:
    """Compare one canonicalised prediction against candidate truths.

    Returns (verdict, index of the matched truth or None):
      'match'    same molecule, stereochemistry included
      'stereo'   same molecule once stereochemistry is ignored
      'wrong'    a valid molecule that matches none of the candidates
      'invalid'  the prediction is not parseable

    `mode` names one of KEYS. 'raw' scores the CXSMILES exactly as predicted --
    what a naive harness computes, and what a caller gets if it pastes the string
    straight out. 'expanded' substitutes the abbreviations the drawing used, which
    is the only comparison that can succeed against a spelled-out reference. The
    '_largest' variants drop the phantom disconnected atoms the recogniser
    sometimes appends to a correct core. No mode is an honest summary on its own,
    so all four are computed and every figure says which one it came from.

    Ground truth is always compared whole and unexpanded: a truth SMILES with a
    real counter-ion is not a phantom, and a reference is already spelled out.
    """
    ck, fk = KEYS[mode]
    if not pred.get("valid") or pred.get(ck) is None:
        return "invalid", None
    for i, t in enumerate(truths):
        if t.get("valid") and t["canonical"] == pred[ck]:
            return "match", i
    for i, t in enumerate(truths):
        if t.get("valid") and t["flat"] == pred[fk]:
            return "stereo", i
    return "wrong", None


def phantom_summary(pred: dict) -> str:
    """'3 x I, 2 x [HH]' -- the fragments a largest-fragment score discards."""
    items = sorted((pred.get("phantom") or {}).items(), key=lambda kv: (-kv[1], kv[0]))
    return ", ".join(f"{n} x {s}" if n > 1 else s for s, n in items)
