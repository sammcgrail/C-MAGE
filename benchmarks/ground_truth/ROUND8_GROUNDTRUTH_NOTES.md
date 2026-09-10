# Round 8 PDF ground truth — CNS, neurology, psychiatry, pain and anaesthesia

Twenty-five recent patent documents, priority dates 2011–2024, covering migraine,
epilepsy, Parkinson's disease, multiple sclerosis, narcolepsy, schizophrenia,
depression, tardive dyskinesia, Rett syndrome, acute pain, pruritus and general
anaesthesia. Selection provenance is in `pdf_corpus_round8_manifest.json`; this
file and `pdf_manifest_round8.json` are the scoreable half, in the
`pdf_manifest_expanded.json` schema that `score_run.py` reads.

Nothing here was derived from a pipeline prediction. Every structure was located
by reading the PDF — `pdftotext -layout` where it yields anything, `pdftoppm` page
renders at 130–400 dpi, and `tesseract` OCR everywhere else.

**Measure the text layer; do not infer it from the document class.** Thirteen of
these twenty-five extracts return **zero** characters from `pdftotext` and twelve
return between 1,400 and 4,500 characters per page — and the split does **not**
follow "scan versus vector", nor even "US versus WIPO". Ten of the US grants and
two US pre-grant publications carry an embedded OCR text layer that survives page
extraction, so their chemical NAMES are machine-readable while their STRUCTURES are
not — but **five other US grants in the same round (`US11820776B2`, `US11919905B2`,
`US11993581B2`, `US12071423B2` and `US12258348B2`) return nothing at all**, as do
two US pre-grant publications (`US20230181470A1`, `US20230338546A1`), and so do
five WIPO A1s including three *vector* ones (`WO2025122953A1`, `WO2023119327A1`,
`WO2023152711A1`) and the CIPO application `CA3224298A1`, whose glyphs are drawn as
outlines rather than set as text. Each group's `drawing_style` in the manifest now states
which it is, measured rather than assumed; an earlier draft of this file asserted
the opposite for fourteen of the twenty-five.

Every resolved molecule needed two independent views to agree: a
PubChem lookup keyed on something **printed in the document** — an INN, a full
IUPAC name, a company code, a CAS number — **and** a reading of the drawing. Where
the document prints no usable name, the SMILES read off the drawing was submitted
to PUG-REST and accepted only when the returned InChIKey matched the hand reading
exactly. Every SMILES round-trips through RDKit, its InChIKey was recomputed with
RDKit and checked against PubChem's, and **every stereocentre was checked with
RDKit's CIP assignment against the descriptor printed in the document.**

**Every file in this round is a page extract.** `pages_kept_from_original` in the
manifest records exactly which pages of each publication were kept. The twenty-five
originals total **1,207 pages and 89.2 MB**; the extracts are **224 pages and
16.1 MB**, and the largest single file is 1.37 MB.

## Counts

`drawn` counts **depictions on the kept pages**. `resolved`, `generic` and
`unresolved` count **rows** — distinct compounds, or named classes of depiction. The
columns do not sum: a compound drawn twenty times is one row.

