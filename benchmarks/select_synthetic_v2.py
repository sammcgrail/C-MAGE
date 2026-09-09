#!/usr/bin/env python3
"""Choose the v2 corpus: pool -> attributes -> strata -> pages. Writes a PLAN.

Separated from the drawing step on purpose. The plan is a JSON file naming every
compound, its source SMILES, its stratum, its sub-buckets and the page and
render condition it will be drawn under; make_synthetic_corpus_v2.py then draws
exactly that and nothing else. So the composition can be reviewed, diffed and
argued with before a single pixel exists, and a redraw cannot quietly select a
different corpus.

Deterministic: the only ordering input is a sort on (bucket, name), so two runs
against the same pool and the same PubChem cache produce the same plan.

MARKUSH BY CONSTRUCTION
-----------------------
v1 hand-wrote 11 scaffolds and had to assert each was a substructure of a named
drug -- two were not, on the first try, for two different reasons (an R on a
position that is hydrogen in the parent; an R on an aromatic ring-fusion carbon,
where the query bond is single and the target bond aromatic). v2 does the
opposite: it CUTS a real drug at an acyclic single bond and replaces the whole
leaving fragment with one dummy atom. The scaffold is then a substructure of the
parent because it was made by deleting atoms from it, and the wildcard's bond is
single because the bond it replaced was. The check is still run -- construction
that cannot be checked is just a different kind of assertion.
"""
import argparse, hashlib, json, sys
from collections import Counter, defaultdict
from pathlib import Path

from rdkit import Chem, RDLogger
from rdkit.Chem import rdAbbreviations, rdMolDescriptors

sys.path.insert(0, str(Path(__file__).resolve().parent))
from synthetic_compounds_v2 import (ABBREV_BUCKETS, MIRRORS, PANEL_N,  # noqa: E402
                                    SIZE_BUCKETS, STEREO_BUCKETS, TARGETS, VOCAB_N)
from cxsmiles import expand                                              # noqa: E402

try:
    from molscribe.constants import ABBREVIATIONS as MS_ABBREV
except ImportError:                                                      # pragma: no cover
    MS_ABBREV = {}

RDLogger.DisableLog("rdApp.*")
# The candidate pool. Not in this repo: it is a 764-row PubChem export that
# lives beside it, so the path is an argument with a sibling-checkout default.
DEFAULT_POOL = Path(__file__).resolve().parents[2] / "ringleader" / "tests" \
    / "pubchem_ground_truth.json"
CACHE = Path(__file__).resolve().parent / "synth_v2_build" / "pubchem_cache_v2.json"

# v1's compounds, named so v2 can contain them and the two corpora can be
# compared on IDENTICAL molecules rather than on two samples of a stratum.
V1_BASIC = ["caffeine", "ibuprofen", "lidocaine", "metronidazole", "phenytoin",
            "warfarin", "melatonin", "temozolomide", "letrozole", "lamotrigine",
            "gabapentin", "propranolol", "metoprolol", "sulfamethoxazole",
            "trimethoprim", "thalidomide", "carbamazepine", "diphenhydramine",
            "ketamine", "theophylline", "minoxidil", "phenobarbital"]
V1_STEREO = ["morphine", "codeine", "oxycodone", "naloxone", "testosterone",
             "estradiol", "progesterone", "cholesterol", "prednisolone",
             "betamethasone", "finasteride", "spironolactone", "lovastatin",
             "simvastatin", "amoxicillin", "cephalexin", "quinine",
             "artemisinin", "doxycycline", "gemcitabine", "oseltamivir"]
V1_ABBREV = ["aspirin", "atrazine", "atenolol", "albuterol", "anastrozole",
             "amlodipine", "benzocaine", "bicalutamide", "bosentan", "capsaicin",
             "amiodarone", "apixaban", "azathioprine", "candesartan", "articaine",
             "alogliptin", "atorvastatin", "benazepril", "camptothecin",
             "aldosterone", "celecoxib", "naproxen"]
V1_NAMES = set(V1_BASIC + V1_STEREO + V1_ABBREV)


def _abbrevs():
    ab = rdAbbreviations.GetDefaultAbbreviations()
    for a in rdAbbreviations.ParseAbbreviations("Ph\t*c1ccccc1\n"):
        ab.append(a)
    return ab


def bucket_of(v, table):
    for name, lo, hi in table:
        if lo <= v <= hi:
            return name
    return table[-1][0]


