# Round 7 PDF ground truth — cardiovascular, metabolic/diabetes and renal patents

Twenty-five recent English-language pharmaceutical patents, priority dates
2012–2024, one per drug, across three therapeutic areas: **cardiovascular** (10),
**metabolic/diabetes** (8) and **renal** (7). Selection provenance is in
`pdf_corpus_round7_manifest.json`; this file and `pdf_manifest_round7.json` are
the scoreable half, in the `pdf_manifest_expanded.json` schema that
`score_run.py` reads.

Nothing here was derived from a pipeline prediction. **Twenty-four of the
twenty-five documents have no text layer at all** — `pdftotext` returns 3
characters — so every structure was located by rendering pages with `pdftoppm`
at 45–400 dpi and reading them, with `tesseract` OCR of those renders used to
recover the printed names. The one exception, `EP3525784B1`, is a vector EPO B1.

Every resolved molecule needed two independent views to agree: a PubChem lookup
keyed on something **printed in the document** — an INN, a full systematic name,
or a compound code expanded elsewhere in the same text — **and** a reading of the
drawing. Where the document prints no name, the SMILES read off the drawing was
submitted to PUG-REST `/compound/smiles/` and accepted only when the returned
InChIKey matched the hand reading exactly. Every SMILES round-trips through RDKit
and its InChIKey was recomputed with RDKit and checked against PubChem's **at
manifest build time**. That build-time check is not ceremonial: it caught three
stereochemical transcription errors that reading had passed, one of which is
described under `WO2020051014A1` below.

## Every file is a page extract, and that is the point

The 25 originals total **1,210 pages and 66.5 MB**. The committed extracts total
**47 pages and 2,429,872 bytes** — an average of 94 KB, largest 237 KB. Pages
were chosen so that **every depiction on a kept page is catalogued here**, which
is what earlier rounds mostly could not say. Round 6 had to mark six of its ten
groups recall-only because most of what those documents drew was uncatalogued;
**all twenty-five round-7 groups are scoreable for precision as well as recall.**
A 209-page patent contributing two pages and one structure is a better benchmark
item than the whole grant, and it is 130× smaller.

## Counts

`drawn` counts **depictions on the kept pages** and is exact everywhere in this
round — every count was made box by box at full resolution, and there are no
estimates. `resolved`, `generic` and `unresolved` count **rows**, i.e. distinct
compounds. The four columns do not sum: a compound drawn four times contributes
4 to `drawn` and 1 to `resolved`.

| group | pages | drawn | resolved (`molecules`) | generic | unresolved |
|---|---|---|---|---|---|
| `EP3525784B1_sparsentan` | 2 | 10 | 8 | 0 | 0 |
| `US11078230B2_omaveloxolone` | 2 | 1 | 1 | 0 | 0 |
| `US11208391B2_tafamidis` | 1 | 4 | 4 | 0 | 0 |
| `US11370739B2_sacubitril` | 1 | 3 | 3 | 0 | 0 |
| `US11465970B2_roxadustat_intermediates` | 2 | 9 | 2 | 4 | 0 |
| `US11479577B2_chenodeoxycholic_acid` | 1 | 2 | 1 | 0 | 1 |
| `US11680058B2_aprocitentan` | 2 | 1 | 1 | 0 | 0 |
| `US12247024B2_aficamten` | 2 | 15 | 12 | 0 | 1 |
| `US12269811B2_omecamtiv_mecarbil` | 5 | 26 | 13 | 0 | 3 |
| `US20240238266A1_iptacopan` | 1 | 2 | 2 | 0 | 0 |
| `US20240246949A1_lanifibranor` | 2 | 1 | 1 | 0 | 0 |
| `US20240391897A1_obicetrapib` | 1 | 9 | 9 | 0 | 0 |
| `WO2020051014A1_tenapanor` | 2 | 7 | 4 | 0 | 2 |
| `WO2021137144A1_ertugliflozin` | 1 | 2 | 2 | 0 | 0 |
| `WO2022006427A1_vadadustat_intermediates` | 2 | 9 | 3 | 2 | 1 |
| `WO2022149161A1_bempedoic_acid` | 2 | 6 | 3 | 0 | 0 |
| `WO2023034364A1_vericiguat` | 3 | 1 | 1 | 0 | 0 |
| `WO2023052652A1_acoramidis` | 4 | 2 | 2 | 0 | 0 |
| `WO2023209729A1_imeglimin` | 2 | 5 | 4 | 1 | 0 |
| `WO2024022998A1_daprodustat` | 1 | 1 | 1 | 0 | 0 |
| `WO2024167899A1_milvexian` | 1 | 1 | 1 | 0 | 0 |
| `WO2024201358A1_pemafibrate` | 2 | 6 | 6 | 0 | 0 |
| `WO2024228213A1_danuglipron` | 1 | 1 | 1 | 0 | 0 |
| `WO2025056984A1_bexagliflozin` | 1 | 1 | 1 | 0 | 0 |
| `WO2025146705A1_resmetirom` | 3 | 1 | 1 | 0 | 0 |
| **total** | **47** | **126** | **87** | **7** | **8** |

