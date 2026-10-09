#!/usr/bin/env python3
"""Supplement to build_more.py (2026-10-09): the PubChem name list produced no drawing with TIPS,
TBDPS, MOM, THP, SEM or Alloc (the named reagents carry one label, the gate wants two), so up to PER
molecules per group come from a PubChem substructure search (fetch_pubchem_sub.py). A pick must show
that group's label after v2 condensation, carry >= 2 labels, have <= MAX_HEAVY heavy atoms, be one
component of C/H/N/O/S/F/Cl/Br/Si/P, not already be in the set, and pass every build_more.gate().
Order within a group is a seeded shuffle of the hits. Appends sa_0476... to synth/set.json + run_set.json."""
import collections, json, random, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import sa_abbrev as A
from build_more import gate, RUN, IMG, ROOT, DEFS
from build_set import assert_clean, label_forms, ocr_text
from PIL import Image
from rdkit import Chem, RDLogger
RDLogger.DisableLog("rdApp.*")
PER = 5
MAX_HEAVY = 45
SEED = 20261009
OK_EL = {1, 6, 7, 8, 9, 14, 15, 16, 17, 35}


def main():
    old = json.load(open(RUN / "set.json"))
    have = {A.canon(x["truth"]) for x in old}
    n0 = max(int(x["id"][3:]) for x in old)
    assert n0 >= 475, n0
    sub = json.load(open(ROOT / "more/pubchem_sub.json"))
    done = {x.get("picked_for") for x in old}
    picks, rej = [], collections.Counter()
    for q, recs in sub.items():
        g = q.removesuffix("_smarts")
        if g in done:
            continue
        recs = sorted(recs, key=lambda r: r["cid"])
        random.Random(f"{SEED}-{q}").shuffle(recs)
        got = 0
        for r in recs:
            if got >= PER:
                break
            s = r["smiles"]
            m = Chem.MolFromSmiles(s) if s and "." not in s else None
            if m is None or m.GetNumHeavyAtoms() > MAX_HEAVY or any(a.GetAtomicNum() not in OK_EL or a.GetIsotope()
                                                                     or a.GetFormalCharge() for a in m.GetAtoms()):
                rej["shape"] += 1; continue
            cn = A.canon(m)
            if cn in have:
                rej["already"] += 1; continue
            if g not in A.labels_of(A.condense(m, defs=DEFS)):
                rej["group not drawn"] += 1; continue
            it, why = gate(dict(src="pubchem", key=None, name=r["title"] or f"CID {r['cid']}", cid=r["cid"], truth=s))
            if not it:
                rej[why.split(":")[0]] += 1; continue
            have.add(cn)
            it["group"] = g
            picks.append(it)
            got += 1
        print(g, got)
    random.Random(SEED).shuffle(picks)
    out = []
    for i, it in enumerate(picks, n0 + 1):
        sid = f"sa_{i:04d}"
        c = it.pop("_c")
        tmp = ROOT / "more/tmp.png"
        A.render(c, 1500, tmp)
        im = Image.open(tmp); im.load()
        png = IMG / f"{sid}.png"
        assert not png.exists(), png
        im.convert("RGB").save(png)
        assert_clean(png)
        nd = lambda x: re.sub(r"[\d,._]", "", x).replace("0", "O")
        txt = nd(ocr_text(png))
        miss = [l for l in sorted(set(it["labels"])) if not any(nd(f) in txt for f in label_forms(l))]
        rec = dict(src="pubchem", key=None, name=it["name"], cid=it["cid"], truth=it["truth"], labels=it["labels"],
                   id=sid, cx=Chem.MolToCXSmiles(c), heavy=it["heavy"], n_labels=len(it["labels"]),
                   ocr_missing=miss, plain_key=None, png=str(png), batch="2026-10-09", abbrev="v2",
                   show=True, picked_for=it["group"])
        if it.get("layout"):
            rec["layout"] = it["layout"]
        out.append(rec)
    json.dump(old + out, open(RUN / "set.json", "w"), indent=1)
    rs = json.load(open(RUN / "run_set.json"))
    assert [x["id"] for x in rs] == [x["id"] for x in old]
    json.dump(rs + [{"id": o["id"], "png": o["png"], "truth": o["truth"]} for o in out],
              open(RUN / "run_set.json", "w"), indent=0)
    sp = ROOT / "more/synth_sub.json"
    json.dump((json.load(open(sp)) if sp.exists() else []) + out, open(sp, "w"), indent=1)
    print(len(out), "supplementary built; rejected", dict(rej))
    print(collections.Counter(l for o in out for l in set(o["labels"])).most_common())


if __name__ == "__main__":
    main()
