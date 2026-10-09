#!/usr/bin/env python3
"""The NOVEL STRUCTURES set: molecules a reader cannot have memorised, drawn exactly like the corpus.

    novel_set.py build        render the images and write benchmarks/novel_set.json

WHY. On the blind corpus Sonnet 5.5 reads ~99% exact, but nearly every image is a famous named
drug, so an answer can be recall rather than reading. This set removes the recall:
- kind A, EDITED FAMOUS DRUGS: one chemically sensible edit to a drug that is in the corpus
  (halogen swap, substituent moved, N <-> CH, a methyl added or removed, one stereocentre
  inverted, a ring resized). The parent is recorded, so an answer that equals the PARENT and not
  the edit is flagged as "autocorrected to parent": the model drew what it remembered.
- kind B, DE NOVO: drug-like molecules assembled from fragments (15-40 heavy atoms, rings,
  heteroatoms, 0-2 stereocentres), none of which has a PubChem record.

RENDERING IS THE CORPUS'S, BYTE FOR BYTE. render_rdkit() is a verbatim copy of the corpus_rdkit_1500
renderer (cmage-img*/build_corpus*.py): 1500 px, clearBackground, font size unclamped, scaled bond
width 2. Checked 29 Sep: re-rendering four corpus compounds from their truth SMILES with this
function gives byte-identical PNGs (same md5) under the .venv-ms RDKit (2025.03.3). Re-checked 8 Oct,
after includeMetadata = False went into both renderers and every stored image was stripped to pixels
only (RDKit had written each image's SMILES and molblock into it as zTXt): all 44 novel images, and
2451 of the 2510 corpus images, are byte-identical to a fresh render of their reference; the other 59
are the 19 Sep coordgen re-renders, byte-identical to cmage-work/overlap-rerender/new. A style
difference would confound the test, so the edited SMILES are written as small edits of the
parent's corpus SMILES and drawn the same way.

PUBCHEM. Identity is checked by full InChIKey from the ORCHESTRATING side only (never the reader),
and stored per row: kind A edits may well exist as impurities or research compounds (that is not
the same as being a drug a model has seen drawn and named a thousand times); kind B must not.

The lane is sonnet_batch.py with SONNET_ARM=nov, which reads this file instead of the corpus.
"""
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from rdkit import Chem, RDLogger
from rdkit.Chem import rdMolDescriptors
from rdkit.Chem.Draw import rdMolDraw2D

RDLogger.DisableLog("rdApp.*")
HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "benchmarks" / "novel_set.json"
IMG = Path("/root/cmage-work/novel/corpus_rdkit_1500")
IMAGES_JSON = HERE.parent / "benchmarks" / "corpus_rows.json"   # private: wall/images.json gates the reference (8 Oct)
PNG_MAGIC = b"\x89PNG"