**The denominator to quote with any recall figure from this round is 87**, and
unlike round 6 there is no recall-only subset to carve out — score all
twenty-five groups.

## Three schema decisions a reader must know

1. **Rows with no SMILES are not in `molecules`.** `score_run.py` calls
   `Chem.MolFromSmiles(m["smiles"])` on every entry and a `None` raises
   `TypeError` before the script's own error message. Generic, undefined and
   unresolved structures live in a sibling per-group `unscoreable` array, which
   the scorer ignores.
2. **Repeat drawings of one compound are collapsed to one row.** 2,3,5-trichloro-
   pyridine is drawn four times in `WO2022006427A1` and is one row; `page` lists
   every page.
3. **`unscoreable` in this round is dominated by a new category: name/drawing
   disagreement.** Four of the eight unresolved rows are cases where the caption
   and the picture describe different molecules and neither view can check the
   other. That is not the same as "no reference exists" — it is a refusal to pick
   a side. They are listed per document below.

`confidence` values used: `name_match`, `drawing_read`, `generic`, `unresolved`.
`pixel_verified` is `false` everywhere.

## The five findings worth carrying forward

### 1. A granted US patent draws its own drug substance wrong

`US12269811B2` (Amgen, *Synthesis of omecamtiv mecarbil*) draws the drug
substance three times. On p1 and p10 it is correct. In **Scheme 1 on p8** the
same box, captioned "Crystalline DS · 2HCl · H2O", carries an **acetyl**
(`Me-C(=O)-N`) where the molecule has a methyl carbamate (`MeO-C(=O)-N`), and an
all-carbon **p-tolyl** where the molecule has a 6-methylpyridin-3-yl. As drawn it
is 1-[3-[(4-acetylpiperazin-1-yl)methyl]-2-fluorophenyl]-3-(4-methylphenyl)urea,
a different compound. The same scheme also captions a plain **cyclohexane**
carboxylate as "Piperazine Nitro·HCl (PIPN)" — a ring with no nitrogen that
cannot form the drawn hydrochloride. Both were verified at 320 dpi and are not
downsampling artefacts; Schemes 2 and 3 on the following pages are correct.

Consequence for grading: a faithful reading of the p8 boxes is scored wrong
against the correct molecule, and the correct molecule is scored wrong against
the p8 boxes. Both are held in `unscoreable`. **This group is the corpus's first
document where the ground truth had to say "the patent is wrong here."**

### 2. Wrong stereo still resolves to a real, confidently wrong record — now on a
### symmetric dimer, where the two ends must agree

Round 6's lesson was one flipped `[C@H]`. Round 7 has four instances and one that
is worse:

- `WO2020051014A1` **tenapanor dihydrochloride**, 76 heavy atoms, symmetric. The
  first transcription in this manifest wrote one isoquinoline centre `[C@H]` and
  the other `[C@@H]`. That returns **CID 134153384**, a real PubChem record whose
  title spells out `(4S)…(4R)…;dihydrochloride` — same formula
  `C50H68Cl6N8O10S2`, same skeleton block `VFRAXTZDILCRKY`, nothing in the API
  response indicating anything is wrong. The correct (4S,4′S) salt is
  **CID 78131177**. **This was caught by the build-time InChIKey assertion, not
  by eye.**
