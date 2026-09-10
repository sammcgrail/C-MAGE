# Round 10 PDF ground truth — immunology, respiratory, dermatology, ophthalmology

Twenty-five recent pharmaceutical patents, priority dates 2015–2024, in four
therapeutic areas: **immunology and inflammation** (9), **respiratory** (6),
**dermatology** (5) and **ophthalmology** (5). Selection provenance is in
[`pdf_corpus_round10_manifest.json`](pdf_corpus_round10_manifest.json); this file
and [`pdf_manifest_round10.json`](pdf_manifest_round10.json) are the scoreable
half, in the `pdf_manifest_expanded.json` schema that `score_run.py` reads.

Nothing here was derived from a pipeline prediction. Every structure was located
by reading the PDF — `pdftotext -layout` on the eleven documents that have a text
layer, `pdftoppm` page renders at 42–400 dpi on the fourteen that do not. Every
resolved molecule needed **two independent views to agree**: a PubChem record
reached from something *printed in the document*, and a reading of the drawing.

## One new tool, and the reference it corrected

New this round: printed IUPAC names were parsed with **OPSIN** (`py2opsin` 1.2.0)
instead of being handed to PUG-REST `/compound/name/`. The chain is

```
printed name → OPSIN → RDKit canonical SMILES → InChIKey → /compound/inchikey/ → CID
```

It matters because `/compound/name/` can substitute a *different molecule* without
saying so. **`/compound/name/nintedanib` does not return nintedanib.** It returns
CID 135423438, the 2-hydroxyindole (carbonimidoyl) **tautomer** — same formula
C31H33N5O4, same forty heavy atoms, no stereocentre at all, and nothing in the
response flags the swap. The correct record, CID 9809715, had to be reached from
the printed `(Z)` name. OPSIN also independently confirmed the two steroids
(vamorolone, clascoterone) centre by centre, which is the standard a steroid
needs. It does **not** parse INNs — `tapinarof`, `ozanimod`, `lotilaner` are all
unparseable — so the two routes are complementary, not interchangeable.

## Counts

`drawn` counts **depictions**. `resolved`, `generic` and `unresolved` count
**rows** — distinct compounds, or named classes of depiction. The columns do not
sum, for the same reason they do not in round 6: a compound drawn forty times is
one row.

| group | area | drawn | resolved | generic | unresolved |
|---|---|---|---|---|---|
| `US10526350B2_baricitinib` | immunology | 37 | 9 | 0 | 0 |
| `US10815227B2_filgotinib` | immunology | 78\* | 16 | 0 | 2 |
| `US11613529B2_deucravacitinib` | immunology | 31\* | 8 | 0 | 2 |
| `US11680050B2_ozanimod` | immunology | 2 | 1 | 0 | 0 |
| `US12049463B2_tolebrutinib` | immunology | 3 | 1 | 0 | 0 |
| `US20230002439A1_vamorolone` | immunology | 12\* | 1 | 0 | 1 |
| `WO2020261041A1_abrocitinib` | immunology | 1 | 1 | 0 | 0 |
| `WO2021005484A1_upadacitinib` | immunology | 120\* | 9 | 1 | 1 |
| `WO2023152691A1_ponesimod` | immunology | 60\* | 9 | 0 | 1 |
| `CN118530179A_elexacaftor` | respiratory | 16\* | 6 | 0 | 0 |
| `EP3344607B1_selexipag` | respiratory | 4 | 3 | 0 | 0 |
| `EP3747864B1_nintedanib` | respiratory | 30\* | 6 | 0 | 1 |
| `US11491155B2_ensifentrine` | respiratory | 1 | 1 | 0 | 0 |
| `WO2022049604A1_revefenacin` | respiratory | 60\* | 3 | 1 | 1 |
| `WO2022083476A1_gefapixant` | respiratory | 3 | 1 | 0 | 0 |
| `EP4302831B1_tirbanibulin` | dermatology | 58\* | 13 | 4 | 1 |
| `US11597692B2_tapinarof` | dermatology | 110\* | 8 | 0 | 1 |
| `US20250215046A1_clascoterone` | dermatology | 12\* | 3 | 1 | 1 |
| `WO2024180493A1_delgocitinib` | dermatology | 1 | 1 | 0 | 0 |
| `WO2024182418A1_trifarotene` | dermatology | 55\* | 10 | 1 | 1 |
| `US10584100B2_netarsudil` | ophthalmology | 1 | 1 | 0 | 0 |
| `US10870621B2_latanoprostene_bunod` | ophthalmology | 27\* | 8 | 0 | 0 |
| `US11345664B2_netarsudil_process` | ophthalmology | 25\* | 2 | 3 | 1 |
| `US20220009893A1_reproxalap` | ophthalmology | 1 | 1 | 0 | 0 |
| `WO2023107660A1_lotilaner` | ophthalmology | 1 | 1 | 0 | 0 |
| **total** | | **749** | **123** | **11** | **14** |

