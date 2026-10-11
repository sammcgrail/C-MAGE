#!/usr/bin/env python3
"""Strip stray-fragment ARTIFACTS from the big superatom set's reference SMILES (Sam, 11 Oct).

The big set's truths come from the patent's own MOL/CDX (big_expand.py). ChemDraw files carry text that was parsed
as atoms and survives into the SMILES as extra fragments, so every reader that reads the molecule correctly is
marked wrong:
  * a stereo descriptor "(S)" next to a stereocentre                  -> a lone `S` (sulfane)
  * the "H" of an "N-H" drawn as its own text block                   -> `[HH]`
  * the compound label under the drawing ("I-27", "BFC-3", "D-Val")   -> `[I-27]`, `[C-3]BF`, `[2H-]`
    (ChemDraw reads "I-27" as iodine with charge -27)
Real salts / solvates that are DRAWN (formic acid, "•H2O", HCl, Na+ ...) are kept.

    clean_truth.py check            dry run over big/set.json: what would change
    clean_truth.py apply            write cleaned truths (original kept in `truth_raw`) + big/truth_cleanup.json
    clean_truth.py count SET.json [--field truth]   count the artifact pattern in another set (report only)

Library: clean(truth, row_id=None, mol_path=None) -> {"truth", "removed", "kept", "undecided", "changed"}.
big_expand.add_rows() calls it on every new row. Never touches a drawing or a reader's answer.
"""
import argparse, fcntl, json, sys
from pathlib import Path

RUN = Path("/root/C-MAGE/benchmarks/published_runs/sonnet55_api_superatoms/big")
LOG = RUN / "truth_cleanup.json"
LOCK = Path("/root/cmage-work/bigsa/big.lock")

METALS = {"Li", "Na", "K", "Rb", "Cs", "Be", "Mg", "Ca", "Sr", "Ba", "Al", "Ga", "In", "Tl", "Sn", "Pb", "Bi",
          "Sc", "Ti", "V", "Cr", "Mn", "Fe", "Co", "Ni", "Cu", "Zn", "Y", "Zr", "Nb", "Mo", "Tc", "Ru", "Rh", "Pd",
          "Ag", "Cd", "La", "Ce", "Gd", "Lu", "Hf", "Ta", "W", "Re", "Os", "Ir", "Pt", "Au", "Hg"}
# A lone, uncharged one-letter atom of these elements is never a drawn component: it is a text glyph ("(S)" stereo
# descriptor, a stray "C"/"B"/"P"). O (water), N (ammonia), halogens (HCl, HBr) are real and are NOT here.
LONE_GLYPH = {"B", "C", "Si", "P", "S", "Se"}
# Drawn counter-ions / salts / solvents: kept automatically (canonical SMILES, no stereo).
KEEP_ION = {"[Cl-]", "[Br-]", "[I-]", "[F-]", "Cl", "Br", "I", "F", "[Na+]", "[K+]", "[Li+]", "[Ca+2]", "[Mg+2]",
            "[Zn+2]", "[NH4+]", "O", "N", "O=CO", "O=C([O-])O", "CC(=O)O", "CC(=O)[O-]", "O=C(O)C(F)(F)F",
            "O=C([O-])C(F)(F)F", "O=S(=O)(O)O", "CS(=O)(=O)O", "Cc1ccc(S(=O)(=O)O)cc1", "O=C(O)C(=O)O",
            "O=C(O)/C=C\\C(=O)O", "O=C(O)/C=C/C(=O)O", "O=C(O)CC(O)(CC(=O)O)C(=O)O", "O=P(O)(O)O",
            "O=C(O)CCC(=O)O", "OC(C(=O)O)C(O)C(=O)O", "O=C(O)C(O)C(O)C(=O)O", "CO", "CCO", "CS(C)=O"}