- `US12247024B2` **(R)-1-azido-5-bromoindane** is CID 59179602; the (S) is
  CID 86638803. On this scan, at 150 dpi, the bold wedge that distinguishes them
  is indistinguishable from a hash. At 400 dpi it is obvious.
- `US12247024B2` **CBS oxazaborolidine catalyst**: printed name says "(3R)", but
  C3 bears two identical phenyls and is not a stereocentre, so the locant cannot
  be right as written; the drawn bold-wedge H at the ring fusion works out to
  3a*S* (CID 2734713) while the printed letter points at CID 9838490. Two real
  records, same skeleton block, views disagree → `unresolved`.
- `US11208391B2` **meglumine**: writing the chain `(2R,3R,4R,5R)` instead of the
  printed `(2R,3R,4R,5S)` gives InChIKey `MBBZMMPHUWSWHV-DBRKOABJSA-N`,
  CID 5745355, a real hexitol. Again caught at build time.

### 3. Four different ways to draw a salt, and one page that uses all four

Multi-component solids are the round's connective theme, and the notations do not
converge:

| document | how the second component is drawn |
|---|---|
| `WO2023052652A1` acoramidis | the bare word `HCl` set beside the ring — no dot, no bond |
| `US20240238266A1` iptacopan | two stacked words, `HCl` over `H2O` |
| `EP3525784B1` I-4 | inside the atom label itself: `NHHCl` |
| `EP3525784B1` I-6 | the six characters `2(COOH)2`, acid not drawn |
| `US11208391B2` tafamidis | a vertical **stack** of two complete structures, no connector |
| `WO2021137144A1` ertugliflozin | two complete structures **side by side**, no connector |
| `US20240391897A1` 1A, 1D | drawn **ion pairs**: circled ⊕ on N, separate circled ⊖ mesylate |
| `US20240391897A1` compound 3 | bracketed anion with a **subscript 2** and a Ca²⁺ outside |
| `WO2020051014A1` tenapanor di-HCl | ion pair, two ⊕NH and two separate ⊖Cl |

`US20240391897A1`'s p60 alone carries an ion pair, a condensed `.HCl`, and the
bracket-subscript hemicalcium. That last one is the sharpest: **the drawing
contains one obicetrapib skeleton and the molecule contains two**, and the
document says so in words at [0005] — "there are only half as many calcium atoms
as obicetrapib anions."

### 4. The wavy bond, and what it means for grading

`US11370739B2` draws two Boc-protected biphenyl intermediates with a **squiggly
bond** at the stereocentre — the standard notation for *configuration not
specified* — eight centimetres from a hashed wedge and a bold wedge on the same
page. This is a **positive assertion of undefinedness**, so the correct reference
is the stereo-unspecified PubChem record (CID 19427706 and CID 58027497), and
both resolve. A tool that reads the squiggle as a plain bond gets the right
answer; a tool that reads it as a wedge gets a different, real, wrong one. This
is the first wavy bond in the corpus.

### 5. Digits and letters printed inside the structure box

Round 6 flagged this once, on `US12018032B2`'s Fig. 33. `US11479577B2` p5 makes
it the whole page: a bare steroid skeleton overprinted with the numerals 1–27
**and** the ring letters A, B, C, D, and beside it chenodeoxycholic acid
overprinted with 1–24, at the same point size as the atom labels and inside the
same bounding box. The first of the two is captioned "General steroid numbering"
— a legend, not a compound — and is left `unresolved` deliberately: it is
nevertheless a complete drawable molecule (flat cholestane, C27H48) that does
return a PubChem hit, so emitting it is defensible and grading it either way
would punish a reasonable reading.

## Per document

