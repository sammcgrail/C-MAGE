#!/usr/bin/env python3
"""RENDERER CONTROL SET: corpus molecules drawn by a DIFFERENT renderer than the corpus.

The corpus images are RDKit 2025.03.3 MolDraw2DCairo renders at 1500 px (render_rdkit in the
cmage-img*/build_corpus*.py builders). A reader that holds RDKit can re-draw a candidate SMILES and
pixel-match it against a corpus image, an oracle no real-world drawing offers. This set draws the
same molecules with EPAM Indigo (its own 2D layout, its own renderer), so the score on it measures
reading, not matching, and pairs one-to-one with the same molecules' corpus readings.

    control_set.py build [--json F] [--img-dir D] [--built ISO]    select, render, verify, write
    control_set.py check [--json F]                                re-verify every image on disk
    control_set.py runset --out F                                  the api_reader_set.py input
    control_set.py score --ledger-dir D                            control vs corpus, paired

SELECTION. Eligible = corpus keys (benchmarks/corpus_rows.json) that have BOTH an ok Sonnet 5.5
API-only reading (published_runs/sonnet55_api/ledger.jsonl, its first API_ROWS lines) AND a Sonnet
5.5 jailed-lane reading (/root/cmage-work/sonnet-s55c/results.jsonl, its first S55C_ROWS lines). The
s55c file is append-only, so its prefix pins the eligible set however much the lane grows; the API
ledger already holds every corpus key (its 50 prompt-v1 rows were re-read and replaced in place on
9 Oct, which changed no key and so no selection). The sorted
eligible keys are shuffled with random.Random(SEED); keys are taken in that order until N pass
rendering and verification. No past verdict is looked at.

RENDERING. Indigo 1.46 + indigo.renderer, one fresh Indigo() per molecule: loadMolecule(truth),
dearomatize() (rings drawn Kekule), layout() (Indigo's own 2D coordinates; wedges/hashes are the
stereo marks Indigo assigns for that layout), PNG 1500 x 1500, white background, bond length 100 px
(Indigo shrinks a molecule that does not fit, labels with it), relative line thickness 1.5, Indigo's
default label style (implicit H shown on heteroatoms and terminal carbons, black, no atom colours).
render-stereo-style "none" so no "Chiral"/abs/and/or text is printed; stereo is shown only by
wedges, hashes and double-bond geometry.

VERIFICATION, per image (a failure skips the key and the next one in the seeded order is taken):
  - the molfile Indigo laid out (2D coordinates + its wedge bonds), parsed by RDKit
    Chem.MolFromMolBlock (which assigns tetrahedral stereo from the wedges and double-bond stereo
    from the coordinates), must give the same RDKit canonical isomeric SMILES as the truth;
  - no two atoms of the layout closer than OVERLAP x the median bond length (an atom drawn on top
    of another cannot be read);
  - the PNG is made pixel-only (png_clean.pixel_only, then assert_pixel_only), and its pixel hash
    must differ from the corpus RDKit image of the same key and from an RDKit default render of
    the truth at the same size.
Filenames are neutral (ctl_001.png ...), numbered in the seeded order.
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import os
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(HERE))
import png_clean  # noqa: E402

CORPUS_ROWS = REPO / "benchmarks" / "corpus_rows.json"
API_LEDGER = REPO / "benchmarks" / "published_runs" / "sonnet55_api" / "ledger.jsonl"
API_RETRIES = REPO / "benchmarks" / "published_runs" / "sonnet55_api" / "retries.jsonl"
S55C = Path("/root/cmage-work/sonnet-s55c/results.jsonl")
CORPUS_IMG_GLOB = "/root/cmage-work/cmage-img*/corpus_rdkit_1500"
JSON = REPO / "benchmarks" / "control_set.json"
IMG_DIR = Path("/root/cmage-work/control/indigo")

SEED = 20261008
N = 150
API_ROWS = 2510          # prefix of the API ledger that defines eligibility
S55C_ROWS = 1792         # prefix of the s55c results file that defines eligibility
SIZE = 1500
BOND_PX = 100.0
THICK = 1.5
OVERLAP = 0.25
OPTS = {"render-output-format": "png", "render-image-size": (SIZE, SIZE),
        "render-background-color": "1, 1, 1", "render-bond-length": BOND_PX,
        "render-relative-thickness": THICK, "render-stereo-style": "none", "timeout": 60000}


def jsonl_prefix(p: Path, n: int) -> list[dict]:
    out = []
    with open(p) as fh:
        for i, l in enumerate(fh):
            if i >= n:
                break
            out.append(json.loads(l))
    if len(out) < n:
        raise SystemExit(f"{p} has {len(out)} rows, fewer than the {n} the set was built from")
    return out


def canon(smi: str) -> str | None:
    from rdkit import Chem
    m = Chem.MolFromSmiles(smi)
    return None if m is None else Chem.MolToSmiles(m)


def eligible() -> tuple[list[str], dict, dict, dict]:
    rows = {r["k"]: r for r in json.load(open(CORPUS_ROWS))["rows"]}
    api = {r["k"]: r for r in jsonl_prefix(API_LEDGER, API_ROWS) if r.get("status") == "ok"}
    jail = {r["k"]: r for r in jsonl_prefix(S55C, S55C_ROWS) if r.get("sonnet_smiles") is not None}
    keys = sorted(set(rows) & set(api) & set(jail))
    return keys, rows, api, jail


def indigo_render(truth: str) -> tuple[bytes, str]:
    from indigo import Indigo
    from indigo.renderer import IndigoRenderer
    ind = Indigo()
    rend = IndigoRenderer(ind)
    for k, v in OPTS.items():
        if isinstance(v, tuple):
            ind.setOption(k, *v)
        else:
            ind.setOption(k, v)
    m = ind.loadMolecule(truth)
    m.dearomatize()
    m.layout()
    molfile = m.molfile()
    png = bytes(rend.renderToBuffer(m))
    return png, molfile


def verify_molfile(molfile: str, truth: str) -> str | None:
    """None if the laid-out molfile is the truth (RDKit canonical isomeric), else the reason."""
    import statistics
    from rdkit import Chem
    m = Chem.MolFromMolBlock(molfile)
    if m is None:
        return "RDKit cannot parse Indigo's molfile"
    got, want = Chem.MolToSmiles(m), canon(truth)
    if got != want:
        flat = Chem.MolToSmiles(m, isomericSmiles=False) == Chem.MolToSmiles(Chem.MolFromSmiles(truth), isomericSmiles=False)
        return ("stereo differs (drawing cannot show the truth's stereo)" if flat else "constitution differs") + \
            f": drawn {got} vs truth {want}"
    m2 = Chem.MolFromMolBlock(molfile, removeHs=False, sanitize=False)
    conf = m2.GetConformer()
    pos = [conf.GetAtomPosition(i) for i in range(m2.GetNumAtoms())]
    bl = [(pos[b.GetBeginAtomIdx()] - pos[b.GetEndAtomIdx()]).Length() for b in m2.GetBonds()]
    med = statistics.median(bl) if bl else 1.0
    for i in range(len(pos)):
        for j in range(i + 1, len(pos)):
            if (pos[i] - pos[j]).Length() < OVERLAP * med:
                return f"atoms {i + 1} and {j + 1} overlap in the layout"
    return None


def rdkit_default(truth: str, w: int, h: int) -> bytes:
    """The corpus renderer's settings (render_rdkit), at the given size."""
    from rdkit import Chem
    from rdkit.Chem.Draw import rdMolDraw2D
    d = rdMolDraw2D.MolDraw2DCairo(w, h)
    o = d.drawOptions()
    o.clearBackground, o.maxFontSize, o.minFontSize = True, -1, -1
    o.scaleBondWidth, o.bondLineWidth = True, 2
    rdMolDraw2D.PrepareAndDrawMolecule(d, Chem.MolFromSmiles(truth))
    d.FinishDrawing()
    return d.GetDrawingText()


