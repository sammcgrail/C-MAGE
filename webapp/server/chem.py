"""SMILES comparison for the web layer, via the pipeline's own RDKit.

The web process deliberately has no RDKit dependency. canon.py is executed by
the stage-3 interpreter (the one that produced the predictions), and results
are memoised per SMILES string for the life of the process.
"""
from __future__ import annotations

import json
import subprocess
import threading
from pathlib import Path

from . import config

_CANON_SCRIPT = Path(__file__).with_name("canon.py")
_cache: dict[str, dict] = {}
_lock = threading.Lock()


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


def _run(smiles: list[str]) -> list[dict]:
    py = stage3_python()
    empty = [{"canonical": None, "flat": None, "valid": False, "error": "rdkit unavailable"} for _ in smiles]
    if py is None:
        return empty
    try:
        proc = subprocess.run([str(py), str(_CANON_SCRIPT)], input=json.dumps(smiles), capture_output=True,
                              text=True, timeout=300, cwd=str(config.CMAGE_ROOT))
        if proc.returncode != 0:
            return [dict(e, error=proc.stderr[-300:]) for e in empty]
        out = json.loads(proc.stdout)
        if len(out) != len(smiles):
            return empty
        return out
    except Exception as exc:  # noqa: BLE001 - a comparison failure must never take the app down
        return [dict(e, error=str(exc)[:300]) for e in empty]


def verdict(pred: dict, truths: list[dict]) -> tuple[str, int | None]:
    """Compare one canonicalised prediction against candidate truths.

    Returns (verdict, index of the matched truth or None):
      'match'    same molecule, stereochemistry included
      'stereo'   same molecule once stereochemistry is ignored
      'wrong'    a valid molecule that matches none of the candidates
      'invalid'  the prediction is not parseable
    """
    if not pred.get("valid"):
        return "invalid", None
    for i, t in enumerate(truths):
        if t.get("valid") and t["canonical"] == pred["canonical"]:
            return "match", i
    for i, t in enumerate(truths):
        if t.get("valid") and t["flat"] == pred["flat"]:
            return "stereo", i
    return "wrong", None