# kind A: (id, parent name, parent corpus key, edit, edited SMILES written from the parent's corpus SMILES)
A = [
    ("A01", "Clopidogrel", "clopidogrel_cid60606", "halogen swap: aryl Cl to Br",
     "COC(=O)[C@H](C1=CC=CC=C1Br)N2CCC3=C(C2)C=CS3"),
    ("A02", "Atorvastatin", "atorvastatin_cid60823", "halogen swap: aryl F to Cl",
     "CC(C)C1=C(C(=C(N1CC[C@H](C[C@H](CC(=O)O)O)O)C2=CC=C(C=C2)Cl)C3=CC=CC=C3)C(=O)NC4=CC=CC=C4"),
    ("A03", "Celecoxib", "celecoxib_cid2662", "substituent moved: tolyl methyl para to meta",
     "CC1=CC=CC(=C1)C2=CC(=NN2C3=CC=C(C=C3)S(=O)(=O)N)C(F)(F)F"),
    ("A04", "Fluoxetine", "fluoxetine_cid3386", "substituent moved: CF3 para to meta",
     "CNCCC(C1=CC=CC=C1)OC2=CC=CC(=C2)C(F)(F)F"),
    ("A05", "Imatinib", "imatinib_cid5291", "N to CH: the pyridin-3-yl becomes phenyl",
     "CC1=C(C=C(C=C1)NC(=O)C2=CC=C(C=C2)CN3CCN(CC3)C)NC4=NC=CC(=N4)C5=CC=CC=C5"),
    ("A06", "Loratadine", "loratadine_cid3957", "N to CH: the pyridine ring becomes benzene",
     "CCOC(=O)N1CCC(=C2C3=C(CCC4=C2C=CC=C4)C=C(C=C3)Cl)CC1"),
    ("A07", "Ondansetron", "ondansetron_cid4595", "methyl removed: the imidazole 2-methyl",
     "C1=NC=CN1CC2CCC3=C(C2=O)C4=CC=CC=C4N3C"),
    ("A08", "Diazepam", "diazepam_cid3016", "methyl added: para on the 5-phenyl",
     "CN1C(=O)CN=C(C2=C1C=CC(=C2)Cl)C3=CC=C(C)C=C3"),
    ("A09", "Paroxetine", "paroxetine_cid43815", "one stereocentre inverted: C3, trans to cis",
     "C1CNC[C@@H]([C@@H]1C2=CC=C(C=C2)F)COC3=CC4=C(C=C3)OCO4"),
    ("A10", "Sertraline", "sertraline_cid68617", "one stereocentre inverted: C1 (the amine), cis to trans",
     "CN[C@@H]1CC[C@H](C2=CC=CC=C12)C3=CC(=C(C=C3)Cl)Cl"),
    ("A11", "Ciprofloxacin", "ciprofloxacin_cid2764", "ring size: N-cyclopropyl to N-cyclobutyl",
     "C1CC(C1)N2C=C(C(=O)C3=CC(=C(C=C32)N4CCNCC4)F)C(=O)O"),
    ("A12", "Sildenafil", "sildenafil_cid135398744", "ring size: N-methylpiperazine to N-methyl-1,4-diazepane",
     "CCCC1=NN(C2=C1N=C(NC2=O)C3=C(C=CC(=C3)S(=O)(=O)N4CCCN(CC4)C)OCC)C"),
]
# kind B: (id, fragments, SMILES)
B = [
    ("B01", "thiazole amide, 4-hydroxypiperidine, pyridine",
     "Cc1nc(-c2ccc(F)cc2Cl)sc1C(=O)N1CCC(O)(CC1)c1cccnc1"),
    ("B02", "prolinamide, quinoline, difluoromethoxy",
     "O=C(Nc1cnc2ccccc2c1)[C@@H]1CCCN1C(=O)c1ccc(OC(F)F)cc1"),
    ("B03", "quinazoline, pyrrolidine, methylimidazole",
     "COc1cc2ncnc(N3CC[C@H](C3)n3ccnc3C)c2cc1C#N"),
    ("B04", "benzofuran, methylpiperazine sulfonamide",
     "CS(=O)(=O)N1CCN(Cc2cc3cc(Cl)ccc3o2)C[C@@H]1C"),
    ("B05", "pyrazole, indole carboxamide, cyclopropyl",
     "Fc1ccc(-n2nc(C3CC3)cc2NC(=O)c2cccc3[nH]ccc23)cc1"),
    ("B06", "benzimidazole, pyridine, oxolane",
     "CC(C)(O)c1ccc(cn1)-c1nc2cc(F)ccc2n1C[C@H]1CCOC1"),
    ("B07", "spiro azetidine-piperidine, bromopyrimidine, sulfonamide",
     "N#Cc1ccc(S(=O)(=O)N2CC3(C2)CCN(c2ncc(Br)cn2)CC3)cc1"),
    ("B08", "oxadiazole, cis-2,6-dimethylmorpholine, thiophene",
     "C[C@@H]1CN(C[C@H](C)O1)C(=O)c1ccc(-c2nc(-c3cccs3)no2)cc1"),
]