def corpus_index() -> dict:
    idx = {}
    for dd in sorted(glob.glob(CORPUS_IMG_GLOB)):
        for p in glob.glob(dd + "/*.png"):
            idx.setdefault(os.path.basename(p)[:-4], p)
    return idx


def not_rdkit(png: bytes, key: str, truth: str, cidx: dict) -> str | None:
    from PIL import Image
    import io
    h = png_clean.pixel_hash(png)
    cp = cidx.get(key)
    if cp is None:
        return "no corpus image to compare against"
    if h == png_clean.pixel_hash(open(cp, "rb").read()):
        return "pixel-identical to the corpus RDKit image"
    im = Image.open(io.BytesIO(png))
    if h == png_clean.pixel_hash(rdkit_default(truth, *im.size)):
        return "pixel-identical to an RDKit default render"
    return None


def cmd_build(a) -> int:
    from rdkit import RDLogger
    RDLogger.DisableLog("rdApp.*")
    import indigo
    keys, rows, api, jail = eligible()
    order = list(keys)
    random.Random(SEED).shuffle(order)
    cidx = corpus_index()
    img_dir, out_json = Path(a.img_dir), Path(a.json)
    img_dir.mkdir(parents=True, exist_ok=True)
    built = a.built
    if not built and out_json.exists():
        built = json.load(open(out_json)).get("built")
    built = built or dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    accepted, skips = [], []
    for k in order:
        if len(accepted) >= N:
            break
        t = rows[k]["t"]
        if api[k]["truth"] != t or jail[k]["truth"] != t:
            skips.append({"k": k, "why": "truth differs between corpus_rows, the API ledger and s55c"})
            continue
        try:
            png, molfile = indigo_render(t)
        except Exception as e:      # IndigoException and anything else the C library raises
            skips.append({"k": k, "why": f"Indigo failed: {type(e).__name__}: {str(e)[:200]}"})
            continue
        why = verify_molfile(molfile, t)
        if why:
            skips.append({"k": k, "why": why})
            continue
        clean = png_clean.pixel_only(png)
        png_clean.assert_pixel_only(clean, k)
        if png_clean.pixel_hash(clean) != png_clean.pixel_hash(png):
            raise SystemExit(f"{k}: pixel_only changed the pixels")
        why = not_rdkit(clean, k, t, cidx)
        if why:
            skips.append({"k": k, "why": why})
            continue
        cid = f"ctl_{len(accepted) + 1:03d}"
        p = img_dir / f"{cid}.png"
        tmp = p.with_suffix(".tmp")
        tmp.write_bytes(clean)
        os.replace(tmp, p)
        accepted.append({"id": cid, "k": k, "n": rows[k]["n"], "t": t, "png": str(p),
                         "pixel_sha256": png_clean.pixel_hash(clean)})
        print(f"{cid} {k}", flush=True)
    if len(accepted) < N:
        raise SystemExit(f"only {len(accepted)} images passed")
    from rdkit import rdBase
    doc = {
        "renderer": f"EPAM Indigo {indigo.Indigo().version()} (indigo.renderer), Indigo's own 2D layout",
        "seed": SEED,
        "built": built,
        "notes": (f"{N} corpus keys drawn uniformly at random (random.Random({SEED}).shuffle of the sorted eligible "
                  f"keys, taken in that order) from the {len(keys)} corpus keys with BOTH an ok Sonnet 5.5 "
                  f"API-only reading (first {API_ROWS} lines of published_runs/sonnet55_api/ledger.jsonl) AND a "
                  f"Sonnet 5.5 jailed-lane (s55c) reading (first {S55C_ROWS} lines of its results.jsonl); no past "
                  f"verdict used. Render: loadMolecule(truth SMILES), dearomatize() (Kekule rings), layout(), PNG "
                  f"{SIZE}x{SIZE} white, render-bond-length {BOND_PX:g}, render-relative-thickness {THICK:g}, "
                  f"render-stereo-style none (no Chiral/abs text; stereo by wedges, hashes and double-bond "
                  f"geometry only), otherwise Indigo defaults (implicit H labels, black atoms). Verified per "
                  f"image: RDKit {rdBase.rdkitVersion} canonical isomeric SMILES of Indigo's laid-out molfile "
                  f"(MolFromMolBlock: stereo from its wedges and 2D coordinates) == canonical(truth); no two atoms "
                  f"closer than {OVERLAP:g} x the median bond length; pixel-only PNG (png_clean); pixel hash differs "
                  f"from the corpus RDKit image of the key and from an RDKit default render of the truth at the "
                  f"same size. {len(skips)} key(s) skipped, listed in 'skipped'."),
        "eligible_n": len(keys),
        "skipped": skips,
        "rows": accepted,
    }
    out_json.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_json.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n")
    os.replace(tmp, out_json)
    print(f"wrote {out_json}: {len(accepted)} rows, {len(skips)} skipped, eligible {len(keys)}")
    return 0


