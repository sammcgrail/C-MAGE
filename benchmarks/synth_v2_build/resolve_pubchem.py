#!/usr/bin/env python3
"""Resolve every candidate compound to a PubChem CID, InChIKey and formula.

Two paths, deliberately different:

  * local pool (ringleader's 764) -- the STRUCTURE is already known, so the
    InChIKey is computed with RDKit and PubChem is asked only "which CID is
    this?". A name lookup here could return a different molecule than the one
    we hold and we would never know; an InChIKey lookup cannot.
  * supplemental names (large naturals, marketed salts) -- no local structure
    exists, so PubChem's own record IS the structure. Resolved by name.

Writes one cache keyed by 'ik:<key>' or 'name:<name>'; reruns are free.
"""
import json, sys, time, urllib.parse, urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from supplemental_names import LARGE, SALT

from rdkit import Chem, RDLogger
RDLogger.DisableLog("rdApp.*")

PUG = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound"
CACHE = Path(__file__).resolve().parent / "pubchem_cache_v2.json"
PROPS = "SMILES,IsomericSMILES,ConnectivitySMILES,MolecularFormula,InChIKey"


def _post(url, data, tries=4):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, data=data.encode(),
                                         headers={"Content-Type": "application/x-www-form-urlencoded"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode())
        except Exception as e:                                    # noqa: BLE001
            if i == tries - 1:
                return None
            time.sleep(2.0 * (i + 1))
    return None


def _get(url, tries=4):
    for i in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=45) as r:
                return json.loads(r.read().decode())
        except Exception:                                         # noqa: BLE001
            if i == tries - 1:
                return None
            time.sleep(1.5 * (i + 1))
    return None


def unpack(p):
    smi = p.get("IsomericSMILES") or p.get("SMILES") or p.get("ConnectivitySMILES")
    return {"cid": p.get("CID"), "smiles": smi,
            "formula": p.get("MolecularFormula"), "inchikey": p.get("InChIKey")}


def main():
    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    n0 = len(cache)

    # ---- local pool, batched by InChIKey
    pool_path = Path(sys.argv[1]) if len(sys.argv) > 1 else (
        Path(__file__).resolve().parents[3] / "ringleader" / "tests"
        / "pubchem_ground_truth.json")
    pool = json.loads(pool_path.read_text())
    want = {}
    for k, v in pool.items():
        smi = v.get("isomeric_smiles") or v.get("canonical_smiles")
        m = Chem.MolFromSmiles(smi) if smi else None
        if m is None:
            continue
        try:
            ik = Chem.MolToInchiKey(m)
        except Exception:                                         # noqa: BLE001
            continue
        if ik and f"ik:{ik}" not in cache:
            want.setdefault(ik, k)
    keys = sorted(want)
    print(f"{len(keys)} inchikeys to resolve", flush=True)
    for i in range(0, len(keys), 50):
        chunk = keys[i:i + 50]
        d = _post(f"{PUG}/inchikey/property/{PROPS}/JSON",
                  urllib.parse.urlencode({"inchikey": ",".join(chunk)}))
        got = {}
        if d and d.get("PropertyTable", {}).get("Properties"):
            for p in d["PropertyTable"]["Properties"]:
                rec = unpack(p)
                if rec["inchikey"]:
                    got[rec["inchikey"]] = rec
        for ik in chunk:
            cache[f"ik:{ik}"] = got.get(ik)
        CACHE.write_text(json.dumps(cache))
        print(f"  ik batch {i//50}: {len(got)}/{len(chunk)}", flush=True)
        time.sleep(0.4)

    # ---- supplemental, one name at a time
    names = [n for n in dict.fromkeys(LARGE + SALT) if f"name:{n}" not in cache]
    print(f"{len(names)} names to resolve", flush=True)
    for j, name in enumerate(names):
        d = _get(f"{PUG}/name/{urllib.parse.quote(name)}/property/{PROPS}/JSON")
        rec = None
        if d and d.get("PropertyTable", {}).get("Properties"):
            rec = unpack(d["PropertyTable"]["Properties"][0])
        cache[f"name:{name}"] = rec
        if j % 20 == 0:
            CACHE.write_text(json.dumps(cache))
            print(f"  name {j}/{len(names)} {name} -> {rec and rec['cid']}", flush=True)
        time.sleep(0.25)
    CACHE.write_text(json.dumps(cache))
    hits = sum(1 for v in cache.values() if v)
    print(f"done: {len(cache)} entries ({n0} before), {hits} resolved", flush=True)


if __name__ == "__main__":
    main()
