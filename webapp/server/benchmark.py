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

EVERY PREDICTION IS SCORED TWICE, and both numbers are reported:

  verdict       the WHOLE predicted SMILES string, which is what a caller gets
                if it pastes the output straight into a database
  frag_verdict  the LARGEST FRAGMENT of it, which is what the recogniser
                actually achieved when it appended phantom disconnected atoms

On a real corpus the two differ enormously -- 14% against 66% on the 97-image
set shipped here -- because the model routinely recovers the molecule and then
hangs unbonded `I` or `[HH]` off it. Publishing either number alone misleads:
the strict one says the tool is useless, the fragment one hides that its raw
output is unusable without a post-process. So the tally carries both, the
confidence cross-tab is broken out under both, and the per-structure record
keeps the fragment count and the discarded fragments themselves.

A run directory may also carry:

    run.json       {"title","corpus","corpus_detail","stages","method",
                    "settings","note","source"} -- what this run was measured
                    on. Displayed with the numbers; a headline accuracy with no
                    corpus attached is not a fact anyone can use.
    verdicts.json  verdicts from an offline scorer. These are NOT trusted in
                   place of recomputation: they are cross-checked against it and
                   the disagreement count is reported.
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
            for sub in list(results.SUBDIRS.values()) + ["03_CXMS_Results", "verdicts.json", "run.json"]:
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


_META_KEYS = ("title", "corpus", "corpus_key", "corpus_detail", "stages", "method", "settings",
              "note", "source", "seconds", "hardware", "rank",
              # A run may declare that a precision figure would not mean anything on
              # its corpus. Partial ground truth is the usual reason: a document that
              # draws 40 compounds and names 5 of them makes every one of the other 35
              # emitted structures score "wrong" regardless of how well it was read, so
              # the percentage measures the manifest's coverage, not the pipeline.
              # precision_reportable: "no" suppresses the number and shows
              # precision_note in its place. Recall is unaffected -- its denominator is
              # the molecules known to be drawn, which is exactly what is known.
              "precision_reportable", "precision_note")

# Sampling facts a manifest may record about the population it was drawn from.
# They are what turns "97 images" into a claim someone can check: how many exist,
# how many were eligible, how they were picked, how many were verified.
_CORPUS_STATS = ("images_dir_file_count", "population_size", "step", "offset", "sample_size",
                 "pubchem_verified", "files_with_empty_smiles", "files_without_key", "generated", "method")


def _run_meta(run: Path) -> dict:
    """Optional run.json beside the stage directories: what corpus this run is
    over, which stages produced it, and any standing caveat. Every headline
    number on this tab is meaningless without the corpus it was measured on,
    so the corpus travels with the run rather than living in page copy."""
    try:
        data = json.loads((run / "run.json").read_text())
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {k: str(data[k]) for k in _META_KEYS if data.get(k)}


def _load_manifests() -> tuple[list[dict], dict]:
    """-> (documents, meta). Each document: {stem, file, title, molecules:[{key,label,smiles}]}."""
    docs: list[dict] = []
    meta: dict = {"names": [], "descriptions": [], "files": [], "corpora": {}}
    for path in manifest_paths():
        try:
            data = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        if not isinstance(data, dict):
            continue
        n_docs = (len(data["groups"]) if isinstance(data.get("groups"), dict)
                  else len(data.get("pdfs") or []))
        if not n_docs:
            # A file under ground_truth/ that names no documents is a provenance or
            # selection record, not a manifest. Listing it as a corpus put an empty
            # "0 groups, 0 molecules" row on the page, which reads as a corpus the
            # pipeline scored nothing on rather than as a file that is not ground truth.
            continue
        meta["files"].append(path.name)
        key = str(data.get("corpus") or path.stem)
        stats = {k: data[k] for k in _CORPUS_STATS if k in data}
        stats["manifest"] = path.name
        stats["groups"] = len(data["groups"]) if isinstance(data.get("groups"), dict) else len(data.get("pdfs") or [])
        stats["molecules"] = sum(len(g.get("molecules") or [])
                                 for g in (data["groups"].values() if isinstance(data.get("groups"), dict)
                                           else (data.get("pdfs") or [])))
        if data.get("excluded"):
            # A sentence, or a list of names. list("a sentence") is 10 single
            # characters and renders as garbage, so a string is wrapped, not iterated.
            stats["excluded"] = ([data["excluded"]] if isinstance(data["excluded"], str)
                                 else list(data["excluded"]))
        if data.get("pubchem_unverified_files"):
            stats["unverified"] = list(data["pubchem_unverified_files"])
        meta["corpora"][key] = stats
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
                    docs.append(_doc(Path(p["file"]).stem, p["file"], p.get("title"), p.get("molecules") or [],
                                     p.get("drawing_style") or p.get("style")))
        if isinstance(data.get("groups"), dict):
            for stem, g in data["groups"].items():
                if isinstance(g, dict):
                    docs.append(_doc(str(stem), g.get("source") or str(stem), g.get("title"),
                                     g.get("molecules") or [], g.get("drawing_style") or g.get("style")))
    # Later manifests override earlier ones for the same stem.
    by_stem: dict[str, dict] = {}
    for d in docs:
        by_stem[d["stem"]] = d
    return list(by_stem.values()), meta


