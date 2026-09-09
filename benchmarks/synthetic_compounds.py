#!/usr/bin/env python3
"""The compound list for the synthetic CXSMILES benchmark -- data, not logic.

Kept apart from make_synthetic_corpus.py so the corpus COMPOSITION can be read,
reviewed and argued with on its own. Every entry is a real compound resolvable
on PubChem by name; the generator turns each name into a CID, an isomeric
SMILES, an InChIKey and a formula at build time and records all four in the
manifest, so nothing here has to be trusted.

Six strata, chosen because each isolates a different failure family the document
corpus could not separate (benchmarks/FINDINGS.md sections 1-5):

  basic        small, no stereocentres, no abbreviations. THE FLOOR. If these
               are not near-ceiling something is broken upstream, so this
               stratum is a control on the corpus, not a result.
  stereo       three or more defined centres; wedge/hash bonds are drawn.
  abbreviated  drawn CONDENSED via rdAbbreviations, so the picture says OMe,
               CF3, CO2H. This is the only stratum that can grade an appendix,
               and the reason the corpus exists.
  complex      60+ heavy atoms, macrocycles, glycopeptides, polyketides.
  salt         counter-ions and permanent charges, drawn as the dot-separated
               multi-fragment species PubChem records.
  markush      explicit R1/R2 variables. No single molecule exists, so these are
               graded on the SKELETON ONLY and reported apart from the rest.

MARKUSH_SCAFFOLDS carry a `parent` name: the generator asserts the scaffold is a
substructure of that real drug, so an R-group skeleton cannot silently drift
into a molecule nobody draws.
"""

# ---------------------------------------------------------------- strata lists
# 22 basic: 12-24 heavy atoms, one fragment, net charge 0, no defined stereo.
BASIC = [
    "caffeine", "ibuprofen", "lidocaine", "metronidazole", "phenytoin",
    "warfarin", "melatonin", "temozolomide", "letrozole", "lamotrigine",
    "gabapentin", "propranolol", "metoprolol", "sulfamethoxazole",
    "trimethoprim", "thalidomide", "carbamazepine", "diphenhydramine",
    "ketamine", "theophylline", "minoxidil", "phenobarbital",
]

# 22 stereo: three or more defined tetrahedral centres.
STEREO = [
    "morphine", "codeine", "oxycodone", "naloxone", "testosterone",
    "estradiol", "progesterone", "cholesterol", "prednisolone",
    "betamethasone", "finasteride", "spironolactone", "lovastatin",
    "simvastatin", "amoxicillin", "cephalexin", "penicillin G", "quinine",
    "artemisinin", "doxycycline", "gemcitabine", "oseltamivir",
]

# 22 abbreviated: every one condenses to at least one label that is in BOTH
# RDKit's 37 default abbreviations and CXMolScribe's 75-entry vocabulary, so a
# correct appendix is a label the model can actually emit. Chosen for label
# spread (OMe CO2H CF3 CN NO2 OAc CO2Et Et iPr tBu nBu nPr NMe SMe CHO Ph),
# not just for count.
ABBREVIATED = [
    "aspirin", "atrazine", "atenolol", "albuterol", "anastrozole",
    "amlodipine", "benzocaine", "bicalutamide", "bosentan", "capsaicin",
    "amiodarone", "apixaban", "azathioprine", "candesartan", "articaine",
    "alogliptin", "atorvastatin", "benazepril", "camptothecin", "aldosterone",
    "celecoxib", "naproxen",
]

# 12 complex: macrocycles, glycopeptides, peptides, taxanes.
COMPLEX = [
    "paclitaxel", "vancomycin", "erythromycin", "azithromycin", "sirolimus",
    "everolimus", "vinblastine", "vincristine", "rifampicin",
    "amphotericin B", "oxytocin", "colistin A",
]

# 11 salt / charged / multi-fragment. Named as the marketed salt so PubChem
# returns the multi-fragment record rather than the free base.
SALT = [
    "metformin hydrochloride", "diclofenac sodium", "naproxen sodium",
    "sertraline hydrochloride", "ondansetron hydrochloride",
    "propranolol hydrochloride", "fluoxetine hydrochloride",
    "amlodipine besylate", "methylene blue", "sitagliptin phosphate",
    "tetraethylammonium chloride",
]