### `EP3525784B1_sparsentan` — 10 drawn, 8 resolved
The round's only EPO B1 and its only document with a text layer. p4 draws
sparsentan with the sulfonyl condensed to the label **`O2S`**; p9's Scheme I
draws seven intermediates, six of them inside square brackets meaning *not
isolated*. Only the codes I-1…I-6 are printed — no intermediate has a chemical
name — so all seven are `drawing_read` confirmed by structure search, and all
seven matched exactly. One box carries **no identifier at all** (the mesylate,
labelled only `CH2OMs`), and I-6's counter-ion is not drawn: it is the six
characters `2(COOH)2`.

### `US11078230B2_omaveloxolone` — 1 drawn, 1 resolved
**139 numbered drawing sheets** (pp12–150 of the original) and exactly one
chemical structure, on p151. Not one sheet is chemical: luciferase bar charts,
XRPD, DSC, TGA. Four times the figure-class ratio of round 6's `US12018032B2`.
The drawn molecule is a pentacyclic triterpenoid with seven stereocentres, all at
ring fusions or quaternary carbons. **The title compound, bardoxolone methyl, is
never drawn** — the picture is its 2,2-difluoropropanamide analogue, and
resolving the title instead of the picture returns a real compound with the same
skeleton and the wrong C17 substituent.

### `US11208391B2_tafamidis` — 4 drawn, 4 resolved
Two composite depictions, each a **vertical stack of two complete structures with
no connector of any kind**. The printed name joins the components with an
**asterisk**: "…benzoxazole-6-carboxylic acid \* (2R,3R,4R,5S)-6-(methyl-amino)-
hexane-1,2,3,4,5-pentol". Four rows — the two composites and each free component
— so every segmentation outcome has somewhere to land. The identifier `E` for the
acetic acid adduct is printed at the far right margin, level with the drawing
rather than under it.

### `US11370739B2_sacubitril` — 3 drawn, 3 resolved
See finding 4. Three stereo notations within 8 cm: bold wedge, hashed wedge, wavy
bond.

### `US11465970B2_roxadustat_intermediates` — 9 drawn, 2 resolved, 4 generic
**The round's Markush stratum, and a mixed one.** Unlike round 6's all-generic
`US9463252B2`, this document draws generic and fully specified structures side by
side, same column, same size, same style: seven of nine depictions carry an
R1/R3/X variable and two — formulae (IV) and (V) — are complete molecules. A tool
that cannot tell them apart scores seven false positives on two pages.
**Roxadustat itself is named 30+ times and never drawn**, so there is no
roxadustat row: named-but-not-drawn is not a scoreable molecule for an OCSR
benchmark. Front page says "19 Claims, No Drawings", which as the corpus README
notes means no drawing *sheets*.
**Caveat.** Formula (IX) is drawn with an explicit `Br` on p1 and with the
variable `X` on p15 — the same formula number, two different depictions, one page
apart. Formula (V)'s regiochemistry rests on the drawing plus mechanistic
continuity with (IV); the alternative reading (7-phenoxy rather than 6-) is a
valid molecule that returns **CID 0**, which is a weak confirmation and is
recorded as such.

### `US11479577B2_chenodeoxycholic_acid` — 2 drawn, 1 resolved, 1 unresolved
See finding 5. Obeticholic acid, the compound in the title, is never drawn.

### `US11680058B2_aprocitentan` — 1 drawn, 1 resolved
Thirteen consecutive XRPD sheets **before** any text, then one structure on p14.
Contributes the corpus's only **sulfamide** (`H2N-SO2-NH-`) and a molecule with
two different pyrimidines and two different bromines, where swapping which ring
carries the aryl bromide gives a plausible isomer of the same formula.

### `US12247024B2_aficamten` — 15 drawn, 12 resolved, 1 unresolved
See finding 2. Two example pages, every depiction catalogued, twelve named
compounds including a **sulfoxide stereocentre** (compound 5, `(R)`-tert-butane-
sulfinamide) — the only one in the corpus.
**Caveat worth quoting.** Example 13's body text charges "(R)-1-amino-2,3-dihydro-
1H-indene-5-carbonitrile **hydrochloride**" while the drawing beside it shows the
**free base** with no HCl anywhere. Both are real compounds and both are rows in
this group; a tool that reads the picture is right to emit the free base.
Example 13 also prints `LRMS calculated for C15H14NO, 266.1 Da` for a compound
whose formula is C15H14N4O — the printed formula drops three nitrogens while the
printed mass is correct.

