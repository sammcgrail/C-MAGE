"""The benchmark tab: pipeline runs over a corpus whose answers are known.

Layout expected under CMAGE_BENCHMARK_DIR (default <repo>/benchmarks):

    <benchmark dir>/**/                 any directory holding a standard pipeline
                                        run (01_VH_Figures / 02_DIS_Segments /
                                        03_CXMS_Results) is one benchmark run
    manifest(s)                         CMAGE_BENCHMARK_MANIFEST, or by default
                                        <dir>/manifest.json + <dir>/ground_truth/*.json

Two manifest shapes are understood. The simple one:

    {"name": "...", "description": "...",
     "pdfs": [{"file": "test_common_drugs_1.pdf", "title": "Common drugs (set 1)",
               "molecules": [{"key": "aspirin", "label": "Aspirin",
                              "smiles": "CC(=O)OC1=CC=CC=C1C(=O)O"}]}]}

and the grouped one, keyed by the document stem the pipeline embeds in every
figure and segment file name:

    {"corpus": "pdfs",
     "groups": {"test_common_drugs_1": {"source": "test_common_drugs_1.pdf",
                "molecules": [{"index": 0, "label": "Aspirin", "name": "Aspirin",
                               "smiles": "..."}]}}}

Structures are attributed to a document by the longest group stem that
prefixes their figure name (`test_common_drugs_1_image_2` ->
`test_common_drugs_1`), and every prediction is compared against that
document's molecules with RDKit canonical SMILES, once with stereochemistry
and once without. A prediction the pipeline scored "high confidence" that is
still the wrong molecule is the thing this tab exists to make visible.

Optionally a run directory may carry a verdicts.json written by whatever
produced it; if present and well-formed it is used as-is instead of recomputing.
"""
from __future__ import annotations

import hashlib
import json
import threading
import time
from pathlib import Path

from . import chem, config, results

_lock = threading.Lock()
_state: dict = {"signature": None, "data": None, "runs": {}}


def manifest_paths() -> list[Path]:
    if config.BENCHMARK_MANIFESTS:
        return [p for p in config.BENCHMARK_MANIFESTS if p.is_file()]
    found = []
    if (config.BENCHMARK_DIR / "manifest.json").is_file():
        found.append(config.BENCHMARK_DIR / "manifest.json")
    gt = config.BENCHMARK_DIR / "ground_truth"
    if gt.is_dir():
        found += sorted(p for p in gt.glob("*.json") if p.is_file())
    return found


def _signature() -> str:
    parts = [str(config.BENCHMARK_DIR)]
    for p in manifest_paths() + _find_runs():
        try:
            st = p.stat()
            parts.append(f"{p}:{st.st_mtime_ns}:{st.st_size}")
        except OSError:
            parts.append(f"{p}:missing")
        if p.is_dir():
            for sub in list(results.SUBDIRS.values()) + ["03_CXMS_Results", "verdicts.json"]:
                try:
                    parts.append(f"{p / sub}:{(p / sub).stat().st_mtime_ns}")
                except OSError:
                    pass
    return hashlib.sha1("|".join(parts).encode()).hexdigest()


def _find_runs() -> list[Path]:
    """Runs to show. CMAGE_BENCHMARK_RUNS (comma-separated, relative to the
    benchmark dir) wins; otherwise the conventional results/pdf_corpus/run if it
    exists; otherwise every run directory found under the benchmark dir."""
    root = config.BENCHMARK_DIR
    if not root.is_dir():
        return []
    if config.BENCHMARK_RUNS:
        return [root / r for r in config.BENCHMARK_RUNS if (root / r / "03_CXMS_Results").is_dir()]
    conventional = root / "results" / "pdf_corpus" / "run"
    if (conventional / "03_CXMS_Results").is_dir():
        return [conventional]
    found = []
    for p in sorted(root.rglob("03_CXMS_Results")):
        if p.is_dir() and len(p.relative_to(root).parts) <= 6:
            found.append(p.parent)
    return found


def _run_id(run: Path) -> str:
    return hashlib.sha1(str(run.relative_to(config.BENCHMARK_DIR)).encode()).hexdigest()[:10]


