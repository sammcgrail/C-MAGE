#!/usr/bin/env python3
"""Supplementary PubChem picks for groups the name list left empty (2026-10-09): a fastsubstructure
search per group (PUG REST, synchronous), properties for the hits -> more/pubchem_sub.json
{group: [{cid, smiles, title}]}. Selection happens in build_more_sub.py."""
import json, time, urllib.parse, urllib.request
from pathlib import Path
ROOT = Path("/root/cmage-work/superatoms")
OUT = ROOT / "more/pubchem_sub.json"
Q = {  # group -> substructure SMILES (the group plus its attachment atom)
    "OTIPS": "CC(C)[Si](OC)(C(C)C)C(C)C",
    "OTBDPS": "CC(C)(C)[Si](OC)(c1ccccc1)c1ccccc1",
    "OMOM": "COCOC",
    "OTHP": "C(OC1CCCCO1)",
    "SEM": "C[Si](C)(C)CCOCN",
    "Trt": "N C(c1ccccc1)(c1ccccc1)c1ccccc1".replace(" ", ""),
    "PMB": "COc1ccc(CN)cc1",
    "Piv": "CC(C)(C)C(=O)N",
    "Alloc": "C=CCOC(=O)N",
    "OTBS": "CC(C)(C)[Si](C)(C)OC",
}
# second pass: the substructure hits for these three were almost all substituted rings / acetals,
# so query SMARTS with hydrogen counts (PubChem fastsubstructure/smarts)
QS = {"OMOM": "[CH3]O[CH2]O[#6]", "OTHP": "[#6]O[CH1]1[CH2][CH2][CH2][CH2]O1", "Alloc": "[CH2]=[CH][CH2]OC(=O)[#7]"}


def get(url):
    for t in range(4):
        try:
            with urllib.request.urlopen(url, timeout=90) as r:
                return json.load(r)
        except Exception as e:
            err = e
            time.sleep(3)
    print("fail", url[:120], err)
    return None


out = json.load(open(OUT)) if OUT.exists() else {}
for g, (ns, smi) in [(g, ("smiles", v)) for g, v in Q.items()] + [(g + "_smarts", ("smarts", v)) for g, v in QS.items()]:
    if g in out:
        continue
    j = get(f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/fastsubstructure/{ns}/"
            + urllib.parse.quote(smi, safe="") + "/cids/JSON?MaxRecords=400")
    cids = (j or {}).get("IdentifierList", {}).get("CID", [])
    time.sleep(0.4)
    recs = []
    for i in range(0, len(cids), 100):
        p = get("https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/" + ",".join(map(str, cids[i:i + 100]))
                + "/property/IsomericSMILES,SMILES,Title,HeavyAtomCount/JSON")
        for x in (p or {}).get("PropertyTable", {}).get("Properties", []):
            recs.append({"cid": x["CID"], "smiles": x.get("IsomericSMILES") or x.get("SMILES"),
                         "title": x.get("Title"), "heavy": x.get("HeavyAtomCount")})
        time.sleep(0.4)
    out[g] = recs
    print(g, len(cids), "hits,", len(recs), "with properties", flush=True)
    OUT.write_text(json.dumps(out))