| group | drawn | resolved (`molecules`) | generic | unresolved |
|---|---|---|---|---|
| `US11447448B2_solriamfetol` | 43\* | 15 | 1 | 3 |
| `US12071423B2_lasmiditan` | 47\* | 14 | 0 | 3 |
| `US11820776B2_remimazolam` | 34\* | 13 | 2 | 2 |
| `US20220402886A1_pitolisant` | 46\* | 13 | 2 | 0 |
| `US12258348B2_lumateperone` | 72\* | 11 | 1 | 2 |
| `US9718795B2_cariprazine` | 40\* | 11 | 0 | 2 |
| `US10358440B2_brexpiprazole` | 48\* | 9 | 1 | 1 |
| `US9630955B2_opicapone` | 66\* | 8 | 1 | 1 |
| `US11174272B2_soticlestat` | 220\* | 6 | 2 | 1 |
| `WO2023152711A1_cenobamate` | 38\* | 6 | 1 | 1 |
| `WO2025122953A1_suzetrigine` | 11 | 6 | 0 | 0 |
| `US10577433B2_sugammadex` | 9 | 5 | 1 | 1 |
| `US10588898B2_oliceridine` | 320\* | 5 | 1 | 2 |
| `US10899752B2_m1pam_benzoxazinones` | 600\* | 5 | 1 | 3 |
| `US11919905B2_benzodiazepine_anaesthetics` | 72\* | 5 | 1 | 2 |
| `US20230181470A1_xanomeline_trospium` | 2 | 5 | 0 | 1 |
| `US11993581B2_nav18_pyridazines` | 180\* | 4 | 1 | 2 |
| `US20210024461A1_esketamine` | 54\* | 4 | 0 | 2 |
| `US10844058B2_valbenazine` | 11\* | 3 | 0 | 2 |
| `US11111223B2_ozanimod` | 2 | 2 | 0 | 1 |
| `US20230338546A1_difelikefalin` | 150\* | 2 | 0 | 2 |
| `WO2023175632A1_rimegepant` | 2 | 2 | 0 | 1 |
| `CA3224298A1_trofinetide` | 1 | 1 | 1 | 1 |
| `WO2022217008A1_zavegepant` | 2 | 1 | 0 | 2 |
| `WO2023119327A1_ubrogepant` | 3 | 1 | 0 | 0 |
| **total** | **2073** | **157** | **17** | **38** |

\* **starred counts are estimates**, made from a 26–55 dpi contact sheet rather than
a box-by-box count at full resolution. They are flagged per group by
`structures_drawn_is_estimate`. No estimated number can move a score: recall is
computed over `molecules` and precision over what a pipeline emits, and both of
those are exact.

**The denominator to quote with any recall figure from this round is 157**, and only
if you score all twenty-five groups.

### Six groups must be scored recall-only

`US9630955B2_opicapone`, `US12258348B2_lumateperone`,
`US20230338546A1_difelikefalin`, `US11174272B2_soticlestat`,
`US10588898B2_oliceridine` and `US10899752B2_m1pam_benzoxazinones` each draw a large
gallery — between 66 and 600 depictions — of which only a handful are catalogued.
Every correct prediction of an uncatalogued gallery member is counted `wrong`, so
**precision over those six is a lower bound**. Each one says so in its own
`unscoreable` array, in those words. Excluding them leaves a recall denominator of
**120** across nineteen groups whose kept pages are catalogued close to
exhaustively.

## Three schema decisions a reader must know

1. **Rows with no SMILES are not in `molecules`.** `score_run.py` calls
   `Chem.MolFromSmiles(m["smiles"])` on every entry and a `None` raises `TypeError`
   before the script's own error message. Generic, variable-stoichiometry,
   no-PubChem-record, named-but-not-drawn and name-disagrees-with-drawing rows all
   live in a sibling per-group `unscoreable` array, which the scorer ignores.
2. **Repeat drawings of one compound are collapsed to one row.** Lasmiditan
   hemisuccinate is drawn six times and is one row; its `page` field lists all six.
3. **`unscoreable` also carries bookkeeping rows** describing a *set* of depictions
   — "the squiggly-fragment compound table", "forty-three drawing sheets, none of
   them chemistry" — so that the arithmetic between `drawn` and the row counts is
   legible rather than mysterious.

`page` numbers throughout refer to the **trimmed file in `benchmarks/corpus/`**, not
to the original publication. `pixel_verified` is `false` everywhere.

## The five findings worth reading even if you skip the rest