### `US12269811B2_omecamtiv_mecarbil` — 26 drawn, 13 resolved, 3 unresolved
See finding 1. Thirteen named compounds across Schemes 1–3, including
**piperazine itself** as a named impurity and a symmetric bis-nitrobenzyl
impurity (BISN·2HCl) whose two aryl groups are drawn in opposite orientations.
The third `unscoreable` row is **PMEC hemi-phosphate hemi-hydrate**, drawn with
the fractional labels `1/2 HPO4²⁻` and `1/2 H2O`: the text says the stoichiometry
is "about 2:1:1" and "may differ slightly … e.g. to a ratio of 6:4:3", so a SMILES
would assert an exact composition the document declines to assert. Same failure
class as round 6's zanubrutinib co-crystal.

### `US20240238266A1_iptacopan` — 2 drawn, 2 resolved
The two depictions are the same line art; the only difference is the two stacked
words `HCl` / `H2O`. PubChem files the monohydrate and the plain hydrochloride
under **one CID**, so name lookup alone cannot separate them — the water in that
row comes from the document's sentence at [0013], not from the API. The indole is
attached through its **4-position**, the least common attachment point.

### `US20240246949A1_lanifibranor` — 1 drawn, 1 resolved
One structure, eleven XRPD sheets. The trimmed file deliberately keeps the pages
in **reverse order** — structure page first, figure sheet second — which is the
opposite of the US layout convention and a small ordering trap.

### `US20240391897A1_obicetrapib` — 9 drawn, 9 resolved
See finding 3. Scheme 1 in full: nine boxes, nine rows, every one resolved.
**Caveat.** Compound 1D's reference is the **free base** while the drawing is the
**mesylate ion pair** — the two-component reading returns CID 0, no record
exists. A faithful reading of the ion pair will grade as a component-level match
at best. Two boxes are captioned "not isolated" and bracketed, and one of them is
the drug itself.

### `WO2020051014A1_tenapanor` — 7 drawn, 4 resolved, 2 unresolved
See finding 2. The largest molecule in the round (76 heavy atoms) drawn at a
**9:1 aspect ratio** across the full text width, where the atom labels are 6–8 px
tall at 150 dpi. Both `unscoreable` rows are name/drawing disagreements:
Scheme A's product is captioned "Tenapanor TFA salt" and contains **no acid
component at all** (verified at 350 dpi) and no stereo bond either, while two
centimetres below, Scheme B draws the corresponding TFA salt of Compound A with
two explicit `CF3COOH` labels — **the same document does it both ways on one
page**. The p2 systematic name carries no stereodescriptors while the p2 drawing
prints `(S)` at both centres and Scheme B uses bold wedges; the INN and the
picture agree and the printed name is silent. [0010] hedges the configuration in
words as "(S or R)" while the drawing commits.

### `WO2021137144A1_ertugliflozin` — 2 drawn, 2 resolved
A **co-crystal drawn as two complete molecules side by side with no connector** —
looser than a salt dot, because the second component is a full structure rather
than a label. Eleven contiguous wedged stereocentres across two boxes on a
bitonal scan with an oversized 2480×3508 pt media box.

### `WO2022006427A1_vadadustat_intermediates` — 9 drawn, 3 resolved, 2 generic, 1 unresolved
A **halogen triplet**: Compounds 6, 6a and 6b are three drawings identical except
for a two-character label (Cl / Br / F), three separate rows, no other cue to
fall back on. Formula (VI) and Compound 6 are the same picture differing only in
whether the 2-position reads `X` or `Cl` — the tightest generic/specific pair in
the corpus. Formula (I) is Markush **and** charged, with a bold `A` carrying a
circled ⊕. Compound 1 is drawn as an ion pair in its **quinoid resonance form**
and returns CID 0; the document's own phrase "or a tautomer thereof" concedes the
drawn form is not the only one intended. Several structures are set
**mid-sentence** with the paragraph running around them. Vadadustat itself is not
drawn on the kept pages.