# kind C, HARD EDITS (29 Sep, Sam): parents are corpus drugs from the categories where CXMolScribe
# fails (macrocycles, dense-stereo steroids and bridged polycycles, glycosides, peptides), every one
# a CXMolScribe miss in the corpus. ONE edit each, placed in the hard part. An edit is either a
# literal substring swap on the parent's corpus SMILES (old, new: must occur exactly once), or
# ("invert", SMARTS): invert the chiral tag of the first atom of the first match.
# (id, parent name, parent corpus key, edit, (old, new) or ("invert", smarts))
C = [
    ("C01", "Artemisinin", "artemisinin_cid68827", "stereocentre inverted: C9 methyl, next to the lactone C=O",
     ("[C@H](C(=O)O[C@H]3", "[C@@H](C(=O)O[C@H]3")),
    ("C02", "Artesunate", "artesunate_cid6917864", "ester to amide: the C10 hemisuccinate O becomes NH",
     ("OC(=O)CCC(=O)O)C", "NC(=O)CCC(=O)O)C")),
    ("C03", "Azamulin", "azamulin_cid16072188", "stereocentre inverted: the C11 carbinol",
     ("[C@@H]1O)C", "[C@H]1O)C")),
    ("C04", "Bimatoprost", "bimatoprost_cid5311027", "stereocentre inverted: the ring 11-OH",
     ("C[C@H]([C@@H]1/C=C/", "C[C@@H]([C@@H]1/C=C/")),
    ("C05", "Buprenorphine", "buprenorphine_cid644073", "stereocentre inverted: the tertiary carbinol on the bridge",
     ("C[C@]([C@H]1C", "C[C@@]([C@H]1C")),
    ("C06", "Alclometasone dipropionate", "alclometasone_dipropionate_cid636374", "steroid methyl flipped: 16-alpha to 16-beta",
     ("[C@]1([C@@H](C[C@@H]2", "[C@]1([C@H](C[C@@H]2")),
    ("C07", "Ansamitocin P-3", "ansamitocin_p_3_cid5282049", "ester to amide: the C3 isobutyrate O becomes NH",
     ("OC(=O)C(C)C)C", "NC(=O)C(C)C)C")),
    ("C08", "Bocodepsin", "bocodepsin_cid118551244", "macrocycle ring size +1: CH2 inserted beside the thiazole",
     ("CC(=O)NCC2=NC(", "CC(=O)NCCC2=NC(")),
    ("C09", "Bryostatin 1", "bryostatin_1_cid5280757", "stereocentre inverted: the C26 carbinol",
     ("[C@@H](C)O", "[C@H](C)O")),
    ("C10", "Amphotericin B", "amphotericin_b_cid5280965", "sugar stereo swapped: the mycosamine C3' amine",
     ("invert", "[C;R;$(C[NH2])]")),
    ("C11", "Alpha-Cyclodextrin", "alpha_cyclodextrin_cid444913", "sugar stereo swapped: one glucose C2-OH of six (glucose to mannose)",
     ("invert", "[CH;R]([OH])[CH;R](O)O")),
    ("C12", "Alpha-Amanitin", "alpha_amanitin_cid9543442", "stereocentre inverted: the hydroxyproline 4-OH",
     ("C[C@H](CN4", "C[C@@H](CN4")),
    ("C13", "Avermectin B1a", "avermectin_b1a_cid6434889", "sugar stereo swapped: the terminal oleandrose 3''-OMe",
     ("O[C@H]7C[C@@H](", "O[C@H]7C[C@H](")),
    ("C14", "Alpha-Galactosylceramide", "alpha_galactosylceramide_cid2826713", "sugar stereo swapped: alpha anomer to beta",
     ("CO[C@@H]1[C@@H](", "CO[C@H]1[C@@H](")),
    ("C15", "Bremelanotide", "bremelanotide_cid9941379", "macrocycle ring size -1: the lactam lysine becomes ornithine",
     ("NCCCC[C@H]", "NCCC[C@H]")),
    ("C16", "2'3'-cGAMP", "2_3_cyclic_guanosine_monophosphate_adenosine_monophosphate_cid135564529",
     "sugar stereo swapped: the adenosine 2'-OH (ribose to arabinose)",
     ("[C@H]([C@@H](O5)N6", "[C@@H]([C@@H](O5)N6")),
    ("C17", "Everolimus", "everolimus_cid6442177", "stereocentre inverted: the pipecolate alpha-carbon (L to D)",
     ("[C@@H]3CCCCN3", "[C@H]3CCCCN3")),
    ("C18", "Tacrolimus", "tacrolimus_cid445643", "stereocentre inverted: the macrocycle carbon bearing the allyl",
     ("[C@@H](/C=C(/C1)\\C)CC=C", "[C@H](/C=C(/C1)\\C)CC=C")),
    ("C19", "Morphine", "morphine_cid5288826", "stereocentre inverted: the C6 allylic alcohol",
     ("[C@H](C=C4)O", "[C@@H](C=C4)O")),
    ("C20", "Oxytocin", "oxytocin_cid439302", "macrocycle ring size +1: Cys1 becomes homocysteine in the disulfide ring",
     ("CSSC[C@@H]", "CSSCC[C@@H]")),
]
# Parents of kind C that the s55c corpus lane has NOT read yet: read fresh, in their own reader
# (never beside their edits), from the corpus's own image. The other parents' readings come from
# the s55c lane itself (same prompt file, same gate).
P_FRESH = ["C17", "C18", "C19", "C20"]