### 1. A patent that draws the wrong molecule beside a correct name
`US10899752B2_m1pam_benzoxazinones`, TABLE 1 row **Example 2**. The printed name is
`8-chloro-3-((1S,2S)-2-hydroxycyclohexyl)-7-methyl-6-((6-methylpyridin-3-yl)methyl)-2,3-dihydro-4H-1,3-benzoxazin-4-one`
and the printed mass is `401.1`. That name is C22H25ClN2O3, [M+H]+ 401.16, and it is
a real record, CID 124155830. **The structure drawn beside it is a different
molecule**: the N-substituent drawn is a 4-hydroxy**oxan**-3-yl, with a ring oxygen,
not a 2-hydroxycyclohexyl. The oxane reading is C21H23ClN2O4, [M+H]+ 403.14, returns
CID 0 — and it is the molecule of **Example 6**, whose own name and mass (403.1) are
printed one page later. The drawing beside row 2 is row 6's structure. Two views
(name, mass) agree against the third (drawing), so the row is `unresolved` by design.
A pipeline that reads that drawing faithfully will emit Example 6's molecule for
Example 2's row; that is the document's error, and no reference can grade it fairly.
Both pages are in the extract so the pair can be inspected.

### 2. The wrong enantiomer, twice, from a hand-written SMILES
`US10588898B2_oliceridine`. The oliceridine precursor
`2-[(9R)-9-(pyridin-2-yl)-6-oxaspiro[4.5]decan-9-yl]ethan-1-amine` was first pinned
to **CID 68314404**, which is the **(9S)** enantiomer — the hand-written SMILES's
chirality tag encoded the opposite configuration and PubChem returned a perfectly
plausible record with no warning. The same error propagated to two table compounds.
The correct records are CID 68314401, 68314127 and 68314514, with InChIKey stereo
layers `-OAHLLOKOSA-`, `-LJQANCHMSA-` and `-HXUWFJFHSA-` against the wrong ones'
`-HNNXBMFYSA-`, `-IBGZPJMESA-` and `-FQEVSTJZSA-`. Same skeleton block, same formula,
same mass. **The fix that catches this: derive every derivative's SMILES by editing
the parent's string in place, never by retyping the stereocentre**, and then confirm
with RDKit's CIP assignment against the printed descriptor. Note also that the CIP
letter at that carbon **changes between the amine (R) and some of its own
derivatives** purely because substituent priorities change — so "R" cannot be carried
between rows by hand either.

### 3. Same mass, different molecule, three times over
`US11174272B2_soticlestat` prints `374.2` for compound **44** (soticlestat itself,
`(4-benzyl-4-hydroxypiperidin-1-yl)(2,4'-bipyridin-3-yl)methanone`), for compound
**84** (`(3,4'-bipyridin-3'-yl)`, a positional isomer, identical formula
C23H23N3O2) and for compound **14** (`2-(pyrimidin-4-yl)pyridin-3-yl`, C22H22N4O2 —
not even an isomer, one carbon swapped for one nitrogen). All three are in the
extract. A mass check cannot separate them; only the drawn ring-nitrogen positions
can. `US10899752B2` does the same thing more quietly, printing `403.1` for two
different compounds.

### 4. The unsymmetrical 1,2,4-oxadiazole
Two groups in this round, `US9630955B2_opicapone` and `US11111223B2_ozanimod`, are
built on a 1,2,4-oxadiazole whose two carbons are **not** equivalent: C5 sits between
O1 and N4, C3 between N2 and N4. Writing the ring the other way round gives a
molecule of identical formula that is not the compound. In the opicapone scan the
single ring oxygen is one of the least legible atoms on the page. Both entries were
written the wrong way round on the first attempt and caught by the drawn-reading
check. The regiochemistry in both was finally settled on the **printed IUPAC name**,
not on the drawing. Score these two groups together.

### 5. Four different ways of drawing a salt, in one round
- **`0.5 H2SO4` as condensed text** beside the base (`WO2023175632A1_rimegepant`) —
  and PubChem's obvious name hit, "rimegepant sulfate" CID 71586738, is the marketed
  **sesquihydrate** with three waters that are not in the drawing. CID 76972049 is
  the anhydrous 2:1 salt actually drawn.
- **The counter-ion drawn twice** (`US12258348B2_lumateperone`, formula (IX) — and
  formula (III) on the facing page is the 1:1 salt with one copy).
