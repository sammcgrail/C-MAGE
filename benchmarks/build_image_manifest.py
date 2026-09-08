#!/usr/bin/env python3
"""Build a scoring manifest for a directory of single-molecule images.

The image corpus is a directory of PubChem 2D depictions named `<key>.png`, and
the ground-truth JSON is keyed by the same `<key>` (e.g. `aspirin_pubchem`) with
`drug_name`, `isomeric_smiles`, `formula`. Files whose key has no non-empty
`isomeric_smiles` are excluded from the population -- there is nothing to score
them against -- and the count of such files is recorded.

Sampling is deterministic and not hand-picked: the population is sorted by file
name and every `--step`-th file from `--offset` is taken. `--step 1` is the whole
population. The sampled files are copied into `--sample-dir` when given, so the
pipeline can be pointed at exactly that set.

Optional `--pubchem-verify` makes the ground truth independent of the JSON: the
compound name is resolved to PubChem CIDs, PubChem's own depiction at the file's
pixel size is fetched, and a CID is accepted only when it is pixel-identical to
the corpus image. The manifest then records, per image, whether the JSON SMILES
agrees with the SMILES of the CID whose picture this is. Needs network access.

Output is the unified manifest the scorer reads:
{
  "corpus": "images", "generated": "...", "population_size": N, "step": k, "offset": o,
  "groups": {
    "<key>": {"source": "<key>.png",
              "molecules": [{"name": "...", "smiles": "...", "formula": "...",
                             "cid": 2244, "pixel_verified": true,
                             "json_smiles_agrees": true}]}
  }
}
A group is one image; the pipeline's outputs are grouped back onto it by the
image stem embedded in every segment file name.
"""
import argparse
import datetime as dt
import hashlib
import json
import shutil
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

PUBCHEM = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound"
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}


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
        except urllib.error.HTTPError as e:  # 404 = no such name; do not retry
            if e.code == 404:
                return None
            last = e
        except Exception as e:  # noqa: BLE001
            last = e
        time.sleep(1.5 * (attempt + 1))
    raise last


def canon(smiles):
    from rdkit import Chem  # noqa: WPS433
    m = Chem.MolFromSmiles(smiles)
    return Chem.MolToSmiles(m) if m else None


def pubchem_verify(name, image_path, cache):
    """Return (cid, smiles, formula, tried) for the CID whose depiction is pixel-identical."""
    import numpy as np
    from PIL import Image
    img = Image.open(image_path).convert("RGB")
    size = img.size[0]
    a = np.asarray(img).astype(int)
    data = http(f"{PUBCHEM}/name/{urllib.parse.quote(name)}/cids/JSON", cache)
    cids = (data or {}).get("IdentifierList", {}).get("CID", [])[:5]
    tried = []
    for cid in cids:
        raw = http(f"{PUBCHEM}/cid/{cid}/PNG?image_size={size}x{size}", cache, binary=True)
        tmp = cache / f"cid{cid}_{size}.png"
        tmp.write_bytes(raw)
        b = np.asarray(Image.open(tmp).convert("RGB")).astype(int)
        same = a.shape == b.shape and int(np.abs(a - b).max()) == 0
        tried.append([cid, same])
        if same:
            p = http(f"{PUBCHEM}/cid/{cid}/property/SMILES,MolecularFormula/JSON", cache)
            p = p["PropertyTable"]["Properties"][0]
            return cid, p.get("SMILES"), p.get("MolecularFormula"), tried
    return None, None, None, tried


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--images", type=Path, required=True, help="Directory of <key>.png images")
    ap.add_argument("--corpus-json", type=Path, required=True, help="Ground-truth JSON keyed by <key>")
    ap.add_argument("--out", type=Path, required=True, help="Manifest JSON to write")
    ap.add_argument("--step", type=int, default=1, help="Take every step-th file of the sorted population")
    ap.add_argument("--offset", type=int, default=0, help="Index of the first file taken")
    ap.add_argument("--sample-dir", type=Path, default=None, help="Copy the sampled files here")
    ap.add_argument("--pubchem-verify", action="store_true", help="Pixel-verify each image against PubChem (network)")
    ap.add_argument("--cache", type=Path, default=Path(".pubchem_cache"))
    args = ap.parse_args()

    gt = json.loads(args.corpus_json.read_text())
    files = sorted(p for p in args.images.iterdir()
                   if p.suffix.lower() in IMAGE_SUFFIXES and not p.name.startswith("."))
    no_key = [p.name for p in files if p.stem not in gt]
    no_smiles = [p.name for p in files if p.stem in gt and not gt[p.stem].get("isomeric_smiles")]
    population = [p for p in files if gt.get(p.stem, {}).get("isomeric_smiles")]
    sample = population[args.offset::args.step]
    print(f"{len(files)} files; {len(no_key)} without a JSON key; {len(no_smiles)} with an empty SMILES; "
          f"population {len(population)}; every {args.step}th from {args.offset} -> {len(sample)}")

    if args.sample_dir:
        args.sample_dir.mkdir(parents=True, exist_ok=True)
        for p in sample:
            shutil.copy(p, args.sample_dir / p.name)

    if args.pubchem_verify:
        args.cache.mkdir(parents=True, exist_ok=True)

    manifest = {"corpus": "images", "generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                "images_dir_file_count": len(files), "files_without_key": len(no_key),
                "files_with_empty_smiles": len(no_smiles), "population_size": len(population),
                "step": args.step, "offset": args.offset, "sample_size": len(sample), "groups": {}}
    disagreements = []
    unverified = []
    for i, p in enumerate(sample):
        e = gt[p.stem]
        mol = {"name": e.get("drug_name"), "smiles": e["isomeric_smiles"], "formula": e.get("formula"),
               "smiles_source": "corpus json"}
        if args.pubchem_verify:
            try:
                cid, smi, formula, tried = pubchem_verify(e.get("drug_name") or p.stem, p, args.cache)
            except Exception as ex:  # noqa: BLE001
                cid, smi, formula, tried = None, None, None, [f"error: {ex}"]
            mol.update({"cid": cid, "pixel_verified": cid is not None, "candidates_tried": tried})
            if cid is not None:
                agrees = canon(smi) == canon(e["isomeric_smiles"])
                mol["pubchem_smiles"] = smi
                mol["json_smiles_agrees"] = agrees
                if not agrees:
                    disagreements.append(p.name)
                    # The picture is PubChem's rendering of this CID, so its SMILES wins.
                    mol["smiles"] = smi
                    mol["smiles_source"] = f"pubchem CID {cid} (json disagreed)"
            else:
                unverified.append(p.name)
            print(f"[{i + 1}/{len(sample)}] {p.name:40s} CID {cid} verified={cid is not None}"
                  f"{'' if cid is None else ' json_agrees=' + str(mol['json_smiles_agrees'])}")
        manifest["groups"][p.stem] = {"source": p.name, "molecules": [mol]}

    if args.pubchem_verify:
        manifest["pubchem_verified"] = len(sample) - len(unverified)
        manifest["pubchem_unverified_files"] = unverified
        manifest["json_smiles_disagreements"] = disagreements
        print(f"\npixel-verified {len(sample) - len(unverified)}/{len(sample)}; "
              f"JSON SMILES disagreed with PubChem for {len(disagreements)}: {disagreements}")
        if unverified:
            print(f"not verifiable (kept with JSON SMILES): {unverified}")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(manifest, indent=1))
    print(f"wrote {args.out}")


if __name__ == "__main__":
    sys.exit(main())