def _load_manifests() -> tuple[list[dict], dict]:
    """-> (documents, meta). Each document: {stem, file, title, molecules:[{key,label,smiles}]}."""
    docs: list[dict] = []
    meta = {"names": [], "descriptions": [], "files": []}
    for path in manifest_paths():
        try:
            data = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        if not isinstance(data, dict):
            continue
        meta["files"].append(path.name)
        if data.get("name"):
            meta["names"].append(str(data["name"]))
        if data.get("description"):
            meta["descriptions"].append(str(data["description"]))
        elif data.get("corpus") or data.get("method"):
            meta["descriptions"].append(
                f"{path.name}: corpus '{data.get('corpus', '?')}'" + (f" — {data['method']}" if data.get("method") else ""))
        if isinstance(data.get("pdfs"), list):
            for p in data["pdfs"]:
                if isinstance(p, dict) and p.get("file"):
                    docs.append(_doc(Path(p["file"]).stem, p["file"], p.get("title"), p.get("molecules") or []))
        if isinstance(data.get("groups"), dict):
            for stem, g in data["groups"].items():
                if isinstance(g, dict):
                    docs.append(_doc(str(stem), g.get("source") or str(stem), g.get("title"), g.get("molecules") or []))
    # Later manifests override earlier ones for the same stem.
    by_stem: dict[str, dict] = {}
    for d in docs:
        by_stem[d["stem"]] = d
    return list(by_stem.values()), meta


def _doc(stem: str, file: str, title, molecules) -> dict:
    mols = []
    for i, m in enumerate(molecules):
        if not isinstance(m, dict):
            continue
        smiles = m.get("smiles") or m.get("isomeric_smiles") or m.get("canonical_smiles") or ""
        keys = m.get("corpus_keys") if isinstance(m.get("corpus_keys"), list) else []
        # The compound name is the key a scorer is most likely to use; corpus
        # keys and positional fallbacks come after it.
        key = m.get("key") or m.get("name") or (keys[0] if keys else None) or f"{stem}:{m.get('index', i)}"
        label = m.get("label") or m.get("name") or m.get("title") or str(key)
        mols.append({"key": str(key), "label": str(label), "smiles": str(smiles)})
    return {"stem": stem, "file": file, "title": title or stem, "molecules": mols}


def _doc_for(source: str, stems: list[str]) -> str | None:
    """Longest document stem that prefixes the figure's source name."""
    best = None
    for stem in stems:
        if source == stem or source.startswith(stem + "_") or source.startswith(stem):
            if best is None or len(stem) > len(best):
                best = stem
    return best


def build() -> dict:
    """Assemble the tab. Cached until anything under the benchmark dir changes."""
    sig = _signature()
    with _lock:
        if _state["signature"] == sig and _state["data"] is not None:
            return _state["data"]
    data = _build()
    with _lock:
        _state["signature"], _state["data"] = sig, data
        _state["runs"] = {r["id"]: Path(r["_path"]) for r in data["_runs"]}
    return data


def run_path(run_id: str) -> Path | None:
    with _lock:
        return _state["runs"].get(run_id)


