"""Build the data behind the benchmark wall: one tile per scored structure.

The page shows every molecule in a continuous scroll, so the payload has to be
small enough to ship whole and the images small enough to decode 1000+ of them.
Two things follow:

  * Tiles are 240 px. The source renders are 1500 px line art; at tile size the
    difference is invisible and the weight is ~40x.
  * Rows carry only what a tile draws plus what its detail sheet needs. The old
    /api/benchmark payload was 618 KB for four runs because it carried every
    scoring intermediate.

PNG, not JPEG: these are black line drawings on white, where JPEG ringing is
both ugly and larger. Quantising to a 32-colour palette after the downscale is
lossless to the eye here and roughly halves the file again.
"""
import csv
import json
import os
import sys
from pathlib import Path

from PIL import Image

TILE = 240
ROOT = Path("/root/C-MAGE/benchmarks")
WALL = ROOT / "wall"
# The corpus WITH every reference SMILES. Not served (only benchmarks/wall/ is mounted at /wall);
# the tools that need truth (sonnet_batch.corpus, novel_set, build_novel, control_set, the dual
# cadence) read this, never a served payload.
CORPUS_ROWS = ROOT / "corpus_rows.json"
# The lanes whose readers run with tools (a shell, Python, network): the Sonnet 5 arm, the
# hand-picked and corpus Sonnet 5.5 lanes, and the renderer-control lane. A reader with a network
# could fetch a served payload, so a reference is SERVED only for an image one of these lanes has
# already read. The API-only arm is not here: it has no tools and cannot fetch anything.
TOOL_LANES = [Path("/root/cmage-work/sonnet/results.jsonl"),
              Path("/root/cmage-work/sonnet-s55/results.jsonl"),
              Path("/root/cmage-work/sonnet-s55c/results.jsonl"),
              Path("/root/cmage-work/sonnet-ctl/results.jsonl")]
# Row fields that carry the reference or something computed from it. "r" is relate(prediction,
# reference): stereocentre and isotope counts against the reference. "ha" is the reference's heavy
# atom count (API tab).
TRUTH_FIELDS = ("t", "r", "ha")
WITHHELD_NOTE = "Withheld until a tool-using Sonnet reader has read this image"


def tool_read_keys() -> set[str]:
    """Corpus keys that a tool-using lane has a published reading of. A results file another run
    appends to can end in a half-written line; that line is skipped, and its key is then simply
    still withheld until the next build."""
    keys: set[str] = set()
    for p in TOOL_LANES:
        if not p.exists():
            continue
        for line in open(p):
            if line.strip():
                try:
                    keys.add(json.loads(line)["k"])
                except (ValueError, KeyError):
                    pass
    return keys


def gate_truth(rows: list[dict], read: set[str]) -> int:
    """RETIRED 9 Oct (Sam): references are served on every row. The protection is the reader
    transcript screen instead (scan_reader_transcript.ANSWER_PATH flags the site, any /wall/ path and
    every payload name), and the jail limits a reader's network to the model API. Kept as a no-op so
    callers need no change; returns 0."""
    return 0
    n = 0
    for r in rows:
        if r["k"] in read:
            continue
        for f in TRUTH_FIELDS:
            r.pop(f, None)
        r["tw"] = 1
        n += 1
    return n