\* **starred counts are estimates**, made from a 42–65 dpi contact sheet rather
than a box-by-box count at full resolution, and flagged per group by
`structures_drawn_is_estimate`. No estimated number can move a score: recall is
computed over `molecules` and precision over what a pipeline emits, and both are
exact.

**The denominator to quote with any recall figure from this round is 123**, and
only if you score all twenty-five groups. Twelve groups carry an `unresolved`
bookkeeping row and should be scored **recall-only**; if you drop those, the
denominator is **35** across the thirteen fully-catalogued groups.

## Three schema decisions a reader must know

1. **Rows with no SMILES are not in `molecules`.** `score_run.py` calls
   `Chem.MolFromSmiles(m["smiles"])` on every entry and a `None` raises
   `TypeError` before its own error message. Generics, counter-ion generics and
   unresolved structures live in a sibling per-group `unscoreable` array.
2. **Repeat drawings of one compound are collapsed to one row.** Selexipag is
   drawn twice and is one row; tapinarof is drawn nine times and is one row.
3. **`unscoreable` also carries bookkeeping rows** that describe a *set* of
   depictions rather than a compound, so the arithmetic between `drawn` and the
   row counts is legible rather than mysterious.

`confidence` values used: `name_match`, `drawing_read`, `generic`, `unresolved`.
`pixel_verified` is `false` everywhere.

## Eleven page extracts to declare

Eleven of the twenty-five files are **not** the whole publication. Each is flagged
`is_page_extract: true` with the kept range in `pages_kept`, and each group's note
opens with the `mutool merge` command that produced it. **In those groups every
page number — in `molecules[].page`, in `unscoreable[].page` and in the prose —
refers to the ORIGINAL published document, not to the extract**, and
`structures_drawn` counts the original.

| file | original | kept | pages |
|---|---|---|---|
| `US11491155B2_ensifentrine.pdf` | 28 | 1-13,28 | 14 |
| `US11597692B2_tapinarof.pdf` | 40 | 1-12,30,36-40 | 18 |
| `US11680050B2_ozanimod.pdf` | 40 | 1-4,14,18,21-22,27,40 | 10 |
| `US12049463B2_tolebrutinib.pdf` | 24 | 1,7-24 | 19 |
| `US20220009893A1_reproxalap.pdf` | 14 | 1-7,14 | 8 |
| `US20230002439A1_vamorolone.pdf` | 36 | 1-3,7,10,20-22,26,30-33,36 | 14 |
| `WO2022049604A1_revefenacin.pdf` | 48 | 1-10,38-45 | 18 |
| `WO2023107660A1_lotilaner.pdf` | 63 | 1-4,35-42,50,55,61-63 | 17 |
| `WO2023152691A1_ponesimod.pdf` | 41 | 1-10,25-28,31-36 | 20 |
| `WO2024180493A1_delgocitinib.pdf` | 69 | 1-6,53-60,66-69 | 18 |
| `WO2024182418A1_trifarotene.pdf` | 44 | 1-10,27-30,34-40 | 21 |

The keep rule was the same every time: the front page, **every structure-bearing
page**, at least one page of each non-structure figure class the document
contains, and the claims. What was dropped is repetition — runs of near-identical
diffractograms, and pages of 2-θ peak lists in prose. Round 10 contributes 19.9 MB
for twenty-five documents; untrimmed it would have been 35.2 MB.

## The seven findings worth carrying forward

**1. A name lookup can return a tautomer.** `EP3747864B1_nintedanib`. Covered
above. The general form: PUG-REST `/compound/name/` resolves a *lexicon*, not a
structure, and its answer can differ from the drawing in the stereo layer, in the
tautomer, or in both. Where a printed systematic name exists, parse it.

**2. Two labels one character apart, two different compounds.**
`US11345664B2_netarsudil_process` p7 draws **"Formula I"** (Roman) and
**"Formula 1"** (Arabic) within twenty lines of each other. The first is
netarsudil *dimesylate*, drawn as the base with `.2CH3SO3H` beside it and the
stereocentre on a hashed wedge to the aryl; the second is the *free base*, drawn
mirror-imaged with a bold wedge to the aminomethyl. Both are (S). Any pipeline
that keys a structure to the nearest label is one glyph away from the wrong
answer.