- **A bracket with a subscript 2** around one counter-ion
  (`US10844058B2_valbenazine`).
- **A three-letter acronym**: every salt in `US20210024461A1_esketamine` is drawn as
  the ketamine skeleton followed by the literal text `.(S)-CSA` or `.(R)-CSA`,
  sometimes with a further `x H2O`. The camphorsulfonate is never drawn at all.

Add to those the **ion-pair** convention in `US9718795B2_cariprazine` (a circled
NH3+ beside a circled Cl-) and the **charged species with no counter-ion at all** in
`US20230181470A1_xanomeline_trospium`.

## Per document

Grouped by what each contributes. Full per-molecule `basis` and `note` text is in
`pdf_manifest_round8.json`; this section is the map.

### The dense synthetic routes — where most of the 157 molecules are

**`US12071423B2_lasmiditan`** — 47 drawn, 14 resolved. Eli Lilly's large-scale route
to lasmiditan hemisuccinate, granted 2024. Three complete numbered schemes plus six
worked Preparations. Four different lasmiditan species are drawn — free base,
hemisuccinate (2:1), acetate (1:1) and hydrochloride — and are four separate rows.
*Caveat:* the label `5a` denotes **two different molecules**, the acid chloride in
Scheme 1 and the primary amide in Scheme 3. *Second caveat:* a name lookup for
`2,6-dibromopyridine` can return **CID 10986, which is cadmium acetate**; the CID
here was pinned by structure search.

**`US11447448B2_solriamfetol`** — 43 drawn, 15 resolved, the largest single group.
Glenmark's solriamfetol process, and the reason it is so productive is an **impurity
table on one page with nine structures each beside its own printed IUPAC name**.
Eight of the nine resolve; only three of the nine names resolve *directly* at
PubChem, the rest had to be built from the name and structure-searched. Also carries
all four aroyl tartaric acid resolving agents — dibenzoyl-D and -L, di-p-toluoyl-D
and -L — as separate rows: same skeleton InChIKey block, different stereo layer.
*Caveat:* impurity **E** is `unresolved` because the printed name carries **no**
stereodescriptor while the drawing carries wedges at both centres. Impurity **G** is
`unresolved` because PubChem has no record at all for it (CID 0).

**`US11820776B2_remimazolam`** — 34 drawn, 13 resolved. Teva's remimazolam process.
*The caveat to quote:* formula **(IV)** is drawn **flat** at the head of Scheme 1 and
with an explicit **hashed wedge** in claim 1 — one document, one label, two different
molecules by any stereo-aware reading, and both are real PubChem records sharing the
InChIKey block `PITXBYGUVDYTBQ`. Both are catalogued, under different names.
*Second caveat, a tautomer one:* the compound (II)/(III)/(III-13) amidines are drawn
with the double bond **inside** the ring (N1=C2, exocyclic N–H) while PubChem
displays them with it **exocyclic**. InChI's mobile-H treatment maps the two onto one
record so the structure search succeeds, but only the SMILES recorded here
reproduces the drawing. *Third:* formulas (III) and (III-S) are drawn **identically**,
so no reading can tell the racemate label from the enantiopure one.

**`US20220402886A1_pitolisant`** — 46 drawn, 13 resolved, **zero unresolved**: the
only group in the round where every drawn species is either catalogued or explicitly
Markush. Includes the **deschloro** impurity series — pitolisant and
1-[3-(3-phenylpropoxy)propyl]piperidine differ by one chlorine atom and nothing else
— and a **spiro quaternary ammonium bromide**.

**`US12258348B2_lumateperone`** — 72 drawn, 11 resolved. Egis's route, four of whose
thirteen drawing sheets are full-page **schemes** rather than instrument plots.
Carries the cleanest **stoichiometry pair** in the corpus: formula (III) is the 1:1
tosylate and formula (IX) the 1:2, drawn on facing pages and differing only by
whether one or two counter-ions are drawn; the naphthalene-2-sulfonates repeat the
trick. Also draws the **cis racemate** (IV) as two separate structures under one
bracket, in different orientations — the situation in which a reader emits the same
molecule twice.