def thumb(src: Path, dst: Path) -> int:
    if dst.exists():
        return dst.stat().st_size
    try:
        im = Image.open(src).convert("RGB")
    except Exception:
        return 0
    im.thumbnail((TILE, TILE), Image.LANCZOS)
    flat = Image.new("RGB", (TILE, TILE), "white")
    flat.paste(im, ((TILE - im.width) // 2, (TILE - im.height) // 2))
    flat.quantize(colors=32, method=Image.MEDIANCUT).save(dst, optimize=True)
    return dst.stat().st_size


def render_pred(smiles: str, dst: Path) -> bool:
    """Draw the molecule the reader actually returned.

    Two SMILES for one molecule routinely look nothing alike -- an aromatic ring
    written lowercase against the same ring written Kekule, opened at a different
    atom. Side by side with the input picture, a drawing settles in one glance
    what comparing two strings cannot."""
    if dst.exists():
        return True
    if not smiles:
        return False
    from rdkit import Chem, RDLogger
    from rdkit.Chem.Draw import rdMolDraw2D
    RDLogger.DisableLog("rdApp.*")
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return False
    d = rdMolDraw2D.MolDraw2DCairo(TILE, TILE)
    o = d.drawOptions()
    o.bondLineWidth = max(1, round(TILE / 150))
    o.padding = 0.06
    try:
        rdMolDraw2D.PrepareAndDrawMolecule(d, mol)
        d.FinishDrawing()
        # Quantise like the input tiles. RDKit writes a full-colour PNG; these are
        # line drawings, so a 32-colour palette is invisible here and roughly
        # thirds the file. That matters because the page PREFETCHES every one of
        # these as its tile appears -- 13 MB of prefetch is a stall, 5 MB is not.
        import io as _io
        Image.open(_io.BytesIO(d.GetDrawingText())).convert("RGB") \
             .quantize(colors=32, method=Image.MEDIANCUT).save(dst, optimize=True)
        return True
    except Exception:
        return False


def relate(pred: str, truth: str) -> dict:
    """State the exact relationship between the two strings, computed, not asserted.

    Two SMILES for one molecule usually look nothing alike, so an EXACT badge over
    two visibly different strings reads like a bug. But the honest note is not the
    same in every case, and the graded ladder's `stereo` rung hides two quite
    different failures behind one word:

      Caffeine      exact -- the two really do canonicalise to one identical string.
      Acetone-D6    graded `stereo`, but no stereocentre is involved. The reference
                    carries six deuteriums and the reader saw three. Calling that
                    "stereochemistry differs" would be false, and calling it
                    "identical" would be false in the reader's favour.

    So the difference is attributed: stereocentres, isotope labels, or both.
    """
    from rdkit import Chem, RDLogger
    RDLogger.DisableLog("rdApp.*")
    if not pred or not truth:
        return {}
    a, b = Chem.MolFromSmiles(pred), Chem.MolFromSmiles(truth)
    if a is None or b is None:
        return {}
    if Chem.MolToSmiles(a) == Chem.MolToSmiles(b):
        return {"how": "identical", "canon": Chem.MolToSmiles(a)}

    def strip(m, stereo=False, iso=False):
        m = Chem.Mol(m)
        if iso:
            # Zeroing the isotope is NOT enough. [2H] is an explicit hydrogen ATOM,
            # so acetone-d6 read as -d3 still differs by three explicit H after the
            # label is cleared, and the isotope branch never fires -- the check
            # passes silently and the note goes missing. Drop the H atoms too.
            for at in m.GetAtoms():
                at.SetIsotope(0)
            try:
                m = Chem.RemoveHs(m)
            except Exception:
                pass
        return Chem.MolToSmiles(m, isomericSmiles=not stereo)

    def iso_count(m):
        return sum(1 for at in m.GetAtoms() if at.GetIsotope())

    

    def centres(m):
        return dict(Chem.FindMolChiralCenters(m, includeUnassigned=True,
                                              useLegacyImplementation=False))

    same_wo_stereo = strip(a, stereo=True) == strip(b, stereo=True)
    same_wo_iso = strip(a, iso=True) == strip(b, iso=True)
    if not (same_wo_stereo or same_wo_iso):
        return {"how": "different"}

    out = {"how": "close", "canon": strip(a, stereo=True, iso=True)}
    ia, ib = iso_count(a), iso_count(b)
    if ia != ib:
        out["iso"] = [ia, ib]
    pa, pb = centres(a), centres(b)
    keys = set(pa) | set(pb)
    d = sum(1 for k in keys if pa.get(k) != pb.get(k))
    if d:
        # Denominator is the UNION, not max(len). One molecule can carry centres
        # the other does not, and max() then reports 14 of 7 -- a number that
        # cannot be true and that nobody would trust the rest of the page after.
        out["stereo"] = [d, len(keys)]

    def bonds(m):
        return {b.GetIdx(): str(b.GetStereo()) for b in m.GetBonds()
                if str(b.GetStereo()) != "STEREONONE"}
    ba, bb = bonds(a), bonds(b)
    nb = sum(1 for k in set(ba) | set(bb) if ba.get(k) != bb.get(k))
    if nb:
        out["geom"] = nb
    if not (out.get("iso") or out.get("stereo") or out.get("geom")):
        out["how"] = "close_other"
    return out


def rows_from(csv_paths: list[Path], image_dirs: list[Path], out_img: Path) -> list[dict]:
    out_img.mkdir(parents=True, exist_ok=True)
    index: dict[str, Path] = {}
    for d in image_dirs:
        for p in d.glob("*.png"):
            index.setdefault(p.name, p)

    rows, missing, bytes_, dupes = [], 0, 0, 0
    seen: set[str] = set()
    for cp in csv_paths:
        if not cp.exists():
            print(f"  MISSING csv {cp}", file=sys.stderr)
            continue
        for r in csv.DictReader(open(cp)):
            fn = r["file_name"]
            src = index.get(fn)
            if src is None:
                missing += 1
                continue
            key = fn.rsplit(".", 1)[0]
            # The scored/ tree holds BOTH per-batch runs and pooled supersets of
            # those same runs, so globbing it counts many compounds twice. 1,710
            # compounds came out as 3,530 rows -- a corpus that looks twice its
            # real size, with every duplicate tile a second opinion on one image
            # (CXMolScribe is not deterministic, so the two need not even agree).
            if key in seen:
                dupes += 1
                continue
            seen.add(key)
            bytes_ += thumb(src, out_img / f"{key}.png")
            pred_dir = out_img.parent / (out_img.name + "_pred")
            pred_dir.mkdir(parents=True, exist_ok=True)
            has_pred = render_pred(r.get("smiles") or "", pred_dir / f"{key}.png")
            conf = r.get("confidence") or ""
            rows.append({
                "k": key,
                "n": r.get("matched_name") or r.get("closest_name") or key,
                "v": r.get("verdict") or "",
                "g": r.get("grade") or "",
                "c": round(float(conf) * 100) if conf else None,
                "s": r.get("smiles") or "",
                "p": 1 if has_pred else 0,
                # Carries a CXSMILES extension block. A property of the OUTPUT, not
                # a verdict, so it is filtered on its own axis rather than mixed
                # into the five scoring states.
                "cx": 1 if "|$" in (r.get("smiles") or "") else 0,
            })
    print(f"  rows {len(rows)}  duplicates dropped {dupes}  no-image {missing}  "
          f"thumbs {bytes_/1e6:.1f} MB")
    assert len(rows) == len(seen), "row count and distinct-key count disagree"
    return rows


def truth_index(manifests: list[Path]) -> dict[str, dict]:
    """group key -> {name, smiles}. Keyed on the manifest's own group name, which
    is also the image stem, so a mismatch shows up as a missing tile rather than
    as a silently wrong 'expected' string."""
    out = {}
    for m in manifests:
        if not m.exists():
            continue
        for g, v in json.load(open(m)).get("groups", {}).items():
            mol = (v.get("molecules") or [{}])[0]
            if mol.get("smiles"):
                out[g] = {"n": mol.get("name") or mol.get("label") or g,
                          "t": mol["smiles"]}
    return out


def build_images() -> dict:
    """Raw-images tab: the best arm, RDKit's own layout at 1500 px, 1210 compounds."""
    print("images tab (arm: corpus_rdkit_1500)")
    # Every batch that has been scored on this arm. Globbed rather than listed,
    # so a new batch appears on the page the moment its scores are published and
    # nobody has to remember to add a line here.
    rows = rows_from(
        sorted(ROOT.glob("scored/*corpus_rdkit_1500/structures.csv")),
        # All FOUR batches. Globbing only three silently dropped 200 rows as
        # "no image" -- a miss that looks exactly like a corpus that is smaller
        # than you thought, which is why the count is printed and checked.
        sorted(Path("/root/cmage-work").glob("cmage-img*/corpus_rdkit_1500")),
        WALL / "img",
    )
    truth = truth_index(sorted(
        ROOT.glob("ground_truth/img_manifest_depictions*.json")))
    hit = 0
    for r in rows:
        t = truth.get(r["k"])
        if t:
            r["t"] = t["t"]
            r["n"] = t["n"]
            rel = relate(r.get("s") or "", t["t"])
            if rel:
                r["r"] = rel
            hit += 1
    print(f"  truth matched {hit}/{len(rows)}")
    if hit != len(rows):
        raise SystemExit(f"FATAL: {len(rows)-hit} rows have no ground truth. A tile "
                         f"with no expected answer is scored against nothing and "
                         f"would show as a grey 'no truth' square indistinguishable "
                         f"from a real one.")
    return {"arm": "RDKit 1500", "rows": rows}


def verdict_breakdown(rows: list[dict]) -> list[dict]:
    """The four scoring outcomes as a stacked bar, in a fixed order.

    Sorted by MEANING, never by size: exact, then right-skeleton, then wrong, then
    unreadable. A bar re-ordered by whichever bucket happens to be largest changes
    shape between builds and stops being comparable with the last one you looked
    at."""
    # THREE POPULATIONS, and they answer different questions. The old vocabulary
    # mixed them, so a document could read "1/2 recovered" beside chips that never
    # said "exact" -- the 1 was a stereo match, and nothing on the page said stereo
    # counted as recovered.
    #
    #   CHECKED    a reference exists, so right or wrong is knowable
    #   NO REFERENCE  the structure was read and nobody catalogued it. NOT wrong.
    #                 This merges two states that were listed separately on a
    #                 technicality -- "not in this document's catalogue" and "this
    #                 document has no catalogue" are the same fact to a reader.
    #   UNREADABLE  nothing usable came out
    order = [("matched", "Matched the reference",
              lambda r: r["v"] == "exact"),
             ("stereo", "Matched, stereochemistry differs",
              lambda r: r["v"] == "stereo"),
             ("misread", "A reference exists and this is not it",
              lambda r: r["v"] in ("misread", "wrong")),
             ("noref", "No reference to check against",
              lambda r: r["v"] in ("unmatched", "no-truth")),
             ("unreadable", "Unreadable — nothing usable produced",
              lambda r: r["v"] == "invalid")]
    out = []
    for key, label, test in order:
        n = sum(1 for r in rows if test(r))
        if n:
            out.append({"key": key, "label": label, "n": n})
    return out


def cx_count(rows: list[dict]) -> int:
    return sum(1 for r in rows if r.get("cx"))


def stats(rows: list[dict], threshold: int = 84) -> dict:
    n = len(rows)
    ex = sum(1 for r in rows if r["v"] == "exact")
    gr = sum(1 for r in rows if r["g"] in ("exact", "stereo", "tautomer", "charge", "salt"))
    hi = [r for r in rows if (r["c"] or 0) >= threshold]
    hix = sum(1 for r in hit_rows(hi) if r["v"] == "exact")
    return {"n": n, "exact": ex, "graded": gr, "high": len(hi), "high_exact": hix,
            "strict_pct": round(ex / n * 100, 1) if n else 0,
            "graded_pct": round(gr / n * 100, 1) if n else 0,
            "high_pct": round(hix / len(hi) * 100, 1) if hi else 0}


def hit_rows(rs):
    return rs


def build_pdfs() -> dict:
    """PDFs tab: the whole pipeline on real documents -- figures out, segments out,
    structures read. Tiles are the SEGMENT crops, i.e. what the reader was actually
    handed after stages 1 and 2, not the page."""
    print("pdfs tab (full pipeline, per-document runs)")
    csv_path = ROOT / "scored/pdfs_all/structures.csv"
    if not csv_path.exists():
        raise SystemExit("no scored corpus run yet -- run tools/score_all_pdfs.py first")
    seg_dirs = sorted(Path("/root/cmage-work/allpdfs/runs").glob("*/out/run_*/02_DIS_Segments"))
    rows = rows_from([csv_path], seg_dirs, WALL / "pdf")

    by_key = {r["k"]: r for r in rows}
    for r in csv.DictReader(open(csv_path)):
        t = by_key.get(r["file_name"].rsplit(".", 1)[0])
        if not t:
            continue
        t["d"] = r["group"]
        t["n"] = r.get("matched_name") or r.get("closest_name") or "unmatched"
        # "Wrong" is a claim, and on this corpus it is usually not supportable.
        # These documents draw ~7x more structures than their ground truth
        # catalogues, so a prediction matching nothing is far more often a real
        # molecule nobody listed than a misreading. Tanimoto to the NEAREST
        # catalogued compound separates the two cases as well as anything can:
        # a near-miss of something catalogued is plausibly a misread; a molecule
        # unlike anything catalogued cannot be called wrong on this evidence.
        if t["v"] == "wrong":
            try:
                tan = float(r.get("closest_tanimoto") or 0)
            except ValueError:
                tan = 0.0
            t["v"] = "misread" if tan >= 0.85 else "unmatched"
            t["tan"] = round(tan, 2)

    # COLLAPSE REPEATS WITHIN A DOCUMENT. A patent redraws the same intermediate in
    # every scheme it appears in, so the pipeline reads it once per scheme and the
    # wall showed it once per scheme too -- 154 tiles for filgotinib's 28 distinct
    # structures. These are NOT pipeline duplicates: the crops differ pixel for
    # pixel and come from different figures. The document really does draw it
    # repeatedly, and the reader really did read it each time.
    #
    # So they are collapsed for DISPLAY, keeping the most confident reading and
    # carrying the count, rather than dropped. 4,484 tiles -> 3,185.
    from rdkit import Chem, RDLogger
    RDLogger.DisableLog("rdApp.*")

    def canon(sm):
        if not sm:
            return None
        m = Chem.MolFromSmiles(sm)
        return Chem.MolToSmiles(m) if m else None

    best: dict = {}
    for r in rows:
        key = (r.get("d"), canon(r.get("s")) or ("!" + r["k"]))
        cur = best.get(key)
        if cur is None or (r.get("c") or 0) > (cur.get("c") or 0):
            if cur is not None:
                r["dup"] = cur.get("dup", 1) + 1
            best[key] = r
        else:
            cur["dup"] = cur.get("dup", 1) + 1
    collapsed = list(best.values())
    print(f"  collapsed repeats within a document: {len(rows)} -> {len(collapsed)} tiles")
    rows = collapsed

    # Per-document recall. The denominator is that document's OWN ground truth,
    # never the corpus total -- summing 138 documents' hits over one global
    # denominator is the classic way to report a number nobody can reproduce.
    #
    # Match on NAME, which is what score_run.py writes into matched_name when it
    # confirms a structure. An earlier version built `expected` from InChIKeys and
    # `found` from names, so the two sets could never intersect and the counts
    # silently drifted apart -- 345 of 663 here against 354 of 697 computed
    # directly. Two computations of one quantity disagreeing is the whole reason
    # to compute it twice.
    truth = json.load(open(ROOT / "ground_truth/pdf_manifest_all.json"))["groups"]
    docs = []
    for g, v in sorted(truth.items()):
        expected = {m["name"] for m in (v.get("molecules") or []) if m.get("name")}
        if not expected:
            continue
        mine = [r for r in rows if r.get("d") == g]
        if not mine:
            continue
        found = {r["n"] for r in mine if r["v"] in ("exact", "stereo")} & expected
        found_exact = {r["n"] for r in mine if r["v"] == "exact"} & expected
        docs.append({"name": g, "expected": len(expected), "found": len(found),
                     "found_exact": len(found_exact)})

    # The 11 documents with no ground truth still RAN and their structures are on
    # the wall; without a row here they are the only tiles you cannot filter to.
    # expected=0 renders an empty bar, which is honest -- there was nothing to
    # recover, not nothing recovered.
    grounded = {d["name"] for d in docs}
    for g in sorted({r["d"] for r in rows if r.get("d")} - grounded):
        # `read`, NOT `found`. `found` means "catalogued compounds recovered" and
        # is summed into the headline; putting a raw structure count in it made the
        # page announce "recovered 1398 of the 697 compounds", 200.6%. Two units in
        # one field, summed without noticing -- the field name was the whole bug.
        docs.append({"name": g, "expected": 0, "found": 0, "nogt": True,
                     "read": sum(1 for r in rows if r.get("d") == g)})
    print(f"  documents with structures {len(docs)}  tiles {len(rows)}")
    return {"arm": "full pipeline", "rows": rows, "docs": docs}


THRESHOLD = 0.8431          # the published confidence cut, not a round number


def _check_rounded(d: dict, path: str = "") -> None:
    """Refuse to publish a percentage with float noise in it.

    13.4790175981434916% reached the page. It is not wrong, it just reads as a
    machine leaking instead of a measurement, and no reviewer will catch every
    one by eye.
    """
    if isinstance(d, dict):
        for k, v in d.items():
            if k in ("pct", "strict_pct", "graded_pct", "high_pct") and isinstance(v, float):
                assert round(v, 1) == v, f"unrounded percentage at {path}.{k}: {v}"
            _check_rounded(v, f"{path}.{k}")
    elif isinstance(d, list):
        for i, v in enumerate(d):
            _check_rounded(v, f"{path}[{i}]")


def write(name: str, d: dict, path: Path | None = None) -> None:
    # Do not clobber stats a caller already set. The PDF tab replaces the
    # accuracy denominator with a recall one on purpose, and an unconditional
    # assignment here silently undid it -- the page then showed 19.2% while the
    # build log printed the number I meant to publish.
    d.setdefault("stats", stats(d["rows"], threshold=round(THRESHOLD * 100)))
    d["threshold"] = round(THRESHOLD * 100)
    sys.path.insert(0, "/root/C-MAGE/tools")
    from wall_arms import build as arms_build
    d["arms"], d["armsNote"] = arms_build(THRESHOLD)
    _check_rounded(d, name)
    path = path or WALL / f"{name}.json"
    tmp = path.with_suffix(".json.tmp")
    json.dump(d, open(tmp, "w"), separators=(",", ":"))
    os.replace(tmp, path)
    print(f"  payload {path.name} {os.path.getsize(path)/1e6:.2f} MB  {json.dumps(d['stats'])}")


if __name__ == "__main__":
    WALL.mkdir(parents=True, exist_ok=True)
    which = sys.argv[1] if len(sys.argv) > 1 else "images"
    if which in ("images", "all"):
        d = build_images()
        s = stats(d["rows"], threshold=round(THRESHOLD * 100))
        d["dir"] = "img"
        d["heroLabel"] = f"of {s['n']} structures exactly right"
        d["breakdown"] = verdict_breakdown(d["rows"])
        d["cx"] = cx_count(d["rows"])
        # Name every grade the graded count admits, from the rows: it counted stereo-only rows
        # (112 of 2,155) under a label that said only "a tautomer or salt".
        gnames = {"stereo": "stereochemistry", "tautomer": "a tautomer", "charge": "a charge",
                  "salt": "a salt form"}
        present = [gnames[g] for g in gnames if any(r["g"] == g for r in d["rows"])]
        glabel = ("Right if " + (", ".join(present[:-1]) + " or " + present[-1] if len(present) > 1
                                 else present[0]) + " may differ") if present else "Right, graded"
        d["bars"] = [
            {"label": glabel, "pct": s["graded_pct"],
             "text": f"{s['graded']} of {s['n']}"},
            {"label": "Right when the model said it was confident", "pct": s["high_pct"],
             "text": f"{s['high_exact']} of {s['high']}", "good": True},
        ]
        d["headline"] = "Input is RDKit's own 1500 px layout, the best of eight — catalogued below."
        d["footer"] = ("Stage 3 only: one already-cropped depiction per image, no figure "
                       "extraction and no segmentation. Scored against PubChem structures "
                       "fetched in the same request batch as the images.")
        # The private copy first, every row with its reference; then the served payload, with
        # the reference only where a tool-using lane has already read the image.
        import copy
        write("corpus_rows", copy.deepcopy(d), CORPUS_ROWS)
        read = tool_read_keys()
        withheld = gate_truth(d["rows"], read)
        if withheld:
            d["withheld"] = {"n": withheld, "note": WITHHELD_NOTE}
        if withheld:
            d["footer"] += (f" Reference SMILES withheld for the {withheld:,} images no tool-using Sonnet reader "
                            f"has read yet; verdicts shown for all.")
        print(f"  reference served for {len(d['rows']) - withheld}, withheld for {withheld}")
        write("images", d)
    if which in ("pdfs", "all"):
        d = build_pdfs()
        s = stats(d["rows"], threshold=round(THRESHOLD * 100))
        d["dir"] = "pdf"
        # Sum ONLY over documents that have ground truth. A document with none
        # contributes to neither numerator nor denominator; it is unscored, not a
        # zero, and averaging it in would understate recall by a silent constant.
        scored_docs = [x for x in d["docs"] if not x.get("nogt")]
        exp = sum(x["expected"] for x in scored_docs)
        fnd = sum(x["found"] for x in scored_docs)
        fex = sum(x["found_exact"] for x in scored_docs)
        assert fex <= fnd <= exp, f"recall over 100%: {fnd} of {exp} — units mixed again"
        # RECALL is the headline here, not accuracy. These documents draw 6x more
        # structures than their ground truth catalogues, so a prediction counted
        # "wrong" is usually a real molecule off the page that nobody listed.
        # Quoting accuracy over all rows would report ~20% for a pipeline that
        # actually recovers half of what was asked for -- a number that is
        # arithmetically true and answers a question no caller asked.
        # EXACT ONLY in the hero, like every other tab. "Recovered" used to count a
        # stereo-only match too, and the page never said so; that figure is the second bar.
        d["stats"] = {"n": exp, "exact": fex,
                      "strict_pct": round(fex / exp * 100, 1) if exp else 0}
        d["heroLabel"] = f"of {exp} catalogued compounds found exactly"
        d["breakdown"] = verdict_breakdown(d["rows"])
        d["cx"] = cx_count(d["rows"])
        checked = sum(x["n"] for x in d["breakdown"]
                      if x["key"] in ("matched", "stereo", "misread"))
        right = sum(x["n"] for x in d["breakdown"] if x["key"] == "matched")
        right_st = sum(x["n"] for x in d["breakdown"] if x["key"] in ("matched", "stereo"))
        pc = lambda a, b: round(a / b * 100, 1) if b else 0
        d["bars"] = [
            {"label": "Found, counting a stereo-only match as found",
             "pct": pc(fnd, exp), "text": f"{fnd} of {exp}", "good": True},
            {"label": "Of the structures that COULD be checked, how many were exactly right",
             "pct": pc(right, checked),
             "text": f"{right} of {checked} ({right_st} counting stereo-only)", "good": True},
        ]
        d["headline"] = (
            f"Whole documents, unedited. Most of what these documents draw was never "
            f"catalogued by anyone, so those structures have no reference to check "
            f"against — they are neither right nor wrong: the slate bar above is "
            f"them.")
        # The corpus as it stands, counted, never typed: the footer said "all 149 committed PDFs,
        # 1,900 pages" for three weeks after 53 of them were removed.
        pdfs = sorted((ROOT / "corpus").glob("*.pdf"))
        pages = 0
        import subprocess
        for f in pdfs:
            out = subprocess.run(["pdfinfo", str(f)], capture_output=True, text=True).stdout
            pages += next((int(l.split()[1]) for l in out.splitlines() if l.startswith("Pages:")), 0)
        with_rows = len({r["d"] for r in d["rows"] if r.get("d")})
        d["footer"] = (f"Stages 1+2+3 on all {len(pdfs)} committed PDFs, {pages:,} pages; "
                       f"{with_rows} of them produced structures. Recall is per document against that "
                       f"document's own ground truth, over the {len(scored_docs)} documents that have one; "
                       f"\"found\" in the headline means the exact structure; the first bar also counts a "
                       f"stereo-only match. Precision over everything drawn is NOT reportable on this corpus "
                       f"and is deliberately not quoted: only {checked:,} of the {len(d['rows']):,} distinct "
                       f"structures read ({pc(checked, len(d['rows']))}%) have a reference to check against.")
        # The 10 Sep cut, said on the tab: the corpus lost its zero-recall documents, which
        # raised recall, and a reader of the page should know that before quoting it.
        cut_p = ROOT / "pdf_corpus_cut.json"
        if cut_p.exists():
            cut = json.load(open(cut_p))
            rm, b = cut["removed"], cut["before"]
            z = sum(1 for x in rm if x["why"] == "zero recall")
            d["heroNotes"] = [
                f"{len(rm)} documents removed from the corpus ({z} with zero recall, {len(rm) - z} non-English; "
                f"commit {cut['commit'][:8]}). With them: exact {b['found_exact']} of {b['expected']} "
                f"({pc(b['found_exact'], b['expected'])}%), stereo-inclusive {b['found']} of {b['expected']} "
                f"({pc(b['found'], b['expected'])}%)."]
        write("pdfs", d)
    if which in ("sonnet", "all"):
        # Sonnet's payload quotes the corpus size, so it MUST be rebuilt whenever
        # the corpus grows. Chaining it here means `build_wall.py all` cannot
        # leave one tab claiming 1,710 while the other says 2,510 -- there is no
        # separate step anybody has to remember.
        import subprocess
        r = subprocess.run(["/root/C-MAGE/.venv-ms/bin/python",
                            "/root/C-MAGE/tools/build_sonnet.py"],
                           capture_output=True, text=True)
        print(r.stdout.rstrip() or r.stderr[-300:])
