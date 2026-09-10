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
        dst.write_bytes(d.GetDrawingText())
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

    rows, missing, bytes_ = [], 0, 0
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
            })
    print(f"  rows {len(rows)}  no-image {missing}  thumbs {bytes_/1e6:.1f} MB")
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
    rows = rows_from(
        [ROOT / "scored/pooled1010_corpus_rdkit_1500/structures.csv",
         ROOT / "scored/batch7_corpus_rdkit_1500/structures.csv"],
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
        if t:
            t["d"] = r["group"]
            t["n"] = r.get("matched_name") or r.get("closest_name") or "unmatched"

    # Per-document recall. The denominator is that document's OWN ground truth,
    # never the corpus total -- summing 138 documents' hits over one global
    # denominator is the classic way to report a number nobody can reproduce.
    truth = json.load(open(ROOT / "ground_truth/pdf_manifest_all.json"))["groups"]
    docs = []
    for g, v in sorted(truth.items()):
        expected = {m["inchikey"] for m in (v.get("molecules") or []) if m.get("inchikey")}
        if not expected:
            continue
        got = {r["n"] for r in rows if r.get("d") == g and r["v"] in ("exact", "stereo")}
        docs.append({"name": g, "expected": len(expected), "found": len(got)})
    docs = [d for d in docs if any(r.get("d") == d["name"] for r in rows)]
    print(f"  documents with structures {len(docs)}  tiles {len(rows)}")
    return {"arm": "full pipeline", "rows": rows, "docs": docs}


THRESHOLD = 0.8431          # the published confidence cut, not a round number


def write(name: str, d: dict) -> None:
    d["stats"] = stats(d["rows"], threshold=round(THRESHOLD * 100))
    d["threshold"] = round(THRESHOLD * 100)
    sys.path.insert(0, "/root/C-MAGE/tools")
    from wall_arms import build as arms_build
    d["arms"], d["armsNote"] = arms_build(THRESHOLD)
    json.dump(d, open(WALL / f"{name}.json", "w"), separators=(",", ":"))
    print(f"  payload {os.path.getsize(WALL / (name + '.json'))/1e6:.2f} MB  {json.dumps(d['stats'])}")


if __name__ == "__main__":
    WALL.mkdir(parents=True, exist_ok=True)
    which = sys.argv[1] if len(sys.argv) > 1 else "images"
    if which in ("images", "all"):
        d = build_images()
        s = stats(d["rows"], threshold=round(THRESHOLD * 100))
        d["dir"] = "img"
        d["headline"] = (
            f"{s['graded_pct']}% right if a tautomer or salt may differ. "
            f"Of the {s['high']} the model marked high-confidence, {s['high_pct']}% are exact. "
            f"Input is RDKit's own 1500 px layout — the best of eight ways of drawing "
            f"the same molecules, catalogued below.")
        d["footer"] = ("Stage 3 only: one already-cropped depiction per image, no figure "
                       "extraction and no segmentation. Scored against PubChem structures "
                       "fetched in the same request batch as the images.")
        write("images", d)
    if which in ("pdfs", "all"):
        d = build_pdfs()
        s = stats(d["rows"], threshold=round(THRESHOLD * 100))
        d["dir"] = "pdf"
        exp = sum(x["expected"] for x in d["docs"])
        fnd = sum(x["found"] for x in d["docs"])
        d["headline"] = (
            f"Whole documents, unedited: figures found, structures cut out, then read. "
            f"{s['graded_pct']}% right if a tautomer or salt may differ. Across "
            f"{len(d['docs'])} documents the pipeline recovered {fnd} of the {exp} "
            f"compounds their ground truth catalogues.")
        d["footer"] = ("Stages 1+2+3 on the committed PDF corpus. Recall is per document "
                       "against that document's own ground truth. A patent draws far more "
                       "than it catalogues, so a tile with no expected answer is a real "
                       "structure that was read, not an error.")
        write("pdfs", d)