### `WO2022149161A1_bempedoic_acid` — 6 drawn, 3 resolved
**The only ring-free stratum in the corpus.** Six acyclic C15 zigzags with
gem-dimethyl caps and a single ketone or hydroxyl in the middle: the entire
identity of each molecule is the **number of vertices**, a failure mode no
ring-containing document here can test. The same keto-diacid is drawn on facing
pages in two different acid notations (drawn `HO-C(=O)` on p2, condensed `HOOC`
on p3), which makes them a controlled pair.
**Caveat.** The document labels that keto-diacid `(III)` in the p3 scheme and in
Example-15 but `(II)` in the Example-1 and Example-2 headings. The name is
constant; only the roman numeral moves.

### `WO2023034364A1_vericiguat` — 1 drawn, 1 resolved
The **low-ink** stratum: the structure's bonds are about one third the stroke
weight of the surrounding body text, close to the noise floor of the bitonal
scan, while the text is solid black. One structure against thirteen XRPD sheets.

### `WO2023052652A1_acoramidis` — 2 drawn, 2 resolved
The **minimal salt cue**: Formula (B) is Formula (A) with the bare word `HCl` set
to the right of the pyrazole. Two rows separated by that typography alone.

### `WO2023209729A1_imeglimin` — 5 drawn, 4 resolved, 1 generic
**The racemate / single-enantiomer controlled pair.** Formula-I (p2) and formula
(IV) (p6) are the same triazine, the same substituents, the same `HCl` text; the
only difference is that p2's C6 methyl sits on a bold wedge and p6's is a plain
line. CID 54763513 (`UXHLCYMTNMEXKZ-PGMHMLKASA-N`) and CID 10176486
(`UXHLCYMTNMEXKZ-UHFFFAOYSA-N`) — same skeleton block, a few dozen black pixels
apart. A tool that normalises away wedge information collapses them into one row
and can only score half.
**Caveat.** Imeglimin's printed name is the **2-imino** tautomer while the drawing
is the **2-amino** tautomer, which is what PubChem stores. Following the name
rather than the picture produces a different InChI. Formula (V) is generic *by
omission*: the caption says "R-Imeglimin -L- amino acid salt" and the acid is
neither named nor drawn. The reagents are metformin hydrochloride — a second
marketed antidiabetic appearing as a starting material — and acetaldehyde diethyl
acetal, whose distinguishing methyl stroke is about six pixels long at 150 dpi.

### `WO2024022998A1_daprodustat` — 1 drawn, 1 resolved
A **tautomer pair in print**: the page names the drawn compound twice, once as
the 2,4,6-trioxo form (which the drawing shows) and once as the 6-hydroxy-2,4-
dioxo enol. Both names resolve; only one matches the picture. The patent's own
subject — a cocrystal of daprodustat free acid with its own alkali-metal salt —
is never drawn.

### `WO2024167899A1_milvexian` — 1 drawn, 1 resolved
The corpus's first **macrocyclic drug drawn inside a patent**. The 12-membered
ring closes through a pyridine C2, a pyrazole C5 and a lactam N-H, so the
macrocyclic bond path is not a visually obvious loop. The printed von Baeyer
macrocyclic name (`3-aza-1(4,2)-pyridina-2(5,4)-pyrazolacyclononaphan-4-one`) does
not resolve in PubChem's name index; only the INN does.

### `WO2024201358A1_pemafibrate` — 6 drawn, 6 resolved
A **Mitsunobu inversion drawn in full**: Formula-V is ethyl (2S)-2-hydroxy-
butanoate with its OH on a hashed wedge, and Formulae VI and I are the (2R)
products with the ether oxygen on a hashed wedge in the same orientation. The
descriptor changes because OH became OR, not because the drawing changed. The
(2S) ester of Formula-VI returns **CID 0** — an inverted reading here fails to
resolve rather than resolving to the wrong thing, which is the opposite of the
aficamten azide and worth contrasting with it.