def _doc(stem: str, file: str, title, molecules, style=None) -> dict:
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
    # The drawing style is the whole point of a deliberately diverse corpus: a
    # per-document score means little without knowing whether that document is
    # ChemDraw vector, a 1980 fax-quality scan, or pen on paper.
    return {"stem": stem, "file": file, "title": title or stem, "molecules": mols,
            "style": str(style) if style else ""}


# THE FOUR SCORINGS, in the order the page shows them. Each is one comparison of
# the same prediction against the same reference; the only thing that changes is
# which representation of the prediction is compared.
#
#   *C1=CC=CC=C1 |$OMe;;;;;;$|          the drawing said "OMe", not O-CH3
#
# A CXSMILES abbreviation is a `*` dummy atom whose label rides in the `|$...$|`
# extension block. It is a faithful transcription of what the chemist drew, and
# comparing it against a spelled-out reference is comparing two different
# representations of the same molecule -- a comparison that can only fail. So the
# abbreviations are expanded at COMPARISON time, using the vocabulary the model
# was trained against, and `raw` is kept beside it to show what the naive
# comparison would have reported. On the 11-document corpus the two differ by a
# factor of two, and the difference is entirely representation.
RUNGS = ("raw", "raw_largest", "expanded", "expanded_largest")

# The ladder the page shows, as a CUMULATIVE chain: each row adds one post-process
# to the row above it, so a row's delta is what that post-process is worth. Note
# what is NOT in the chain: `raw_largest`. Fragment stripping and abbreviation
# expansion are INDEPENDENT post-processes, and threading all four comparisons into
# one chain produced a negative delta on the corpora where stripping does the work
# -- a ladder that appears to lose molecules at the step which in fact gains them.
# `raw_largest` is reported beside the chain as the control that isolates stripping
# on its own.
LADDER = ("raw", "expanded", "expanded_largest")
CONTROL = "raw_largest"

