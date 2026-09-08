#!/usr/bin/env python3
"""Recover, per PDF, exactly which molecules were drawn in the ground-truth PDF corpus.

The ground-truth corpus is a set of single-page PDFs, each a 2x2 grid of PubChem
2D depictions (300x300 PNG) with the compound name printed under each picture.
Because every picture is PubChem's own rendering of a specific CID, the drawn
molecule can be pinned exactly:

  1. `pdfimages` extracts the embedded pictures in content-stream order
     (top-left, top-right, bottom-left, bottom-right).
  2. `pdftotext -layout` gives the labels in the same order.
  3. Each label is resolved to PubChem CIDs, and PubChem's PNG for each CID at
     the embedded picture's pixel size is compared pixel-for-pixel with it. A
     CID is accepted only when the pictures are identical; the SMILES for that
     CID is then the ground truth for that picture, with no room for a
     name/salt/isomer mix-up.
  4. Optionally the corpus's own ground-truth JSON is cross-checked: where it has
     a SMILES for the same compound, the two must canonicalise to the same thing.

Output is the unified manifest the scorer reads (groups keyed by PDF stem, which
is the prefix of every figure and segment file name the pipeline writes):
{
  "corpus": "pdfs", "generated": "...",
  "groups": {
    "test_x": {"source": "test_x.pdf", "pages": 1,
               "molecules": [{"index": 0, "label": "Aspirin", "name": "Aspirin",
                              "cid": 2244, "smiles": "...", "formula": "C9H8O4",
                              "pixel_verified": true, "corpus_keys": ["aspirin_pubchem"],
                              "corpus_smiles_agrees": true}]}
  }
}
It carries only compound names, CIDs and SMILES -- nothing machine-specific --
so it can be committed and reused without network access.

Requires: poppler-utils (pdfimages, pdftotext, pdfinfo), Pillow, numpy, network
access to PubChem. RDKit is optional (used only for the cross-check).

Usage:
  build_ground_truth.py --pdf-dir corpus/ --out ground_truth/pdf_manifest.json \
      [--corpus-json pubchem_ground_truth.json] [--cache .pubchem_cache] \
      [--exclude test_reactions_coupling.pdf]
"""
import argparse
import datetime as dt
import hashlib
import json
import re
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image

PUBCHEM = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound"


def sh(*cmd):
    return subprocess.run(list(cmd), check=True, capture_output=True, text=True).stdout


def page_count(pdf):
    m = re.search(r"^Pages:\s+(\d+)", sh("pdfinfo", str(pdf)), re.M)
    return int(m.group(1)) if m else None


def embedded_images(pdf, workdir):
    """Extract embedded raster images in content-stream order."""
    prefix = Path(workdir) / pdf.stem
    subprocess.run(["pdfimages", "-png", str(pdf), str(prefix)], check=True)
    return sorted(Path(workdir).glob(pdf.stem + "-*.png"))


def labels_from_text(pdf):
    """Labels in reading order. The first non-empty line is the page title."""
    text = sh("pdftotext", "-layout", str(pdf), "-")
    lines = [l.rstrip() for l in text.splitlines() if l.strip()]
    labels = []
    for line in lines[1:]:
        labels.extend(p.strip() for p in re.split(r"\s{3,}", line.strip()) if p.strip())
    return labels


def query_name(label):
    """'Aspirin (Acetylsalicylic Acid)' -> 'Aspirin'; 'ARV-110 (PROTAC)' -> 'ARV-110'."""
    return re.sub(r"\s*\(.*?\)\s*$", "", label).strip()


def http(url, cache, binary=False, retries=4):
    key = hashlib.sha1(url.encode()).hexdigest()
    cached = cache / (key + (".bin" if binary else ".json"))
    if cached.exists():
        return cached.read_bytes() if binary else json.loads(cached.read_text())
    last = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                raw = r.read()
            time.sleep(0.25)  # PubChem asks for <= 5 requests/s
            if binary:
                cached.write_bytes(raw)
                return raw
            data = json.loads(raw.decode())
            cached.write_text(json.dumps(data))
            return data
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            last = e
        except Exception as e:  # noqa: BLE001
            last = e
        time.sleep(1.5 * (attempt + 1))
    raise last