### `WO2024228213A1_danuglipron` — 1 drawn, 1 resolved
One stereocentre in a 41-heavy-atom molecule, and it is on a **four-membered
oxetane**, drawn with a single hashed wedge whose hash marks overlap the ring
bonds at 150 dpi. The tromethamine salt the patent is about is discussed in words
on p3 and never drawn.

### `WO2025056984A1_bexagliflozin` — 1 drawn, 1 resolved
A **name/name conflict inside one document**: p3 prints five stereodescriptors
for the drug and p14 prints four for the same compound, silently dropping the
`2S` at the anomeric centre — the one that distinguishes a C-glycoside from its
epimer. The sugar's stereochemistry is carried by hash marks **inside the HO/OH
labels** rather than by drawn wedge bonds, so a wedge detector sees an achiral
pyranose. The cyclopropyl ether is a bare triangle with no atom labels.

### `WO2025146705A1_resmetirom` — 1 drawn, 1 resolved
Two adjacent ring nitrogens in each of two heterocycles, and in both cases only
**one** of the pair carries a substituent, so the identity turns on which one.
Medium-stroke counterpart to the vericiguat file's hairline drawing; the p1
abstract block carries a second, much smaller copy of the same structure.

## Validation performed

- All 87 `molecules` parse under RDKit, are RDKit-canonical, and their recomputed
  InChIKeys match both the recorded value and PubChem's for the recorded CID.
  This is asserted at manifest build time and the build fails otherwise.
- No group contains a duplicate `name` or a duplicate `smiles`; asserted at build
  time.
- All 15 `unscoreable` rows have `smiles: null`, `cid: null` and `basis: null`.
- Page counts in `pdf_manifest_round7.json` match `pdfinfo` on the committed
  files, and every committed file's SHA-256 is recorded in
  `pdf_corpus_round7_manifest.json` as well as in `../corpus/SHA256SUMS`.

## Notes on retrieval, for whoever adds round 8

Both round-6 routes still work, and there is a faster third.

- **EPO publication server**, unauthenticated, for any granted EP:
  `https://data.epo.org/publication-server/rest/v1.2/patents/EP<number>NWB1/document.pdf`.
  **B1 only** — an A1 request returns HTTP 500. Used for `EP3525784B1`.
- **A read-through proxy asked for HTML** reaches Google Patents where plain
  `curl` gets 503.
- **New and much faster:** the same proxy reaches
  `https://patents.google.com/xhr/query`, and each result carries a **`pdf`
  field holding the hashed patentimages path directly** — e.g.
  `"pdf":"78/93/01/3e38ee97220088/US12247024.pdf"`. Prefix
  `https://patentimages.storage.googleapis.com/` and plain `curl` fetches it.
  A search result becomes a download without ever fetching the patent page. That
  is how 24 of these 25 were retrieved.

Two operational caveats that cost time here:

- **The proxy truncates long JSON responses.** `json.loads` then fails on a cut
  string and the whole query looks like a miss. Parse the search output with a
  regex over `"patent":{` blocks instead; a truncated tail simply yields fewer
  rows.
- **Google rate-limits.** More than about two concurrent queries returns an HTML
  `Sorry...` interstitial that is not JSON at all. Queries were run serially with
  a 12 s gap and a 30 s backoff on failure.

And three process lessons:

- **Two OCR passes appending to the same output file produce interleaved page
  markers, and the result reads like a valid document.** Two background queues
  were briefly running on the same PDF; the merged text file had 115 `=== PAGE`
  markers for a 63-page document and attributed a paragraph from p2 to p13. The
  render of p13 disagreed, which is the only reason it was caught. **Check the
  marker count against `pdfinfo` before trusting an OCR file.**
- **Verify the patent number by opening the document**, as round 6 said — but
  also verify what the document is *about* from its own title page and not from a
  truncated OCR line. One candidate here was briefly mis-read as the wrong drug
  from a garbled line and corrected by reading the `(54) Title` field.
- **150 dpi is not enough to tell a bold wedge from a hashed one** on a USPTO
  bitonal scan. It was enough on every EPO and WIPO document tried. Where a
  stereocentre matters, render at 300–400 dpi before deciding.
