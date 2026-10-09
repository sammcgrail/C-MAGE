#!/usr/bin/env python3
"""Resolve pubchem_names.txt on PubChem (PUG REST, <= 3/s) -> synth/pubchem.json: name, CID,
isomeric SMILES, InChIKey. A name that does not resolve is recorded and skipped.

    fetch_pubchem.py [NAMES OUT]     defaults: pubchem_names.txt synth/pubchem.json
    (the 2026-10-09 expansion: pubchem_names2.txt more/pubchem2.json)"""
import json, sys, time, urllib.error, urllib.parse, urllib.request
from pathlib import Path
ROOT = Path("/root/cmage-work/superatoms")
NAMES = ROOT / (sys.argv[1] if len(sys.argv) > 2 else "pubchem_names.txt")
OUT = ROOT / (sys.argv[2] if len(sys.argv) > 2 else "synth/pubchem.json")
cache = json.load(open(OUT)) if OUT.exists() else {}
names = [l.strip() for l in open(NAMES) if l.strip() and not l.startswith("#")]
for n in names:
    if n in cache:
        continue
    url = ("https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/" + urllib.parse.quote(n, safe="")
           + "/property/IsomericSMILES,SMILES,InChIKey,MolecularFormula/JSON")
    rec = None
    for t in range(3):
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                p = json.load(r)["PropertyTable"]["Properties"][0]
                rec = {"cid": p["CID"], "smiles": p.get("IsomericSMILES") or p.get("SMILES"),
                       "inchikey": p.get("InChIKey"), "formula": p.get("MolecularFormula")}
            break
        except urllib.error.HTTPError as e:
            if e.code == 404:
                break
            time.sleep(2)
        except Exception:
            time.sleep(2)
    cache[n] = rec
    print(n, "->", rec and rec["cid"], flush=True)
    time.sleep(0.34)
    OUT.write_text(json.dumps(cache, indent=1))
OUT.write_text(json.dumps(cache, indent=1))