**3. A caption can name a different molecule than the box it sits under.**
`WO2024182418A1_trifarotene` FIG. 1 prints a full IUPAC name under each of ten
boxes — and box 7's caption repeats box 2's, which describes a bromo-*tert*-butyl
succinanilic acid while the drawing is a protected ether of an iodo-biphenyl
carbonitrile. Name and drawing are two identity signals and they disagree, so
that box is `unresolved`. Same failure class as `US4117118A`'s cyclosporin.

**4. Sometimes the reference is *less* specified than the drawing.** Round 6 found
the reverse. Here it goes the other way three times:
- `WO2023152691A1_ponesimod` — the printed name fixes `(2Z,5Z)` and `(2R)`, but
  PubChem's ponesimod (CID 11363176) leaves the propylimino C=N open, and the
  fully specified InChIKey `LPAUOXUZGSBGDU-STDDISTJSA-N` has **no PubChem record
  at all**. Intermediate (VI) has the identical problem.
- `WO2020261041A1_abrocitinib` — the name says *cis* and both cyclobutane
  substituents are drawn on hashed wedges, but CID 78323835 stores no stereo.

  In all of these a faithful reading scores `stereo`, not `exact`. That is a
  property of the reference, not a failure of the prediction.

**5. Three stereo conventions now appear in the corpus, and a fourth is
"nothing".** Bold/hashed wedges everywhere; printed italic CIP letters beside the
centre (`US10584100B2_netarsudil`, which gives the same centre three ways —
wedge, letter, and `(1S)` in the name); and a **squiggly bond** in
`US11597692B2_tapinarof` formula (IIa), where the chlorine's configuration is
deliberately undefined and a tool that invents a wedge is asserting something the
document refuses to. `WO2023107660A1_lotilaner`'s centre is **quaternary** — aryl,
CF3, ring O, ring CH2, no hydrogen — so there is no implicit H to anchor a wedge
to.

