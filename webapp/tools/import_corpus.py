#!/usr/bin/env python3
"""Adopt a MULTI-document benchmark run into the gallery, one entry per document.

`import_run.py` adopts one run as one gallery entry, which is right for a run over
one document. A benchmark run over a corpus holds several documents in the same
three folders, told apart only by the stem embedded in every file name, and
importing it whole would produce a single entry titled after nothing in
particular, with every document's figures shuffled together. This splits it back
out: one gallery entry per document, each carrying that document's own figures,
crops, spreadsheet rows and ground truth.

    webapp/tools/import_corpus.py --run benchmarks/published_runs/<x>/run \\
        --manifest benchmarks/ground_truth/<grouped>.json --data /path/to/data

  --run       a run directory (01_VH_Figures / 02_DIS_Segments / 03_CXMS_Results)
  --manifest  a GROUPED manifest: {"groups": {<stem>: {source, pages,
              drawing_style, molecules: [...]}}}. It supplies the document
              metadata and the answers the verdicts are computed against.
  --data      the server's data directory (else $CMAGE_DATA / the built-in default)
  --replace   delete existing imported entries with the same file name first;
              without it a second run of this tool duplicates the gallery
  --private   import them unlisted
  --dry-run   print what would be imported and write nothing

WHY THE VERDICTS ARE COMPUTED HERE, PER DOCUMENT

Every prediction is compared with RDKit canonical SMILES against **the molecules
of its own document**, never against the corpus as a whole. Scoring a
single-document run against a whole-corpus manifest is the mistake that turns a
recall of 9 out of 34 into 9 out of 374: each document's denominator silently
becomes the corpus total. The same comparison the Benchmark tab performs is
performed here, from the same run and the same manifest, so a card in the gallery
and a row on the Benchmark tab cannot disagree.

Each structure gains, on top of what import_run.py stores:

    cxsmiles      the LOSSLESS prediction: the CXSMILES with its `|$...$|`
                  abbreviation block intact. `Chem.MolToSmiles` drops that block,
                  so storing the plain SMILES destroyed the abbreviation silently.
    expanded      the same molecule with each abbreviation replaced by the group it
                  names, so it can be pasted into any toolkit
    abbreviations the labels the drawing used: OMe, Ph, Boc, CHO
    markush       labels denoting no single molecule (R1, X, OR2) -- unexpandable
                  by anyone, and not a recognition failure
    missing       labels denoting a definite group absent from MolScribe's
                  vocabulary (OTBS, OTHP) -- a closable coverage gap
    verdict       match | stereo | wrong | invalid, on the EXPANDED string
    raw_verdict   the same comparison WITHOUT expanding, i.e. what a naive harness
                  would have reported for this card
    frag_verdict  expanded, largest fragment only
    matched       the label of the molecule it matched, when it matched one
    truth_smiles  what it was compared against, where that is unambiguous

WHY BOTH `verdict` AND `raw_verdict` ARE STORED. A card showing only the expanded
verdict hides the finding; a card showing only the raw one repeats the bug. Where
the two differ the card can say "this scored wrong until its abbreviations were
expanded, and here is the pair" -- which is the most instructive thing on the site,
because it shows what the model said and what it meant, side by side.
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import benchmark, chem, config, results  # noqa: E402


def short_style(style: str, limit: int = 48) -> str:
    """A chip-sized label out of a paragraph-sized drawing-style description.

    Cut at the widest separator that fits, in order, rather than truncating: a
    hard slice lands mid-word ("EPO B1 hybrid: vector Arial text with 15 inline ")
    and, worse, mid-parenthesis ("(pen on paper"), which reads as a broken string
    rather than a label.
    """
    text = " ".join((style or "").split())
    for sep in (";", ":", ",", "("):
        if len(text) <= limit:
            break
        head = text.split(sep)[0].strip()
        if head:
            text = head
    if text.count("(") != text.count(")"):
        text = text.split("(")[0].strip()
    if len(text) > limit:
        cut = text[:limit].rsplit(" ", 1)[0]
        text = cut or text[:limit]
    return text.rstrip(" ,;:-")


def load_groups(manifest: Path) -> dict:
    data = json.loads(manifest.read_text())
    groups = data.get("groups")
    if not isinstance(groups, dict) or not groups:
        sys.exit(f"{manifest} has no 'groups' object; this tool needs a grouped manifest")
    return groups


def note_for(stem: str, group: dict, mols: list[dict], counts: dict, found: int, raw_found: int,
             stats: dict, corpus_dir: str) -> str:
    """The caveat shown above this document's results. Every figure in it comes from
    the counts just computed; none of it is prose written here and left to go stale."""
    names = ", ".join(m["label"] for m in mols)
    style = (group.get("drawing_style") or "").strip()
    bits = []
    if style:
        bits.append("Drawing style — " + style.rstrip(".") + ".")
    bits.append(
        f"Ground truth for this document: {len(mols)} molecule{'' if len(mols) == 1 else 's'}"
        + (f" ({names})" if names else "")
        + f". The pipeline emitted {counts['structures']} structures from {counts['figures']} figures, and "
          f"{found} of the {len(mols)} were recovered exactly. Recall here is counted against THIS document's "
          f"molecules, never against the whole corpus.")
    if stats["abbrev"]:
        bits.append(
            f"{stats['abbrev']} of the {counts['structures']} predictions carry a CXSMILES abbreviation: the "
            f"drawing said OMe or Ph or Boc, and the reader kept that label rather than guessing an expansion "
            f"\u2014 which is more information than expanding it would have been, not less. Every card below "
            f"shows the prediction as CXSMILES beside the same molecule with its abbreviations expanded, and "
            f"names the labels. That expansion is what makes a comparison against a spelled-out reference "
            f"possible at all.")
    if found > raw_found:
        bits.append(
            f"Expanding them is worth {found - raw_found} of this document's {found} recovered "
            f"molecule{'' if found == 1 else 's'}: comparing the raw CXSMILES against the reference recovers "
            f"only {raw_found}. The pipeline had read them correctly all along.")
    if stats["markush"] or stats["missing"]:
        parts = []
        if stats["markush"]:
            parts.append(f"{stats['markush']} carry a Markush variable (R1, X, OR2), which denotes no single "
                         f"molecule and cannot be expanded by anyone")
        if stats["missing"]:
            parts.append(f"{stats['missing']} carry a group that is real but absent from MolScribe's "
                         f"vocabulary, such as OTBS or a phosphate ester, which is a closable coverage gap")
        bits.append("Two kinds of label stay unexpanded here, and they are not the same finding: "
                    + "; and ".join(parts) + ".")
    bits.append(
        f"The PDF behind this is committed at {corpus_dir}/{group.get('source') or stem + '.pdf'} with a "
        f"SHA-256 checksum, so the whole run can be reproduced. The corpus-level numbers are on the "
        f"Benchmark tab.")
    return " ".join(bits)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", required=True, type=Path)
    ap.add_argument("--manifest", required=True, type=Path)
    ap.add_argument("--data", type=Path)
    ap.add_argument("--label", default="", help="extra chip on every entry; the drawing style is added anyway")
    ap.add_argument("--corpus-dir", default="benchmarks/corpus")
    ap.add_argument("--replace", action="store_true")
    ap.add_argument("--private", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if args.data:
        config.DATA_DIR = args.data.resolve()
        config.JOBS_DIR = config.DATA_DIR / "jobs"
        config.INDEX_FILE = config.DATA_DIR / "runs.json"

    run = args.run.resolve()
    res_dir = run / "03_CXMS_Results"
    if not res_dir.is_dir():
        sys.exit(f"not a run directory (no 03_CXMS_Results): {run}")
    groups = load_groups(args.manifest)
    parsed = results.parse_run(run)
    if not parsed["structures"]:
        sys.exit(f"{run} parsed to 0 structures; nothing to import")

    # One RDKit round trip for the whole run, predictions and truths together.
    stems = list(groups)
    preds = chem.canonicalize([s["smiles"] for s in parsed["structures"]])
    truth_by_stem: dict[str, list[dict]] = {}
    flat = [(stem, m) for stem in stems for m in (groups[stem].get("molecules") or [])]
    canon = chem.canonicalize([str(m.get("smiles") or "") for _, m in flat])
    for (stem, m), c in zip(flat, canon):
        truth_by_stem.setdefault(stem, []).append(
            {"key": str(m.get("name") or m.get("key") or m.get("index")),
             "label": str(m.get("label") or m.get("name") or m.get("index")),
             "smiles": str(m.get("smiles") or ""), **c})
    if not any(t.get("valid") for v in truth_by_stem.values() for t in v):
        sys.exit("not one ground-truth SMILES parsed; RDKit is unavailable or the manifest is wrong. "
                 "Refusing to import cards whose every verdict would read 'invalid'.")

    by_stem: dict[str, list[dict]] = {}
    for s, pred in zip(parsed["structures"], preds):
        stem = benchmark._doc_for(s["source"], stems)
        if stem is None:
            continue
        truths = truth_by_stem.get(stem) or []
        v, idx = chem.verdict(pred, truths, mode="expanded")
        fv, fidx = chem.verdict(pred, truths, mode="expanded_largest")
        rv, ridx = chem.verdict(pred, truths, mode="raw")
        shown = next((truths[i] for i in (idx, fidx, ridx) if i is not None), None)
        if shown is None and len(truths) == 1:
            shown = truths[0]
        by_stem.setdefault(stem, []).append(dict(
            s, verdict=v, frag_verdict=fv, raw_verdict=rv,
            matched=truths[idx]["label"] if idx is not None else None,
            truth_smiles=shown["smiles"] if shown else None,
            # The lossless prediction AND what it means, both stored. Keeping only
            # the plain SMILES is what destroyed the abbreviations on the upload path.
            cxsmiles=pred.get("cxsmiles") or s["smiles"],
            expanded=pred.get("expanded"),
            abbreviations=pred.get("abbreviations") or [],
            markush=pred.get("markush") or [],
            missing=pred.get("missing") or [],
            failed=pred.get("failed") or []))

    if not by_stem:
        sys.exit("no structure in the run could be attributed to a document in the manifest; "
                 "the manifest stems and the run's file names do not match")

    existing = {}
    if config.JOBS_DIR.is_dir():
        for jd in config.JOBS_DIR.iterdir():
            rec = jd / "job.json"
            if rec.is_file():
                try:
                    d = json.loads(rec.read_text())
                except ValueError:
                    continue
                if d.get("origin") == "import":
                    existing.setdefault(d.get("filename"), []).append(jd)

    imported = 0
    for stem in stems:
        rows = by_stem.get(stem)
        if not rows:
            continue
        group = groups[stem]
        filename = group.get("source") or f"{stem}.pdf"
        mols = truth_by_stem.get(stem) or []
        found = len({r["matched"] for r in rows if r["matched"]})
        # What the naive comparison would have recovered on this document, so the
        # card can state what expansion was worth instead of asserting it.
        raw_found = len({r["matched"] for r in rows
                         if r["matched"] and r["raw_verdict"] in ("match", "stereo")})
        stats = {"abbrev": sum(1 for r in rows if r["abbreviations"]),
                 "markush": sum(1 for r in rows if r["markush"]),
                 "missing": sum(1 for r in rows if r["missing"])}
        # Every figure stage 1 extracted for this document, not only the ones that
        # yielded a structure: "42 structures from 8 figures" would understate how
        # much of the document was looked at, and the figures with nothing in them
        # are part of what the run did.
        figures = sorted(f for f in parsed["figures"] if benchmark._doc_for(Path(f).stem, stems) == stem)
        counts = {"figures": len(figures), "segments": sum(1 for r in rows if r["segment_image"]),
                  "structures": len(rows), "high": sum(1 for r in rows if r["tier"] == "high"),
                  "low": sum(1 for r in rows if r["tier"] != "high"),
                  "invalid": sum(1 for r in rows if not r["valid"])}
        label = args.label or short_style(group.get("drawing_style") or "") or stem

        if args.dry_run:
            print(f"{filename}: {counts['structures']} structures, {counts['figures']} figures, "
                  f"{found}/{len(mols)} recovered ({raw_found} without expanding), "
                  f"{stats['abbrev']} with an abbreviation, label {label!r}")
            imported += 1
            continue

        for jd in existing.get(filename, []):
            if not args.replace:
                sys.exit(f"{filename} is already in the gallery at {jd.name}; pass --replace to rebuild it "
                         f"(without it this tool would add a duplicate entry)")
            shutil.rmtree(jd)

        job_id = secrets.token_urlsafe(9)
        job_dir = config.JOBS_DIR / job_id
        run_dir = job_dir / "out" / "run_import"
        for sub in results.SUBDIRS.values():
            (run_dir / sub).mkdir(parents=True, exist_ok=True)
        for name in (results.HC_XLSX, results.LC_XLSX):
            src = res_dir / "per_document" / f"{stem}_{name}"
            if not src.is_file():
                src = res_dir / name          # single-document run: the workbook is the document's
            if src.is_file():
                shutil.copy2(src, run_dir / "03_CXMS_Results" / name)
        newest = 0.0
        for r in rows:
            for kind, name in (("segment", r["segment_image"]), (r["tier"], r["rendered_image"])):
                if not name:
                    continue
                src = run / results.SUBDIRS[kind] / name
                if src.is_file():
                    shutil.copy2(src, run_dir / results.SUBDIRS[kind] / name)
                    newest = max(newest, src.stat().st_mtime)
        for name in figures:
            src = run / results.SUBDIRS["figure"] / name
            if src.is_file():
                shutil.copy2(src, run_dir / results.SUBDIRS["figure"] / name)

        record = {
            "id": job_id, "kind": "pdf", "filename": filename, "size": 0,
            "pages": int(group.get("pages") or 1), "created": newest or time.time(), "origin": "import",
            "status": "done", "stage": 3, "stage_started": None, "started": newest or time.time(),
            "finished": newest or time.time(), "error": None, "client": "", "label": label,
            "run_dir": str(run_dir.relative_to(job_dir)),
            # The structures carry the verdicts computed above; the counts are recounted
            # from the same rows rather than taken from the whole-run parse.
            "results": {"structures": rows, "figures": figures, "counts": counts},
            "note": note_for(stem, group, mols, counts, found, raw_found, stats, args.corpus_dir),
            "public": not args.private, "sample": False, "token": secrets.token_urlsafe(16),
        }
        tmp = job_dir / "job.json.tmp"
        tmp.write_text(json.dumps(record, indent=1, sort_keys=True))
        os.replace(tmp, job_dir / "job.json")
        print(f"imported {job_id}: {filename} — {counts['structures']} structures "
              f"({counts['high']} high, {counts['low']} low), {counts['figures']} figures, "
              f"{found}/{len(mols)} recovered ({raw_found} unexpanded), "
              f"{stats['abbrev']} abbreviated, {'listed' if record['public'] else 'unlisted'}")
        imported += 1

    if not imported:
        sys.exit("nothing was imported")
    print(f"{imported} document{'' if imported == 1 else 's'}"
          + (" (dry run, nothing written)" if args.dry_run else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