# Human labels, and what each rung adds to the one before. The page renders these
# rather than carrying its own copy, so a row cannot be captioned with a scoring it
# was not computed under -- which is exactly the mistake that shipped once already,
# a largest-fragment caption over a number that stereochemistry had moved.
RUNG_LABEL = {
    "raw": "CXSMILES exactly as predicted, against the spelled-out reference",
    "raw_largest": "the same, largest fragment only",
    "expanded": "abbreviations expanded to the groups they name",
    "expanded_largest": "abbreviations expanded AND largest fragment only",
}


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
        "corpus_path": config.CORPUS_PATH,
        "corpus_url": config.CORPUS_URL,
        # Has the CXSMILES expander passed its stereo gate? Every expanded figure
        # depends on it. A broken expander does not raise -- it reports a plausibly
        # LOWER accuracy, indistinguishable from the pipeline being worse than it
        # is -- so the answer is asked for and a false answer withholds the figures.
        "expander": chem.expander_status(),
        "generated": time.time(),
        "corpora": meta["corpora"],
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
            per_doc[d["stem"]] = {"file": d["file"], "title": d["title"], "style": d["style"],
                                  "molecules": [{k: m.get(k) for k in ("key", "label", "smiles", "canonical", "valid")}
                                                for m in truth_by_stem[d["stem"]]],
                                  "structures": [],
                                  # One recovered-molecule set per scoring, plus the
                                  # subset recovered with stereochemistry REQUIRED.
                                  # Kept per document because the denominator is per
                                  # document: summing 11 documents against the corpus
                                  # total is how 9 of 34 becomes 9 of 374.
                                  "keys": {m: [] for m in RUNGS}, "exact_keys": [],
                                  "matched_keys": [], "frag_matched_keys": []}
        unassigned = []
        disagreements = 0
        for s, pred in zip(structs, preds):
            stem = _doc_for(s["source"], stems)
            # Both scorings, always, from the same RDKit canonicalisation:
            #   verdict       the whole predicted string, as a caller would paste it
            #   frag_verdict  the largest fragment alone, dropping phantom atoms
            # Reporting only one of these is the difference between "14% works"
            # and "66% works", so the record carries both and so does the UI.
            rec = dict(s, pred_canonical=pred.get("exp_canonical"), pred_largest=pred.get("exp_largest"),
                       raw_canonical=pred.get("canonical"),
                       fragments=pred.get("fragments") or 0, phantom=chem.phantom_summary(pred),
                       # The lossless form, and what it means. MolToSmiles drops the
                       # |$...$| block, so storing `canonical` alone destroyed the
                       # abbreviation with no warning; both are kept and both shown.
                       cxsmiles=pred.get("cxsmiles") or s["smiles"],
                       expanded=pred.get("expanded"),
                       abbreviations=pred.get("abbreviations") or [],
                       markush=pred.get("markush") or [],
                       missing=pred.get("missing") or [],
                       failed=pred.get("failed") or [])
            if stem is None:
                rec.update(verdict="unassigned", frag_verdict="unassigned", raw_verdict="unassigned",
                           raw_frag_verdict="unassigned", matched_key=None, truth_smiles=None)
                unassigned.append(rec)
                continue
            truths = truth_by_stem[stem]
            # All four scorings, from the one RDKit canonicalisation. Each is
            # recorded separately: letting a later rung fill in an earlier rung's
            # matched key would move a headline number with nothing saying so.
            hits = {}
            for mode in RUNGS:
                v, idx = chem.verdict(pred, truths, mode=mode)
                hits[mode] = (v, truths[idx] if idx is not None else None)
            v, strict_truth = hits["expanded"]
            fv, frag_truth = hits["expanded_largest"]
            shown = strict_truth or frag_truth or hits["raw"][1]
            rec.update(verdict=v, frag_verdict=fv,
                       raw_verdict=hits["raw"][0], raw_frag_verdict=hits["raw_largest"][0],
                       matched_key=strict_truth["key"] if strict_truth else None,
                       frag_matched_key=frag_truth["key"] if frag_truth else None,
                       truth_smiles=shown["smiles"] if shown else None)
            for mode in RUNGS:
                mv, mt = hits[mode]
                if mt is not None and mt["key"] not in per_doc[stem]["keys"][mode]:
                    per_doc[stem]["keys"][mode].append(mt["key"])
                # Stereochemistry REQUIRED, on the headline scoring. Tracked because
                # "18 of 34" reads as exact, and if any of it were only stereo-relaxed
                # the page would have to say so.
                if mode == "expanded" and mv == "match" and mt is not None \
                        and mt["key"] not in per_doc[stem]["exact_keys"]:
                    per_doc[stem]["exact_keys"].append(mt["key"])
            pre = (precomputed or {}).get(s.get("segment_image") or "")
            if pre:
                # A verdicts.json written by the offline scorer. It is used for the
                # extras it carries (nearest miss + Tanimoto), and its verdict is
                # CHECKED against the one just recomputed rather than trusted: a
                # silent disagreement between the two would otherwise be invisible.
                mk = pre.get("matched_key")
                pt = next((t for t in truths if mk and mk in (t["key"], t["label"])), None)
                if pre["verdict"] != v:
                    disagreements += 1
                rec.update(closest_key=pre.get("closest_key"), closest_tanimoto=pre.get("closest_tanimoto"))
                if pt is not None and rec["truth_smiles"] is None:
                    rec["truth_smiles"] = pt["smiles"]
            if rec["truth_smiles"] is None and len(truths) == 1:
                # One drawn molecule in the group: the answer it was scored against
                # is unambiguous even when the prediction misses it entirely.
                rec["truth_smiles"] = truths[0]["smiles"]
            for field, bucket in (("matched_key", "matched_keys"), ("frag_matched_key", "frag_matched_keys")):
                if rec[field] and rec[field] not in per_doc[stem][bucket]:
                    per_doc[stem][bucket].append(rec[field])
            per_doc[stem]["structures"].append(rec)

        blank = lambda: {"n": 0, "match": 0, "stereo": 0, "wrong": 0, "invalid": 0,  # noqa: E731
                         "frag_match": 0, "frag_stereo": 0, "frag_wrong": 0, "frag_invalid": 0}
        tally = {"structures": len(structs), "match": 0, "stereo": 0, "wrong": 0, "invalid": 0,
                 "frag_match": 0, "frag_stereo": 0, "frag_wrong": 0, "frag_invalid": 0,
                 "unassigned": len(unassigned), "high": 0, "high_wrong": 0, "low": 0, "low_right": 0,
                 "expected": 0, "found": 0, "frag_found": 0, "documents": 0,
                 "phantom": 0, "rescued": 0, "phantom_atoms": 0,
                 # Molecules recovered under each of the four scorings, and the
                 # subset of the headline one that is exact rather than
                 # stereo-relaxed. These are the ladder the page renders.
                 "rung_found": {m: 0 for m in RUNGS}, "exact_found": 0,
                 # Predictions carrying a CXSMILES abbreviation, and what became of
                 # it. `abbrev_expanded` + `abbrev_markush` + `abbrev_missing` need
                 # not sum to `abbrev`: one prediction can carry both an expandable
                 # label and an unexpandable one, so it is counted in more than one.
                 "abbrev": 0, "abbrev_expanded": 0, "abbrev_markush": 0, "abbrev_missing": 0,
                 "abbrev_failed": 0, "abbrev_rescued": 0,
                 "abbrev_labels": {}, "markush_labels": {}, "missing_labels": {},
                 "crosstab": {"high": blank(), "low": blank()},
                 # Confidence of the answers that turned out RIGHT vs WRONG, scored
                 # on the largest fragment. If these two ranges overlap, the score
                 # cannot be used to tell one from the other, and saying so with the
                 # run's own numbers beats asserting it in prose.
                 "conf_right": [], "conf_wrong": []}
        blocks = []
        for stem in stems:
            block = per_doc[stem]
            block["matched_keys"] = list(block["keys"]["expanded"])
            block["frag_matched_keys"] = list(block["keys"]["expanded_largest"])
            block["rung_found"] = {m: len(block["keys"][m]) for m in RUNGS}
            block["found"] = block["rung_found"]["expanded"]
            block["frag_found"] = block["rung_found"]["expanded_largest"]
            block["raw_found"] = block["rung_found"]["raw"]
            block["exact_found"] = len(block["exact_keys"])
            block["expected"] = len(block["molecules"])
            block["missing"] = [m for m in block["molecules"] if m["key"] not in block["matched_keys"]]
            # Documents the run never touched are left out rather than shown as all-missing.
            if not block["structures"] and not any(s["source"].startswith(stem) for s in structs):
                continue
            blocks.append(block)
            tally["documents"] += 1
            tally["expected"] += block["expected"]
            tally["found"] += block["found"]
            tally["frag_found"] += block["frag_found"]
            tally["exact_found"] += block["exact_found"]
            for mode in RUNGS:
                tally["rung_found"][mode] += block["rung_found"][mode]
            block["abbrev"] = sum(1 for r in block["structures"] if r.get("abbreviations"))
            # Per document, because "most of what this document emitted is a Markush
            # skeleton" is a statement about THAT document's ground truth, and the
            # corpus-wide figure cannot make it.
            block["markush"] = sum(1 for r in block["structures"] if r.get("markush"))
            block["missing"] = sum(1 for r in block["structures"] if r.get("missing"))
            for rec in block["structures"]:
                if rec.get("abbreviations"):
                    tally["abbrev"] += 1
                    if rec.get("markush"):
                        tally["abbrev_markush"] += 1
                    if rec.get("missing"):
                        tally["abbrev_missing"] += 1
                    if rec.get("failed"):
                        tally["abbrev_failed"] += 1
                    if not rec.get("markush") and not rec.get("missing") and not rec.get("failed"):
                        tally["abbrev_expanded"] += 1
                    # Expansion turned this prediction from not-a-match into a match.
                    # The whole case for expanding rests on this count, so it is
                    # counted rather than argued.
                    if rec["verdict"] in ("match", "stereo") and rec["raw_verdict"] not in ("match", "stereo"):
                        tally["abbrev_rescued"] += 1
                    # Counted once per STRUCTURE, not once per occurrence: one
                    # pathological prediction repeated a single label 45 times, which
                    # would otherwise top the vocabulary list.
                    for bucket, labels in (("abbrev_labels", rec["abbreviations"]),
                                           ("markush_labels", rec.get("markush") or []),
                                           ("missing_labels", rec.get("missing") or [])):
                        for lab in set(labels):
                            if any(c.isalpha() for c in lab):
                                tally[bucket][lab] = tally[bucket].get(lab, 0) + 1
                tier = "high" if rec["tier"] == "high" else "low"
                cell = tally["crosstab"][tier]
                cell["n"] += 1
                tally[rec["verdict"]] = tally.get(rec["verdict"], 0) + 1
                cell[rec["verdict"]] = cell.get(rec["verdict"], 0) + 1
                tally["frag_" + rec["frag_verdict"]] = tally.get("frag_" + rec["frag_verdict"], 0) + 1
                cell["frag_" + rec["frag_verdict"]] = cell.get("frag_" + rec["frag_verdict"], 0) + 1
                right = rec["verdict"] in ("match", "stereo")
                if rec["confidence"] is not None:
                    key = "conf_right" if rec["frag_verdict"] in ("match", "stereo") else "conf_wrong"
                    tally[key].append(round(float(rec["confidence"]), 4))
                if rec["fragments"] > 1:
                    tally["phantom"] += 1
                    tally["phantom_atoms"] += rec["fragments"] - 1
                    # RESCUED BY THE FRAGMENT STRIP, measured against the rung
                    # immediately below it -- expanded-whole, not raw. Comparing it
                    # against raw would credit fragment stripping with everything
                    # expansion did, which is how the third row of this ladder came
                    # to be captioned "+ largest fragment" over a number that
                    # stereochemistry had moved.
                    if rec["frag_verdict"] in ("match", "stereo") and not right:
                        tally["rescued"] += 1
                if tier == "high":
                    tally["high"] += 1
                    if not right:
                        tally["high_wrong"] += 1
                else:
                    tally["low"] += 1
                    if right:
                        tally["low_right"] += 1
        for bucket in ("abbrev_labels", "markush_labels", "missing_labels"):
            tally[bucket] = sorted(tally[bucket].items(), key=lambda kv: (-kv[1], kv[0]))[:14]
        for key in ("conf_right", "conf_wrong"):
            vals = tally.pop(key)
            tally[key] = {"n": len(vals), "min": min(vals), "max": max(vals),
                          "mean": round(sum(vals) / len(vals), 4)} if vals else None
        try:
            mtime = max((run / sub).stat().st_mtime for sub in results.SUBDIRS.values() if (run / sub).exists())
        except ValueError:
            mtime = run.stat().st_mtime
        out["runs"].append({
            "id": rid, "name": str(run.relative_to(config.BENCHMARK_DIR)), "mtime": mtime,
            "tally": tally, "pdfs": blocks, "unassigned": unassigned,
            # The scoring ladder: one row per comparison, each row's caption bound to
            # the value it was computed from. `delta` is what this rung added to the
            # one above it, so a rung that changes nothing says so instead of being
            # read as the reason for the total.
            "ladder": [{"mode": m, "label": RUNG_LABEL[m], "expected": tally["expected"],
                        "found": tally["rung_found"][m],
                        "delta": tally["rung_found"][m] - (tally["rung_found"][LADDER[i - 1]] if i else 0)}
                       for i, m in enumerate(LADDER)],
            "control": {"mode": CONTROL, "label": RUNG_LABEL[CONTROL], "expected": tally["expected"],
                        "found": tally["rung_found"][CONTROL],
                        "delta": tally["rung_found"][CONTROL] - tally["rung_found"]["raw"]},
            "meta": _run_meta(run),
            # Verdicts are ALWAYS recomputed here. A verdicts.json, when present,
            # is cross-checked against them; a non-zero disagreement count is a
            # defect worth surfacing, not something to average away.
            "verdict_source": "rdkit",
            "cross_checked": bool(precomputed),
            "cross_check_disagreements": disagreements,
            "has_crops": bool(parsed["counts"]["segments"]),
        })
        out["_runs"].append({"id": rid, "_path": str(run)})
    # Explicit rank first, newest last. Ordering by mtime alone put whichever run
    # happened to be copied most recently in front, and the run that lands first is
    # the one most readers will take as "the" result -- which for a deliberately
    # hard 24-image subset would be badly misleading.
    out["runs"].sort(key=lambda r: (int(r["meta"].get("rank") or 99), -r["mtime"]))
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
        entries = [s for key in ("pdfs", "groups", "documents", "images") for p in (data.get(key) or [])
                   if isinstance(p, dict) for s in p.get("structures", [])]
    synonyms = {"exact": "match", "match": "match", "stereo": "stereo", "wrong": "wrong", "invalid": "invalid"}
    for s in entries or []:
        if isinstance(s, dict) and s.get("segment_image") and s.get("verdict") in synonyms:
            table[s["segment_image"]] = dict(s, verdict=synonyms[s["verdict"]])
    return table or None