**`US9718795B2_cariprazine`** — 40 drawn, 11 resolved, and **the whole document is
kept** (11 pages, 896 KB, structures on ten of them). *The caveat to quote:* every
molecule is a **trans-1,4-disubstituted cyclohexane**, drawn with explicit bold and
hashed ring bonds and named "trans" in the text — and **PubChem has no
stereo-specified record for any of them**. `KPWSJANDNDDRMB-CALCHBBNSA-N` (trans
cariprazine) returns 404, and a structure search on the trans SMILES silently falls
back to the unspecified CID. **A faithful reading of these drawings scores `stereo`,
not `exact`.** That is a property of the reference. Also draws `OMs` and `NCO` as
condensed labels, the latter with its atoms in the reverse of bonding order.

**`US10358440B2_brexpiprazole`** — 48 drawn, 9 resolved. Cadila's process, with a
named starting-material and impurity gallery. Contains the round's other **spiro
quaternary ammonium** (formula III) and a 48-heavy-atom bis-adduct impurity.

**`US9630955B2_opicapone`** — 66 drawn, 8 resolved. Six full-page scheme sheets at
the coarsest scan resolution in the round. Draws the acid chloride **inside square
brackets** (a chemist's mark for a transient species — a non-molecular graphical
element inside the structure box) and pairs the N-oxide and des-N-oxide compounds
adjacently, so a reader that drops the `[N+]–[O-]` produces the wrong neighbour.

**`WO2023152711A1_cenobamate`** — 38 drawn, 6 resolved. The one page of fully
specified molecules carries the drug, the prior-art epoxide route and the arylketone;
everything else is a nineteen-formula Markush stratum with `PG`, `Lg`, `R`, `X` and
`M` variables. Cenobamate is the round's **tetrazole regiochemistry** test: the ring
is attached through **N2**, not N1.

**`WO2025122953A1_suzetrigine`** — 11 drawn, 6 resolved, from a **209-page**
application trimmed to four. Suzetrigine itself is **named throughout and never
drawn**; its four alkyne precursors are, inside claims 45 and 46. Contains the round's
only **silicon**, behind the condensed label `TMS`, and a **quaternary carbinol
stereocentre** whose mirror image has no PubChem record — the only reason that
assignment is safe.

**`US10577433B2_sugammadex`** — 9 drawn, 5 resolved, and by far the **largest
structures in the round**: eight-fold-symmetric γ-cyclodextrin macrocycles, 128 heavy
atoms and 32 stereocentres in a single box. The Markush formula (II) puts the letter
`X` at **eight positions at once**. Formula I draws its eight sodiums as free `Na+`
ions while formula III on the facing page hides its two inside the atom labels
`NaS` and `COONa`.

### The document-class and false-positive tests

**`US11111223B2_ozanimod`** — 2 drawn, 2 resolved. **The most extreme figure-class
document in the corpus**: twenty-five consecutive drawing sheets — about fifty XRPD,
DSC, TGA and DVS traces, particle-size distributions and a **polarised-light
photomicrograph** — and exactly two chemical structures in the entire grant. Four
decoy sheets are kept. A tool that equates "numbered drawing sheet" with "structure"
scores 25 false positives against a true count of 2.

**`US20230181470A1_xanomeline_trospium`** — 2 drawn, 5 resolved. Forty-three drawing
sheets, none of them chemistry, and **twenty-eight of them are formulation
SPECIFICATION TABLES typeset as numbered figures** — a figure class that appears
nowhere else in the corpus. FIG. 1 is an SEM micrograph. Both actual structures are
**cations with no counter-ion drawn**, differing from each other by one oxygen atom;
one has InChIKey suffix `-O` rather than `-N`, which is InChI recording the
protonation state. Xanomeline, its tartrate and trospium chloride are all named and
never drawn.