def cmd_check(a) -> int:
    doc = json.load(open(a.json))
    bad = 0
    for r in doc["rows"]:
        data = open(r["png"], "rb").read()
        try:
            png_clean.assert_pixel_only(data, r["id"])
        except png_clean.PngMetadataError as e:
            print(e)
            bad += 1
        if png_clean.pixel_hash(data) != r["pixel_sha256"]:
            print(f"{r['id']}: pixel hash differs from the set")
            bad += 1
        if r["k"] in data.decode("latin1") or r["n"] in data.decode("latin1"):
            print(f"{r['id']}: key or name bytes inside the PNG")
            bad += 1
    print(f"{len(doc['rows'])} rows, {bad} problem(s)")
    return 1 if bad else 0


def cmd_runset(a) -> int:
    doc = json.load(open(a.json))
    items = [{"id": r["id"], "png": r["png"], "truth": r["t"]} for r in doc["rows"]]
    Path(a.out).write_text(json.dumps(items, indent=1) + "\n")
    print(f"wrote {a.out}: {len(items)} items")
    return 0


def api_scored(led: list[dict], rets: list[dict]) -> dict:
    """k -> the reply build_sonnet55api scores: the last finished retry, else the last that landed,
    else the first reading."""
    by = {}
    for x in rets:
        by.setdefault(x["k"], []).append(x)
    out = {}
    for r0 in led:
        if r0["status"] != "ok":
            continue
        rr = [x for x in by.get(r0["k"], []) if x["status"] == "ok"]
        fin = [x for x in rr if x.get("stop_reason") != "max_tokens"]
        out[r0["k"]] = fin[-1] if fin else rr[-1] if rr else r0
    return out