def _build() -> dict:
    docs, meta = _load_manifests()
    runs = _find_runs()
    out = {
        "available": bool(runs) and bool(docs),
        "manifest_found": bool(docs),
        "manifests": meta["files"],
        "runs_found": len(runs),
        "name": meta["names"][0] if meta["names"] else "Known-answer corpus",
        "description": " · ".join(meta["descriptions"]),
        "threshold": config.CONFIDENCE_THRESHOLD,
        "generated": time.time(),
        "runs": [],
        "_runs": [],
    }
    if not runs or not docs:
        return out

    stems = [d["stem"] for d in docs]
    truth_smiles = [m["smiles"] for d in docs for m in d["molecules"]]
    truth_canon = chem.canonicalize(truth_smiles)
    truth_by_stem: dict[str, list[dict]] = {}
    i = 0
    for d in docs:
        mols = []
        for m in d["molecules"]:
            mols.append({**m, **truth_canon[i]})
            i += 1
        truth_by_stem[d["stem"]] = mols

    for run in runs:
        rid = _run_id(run)
        parsed = results.parse_run(run)
        structs = parsed["structures"]
        preds = chem.canonicalize([s["smiles"] for s in structs])
        precomputed = None
        for verdicts_file in (run / "verdicts.json", run.parent / "scored" / "verdicts.json"):
            if verdicts_file.is_file():
                precomputed = _load_verdicts(verdicts_file)
                if precomputed:
                    break

        per_doc: dict[str, dict] = {}
        for d in docs:
            per_doc[d["stem"]] = {"file": d["file"], "title": d["title"],
                                  "molecules": [{k: m.get(k) for k in ("key", "label", "smiles", "canonical", "valid")}
                                                for m in truth_by_stem[d["stem"]]],
                                  "structures": [], "matched_keys": []}
        unassigned = []
        for s, pred in zip(structs, preds):
            stem = _doc_for(s["source"], stems)
            rec = dict(s, pred_canonical=pred.get("canonical"))
            if stem is None:
                rec.update(verdict="unassigned", matched_key=None, truth_smiles=None)
                unassigned.append(rec)
                continue
            pre = (precomputed or {}).get(s.get("segment_image") or "")
            if pre:
                mk = pre.get("matched_key")
                truth = next((t for t in truth_by_stem[stem] if mk and mk in (t["key"], t["label"])), None)
                rec.update(verdict=pre["verdict"], matched_key=truth["key"] if truth else mk,
                           truth_smiles=pre.get("truth_smiles") or (truth["smiles"] if truth else None),
                           closest_key=pre.get("closest_key"), closest_tanimoto=pre.get("closest_tanimoto"))
            else:
                v, idx = chem.verdict(pred, truth_by_stem[stem])
                truth = truth_by_stem[stem][idx] if idx is not None else None
                rec.update(verdict=v, matched_key=truth["key"] if truth else None,
                           truth_smiles=truth["smiles"] if truth else None)
            if rec["matched_key"] and rec["matched_key"] not in per_doc[stem]["matched_keys"]:
                per_doc[stem]["matched_keys"].append(rec["matched_key"])
            per_doc[stem]["structures"].append(rec)

        tally = {"structures": len(structs), "match": 0, "stereo": 0, "wrong": 0, "invalid": 0,
                 "unassigned": len(unassigned), "high": 0, "high_wrong": 0, "low": 0, "low_right": 0,
                 "expected": 0, "found": 0, "documents": 0}
        blocks = []
        for stem in stems:
            block = per_doc[stem]
            block["found"] = len(block["matched_keys"])
            block["expected"] = len(block["molecules"])
            block["missing"] = [m for m in block["molecules"] if m["key"] not in block["matched_keys"]]
            # Documents the run never touched are left out rather than shown as all-missing.
            if not block["structures"] and not any(s["source"].startswith(stem) for s in structs):
                continue
            blocks.append(block)
            tally["documents"] += 1
            tally["expected"] += block["expected"]
            tally["found"] += block["found"]
            for rec in block["structures"]:
                tally[rec["verdict"]] = tally.get(rec["verdict"], 0) + 1
                right = rec["verdict"] in ("match", "stereo")
                if rec["tier"] == "high":
                    tally["high"] += 1
                    if not right:
                        tally["high_wrong"] += 1
                else:
                    tally["low"] += 1
                    if right:
                        tally["low_right"] += 1
        try:
            mtime = max((run / sub).stat().st_mtime for sub in results.SUBDIRS.values() if (run / sub).exists())
        except ValueError:
            mtime = run.stat().st_mtime
        out["runs"].append({
            "id": rid, "name": str(run.relative_to(config.BENCHMARK_DIR)), "mtime": mtime,
            "tally": tally, "pdfs": blocks, "unassigned": unassigned,
            "verdict_source": "precomputed" if precomputed else "rdkit",
            "has_crops": bool(parsed["counts"]["segments"]),
        })
        out["_runs"].append({"id": rid, "_path": str(run)})
    out["runs"].sort(key=lambda r: r["mtime"], reverse=True)
    return out


def _load_verdicts(path: Path) -> dict | None:
    """verdicts.json -> {segment_image: {verdict, matched_key, truth_smiles}}."""
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return None
    table = {}
    entries = data.get("structures") if isinstance(data, dict) else None
    if entries is None and isinstance(data, dict):
        entries = [s for key in ("pdfs", "groups", "documents") for p in (data.get(key) or [])
                   if isinstance(p, dict) for s in p.get("structures", [])]
    synonyms = {"exact": "match", "match": "match", "stereo": "stereo", "wrong": "wrong", "invalid": "invalid"}
    for s in entries or []:
        if isinstance(s, dict) and s.get("segment_image") and s.get("verdict") in synonyms:
            table[s["segment_image"]] = dict(s, verdict=synonyms[s["verdict"]])
    return table or None