**6. Salts are drawn four different ways in this round.** As a neutral
two-component adduct with a dot; as an **ion pair** with circled charges and
separate anions (`EP4302831B1_tirbanibulin`, KX2-391 diHCl — same InChIKey as
PubChem's neutral record but a different CID and a different canonical SMILES); as
a **counter-ion genus**, `X-` with the text saying only "an anion"
(`WO2022049604A1_revefenacin`); and as a **non-integer** `Zn(0.5)` carboxylate
(`US11613529B2_deucravacitinib` compound 8), which no two-component SMILES can
express. Separately, five documents are *about* a salt and never draw one —
netarsudil mesylate, gefapixant citrate, ensifentrine's nine acid addition salts,
reproxalap's four, and ozanimod hydrochloride.

**7. Regiochemistry can be a blocking group.** `US11613529B2_deucravacitinib`
compound 4 is **5-chloro-2-methoxybenzonitrile**, not the 3-chloro isomer the
API's 1,2,3-substitution pattern suggests; that chlorine is removed by
hydrogenolysis three steps later. Both isomers are real PubChem records. Read the
drawing at 400 dpi, not the product.

## The false-positive stratum

Nine documents draw **three structures or fewer** and carry between four and
twenty-five numbered figure sheets. They are in the round on purpose — precision
is meaningless without them.

| group | structures | non-structure figure sheets |
|---|---|---|
| `WO2024180493A1_delgocitinib` | 1 | 9, plus 49 pages of 2-θ peak lists in prose |
| `WO2023107660A1_lotilaner` | 1 | 24, including annotated ssNMR spectra |
| `US10584100B2_netarsudil` | 1 | 7 PXRD |
| `US11491155B2_ensifentrine` | 1 | 8 sheets / 12 figures + 17 pages of tables |
| `US20220009893A1_reproxalap` | 1 | 5 PXRD, one of them the front-page abstract figure |
| `WO2020261041A1_abrocitinib` | 1 | 4, plus the International Search Report |
| `US11680050B2_ozanimod` | 2 | 25 sheets / ~50 figures inc. photomicrographs |
| `US12049463B2_tolebrutinib` | 3 | 6, plus 5 pages of dense citation lists |
| `WO2022083476A1_gefapixant` | 3 | 4, plus 7 pages of ISR/IPRP forms; Chinese-language |

Figure classes present across the round, several new to the corpus: PXRD, DSC,
TGA, DVS moisture-sorption isotherms, Raman, FTIR, **infrared** (only
`US20250215046A1_clascoterone`), ¹³C and ¹⁵N solid-state NMR, HPLC chromatograms
with integration tables, particle-size histograms, **optical photomicrographs**,
dissolution curves, horizontal bar charts, a greyscale **raster heatmap**
(`US20230002439A1_vamorolone` p21), and International Search Report forms.

## Figure and layout classes that are *not* instrument traces

Four documents contribute layout problems rather than chemistry problems:

- **Structures inside a table.** `WO2021005484A1_upadacitinib` pp11–13 is a
  `Sr. No | Chemical Name | Sr. No | Chemical Structure` table with nine
  compounds drawn inside table cells. A border-following layout model
  mis-segments it.
- **A landscape drawing sheet.** `WO2024182418A1_trifarotene` FIG. 1 is a numbered
  drawing sheet that contains a full route and is printed rotated ninety degrees.
  Un-rotated, every structure on it is read sideways.
- **An annotation rectangle inside a structure.** `CN118530179A_elexacaftor` p4
  rules a box around the pyrazole ether fragment and the caption says so
  explicitly. A segmenter that treats rectangles as figure boundaries cuts the
  molecule in half.
- **A structure overlaid on an instrument plot.** `WO2022083476A1_gefapixant`'s
  front-page abstract figure puts the molecule on the XRPD plot area, so the two
  are one composite figure.

## Two language notes

Two documents are non-English: `WO2022083476A1_gefapixant` (Chinese, with the
compound named only in Chinese characters and the drug name left in Latin script)
and `CN118530179A_elexacaftor` (Chinese CNIPA). `EP4302831B1_tirbanibulin` and
`EP3747864B1_nintedanib` print their claims in **English, German and French**, so
every claim structure is drawn three times in one file.

## What resolves and what does not

Of 123 scoreable rows, **103 are `name_match`** and **20 are `drawing_read`**. The
fourteen `unresolved` rows fail for four distinct, documented reasons, and the
distinction is worth preserving:

- **no printed name** — numbered-only intermediates (deucravacitinib 1–3, 6–13;
  the ponesimod Roman numerals; the revefenacin route);
- **no PubChem record for the read structure** — filgotinib formula (XV), whose
  drawn reading returns CID 0, and the upadacitinib sulfoxonium ylide, whose
  OPSIN-parsed InChIKey `LINGMGRWISLEAF-ZJUUUORDSA-N` is absent;
- **name and drawing disagree** — trifarotene FIG. 1 box 7;
- **a stoichiometry no SMILES can carry** — deucravacitinib compound 8's
  `Zn(0.5)`.

The eleven `generic` rows are ordinary R-group Markush except for two worth
naming: `WO2022049604A1_revefenacin`'s bare `X-` counter-ion genus, and
`US20250215046A1_clascoterone` formula (III), a Markush with **exactly two
members** (`R = H, CH3`) — narrower than anything else in the corpus and a case
where "emit one of the two" is not obviously wrong.

## Validation performed

- All **123** `molecules` parse under RDKit, are already RDKit-canonical, and
  their recomputed InChIKeys match the recorded ones. All `unscoreable` rows have
  `smiles: null`.
- No group contains a duplicate `name` or a duplicate `smiles`.
  Across groups, one name repeats — `netarsudil`, in the two deliberately paired
  netarsudil documents.
- Every required field (`index`, `name`, `cid`, `smiles`, `connectivity_smiles`,
  `formula`, `inchikey`, `page`, `smiles_source`, `confidence`, `basis`,
  `pixel_verified`) is present on every molecule row.
- `structures_resolved` equals `len(molecules)` for all twenty-five groups.
- Every patent number was verified by **opening the committed PDF and reading its
  own title page**, not from a search summary.
- Each trimmed file was re-opened after trimming and a known structure page was
  rendered to confirm it survived.

## A note for whoever adds round 11

`patents.google.com/xhr/query` now answers **plain `curl`** from this server —
HTTP 200 in about 0.7 s — although `patents.google.com/patent/<ID>/en` still
returns 503. Only the *search* endpoint is open, and Google captchas it after
roughly fifteen to twenty direct queries, at which point the read-through proxy
still works. Use `TI%3D(<compound>)` — title-restricted — because free text
returns mostly third-party documents that merely mention the drug.

An **EP A1 is not retrievable from this server at all**: the EPO publication
server refuses A1 (HTTP 500) *and* Google's patentimages has no PDF for one. Use
the WO twin. That cost two candidates this round.

And the round-6 lesson held again in a new form: a *title* is not a screen either.
`US11993605B2` is called "Processes for the preparation of (3S,4R)-3-ethyl-4-…"
and is a 229-page, 17.7 MB **clinical** document with ninety pharmacology figure
sheets and almost no drawings. It was fetched, opened, and rejected on the
evidence.