# Decisions taken by looking at the drawing (Read the PNG). (row id, fragment as it appears in the truth) ->
# (action, reason[, replacement]). Every one is also written to truth_cleanup.json with "how": "manual".
MANUAL = {
    ("rb_0585", "O"): ("keep", "drawn as '•H2O' (a hydrate): a real, drawn component"),
    ("rb_1740", "O"): ("remove", "two stray 'O' glyphs float in the drawing, bonded to nothing; a drawing defect, "
                                 "not a component (the patent's depiction of the parent is itself mangled)"),
    ("rb_1785", "O"): ("remove", "a stray 'O' glyph floats above the ring, bonded to nothing; a drawing defect"),
    ("rb_1785", "CC"): ("remove", "a floating ethyl stroke at the top edge, detached from its N; a drawing defect, "
                                  "not ethane"),
    ("rb_1657", "CC"): ("remove", "a floating ethyl stroke at the top, detached from its N; a drawing defect, "
                                  "not ethane"),
    ("rb_2404", "CC#CC#CB(F)C#CC#CC"): ("remove", "the compound label '(BFC10)' under the drawing, parsed as atoms"),
    ("rb_2132", "[GaH3]"): ("replace", "Ga is drawn, unbonded, inside the DOTA cage; the three H are MOL valence "
                                       "fill, not drawn", "[Ga]"),
    ("rb_2171", "[GaH3]"): ("replace", "Ga drawn unbonded inside the DOTA cage; H3 is valence fill", "[Ga]"),
    ("rb_2196", "[GaH3]"): ("replace", "Ga drawn unbonded inside the DOTA cage; H3 is valence fill", "[Ga]"),
    ("rb_2339", "[GaH3]"): ("replace", "Ga drawn unbonded inside the DOTA cage; H3 is valence fill", "[Ga]"),
    ("rb_2094", "[F-]"): ("merge_bf3", "the drawing shows one 'BF3-' label; the MOL split it into a neutral "
                                       "-BF2 on the molecule and a loose F-. Rejoined as -[B-](F)(F)F"),
}
# Rows whose DRAWING does not determine one molecule (a reaction scheme, a Markush 'Ar', a polymer or framework,
# an antibody conjugate, compound arrows). Fragment cleaning cannot fix them; they are left untouched and listed
# in truth_cleanup.json "flagged_rows" for a separate exclude decision (not taken here).
FLAGGED = {
    "rb_0267": "reaction scheme: 4 compounds + 'Zn' reagent text; the truth is the whole scheme",
    "rb_2264": "Markush: 'Ar' ring + resin bead, two Ar= options drawn below; truth has argon + both options",
    "rb_2496": "polysiloxane with '221K' arrow labels; truth has 110 K-K fragments",
    "rb_2075": "polymer repeat unit cut by a wavy bond; truth carries a detached piece of it",
    "rb_2433": "covalent organic framework with wavy cut bonds and boxed 'Z' labels",
    "rb_2288": "antibody-drug conjugate ('MAB' cartoon, (...)n); truth carries a stray C",
    "rb_1657": "the patent's drawing is mangled (floating ethyl, broken ring); cleaned, but the parent is not the "
               "intended compound",
    "rb_1740": "the patent's drawing is mangled (stray O glyphs, broken ring); cleaned, but the parent is not the "
               "intended compound",
    "rb_1785": "the patent's drawing is mangled (stray O, floating ethyl); cleaned, but the parent is not the "
               "intended compound",
}
UNTOUCHED = {k for k in FLAGGED if k not in {"rb_1657", "rb_1740", "rb_1785"}}


def _rd():
    from rdkit import Chem, RDLogger
    RDLogger.DisableLog("rdApp.*")
    return Chem


def auto_rule(frag: str):
    """(action, rule, reason) for one non-parent fragment, or ("undecided", None, why)."""
    Chem = _rd()
    m = Chem.MolFromSmiles(frag)
    if m is None:
        return "undecided", None, "fragment does not parse"
    atoms = list(m.GetAtoms())
    can = Chem.MolToSmiles(m, isomericSmiles=False)
    if can == "[HH]":
        return "remove", "h2", "H2: the 'H' of an N-H / C-H drawn as its own text block"
    for a in atoms:
        q, el = a.GetFormalCharge(), a.GetSymbol()
        if abs(q) > 3 or (abs(q) >= 2 and el not in METALS) or (el == "H" and q != 0):
            return ("remove", "label_text", f"compound label text parsed as atoms ({el} with charge {q:+d}, "
                    f"e.g. 'I-27' -> iodine -27, 'BFC-3', 'D-' -> deuteride)")
        iso = a.GetIsotope()
        if iso and not (el == "H" and iso in (2, 3)) and iso not in (11, 13, 14, 15, 18):
            return "remove", "isotope", f"isotope label {iso}{el} is not a drawing convention"
    if can in KEEP_ION:
        return "keep", "counter_ion", "drawn salt / counter-ion / solvent"
    if len(atoms) == 1 and atoms[0].GetFormalCharge() == 0:
        el = atoms[0].GetSymbol()
        if el in LONE_GLYPH:
            return "remove", "lone_glyph", f"lone '{el}': a text glyph (stereo descriptor '(S)' etc.), not a component"
        if el in METALS:
            return "undecided", None, f"metal {can}: look at the drawing (drawn metal vs MOL hydride fill)"
    return "undecided", None, "not a known counter-ion; look at the drawing"