# ------------------------------------------------------------------- markush
# (name, SMILES with dummy atoms, [label per dummy in atom order], parent drug)
# The parent is the drug the scaffold must be a substructure OF, and it is
# picked so that every R position lands on a real atom: a dummy is a wildcard
# for an ATOM, so an R that is hydrogen in the parent cannot match, and an R on
# an aromatic ring-fusion carbon cannot match either (the query bond is single,
# the target bond aromatic). Both mistakes were made here first -- ciprofloxacin
# has an unsubstituted piperazine NH (enrofloxacin's N-ethyl matches) and
# naproxen's para position is a naphthalene fusion carbon (ibuprofen's
# isobutyl-bearing carbon matches).
# The dummies are written as [*:n] purely to fix their order; the generator
# clears the map numbers and sets `atomLabel` to the label, which is what RDKit
# draws and what MolToCXSmiles writes into the $-block.
MARKUSH_SCAFFOLDS = [
    ("fluoroquinolone core", "O=C(O)c1cn([*:1])c2cc(N3CCN([*:2])CC3)c(F)cc2c1=O",
     ["R1", "R2"], "enrofloxacin"),
    ("penicillin core", "[*:1]C(=O)NC1C(=O)N2C1SC(C)(C)C2C(=O)O",
     ["R1"], "penicillin G"),
    ("cephalosporin core", "[*:1]C(=O)NC1C(=O)N2C(C(=O)O)=C([*:2])CSC12",
     ["R1", "R2"], "cephalexin"),
    ("1,4-benzodiazepin-2-one core", "[*:1]N1c2ccc([*:2])cc2C(c2ccccc2)=NCC1=O",
     ["R1", "R2"], "diazepam"),
    ("barbiturate core", "[*:1]C1([*:2])C(=O)NC(=O)NC1=O",
     ["R1", "R2"], "phenobarbital"),
    ("sulfanilamide core", "Nc1ccc(S(=O)(=O)N[*:1])cc1",
     ["R1"], "sulfamethoxazole"),
    ("1,4-dihydropyridine core", "[*:1]OC(=O)C1=C(C)NC(C)=C(C(=O)O[*:2])C1c1ccccc1[N+](=O)[O-]",
     ["R1", "R2"], "nifedipine"),
    ("androstane core", "C[C@]12CC[C@H]3[C@@H](CCC4=CC(=O)CC[C@]43C)[C@@H]1CC[C@@H]2[*:1]",
     ["R1"], "testosterone"),
    ("2-arylpropionic acid core", "C[C@@H](C(=O)O)c1ccc([*:1])cc1",
     ["R1"], "ibuprofen"),
    ("4-anilinoquinazoline core", "[*:1]Nc1ncnc2cc([*:2])c(OC)cc12",
     ["R1", "R2"], "erlotinib"),
    ("guanine N9 core", "Nc1nc2c(ncn2[*:1])c(=O)[nH]1",
     ["R1"], "acyclovir"),
]

# ------------------------------------------------------------- page assignment
# 10 PDFs x 10 compounds. Nine groups are stratum-PURE so a prediction that
# matches nothing can still be attributed to a stratum by its group; the tenth
# mixes strata on one page, which is what a real document looks like, and is
# reported separately for exactly that reason.
PDFS = [
    ("synth_basic_1", "Small-molecule reference set, part 1",
     [("basic", n) for n in BASIC[0:10]]),
    ("synth_basic_2", "Small-molecule reference set, part 2",
     [("basic", n) for n in BASIC[10:20]]),
    ("synth_stereo_1", "Stereochemically defined compounds, part 1",
     [("stereo", n) for n in STEREO[0:10]]),
    ("synth_stereo_2", "Stereochemically defined compounds, part 2",
     [("stereo", n) for n in STEREO[10:20]]),
    ("synth_abbrev_1", "Compounds drawn with condensed substituent labels, part 1",
     [("abbreviated", n) for n in ABBREVIATED[0:10]]),
    ("synth_abbrev_2", "Compounds drawn with condensed substituent labels, part 2",
     [("abbreviated", n) for n in ABBREVIATED[10:20]]),
    ("synth_complex", "Macrocyclic, peptidic and polycyclic natural products",
     [("complex", n) for n in COMPLEX[0:10]]),
    ("synth_salt", "Salts, counter-ions and permanently charged species",
     [("salt", n) for n in SALT[0:10]]),
    ("synth_markush", "Generic scaffolds with variable substituents",
     [("markush", s[0]) for s in MARKUSH_SCAFFOLDS[0:10]]),
    ("synth_mixed", "Mixed set: all six strata on the same pages",
     [("basic", BASIC[20]), ("basic", BASIC[21]),
      ("stereo", STEREO[20]), ("stereo", STEREO[21]),
      ("abbreviated", ABBREVIATED[20]), ("abbreviated", ABBREVIATED[21]),
      ("complex", COMPLEX[10]), ("complex", COMPLEX[11]),
      ("salt", SALT[10]), ("markush", MARKUSH_SCAFFOLDS[10][0])]),
]

STRATA = ("basic", "stereo", "abbreviated", "complex", "salt", "markush")
