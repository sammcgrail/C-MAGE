#!/usr/bin/env python3
"""Composition and RENDER conditions for the v2 synthetic CXSMILES benchmark.

Data, not logic -- the shape of the corpus should be arguable without reading a
line of the generator. What changed from v1 (benchmarks/synthetic_compounds.py,
100 compounds) and why:

WHY V2 EXISTS
-------------
v1 answered "does the pipeline read a drawn structure" with n = 11-13 in four of
its six strata. At that size a 5/12 and a 12/22 cannot be told apart from noise,
and three questions could not be asked at all:

  1. HOW MUCH does stage 2 erase, as a function of how the page is drawn?
     v1 measured the erasure at exactly ONE drawing density, so it produced a
     point, not a gradient, and a point cannot support a recommendation.
  2. WHERE does stereo recall break -- at one centre, or at eight?
     v1's `stereo` stratum was a single bucket of ">= 3 defined centres".
  3. Is `complex` bad because it is BIG or because it is topologically hard?
     v1's `complex` predicate was `heavy >= 55 OR largest ring >= 13`, which is
     a disjunction of the two variables it needed to separate.

So v2 keeps every v1 stratum (so the two corpora can be compared directly),
raises each to n >= 60, and adds three CROSSED factors measured on the SAME
compounds drawn more than once. Crossing matters: a between-compound comparison
of "dense pages" against "sparse pages" confounds the page with the molecules on
it, and the whole point is that the molecule is held fixed.

THE THREE CROSSED FACTORS
-------------------------
  density   the same 48 compounds drawn 1, 4, 6, 12 and 20 to a page. Everything
            else identical. Structures shrink as the grid tightens because
            RDKit fits the drawing to its box, so this varies ink-per-structure
            and structure-to-structure distance together -- which is exactly
            what a real journal page varies.
  ink       the same 48 compounds at bondLineWidth 1.0, 2.0 and 3.5, at a FIXED
            6-per-page grid. Same geometry, different amount of ink on the same
            lines. This separates "thin lines are lost" from "small drawings are
            lost", which density alone cannot.
  spacing   the same 48 compounds at 6-per-page, cells packed edge to edge
            instead of separated by a 50 x 84 unit gutter. Each DRAWING is
            pixel-identical to its `std` twin; only the distance between
            neighbours changes. Isolates segmentation bleed from drawing size.

The density arm draws no per-structure caption. `tight` would collide with one,
and a caption is ink near a structure -- a confound in an experiment about ink.
The arm therefore contains its own `dens_std` control drawn under exactly the
arm's conventions, and density numbers are compared only inside the arm.

THE VOCABULARY ARM
------------------
Same 48 abbreviated compounds drawn twice, once with the label RDKit's
abbreviation table produces (`CO2Et`, `OAc`, `NHAc` ...) and once with that
label MIRRORED (`EtO2C`, `AcO`, `AcHN` ...). A mirrored label is how a chemist
writes the same superatom when it attaches from the other side, so the picture
is equally correct either way -- but CXMolScribe's 75-entry vocabulary contains
the first form and not the second. The molecule graph is byte-identical between
the two drawings; only the label string differs. Any gap is the vocabulary and
nothing else.

MIRRORS is checked at build time in both directions: the canonical form must be
IN CXMolScribe's vocabulary and the mirrored form must be OUT of it. If the
model ever learns `EtO2C` this file fails its own gate rather than quietly
reporting a stale result.
"""

# ---------------------------------------------------------------- page geometry
# All units are 1/200 inch = one pixel as stage 1 will see the page, because
# pdf2image renders at its default 200 dpi (MERMaid/src/visualheist/
# methods_visualheist.py:_pdf_to_image calls convert_from_path with no dpi).
DPI = 200
PAGE_W, PAGE_H = int(8.5 * DPI), int(11 * DPI)          # US Letter, 1700 x 2200
FIXED_BOND_LENGTH = 80                                   # 0.40 in at 200 dpi

# name -> (rows, cols, box_w, box_h, gutter_x, gutter_y, caption)
# box_* is the drawing box handed to RDKit; gutter_* is white space BETWEEN
# boxes. The grid is centred on the page under the title.
LAYOUTS = {
    # v1's geometry exactly, so the core corpus is comparable to the 100-compound run
    "g6":  dict(rows=3, cols=2, box_w=700, box_h=552, gut_x=50, gut_y=84, caption=True),
    "g1":  dict(rows=1, cols=1, box_w=1400, box_h=1700, gut_x=0, gut_y=0, caption=False),
    "g4":  dict(rows=2, cols=2, box_w=700, box_h=850, gut_x=50, gut_y=84, caption=False),
    "g6n": dict(rows=3, cols=2, box_w=700, box_h=552, gut_x=50, gut_y=84, caption=False),
    "g12": dict(rows=4, cols=3, box_w=466, box_h=430, gut_x=30, gut_y=40, caption=False),
    "g20": dict(rows=5, cols=4, box_w=350, box_h=350, gut_x=20, gut_y=24, caption=False),
    # identical boxes to g6n, gutters removed: same drawings, neighbours touching
    "g6tight": dict(rows=3, cols=2, box_w=700, box_h=552, gut_x=0, gut_y=0, caption=False),
}