def _merge_bf3(truth: str) -> str:
    Chem = _rd()
    m = Chem.RWMol(Chem.MolFromSmiles(truth))
    f = [a.GetIdx() for a in m.GetAtoms() if a.GetSymbol() == "F" and a.GetFormalCharge() == -1 and a.GetDegree() == 0]
    b = [a.GetIdx() for a in m.GetAtoms() if a.GetSymbol() == "B" and a.GetFormalCharge() == 0
         and sum(n.GetSymbol() == "F" for n in a.GetNeighbors()) == 2 and a.GetDegree() == 3]
    assert len(f) == 1 and len(b) == 1, (f, b)
    m.GetAtomWithIdx(f[0]).SetFormalCharge(0)
    m.GetAtomWithIdx(b[0]).SetFormalCharge(-1)
    m.AddBond(b[0], f[0], Chem.BondType.SINGLE)
    Chem.SanitizeMol(m)
    return Chem.MolToSmiles(m)


def mol_geometry(mol_path):
    """canonical fragment SMILES -> [{inside, d}] from the source MOL: is the fragment inside the parent's bounding
    box, and its distance to the parent in median bond lengths. Evidence only; never decides on its own."""
    if not mol_path or not Path(mol_path).exists():
        return {}
    Chem = _rd()
    m = Chem.MolFromMolBlock(Path(mol_path).read_text(encoding="latin-1"), sanitize=True, removeHs=True)
    if m is None or not m.GetNumConformers():
        return {}
    P = m.GetConformer().GetAtomPosition
    frags = Chem.GetMolFrags(m)
    main = max(frags, key=len)
    xs, ys = [P(i).x for i in main], [P(i).y for i in main]
    bl = sorted((P(b.GetBeginAtomIdx()) - P(b.GetEndAtomIdx())).Length() for b in m.GetBonds()) or [1.0]
    bl = bl[len(bl) // 2] or 1.0
    out = {}
    for f in frags:
        if f is main:
            continue
        smi = Chem.MolToSmiles(Chem.MolFromSmiles(Chem.MolFragmentToSmiles(m, f)) or Chem.Mol(), isomericSmiles=False)
        out.setdefault(smi, []).append({
            "inside": all(min(xs) <= P(i).x <= max(xs) and min(ys) <= P(i).y <= max(ys) for i in f),
            "d": round(min(min((P(i) - P(j)).Length() for j in main) for i in f) / bl, 2)})
    return out


def clean(truth: str, row_id: str | None = None, mol_path=None) -> dict:
    """Split on '.', keep the largest fragment (by heavy atoms) as the parent, judge every other fragment.
    Kept fragments keep their original text; the result is unchanged when nothing is removed."""
    Chem = _rd()
    res = {"truth": truth, "removed": [], "kept": [], "undecided": [], "changed": False}
    if "." not in truth or row_id in UNTOUCHED:
        return res
    frags = truth.split(".")
    heavy = [(Chem.MolFromSmiles(f).GetNumHeavyAtoms() if Chem.MolFromSmiles(f) else -1) for f in frags]
    parent = max(range(len(frags)), key=lambda i: heavy[i])
    geo = mol_geometry(mol_path)
    out, merge = [frags[parent]], False
    for i, f in enumerate(frags):
        if i == parent:
            continue
        m = Chem.MolFromSmiles(f)
        g = (geo.get(Chem.MolToSmiles(m, isomericSmiles=False)) or [None])[0] if m is not None else None
        rec = {"fragment": f, **({"mol": g} if g else {})}
        man = MANUAL.get((row_id, f))
        if man:
            act, why = man[0], man[1]
            rec.update(how="manual", reason=why)
            if act == "keep":
                out.append(f); res["kept"].append({**rec, "rule": "manual"})
            elif act == "remove":
                res["removed"].append({**rec, "rule": "manual"})
            elif act == "replace":
                out.append(man[2]); res["removed"].append({**rec, "rule": "manual", "replaced_by": man[2]})
            elif act == "merge_bf3":
                out.append(f); merge = True; res["removed"].append({**rec, "rule": "manual", "replaced_by": "merged into -[B-](F)(F)F"})
            continue
        act, rule, why = auto_rule(f)
        rec.update(how="auto", rule=rule, reason=why)
        if act == "remove":
            res["removed"].append(rec)
        else:
            out.append(f)
            (res["kept"] if act == "keep" else res["undecided"]).append(rec)
    new = ".".join(out)
    if merge:
        new = _merge_bf3(new)
    res["truth"] = new
    res["changed"] = new != truth
    return res


def _rows():
    return json.load(open(RUN / "set.json"))


def run(apply: bool) -> int:
    Chem = _rd()
    import collections
    fh = open(LOCK, "a+")
    fcntl.flock(fh, fcntl.LOCK_EX)              # big_expand.py step holds the same lock while it writes set.json
    rows = _rows()
    log = {"rows": [], "flagged_rows": [{"id": k, "why": v} for k, v in sorted(FLAGGED.items())]}
    by_rule, n_rows, n_prot = collections.Counter(), 0, 0
    for x in rows:
        raw = x.get("truth_raw", x["truth"])
        r = clean(raw, x["id"], x.get("orig_mol"))
        for d in r["removed"]:
            by_rule[d["rule"] if d["how"] == "auto" else "manual"] += 1
        if r["removed"] or r["undecided"] or r["kept"]:
            log["rows"].append({"id": x["id"], "cls": x["cls"], "truth_raw": raw, "truth": r["truth"],
                                "removed": r["removed"], "kept": r["kept"], "undecided": r["undecided"]})
        if r["changed"]:
            n_rows += 1
            n_prot += x["cls"] == "protac"
            assert Chem.MolFromSmiles(r["truth"]) is not None, (x["id"], r["truth"])
            if apply:
                x["truth_raw"] = raw
                x["truth"] = r["truth"]
        elif apply and "truth_raw" in x and x["truth_raw"] == r["truth"]:
            x["truth"] = x.pop("truth_raw")
    und = [(r["id"], d["fragment"]) for r in log["rows"] for d in r["undecided"]]
    log["summary"] = {"rows_changed": n_rows, "protac_rows_changed": n_prot, "removed_by_rule": dict(by_rule),
                      "undecided": len(und)}
    print(json.dumps(log["summary"]))
    for u in und[:40]:
        print("undecided:", *u)
    if apply:
        tmp = RUN / "set.json.tmp"
        json.dump(rows, open(tmp, "w"), indent=1)
        tmp.replace(RUN / "set.json")
        json.dump([{"id": x["id"], "png": x["png"], "truth": x["truth"]} for x in rows],
                  open(RUN / "run_set.json", "w"), indent=0)
        json.dump(log, open(LOG, "w"), indent=1)
        print(f"wrote {RUN / 'set.json'}, run_set.json, {LOG}")
    return 0


def count(path: str, field: str) -> int:
    """Report-only: how many rows of another set carry a fragment the auto rules would remove."""
    import collections
    d = json.load(open(path))
    rows = d["rows"] if isinstance(d, dict) else d
    c, n = collections.Counter(), 0
    for x in rows:
        t = x.get(field) or ""
        if "." not in t:
            continue
        r = clean(t)
        if r["removed"]:
            n += 1
            for q in r["removed"]:
                c[q["rule"]] += 1
    print(json.dumps({"set": path, "rows": len(rows), "rows_with_artifacts": n, "fragments_by_rule": dict(c)}))
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["check", "apply", "count"])
    ap.add_argument("path", nargs="?")
    ap.add_argument("--field", default="truth")
    a = ap.parse_args()
    if a.cmd == "count":
        return count(a.path, a.field)
    return run(a.cmd == "apply")


if __name__ == "__main__":
    sys.exit(main())