def canon(smiles):
    try:
        from rdkit import Chem  # noqa: WPS433
    except ImportError:
        return None
    m = Chem.MolFromSmiles(smiles)
    return Chem.MolToSmiles(m) if m else None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pdf-dir", type=Path, required=True, help="Directory of ground-truth PDFs")
    ap.add_argument("--out", type=Path, required=True, help="Manifest JSON to write")
    ap.add_argument("--corpus-json", type=Path, default=None,
                    help="The corpus's own ground-truth JSON (keys like aspirin_pubchem) for a cross-check")
    ap.add_argument("--cache", type=Path, default=Path(".pubchem_cache"), help="HTTP cache directory")
    ap.add_argument("--exclude", action="append", default=[], help="PDF file name to skip (repeatable)")
    args = ap.parse_args()

    args.cache.mkdir(parents=True, exist_ok=True)
    corpus = json.loads(args.corpus_json.read_text()) if args.corpus_json else {}
    by_name = {}
    for key, entry in corpus.items():
        by_name.setdefault((entry.get("drug_name") or "").lower(), []).append(key)

    manifest = {"corpus": "pdfs", "generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                "method": "embedded image == PubChem depiction of CID, pixel-exact",
                "excluded": args.exclude, "groups": {}}
    problems = []
    with tempfile.TemporaryDirectory() as td:
        for pdf in sorted(args.pdf_dir.glob("*.pdf")):
            if pdf.name in args.exclude:
                print(f"skip {pdf.name}")
                continue
            imgs = embedded_images(pdf, td)
            labels = labels_from_text(pdf)
            if len(imgs) != len(labels):
                problems.append(f"{pdf.name}: {len(imgs)} images but {len(labels)} labels {labels}")
                continue
            group = {"source": pdf.name, "pages": page_count(pdf), "molecules": []}
            for i, (img_path, label) in enumerate(zip(imgs, labels)):
                emb = Image.open(img_path).convert("RGB")
                a = np.asarray(emb).astype(int)
                name = query_name(label)
                data = http(f"{PUBCHEM}/name/{urllib.parse.quote(name)}/cids/JSON", args.cache)
                cids = (data or {}).get("IdentifierList", {}).get("CID", [])[:5]
                chosen, tried = None, []
                for cid in cids:
                    raw = http(f"{PUBCHEM}/cid/{cid}/PNG?image_size={emb.size[0]}x{emb.size[1]}", args.cache, binary=True)
                    tmp = args.cache / f"cid{cid}_{emb.size[0]}.png"
                    tmp.write_bytes(raw)
                    b = np.asarray(Image.open(tmp).convert("RGB")).astype(int)
                    same = a.shape == b.shape and int(np.abs(a - b).max()) == 0
                    tried.append([cid, same])
                    if same:
                        chosen = cid
                        break
                mol = {"index": i, "label": label, "name": name, "cid": chosen,
                       "pixel_verified": chosen is not None, "candidates_tried": tried}
                if chosen is not None:
                    p = http(f"{PUBCHEM}/cid/{chosen}/property/SMILES,ConnectivitySMILES,"
                             f"MolecularFormula,MolecularWeight,Title/JSON", args.cache)
                    p = p["PropertyTable"]["Properties"][0]
                    mol.update({"title": p.get("Title"), "smiles": p.get("SMILES"),
                                "connectivity_smiles": p.get("ConnectivitySMILES"),
                                "formula": p.get("MolecularFormula"), "mw": p.get("MolecularWeight")})
                    keys = by_name.get(name.lower(), [])
                    corpus_smi = [corpus[k]["isomeric_smiles"] for k in keys if corpus[k].get("isomeric_smiles")]
                    mol["corpus_keys"] = keys
                    if corpus_smi:
                        c_pub = canon(mol["smiles"])
                        agree = all(canon(s) == c_pub for s in corpus_smi) if c_pub else None
                        mol["corpus_smiles_agrees"] = agree
                        if agree is False:
                            problems.append(f"{pdf.name}[{i}] {name}: corpus JSON SMILES differs from PubChem CID {chosen}")
                    else:
                        mol["corpus_smiles_agrees"] = None  # corpus JSON has no SMILES for it
                else:
                    problems.append(f"{pdf.name}[{i}] {label}: no PubChem CID depiction matched the embedded image")
                group["molecules"].append(mol)
                print(f"{'ok ' if chosen else '!! '}{pdf.name:28s} [{i}] {label:32s} -> CID {chosen} {mol.get('formula', '')}")
            manifest["groups"][pdf.stem] = group

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(manifest, indent=1))
    n = sum(len(g["molecules"]) for g in manifest["groups"].values())
    ok = sum(m["pixel_verified"] for g in manifest["groups"].values() for m in g["molecules"])
    print(f"\nwrote {args.out}: {len(manifest['groups'])} PDFs, {n} drawn molecules, {ok} pixel-verified")
    if problems:
        print("\nPROBLEMS:")
        for p in problems:
            print("  " + p)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