**`US10844058B2_valbenazine`** — 11 drawn, 3 resolved. Eighteen drawing sheets, one
of which is kept and is a **scanning electron micrograph** with a scale bar: a
photograph of matter, not a diagram. Draws four-wedge valbenazine and **flat
tetrabenazine on the same page**, which share a core and differ only at C2 — a direct
test of whether a reader transcribes wedges or ignores them.

**`CA3224298A1_trofinetide`** — 1 drawn, 1 resolved. Exactly one structure in
fifty-eight pages, and among the thirteen drawing sheets a **3-D ORTEP
thermal-ellipsoid plot** — every atom a shaded ellipsoid, no bonds in the page plane,
no element labels. It genuinely depicts the molecule and cannot be read as one. The
"trofinetide hydrate" is defined as `trofinetide · xH2O` with the document stating it
"does not have a fixed stoichiometry".

**`WO2023175632A1_rimegepant`** (164 KB, the smallest file in the round),
**`WO2023119327A1_ubrogepant`** (172 KB) and **`WO2022217008A1_zavegepant`**
(168 KB) are three cheap, clean single-structure gepant documents kept as a matched
set: one salt drawn with a condensed `0.5 H2SO4`, one free base with a
**quaternary spiro stereocentre**, and one 55-heavy-atom drawing running the width of
the page. Each is paired with two or three instrument sheets as decoys.

### The fragment, gallery and abbreviation strata

**`US11993581B2_nav18_pyridazines`** — 180 drawn, 4 resolved. FIG. 1 draws four
complete **named clinical compounds** (PF-01247324, PF-04531083, PF-06305591 and one
captioned "**Similar to** DSP-2230" — a hedge, and the reference there was pinned by
reading the drawing, not by trusting the caption). The compound table is the round's
**squiggly-fragment stratum**: each row draws only the variable fragment terminated
by a wavy open valence, with the complete IUPAC name and an ES+ mass in adjacent
columns. The molecule is fully specified *in text* while the drawing is a radical.
Same failure mode as the round-6 auristatin fragments, here paired with a complete
name for every entry.

**`US10588898B2_oliceridine`** — 320 drawn, 5 resolved. Trevena's genus patent, with a
Markush whose **ring size is itself a variable** (`( )n`, n = 1–2) and a 500-row
name-plus-structure example table. Oliceridine is in it under its IUPAC name only —
the INN post-dates the filing. Twenty-six pages of the original are a **bare list of
1,200 chemical names with no structures at all** and were deliberately dropped.
Carries the pyrazol-3-yl / pyrazol-4-yl near-miss described above.

**`US11174272B2_soticlestat`** — 220 drawn, 6 resolved. Takeda's CH24H genus. Draws a
prior-art formula in which **an entire heterocyclic ring is replaced by the letters
`Ht` inside a circle** — the strongest form of the abbreviation-bracket problem in the
corpus, worse than round 4's thienamycin `Th`. Soticlestat's presence was confirmed
independently: PubChem's soticlestat record CID 73437845 lists `US-11174272-B2` among
its patent cross-references.

**`US10899752B2_m1pam_benzoxazinones`** — 600 drawn, 5 resolved. Takeda's M1 PAM
genus, and the source of finding #1. Five of its unresolved rows are named in
**carbohydrate nomenclature** (`1,5-anhydro-2,4-dideoxy-…-threo-pentitol`, which is a
4-hydroxyoxan-3-yl) and one of those carries the parenthetical "(optical isomer)" in
place of a stereodescriptor, which specifies nothing.

**`US20230338546A1_difelikefalin`** — 150 drawn, 2 resolved. Difelikefalin is a
**tetrapeptide drawn atom by atom** in extended zig-zag with a hashed wedge at each of
four alpha carbons; the D-configuration that makes it peripherally restricted is
stated only in the shorthand caption `D-Phe-D-Phe-D-Leu-D-Lys-…`, not by the wedges.
A fifth candidate centre — the 4-aminopiperidine-4-carboxylic acid quaternary carbon
— is **not** a stereocentre because the ring is symmetric; a tool that treats it as
one emits a spurious descriptor. The 150-row analogue gallery is not catalogued.