def apply_edit(parent: str, how) -> str:
    if how[0] == "invert":
        m = Chem.MolFromSmiles(parent)
        hits = m.GetSubstructMatches(Chem.MolFromSmarts(how[1]))
        if not hits:
            raise SystemExit(f"invert: no match for {how[1]}")
        a = m.GetAtomWithIdx(hits[0][0])
        t = a.GetChiralTag()
        if t not in (Chem.ChiralType.CHI_TETRAHEDRAL_CW, Chem.ChiralType.CHI_TETRAHEDRAL_CCW):
            raise SystemExit(f"invert: matched atom {a.GetIdx()} is not a tetrahedral stereocentre")
        a.SetChiralTag(Chem.ChiralType.CHI_TETRAHEDRAL_CW if t == Chem.ChiralType.CHI_TETRAHEDRAL_CCW
                       else Chem.ChiralType.CHI_TETRAHEDRAL_CCW)
        return Chem.MolToSmiles(m)
    old, new = how
    if parent.count(old) != 1:
        raise SystemExit(f"edit anchor {old!r} occurs {parent.count(old)} times in the parent")
    return parent.replace(old, new)


def render_rdkit(smiles, S, out):
    """Verbatim: the corpus_rdkit_1500 renderer."""
    m = Chem.MolFromSmiles(smiles)
    if m is None:
        return False, "rdkit could not parse SMILES"
    try:
        d = rdMolDraw2D.MolDraw2DCairo(S, S)
        o = d.drawOptions()
        o.clearBackground = True
        o.maxFontSize = -1
        o.minFontSize = -1
        o.scaleBondWidth = True
        o.bondLineWidth = 2
        o.includeMetadata = False   # 8 Oct: RDKit otherwise writes the SMILES/molblock into the PNG
        rdMolDraw2D.PrepareAndDrawMolecule(d, m)
        d.FinishDrawing()
        data = d.GetDrawingText()
        if not data.startswith(PNG_MAGIC):
            return False, "renderer produced non-PNG"
        open(out, "wb").write(data)
        return True, ""
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def canon(s, stereo=True):
    return Chem.MolToSmiles(Chem.MolFromSmiles(s), isomericSmiles=stereo)