def cmd_score(a) -> int:
    from collections import Counter
    from api_reader import parse_smiles
    from sonnet_batch import verdict
    from build_sonnet55 import mcnemar_exact
    doc = json.load(open(a.json))
    d = Path(a.ledger_dir)
    load = lambda p: [json.loads(l) for l in open(p) if l.strip()] if p.exists() else []
    ctl_led, ctl_ret = load(d / "ledger.jsonl"), load(d / "retries.jsonl")
    ctl = api_scored(ctl_led, ctl_ret)
    corp = api_scored(load(API_LEDGER), load(API_RETRIES))
    keys, rows, api, jail = eligible()
    pairs = []
    for r in doc["rows"]:
        c = ctl.get(r["id"])
        if c is None:
            continue
        if c["truth"] != r["t"]:
            raise SystemExit(f"{r['id']}: truth mismatch")
        cv = verdict(parse_smiles(c.get("text")) or "", r["t"])
        pv = verdict(parse_smiles(corp[r["k"]].get("text")) or "", r["t"])
        pairs.append({"id": r["id"], "k": r["k"], "control": cv, "corpus": pv,
                      "corpus_prompt": corp[r["k"]].get("prompt", "v1"),
                      "control_smiles": parse_smiles(c.get("text")), "control_stop": c.get("stop_reason")})
    n = len(pairs)
    cc, pc = Counter(p["control"] for p in pairs), Counter(p["corpus"] for p in pairs)
    b = sum(1 for p in pairs if p["corpus"] == "exact" and p["control"] != "exact")
    c_ = sum(1 for p in pairs if p["corpus"] != "exact" and p["control"] == "exact")
    cost = sum(x.get("cost_usd") or 0 for x in ctl_led + ctl_ret)
    res = {"n": n, "control_exact": cc["exact"], "corpus_exact": pc["exact"], "control": dict(cc), "corpus": dict(pc),
           "corpus_exact_control_not": b, "control_exact_corpus_not": c_, "mcnemar_p": mcnemar_exact(b, c_),
           "cost_usd": round(cost, 4), "failed": sum(1 for x in ctl_led if x["status"] != "ok"),
           "max_tokens_rows": sum(1 for x in ctl_led if x.get("stop_reason") == "max_tokens"),
           "corpus_prompt_versions": dict(Counter(p["corpus_prompt"] for p in pairs))}
    # the jailed lane on the same keys, for reference (its own corpus reading, rescored with verdict)
    jc = Counter(verdict(jail[p["k"]].get("sonnet_smiles"), jail[p["k"]]["truth"]) for p in pairs)
    res["jailed_corpus"] = dict(jc)
    if a.pairs_out:
        Path(a.pairs_out).write_text("\n".join(json.dumps(p) for p in pairs) + "\n")
    print(json.dumps(res, indent=1))
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    b = sp.add_parser("build")
    b.add_argument("--json", default=str(JSON))
    b.add_argument("--img-dir", default=str(IMG_DIR))
    b.add_argument("--built", help="ISO timestamp to record (default: the existing file's, else now)")
    c = sp.add_parser("check")
    c.add_argument("--json", default=str(JSON))
    r = sp.add_parser("runset")
    r.add_argument("--json", default=str(JSON))
    r.add_argument("--out", required=True)
    s = sp.add_parser("score")
    s.add_argument("--json", default=str(JSON))
    s.add_argument("--ledger-dir", required=True)
    s.add_argument("--pairs-out")
    a = ap.parse_args()
    sys.exit({"build": cmd_build, "check": cmd_check, "runset": cmd_runset, "score": cmd_score}[a.cmd](a))