**`US11919905B2_benzodiazepine_anaesthetics`** — 72 drawn, 5 resolved. Explicit
remimazolam analogues; pairs with `US11820776B2`. **Its unresolved rows are the
interesting ones**: compounds 1-B, 1-C and 1-D are fully drawn *and* carry a printed
ESI-MS, and the hand reading reproduces the printed mass to 0.01 Da every time —
including 1-C, where the calculated 410.13 for the drawn **hydrochloride** (free base
374.15 + HCl 35.98) matches exactly, confirming the counter-ion as well as the
skeleton. But PUG-REST returns CID 0 for all of them, so the two-independent-views
rule is not met and they are left unresolved rather than entered on a hand reading
alone. A future round with a mass-based acceptance rule could promote them.

### The stereochemistry set

**`US20210024461A1_esketamine`** — 54 drawn, 4 resolved. Janssen's CSA resolution.
Racemic ketamine, esketamine and arketamine are drawn **on the same page in the same
orientation**, differing only in whether the N-methylamino bond is absent, bold or
hashed. All three share the InChIKey block `YQEZLKZALYSWHR` — the tightest stereo
cluster in the round. A tool that ignores stereo emits one molecule three times and
matches only the racemate row.

## One overlap with a concurrent round, declared

`US11111223B2_ozanimod` (this round) and `US11680050B2_ozanimod` (round 10) are two
**different patents about the same drug**, added within fifteen minutes of each other
by two agents working concurrently. There is no filename or patent-number collision
and `score_run.py` matches per group, so nothing breaks — but **`ozanimod` is now
double-weighted in any recall figure computed across the whole corpus**. Count it
once. The two are kept because they are different document classes: round 10's is a
one-molecule entry, while this one exists for its twenty-five non-chemistry drawing
sheets. The corpus already had a precedent for two documents on one drug —
`US6699871B2_sitagliptin` and `US7326708B2_sitagliptin_phosphate`.

## Retrieval — what worked, for whoever adds round 9

Both round-6 routes still work and both were used.

- **EPO publication server**, unauthenticated, for any granted EP:
  `https://data.epo.org/publication-server/rest/v1.2/patents/EP<number>NW<kind>/document.pdf`
  — **B1 only**; an A1 request returns HTTP 500. Confirmed this session
  (`EP3494109NWB1` → 200, 483 KB). This is why round 8 has no **tavapadon**: the only
  usable document is an EP **A1**.
- **A read-through proxy asked for HTML** reaches Google Patents where plain `curl`
  gets 503.

**The improvement worth carrying forward:** the same proxy reaches
`https://patents.google.com/xhr/query`, and the JSON it returns carries a **`pdf`
field holding the hashed `patentimages` path for every hit**. One search therefore
yields directly fetchable URLs and the per-patent page fetch can be skipped entirely.
Every PDF in this round was fetched that way.

Three practical limits:

- Google **rate-limits the proxy** after roughly six queries in quick succession —
  the response is an HTML page titled `Sorry...` rather than JSON. Spacing searches
  16–20 s apart was reliable.
- **PubChem PUG-REST throttles** under four concurrent agents. Expect
  `PUGREST.ServerBusy`; back off 4–30 s and retry.
- **Long or paren-heavy SMILES in the URL path** trigger an NCBI `WWW Error 803`.
  POST the SMILES as form data to
  `https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/smiles/property/...` instead —
  that never failed once.

**And a query-formulation warning that cost an hour.** For about half these drugs the
phrasing *"process for the preparation of `<drug>`"* causes the drug name to be
dropped from the query entirely: cariprazine, brexpiprazole, opicapone, ozanimod,
pitolisant and sugammadex all returned the **same six irrelevant hits** with totals in
the thousands. The bare drug name plus one distinguishing chemical word, with
`language=ENGLISH&type=PATENT` in the `url` parameter, works reliably.