# name -> (layout, bondLineWidth). `std` is the core corpus's condition.
RENDER = {
    "std":       ("g6",      2.0),
    "dens_std":  ("g6n",     2.0),
    "dens_1":    ("g1",      2.0),
    "dens_4":    ("g4",      2.0),
    "dens_12":   ("g12",     2.0),
    "dens_20":   ("g20",     2.0),
    "ink_thin":  ("g6n",     1.0),
    "ink_thick": ("g6n",     3.5),
    "space_tight": ("g6tight", 2.0),
}
DENSITY_ARM = ["dens_1", "dens_4", "dens_std", "dens_12", "dens_20"]
INK_ARM = ["ink_thin", "dens_std", "ink_thick"]
SPACING_ARM = ["dens_std", "space_tight"]

# structures per page implied by each condition, for the report
PER_PAGE = {k: LAYOUTS[v[0]]["rows"] * LAYOUTS[v[0]]["cols"] for k, v in RENDER.items()}

# ------------------------------------------------------------------- vocabulary
# canonical label produced by RDKit's table -> the same superatom written
# mirrored. Left side must be IN CXMolScribe's 75-entry vocabulary, right side
# must be OUT of it; make_synthetic_corpus_v2.py asserts both.
MIRRORS = {
    "CO2Et": "EtO2C",
    "COOEt": "EtOOC",
    "CO2H":  "HOOC",
    "COOH":  "HOOC",
    "OAc":   "AcO",
    "NHAc":  "AcHN",
    "OMe":   "CH3O",
    "OEt":   "C2H5O",
    "SMe":   "H3CS",
    "CHO":   "HCO",
    "CCl3":  "Cl3C",
    "SO3H":  "HO3S",
    "OiBu":  "iBuO",
}

# RDKit labels that CXMolScribe has never heard of even unmirrored. Present so
# the abbreviated stratum can be split into "the model could know this" and
# "the model cannot know this" without changing a single pixel of the drawing.
RDKIT_ONLY_LABELS = ["nDec", "nNon", "nOct", "nHept", "nHex", "nPent", "iPent",
                     "N(OH)CH3", "NO", "CO2-", "COO-"]

# ------------------------------------------------------------------- strata
# Predicates are enforced in make_synthetic_corpus_v2.py:stratum_ok. Stated here
# so the composition can be checked against the claim without reading it.
#
#   basic        0 defined centres, 1 fragment, net charge 0, <= 26 heavy atoms,
#                drawn uncondensed. THE CONTROL: near-ceiling on clean crops or
#                the generator has changed something.
#   stereo       >= 1 defined tetrahedral centre, drawn uncondensed. Bucketed by
#                DEPTH: 1, 2-3, 4-7, 8+ centres, >= 15 per bucket.
#   abbreviated  drawn condensed, >= 1 superatom. Bucketed by DEPTH: 1, 2, 3+
#                superatoms, and split in/out of CXMolScribe's vocabulary.
#   complex      macrocyclic (largest ring >= 12) or >= 51 heavy atoms or >= 4
#                rings in one fused system. `topology` records WHICH, so size and
#                ring topology can finally be reported apart.
#   salt         >= 2 fragments or net charge != 0.
#   markush      explicit R-group dummies. No single molecule exists; skeleton
#                graded only. Generated by cutting a real drug (see
#                select_synthetic_v2.py:make_markush), so every scaffold is a
#                substructure of a named parent BY CONSTRUCTION rather than by
#                assertion -- v1 hand-wrote 11 and two of them were wrong.
TARGETS = {
    "basic": 66, "stereo": 120, "abbreviated": 120,
    "complex": 66, "salt": 66, "markush": 66,
}
STRATA = tuple(TARGETS)

SIZE_BUCKETS = [("<=15", 0, 15), ("16-30", 16, 30), ("31-50", 31, 50), ("51+", 51, 10 ** 6)]
STEREO_BUCKETS = [("s0", 0, 0), ("s1", 1, 1), ("s2-3", 2, 3), ("s4-7", 4, 7), ("s8+", 8, 10 ** 6)]
ABBREV_BUCKETS = [("a1", 1, 1), ("a2", 2, 2), ("a3+", 3, 10 ** 6)]

# how many compounds are re-drawn in the crossed arms
PANEL_N = 48
VOCAB_N = 60