def fused_max(mol):
    """Largest number of rings sharing bonds in one fused system."""
    ri = mol.GetRingInfo()
    rings = [set(r) for r in ri.BondRings()]
    if not rings:
        return 0
    parent = list(range(len(rings)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(len(rings)):
        for j in range(i + 1, len(rings)):
            if rings[i] & rings[j]:
                a, b = find(i), find(j)
                if a != b:
                    parent[a] = b
    return max(Counter(find(i) for i in range(len(rings))).values())


def _strip(mol):
    m = Chem.Mol(mol)
    for a in m.GetAtoms():
        for prop in ("atomLabel", "_displayLabel", "_displayLabelW", "dummyLabel"):
            if a.HasProp(prop):
                a.ClearProp(prop)
    return m


def attrs(name, smiles, cid, inchikey, formula, ab):
    m = Chem.MolFromSmiles(smiles) if smiles else None
    if m is None:
        return None
    try:
        cond = rdAbbreviations.CondenseMolAbbreviations(m, ab, maxCoverage=0.8)
        labels = [a.GetProp("atomLabel") for a in cond.GetAtoms() if a.HasProp("atomLabel")]
    except Exception:                                             # noqa: BLE001
        cond, labels = None, []
    # Can this compound be DRAWN condensed and still be the molecule it claims?
    # Two ways it cannot, both found the hard way:
    #  * RDKit's condensation DROPS a chiral tag when a stereocentre's
    #    substituent is absorbed into a superatom -- valine condenses to
    #    `*C(*)N |$iPr;;CO2H;$|` with NO defined centre, so the drawing is not
    #    valine any more while the manifest would still say it is.
    #  * a label RDKit emits but CXMolScribe has never heard of (nPent, nNon,
    #    CO2-) can never be graded fairly against the model's own table.
    n_centres = len(Chem.FindMolChiralCenters(m, useLegacyImplementation=False,
                                              includeUnassigned=False))
    stereo_kept = expand_ok = None
    if labels:
        try:
            # a condensed stereocentre can leave RDKit's CIP labeller with a
            # carrier it cannot resolve ("configuration must have 4 carriers");
            # a molecule whose own drawer cannot name its centres is not one to
            # put in a stereo benchmark, so the raise is a rejection, not a bug
            cond_centres = len(Chem.FindMolChiralCenters(cond, useLegacyImplementation=False,
                                                         includeUnassigned=False))
            stereo_kept = cond_centres == n_centres
        except Exception:                                         # noqa: BLE001
            stereo_kept = False
        try:
            back, _note = expand(Chem.MolToCXSmiles(cond))
            expand_ok = bool(back) and Chem.CanonSmiles(back) == Chem.CanonSmiles(smiles)
        except Exception:                                         # noqa: BLE001
            expand_ok = False
    ha = m.GetNumHeavyAtoms()
    rings = m.GetRingInfo().AtomRings()
    return {
        "name": name, "cid": cid, "inchikey": inchikey or Chem.MolToInchiKey(m),
        "formula": formula or rdMolDescriptors.CalcMolFormula(m),
        "source_smiles": smiles,
        "heavy_atoms": ha,
        "size_bucket": bucket_of(ha, SIZE_BUCKETS),
        "stereocentres": len(Chem.FindMolChiralCenters(
            m, useLegacyImplementation=False, includeUnassigned=False)),
        "fragments": len(Chem.GetMolFrags(m)),
        "net_charge": Chem.GetFormalCharge(m),
        "largest_ring": max([len(r) for r in rings], default=0),
        "n_rings": len(rings),
        "fused_max": fused_max(m),
        "n_superatoms": len(labels),
        "superatoms": labels,
        "mirrorable": sorted({l for l in labels if l in MIRRORS}),
        # The skeleton as it will be DRAWN. Two DIFFERENT compounds can share
        # one -- cefotaxime's OAc and cefpodoxime's OMe both condense to a single
        # dummy at the same position -- and two such drawings in one PDF cannot
        # be told apart by score_cx's assignment step (it ties at the top score
        # and its `ambiguous` flag only fires on LOW scores, so the tie is
        # invisible). Recorded here so the plan can keep them apart.
        "skel_plain": Chem.MolToSmiles(m),
        "skel_cond": (Chem.MolToSmiles(_strip(cond)) if cond is not None
                      else Chem.MolToSmiles(m)),
        "all_in_vocab": bool(labels) and all(l in MS_ABBREV for l in labels),
        "condense_stereo_kept": stereo_kept,
        "condense_expands_back": expand_ok,
        "drawable_condensed": bool(labels) and bool(expand_ok)
                              and all(l in MS_ABBREV for l in labels),
    }


# ------------------------------------------------------------------ markush
def make_markush(parent_smiles, n_r, min_core=11, max_leave=12):
    """Cut `n_r` acyclic single bonds off a drug; each leaving group -> one R.

    Returns (scaffold mol with atomLabel R1.., ordered labels) or None.
    """
    base = Chem.MolFromSmiles(parent_smiles)
    if base is None:
        return None
    Chem.RemoveStereochemistry(base)
    mol = Chem.Mol(base)
    labels = []
    for k in range(n_r):
        cand = []
        for b in mol.GetBonds():
            if b.IsInRing() or b.GetBondType() != Chem.BondType.SINGLE:
                continue
            i, j = b.GetBeginAtomIdx(), b.GetEndAtomIdx()
            if mol.GetAtomWithIdx(i).GetAtomicNum() == 0 or mol.GetAtomWithIdx(j).GetAtomicNum() == 0:
                continue
            em = Chem.RWMol(mol)
            em.RemoveBond(i, j)
            frags = Chem.GetMolFrags(em)
            if len(frags) != 2:
                continue
            fi = next(f for f in frags if i in f)
            fj = next(f for f in frags if j in f)
            for keep, drop, anchor in ((fi, fj, i), (fj, fi, j)):
                if len(drop) < 1 or len(drop) > max_leave or len(keep) < min_core:
                    continue
                if not any(mol.GetAtomWithIdx(a).IsInRing() for a in keep):
                    continue
                cand.append((len(drop), sorted(drop), anchor))
        if not cand:
            return None
        # deterministic: the largest allowed leaving group, ties by atom index
        cand.sort(key=lambda c: (-c[0], c[1]))
        _, drop, anchor = cand[0]
        em = Chem.RWMol(mol)
        d = em.AddAtom(Chem.Atom(0))
        em.AddBond(anchor, d, Chem.BondType.SINGLE)
        for idx in sorted(drop, reverse=True):
            em.RemoveAtom(idx)
        try:
            mol = em.GetMol()
            Chem.SanitizeMol(mol)
        except Exception:                                         # noqa: BLE001
            return None
        labels.append(f"R{k + 1}")
    dummies = [a for a in mol.GetAtoms() if a.GetAtomicNum() == 0]
    if len(dummies) != n_r:
        return None
    for a, lab in zip(dummies, labels):
        a.SetAtomMapNum(0)
        a.SetProp("atomLabel", lab)
        if a.HasProp("dummyLabel"):
            a.ClearProp("dummyLabel")
    # the construction claim, checked
    q = Chem.AdjustQueryProperties(
        Chem.MolFromSmiles(Chem.MolToSmiles(mol)),
        (lambda p: (setattr(p, "makeDummiesQueries", True), p)[1])(
            Chem.AdjustQueryParameters.NoAdjustments()))
    if q is None or not base.HasSubstructMatch(q):
        return None
    return mol, labels


# ------------------------------------------------------------------ selection
def spread_pick(cands, n, key):
    """Take n items round-robin across the values of `key`, so a stratum is not
    silently all one bucket. Deterministic: sorted by (bucket, name)."""
    by = defaultdict(list)
    for c in cands:
        by[c[key]].append(c)
    for k in by:
        by[k].sort(key=lambda c: c["name"])
    order, out, seen = sorted(by), [], set()
    while len(out) < n:
        moved = False
        for k in order:
            if by[k]:
                c = by[k].pop(0)
                if c["name"] in seen:
                    continue
                out.append(c)
                seen.add(c["name"])
                moved = True
                if len(out) >= n:
                    break
        if not moved:
            break
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path,
                    default=Path(__file__).resolve().parent / "synth_v2_build"
                    / "synthetic_plan_v2.json")
    ap.add_argument("--pool", type=Path, default=DEFAULT_POOL,
                    help="PubChem export used as the candidate pool")
    args = ap.parse_args()

    ab = _abbrevs()
    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    pool = json.loads(args.pool.read_text())

    # ---- candidate table
    cands, seen_ik, dupes = {}, {}, []
    for k, v in sorted(pool.items()):
        smi = v.get("isomeric_smiles") or v.get("canonical_smiles")
        m = Chem.MolFromSmiles(smi) if smi else None
        if m is None:
            continue
        ik = Chem.MolToInchiKey(m)
        rec = cache.get(f"ik:{ik}") or {}
        if ik in seen_ik:
            # the pool holds brand names beside generics -- arimidex/anastrozole,
            # pulmicort/rhinocort/budesonide, calquence/acalabrutinib. Nine such
            # pairs. Keeping both would put one molecule in a stratum twice and
            # two identical drawings in one PDF, where the scorer cannot tell
            # which reference a prediction belongs to.
            dupes.append((ik, seen_ik[ik], v.get("drug_name") or k))
            continue
        a = attrs(v.get("drug_name") or k, smi, rec.get("cid"), ik,
                  v.get("formula"), ab)
        if a:
            a["source"] = "ringleader"
            cands[a["name"]] = a
            seen_ik[ik] = a["name"]
    for key, rec in sorted(cache.items()):
        if not key.startswith("name:") or not rec or not rec.get("smiles"):
            continue
        name = key[5:]
        if name in cands:
            continue
        a = attrs(name, rec["smiles"], rec.get("cid"), rec.get("inchikey"),
                  rec.get("formula"), ab)
        if not a:
            continue
        if a["inchikey"] in seen_ik:            # same molecule under two names
            continue
        a["source"] = "pubchem_name"
        cands[name] = a
        seen_ik[a["inchikey"]] = name
    print(f"{len(cands)} distinct candidates "
          f"({len(dupes)} pool entries dropped as InChIKey duplicates: "
          f"{', '.join(d[2] for d in dupes[:6])}...)", flush=True)

    used = set()

    def take(pred, n, key, prefer=()):
        avail = [c for c in cands.values() if c["name"] not in used and pred(c)]
        first = [c for c in avail if c["name"] in prefer]
        rest = [c for c in avail if c["name"] not in prefer]
        got = first[:n] + spread_pick(rest, max(0, n - len(first)), key)
        for c in got:
            used.add(c["name"])
        return got

    sel = {}
    sel["basic"] = take(lambda c: (c["stereocentres"] == 0 and c["fragments"] == 1
                                   and c["net_charge"] == 0 and c["heavy_atoms"] <= 26
                                   and c["n_rings"] >= 1),
                        TARGETS["basic"], "size_bucket", prefer=set(V1_BASIC))
    for c in sel["basic"]:
        c["stratum"] = "basic"

    def sbucket(c):
        return bucket_of(c["stereocentres"], STEREO_BUCKETS)
    stereo = []
    for b, lo, hi in STEREO_BUCKETS[1:]:                # s1, s2-3, s4-7, s8+
        stereo += take(lambda c, lo=lo, hi=hi: (lo <= c["stereocentres"] <= hi
                                                and c["fragments"] == 1 and c["net_charge"] == 0),
                       TARGETS["stereo"] // 4, "size_bucket", prefer=set(V1_STEREO))
    sel["stereo"] = stereo
    for c in sel["stereo"]:
        c["stratum"] = "stereo"
        c["stereo_bucket"] = sbucket(c)

    def abucket(c):
        return bucket_of(c["n_superatoms"], ABBREV_BUCKETS)
    abbrev = []
    for b, lo, hi in ABBREV_BUCKETS:
        abbrev += take(lambda c, lo=lo, hi=hi: (lo <= c["n_superatoms"] <= hi
                                                and c["drawable_condensed"]
                                                and c["fragments"] == 1 and c["net_charge"] == 0),
                       TARGETS["abbreviated"] // 3, "size_bucket", prefer=set(V1_ABBREV))
    sel["abbreviated"] = abbrev
    for c in sel["abbreviated"]:
        c["stratum"] = "abbreviated"
        c["abbrev_bucket"] = abucket(c)

    def topo(c):
        if c["largest_ring"] >= 12:
            return "macrocycle"
        if c["fused_max"] >= 4:
            return "fused>=4"
        return "large-open"
    cplx, preds = [], (
        ("macrocycle", lambda c: c["largest_ring"] >= 12),
        ("fused>=4", lambda c: c["largest_ring"] < 12 and c["fused_max"] >= 4),
        ("large-open", lambda c: (c["largest_ring"] < 12 and c["fused_max"] < 4
                                  and c["heavy_atoms"] >= 51)))
    for t, pred in preds:
        cplx += take(lambda c, p=pred: p(c) and c["fragments"] == 1,
                     TARGETS["complex"] // 3, "size_bucket")
    # `large-open` runs dry at 9 of 22 -- there simply are not many 51+ atom drugs
    # with no macrocycle and no 4-ring fusion. Top up from the buckets that do
    # have depth rather than reporting a short stratum and calling it a target.
    for t, pred in preds[:2]:
        if len(cplx) >= TARGETS["complex"]:
            break
        cplx += take(lambda c, p=pred: p(c) and c["fragments"] == 1,
                     TARGETS["complex"] - len(cplx), "size_bucket")
    sel["complex"] = cplx
    for c in sel["complex"]:
        c["stratum"] = "complex"
        c["topology"] = topo(c)

    sel["salt"] = take(lambda c: c["fragments"] >= 2 or c["net_charge"] != 0,
                       TARGETS["salt"], "size_bucket")
    for c in sel["salt"]:
        c["stratum"] = "salt"

    # ---- markush, cut from parents not yet drawn anywhere
    mk, i, mk_skels = [], 0, set()
    parents = [c for c in sorted(cands.values(), key=lambda c: c["name"])
               if c["name"] not in used and c["fragments"] == 1
               and 14 <= c["heavy_atoms"] <= 45 and c["n_rings"] >= 2]
    for c in parents:
        if len(mk) >= TARGETS["markush"]:
            break
        n_r = 1 + (i % 2)
        i += 1
        got = make_markush(c["source_smiles"], n_r)
        if not got:
            got = make_markush(c["source_smiles"], 1)
            if not got:
                continue
        scaf, labels = got
        smi = Chem.MolToSmiles(scaf)
        # cutting aripiprazole, brexpiprazole and buspirone all leave the same
        # butyl-piperazine core; three copies of one drawing is not a bigger
        # sample, it is an unscoreable three-way tie
        if Chem.MolToSmiles(_strip(scaf)) in mk_skels:
            continue
        mk_skels.add(Chem.MolToSmiles(_strip(scaf)))
        used.add(c["name"])
        mk.append({
            "name": f"scaffold of {c['name']}", "stratum": "markush",
            "markush": True, "scaffold_smiles": smi, "r_labels": labels,
            "parent_name": c["name"], "parent_cid": c["cid"],
            "parent_inchikey": c["inchikey"], "parent_smiles": c["source_smiles"],
            "cid": None, "inchikey": None,
            "formula": rdMolDescriptors.CalcMolFormula(
                Chem.MolFromSmiles(smi.split(" ")[0])) if smi else None,
            "heavy_atoms": Chem.MolFromSmiles(smi).GetNumHeavyAtoms(),
            "size_bucket": bucket_of(Chem.MolFromSmiles(smi).GetNumHeavyAtoms(), SIZE_BUCKETS),
            "n_superatoms": len(labels), "superatoms": labels,
            "stereocentres": 0, "fragments": 1, "net_charge": 0,
            "source": "cut-from-drug", "source_smiles": None,
        })
    sel["markush"] = mk

    # ---------------------------------------------------------- page assignment
    plan_pdfs = []

    def drawn_skel(c):
        if c.get("markush"):
            return c["scaffold_smiles"]
        return c["skel_cond"] if c["stratum"] == "abbreviated" else c["skel_plain"]

    def dedupe(members, label):
        """Drop any member whose DRAWN skeleton already appears in this list.

        Not the same check as the InChIKey dedup: these are different compounds
        that become the same picture. score_cx assigns a prediction to the
        best-matching reference in its group; two references with one skeleton
        tie at the top score, the first wins, and the second is scored as a miss
        no matter how well it was read.
        """
        out, seen, dropped = [], set(), []
        for c in members:
            k = drawn_skel(c)
            if k in seen:
                dropped.append(c["name"])
                continue
            seen.add(k)
            out.append(c)
        if dropped:
            print(f"  {label}: dropped {len(dropped)} for a duplicate drawn "
                  f"skeleton: {dropped[:5]}")
        return out

    for k in sel:
        sel[k] = dedupe(sel[k], k)

    def chunk(seq, k):
        return [seq[i:i + k] for i in range(0, len(seq), k)]

    def add(stem, title, render, members, arm, **kw):
        if not members:
            return
        plan_pdfs.append(dict({"stem": stem, "title": title, "render": render,
                               "arm": arm, "members": members}, **kw))

    TITLES = {
        "basic": "Small-molecule reference set",
        "stereo": "Stereochemically defined compounds",
        "abbreviated": "Compounds drawn with condensed substituent labels",
        "complex": "Macrocyclic, fused-polycyclic and large open-chain compounds",
        "salt": "Salts, counter-ions and permanently charged species",
        "markush": "Generic scaffolds with variable substituents",
    }
    # 12 per PDF at 6 per page: small groups keep score_cx's within-group
    # assignment easy, which is why v1 used 10 and not 100.
    for s in ("basic", "stereo", "abbreviated", "complex", "salt", "markush"):
        for i, ch in enumerate(chunk(sel[s], 12), 1):
            add(f"s2_{s}_{i:02d}", f"{TITLES[s]}, part {i}", "std", ch, "core")

    # a mixed set, because a real page is not stratum-pure. Reported separately.
    mixed = []
    for s in ("basic", "stereo", "abbreviated", "complex", "salt", "markush"):
        mixed += sel[s][-4:]
    mixed = dedupe(mixed, "mixed")
    for i, ch in enumerate(chunk(mixed, 12), 1):
        add(f"s2_mixed_{i:02d}", f"Mixed set: all six strata on one page, part {i}",
            "std", ch, "mixed")

    # ---- crossed arms: the SAME compounds redrawn, one variable at a time
    panel = dedupe(sel["basic"][:PANEL_N // 3] + sel["stereo"][:PANEL_N // 3]
                   + sel["abbreviated"][:PANEL_N // 3], "panel")
    for i, c in enumerate(panel):
        c["panel_id"] = i
    from synthetic_compounds_v2 import DENSITY_ARM, INK_ARM, PER_PAGE, SPACING_ARM
    for cond in sorted(set(DENSITY_ARM + INK_ARM + SPACING_ARM)):
        pp = PER_PAGE[cond]
        k = pp * max(1, -(-12 // pp))          # >= 12 per PDF, whole pages only
        for i, ch in enumerate(chunk(panel, k), 1):
            add(f"s2_{cond}_{i:02d}",
                f"Density/ink panel under condition {cond}, part {i}", cond, ch, "crossed")

    # ---- vocabulary arm: same molecule, label CXMolScribe knows vs its mirror
    pool_v = sel["abbreviated"] + sel["basic"] + sel["stereo"] + sel["complex"]
    vocab = dedupe([dict(c, stratum="abbreviated") for c in pool_v
                    if c.get("mirrorable") and c.get("drawable_condensed")], "vocab")[:VOCAB_N]
    for i, ch in enumerate(chunk(vocab, 12), 1):
        add(f"s2_vocab_in_{i:02d}", f"Condensed labels inside the model vocabulary, part {i}",
            "std", ch, "vocab_in", plain_labels=True)
        add(f"s2_vocab_out_{i:02d}", f"The same labels written mirrored, part {i}",
            "std", ch, "vocab_out", plain_labels=True, mirrored=True)

    plan = {"candidates": len(cands),
            "selected": {k: len(v) for k, v in sel.items()},
            "panel": [c["name"] for c in panel],
            "vocab_panel": [c["name"] for c in vocab],
            "strata": sel, "pdfs": plan_pdfs}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(plan, indent=1))
    print(json.dumps(plan["selected"], indent=0))
    for s, xs in sel.items():
        print(f"  {s:12s} sizes {dict(Counter(x['size_bucket'] for x in xs))}")
    allc = [x for xs in sel.values() for x in xs]
    print("SIZE BUCKETS overall:", dict(Counter(x["size_bucket"] for x in allc)))
    print("STEREO buckets:", dict(Counter(bucket_of(x.get("stereocentres", 0), STEREO_BUCKETS)
                                          for x in allc)))
    print("ABBREV buckets:", dict(Counter(bucket_of(x.get("n_superatoms", 0), ABBREV_BUCKETS)
                                          for x in allc if x.get("n_superatoms"))))
    cond_any = [c for c in cands.values() if c["n_superatoms"]]
    print(f"condensable candidates {len(cond_any)}: "
          f"stereo dropped by condensation {sum(1 for c in cond_any if c['condense_stereo_kept'] is False)}, "
          f"label outside CXMolScribe vocab {sum(1 for c in cond_any if not c['all_in_vocab'])}, "
          f"drawable condensed {sum(1 for c in cond_any if c['drawable_condensed'])}")
    print(f"distinct compounds {len(allc)}   panel {len(panel)}   vocab {len(vocab)}")
    drawings = sum(len(j["members"]) for j in plan_pdfs)
    print(f"PDFs {len(plan_pdfs)}   drawings {drawings}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