def pubchem(ik: str) -> dict:
    """Full-InChIKey identity lookup. Orchestrator side only; the reader never has this."""
    def get(url):
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            raise
    j = get(f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/inchikey/{ik}/cids/JSON")
    cids = (j or {}).get("IdentifierList", {}).get("CID", [])
    syn = []
    if cids:
        s = get(f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{cids[0]}/synonyms/JSON")
        syn = (s or {}).get("InformationList", {}).get("Information", [{}])[0].get("Synonym", [])[:3]
    time.sleep(0.3)
    return {"cids": cids, "synonyms": syn,
            "checked": time.strftime("%Y-%m-%d", time.gmtime())}


def build() -> int:
    corpus = {r["k"]: r for r in json.load(open(IMAGES_JSON))["rows"]}
    old = {r["k"]: r for r in json.load(open(OUT))["rows"]} if OUT.exists() else {}
    IMG.mkdir(parents=True, exist_ok=True)
    rows = []
    cdefs = [(i, pn, pk, ed, apply_edit(corpus[pk]["t"], how)) for i, pn, pk, ed, how in C]
    pdefs = [(f"P{i[1:]}", pn, pk, "unedited parent of " + i, corpus[pk]["t"])
             for i, pn, pk, ed, how in C if i in P_FRESH]
    for kind, defs in (("A", A), ("B", B), ("C", cdefs), ("P", pdefs)):
        for d in defs:
            i, smi = d[0], d[-1]
            k = f"novel_{i}"
            m = Chem.MolFromSmiles(smi)
            if m is None:
                raise SystemExit(f"{i}: unparseable {smi}")
            row = {"k": k, "kind": kind, "t": smi, "heavy": m.GetNumHeavyAtoms(),
                   "formula": rdMolDescriptors.CalcMolFormula(m),
                   "stereocentres": len(Chem.FindMolChiralCenters(m, includeUnassigned=True)),
                   "inchikey": Chem.MolToInchiKey(m)}
            if kind in ("A", "C"):
                _, pname, pkey, edit, _ = d
                parent = corpus[pkey]["t"]
                if canon(parent) == canon(smi):
                    raise SystemExit(f"{i}: the edit is the parent")
                row.update(n=f"{pname}, edited ({edit.split(':')[0]})", parent=pname, parent_key=pkey,
                           parent_t=parent, edit=edit,
                           stereo_only_edit=canon(parent, False) == canon(smi, False))
            elif kind == "P":
                _, pname, pkey, note, _ = d
                row.update(n=pname, parent=pname, parent_key=pkey, parent_t=smi, edit=note, of="C" + i[1:])
            else:
                row.update(n=f"De novo {i}", fragments=d[1])
            row["pubchem"] = (old.get(k, {}).get("pubchem")
                              if old.get(k, {}).get("inchikey") == row["inchikey"] else None) or pubchem(row["inchikey"])
            if kind == "B" and row["pubchem"]["cids"]:
                raise SystemExit(f"{i}: has a PubChem record {row['pubchem']['cids']}; pick another")
            if kind == "P":
                # the corpus's own file, byte for byte: this IS the image the corpus lane reads
                src = next(Path("/root/cmage-work").glob(f"cmage-img*/corpus_rdkit_1500/{d[2]}.png"))
                (IMG / f"{k}.png").write_bytes(src.read_bytes())
                ok, err = True, ""
            else:
                ok, err = render_rdkit(smi, 1500, IMG / f"{k}.png")
            if not ok:
                raise SystemExit(f"{i}: {err}")
            # the lane's row shape (sonnet_batch corpus rows): CXMolScribe fields filled by
            # novel_cx.py; None until it has run
            row.update(s=old.get(k, {}).get("s"), v=old.get(k, {}).get("v"), c=old.get(k, {}).get("c"))
            rows.append(row)
    OUT.write_text(json.dumps({"built": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                               "renderer": "corpus_rdkit_1500, includeMetadata off (byte-identical check passed)",
                               "rows": rows}, indent=1) + "\n")
    print(f"wrote {OUT}: " + ", ".join(f"{sum(r['kind'] == x for r in rows)} kind {x}" for x in "ABCP") + "; "
          f"images in {IMG}")
    for r in rows:
        print(f"  {r['k']} {r['heavy']:>2} HA  pubchem {r['pubchem']['cids'][:2] or 'none'}  {r['n']}")
    return 0


if __name__ == "__main__":
    if sys.argv[1:] == ["build"]:
        sys.exit(build())
    raise SystemExit(__doc__)
