# Round 3/4 PDF ground truth — what is in `pdf_manifest_round34.json`

Six real documents that had completed pipeline runs but existed only in the
corpus-*selection* records (`pdf_corpus_round3_manifest.json`,
`pdf_corpus_round4_manifest.json`), which carry provenance and no SMILES.
This file is the scoreable manifest for them, in the `pdf_manifest_expanded.json`
schema that `score_run.py` reads.

Nothing here was derived from a pipeline prediction. Every structure was located
by reading the PDF (`pdftotext -layout`, `pdfimages`, `pdftoppm` page crops) and
every resolved molecule needed two independent views to agree: a PubChem lookup
(by a name or CAS printed in the document, or — where the document prints no
name — by a SMILES structure search on the drawn reading) **and** a reading of the
drawing. Every SMILES round-trips through RDKit and its InChIKey is recorded.

## Counts

| group | drawn | resolved (`molecules`) | generic | unresolved |
|---|---|---|---|---|
| ntp_roc_cisplatin | 1 | 1 | 0 | 0 |
| ntp_roc_heterocyclicamines | 4 | 4 | 0 | 0 |
| ntp_roc_pahs | 15 | 15 | 0 | 0 |
| DE60100786T2_citalopram_german | 5 | 2 | 1 | 0 |
| CN108503621B_vonoprazan | 29 | 12 | 0 | 0 |
| PMC10180415_approved2022_aa_fluorine | 100 | 41 | 0 | 43 |
| **total** | **154** | **75** | **1** | **43** |

`drawn` counts depictions on the page. `resolved` counts rows in `molecules`,
which are **distinct compounds**, not depictions — see "Two schema decisions".

## Two schema decisions a reader must know

1. **Rows with no SMILES are not in `molecules`.** `score_run.py` calls
   `Chem.MolFromSmiles(m["smiles"])` on every entry of `molecules`, and a `None`
   raises `TypeError` before the script's own error message. Generic (Markush)
   and unresolved structures therefore live in a sibling per-group array
   `unscoreable`, which the scorer ignores. Each carries `generic`,
   `confidence`, `page` and a `note` describing what is drawn.
2. **Repeat drawings of one compound are collapsed to one row.**
   `score_run.py` matches a prediction to a molecule by `name` and then counts
   recall per molecule row. Two rows for the same compound would let one
   prediction score two recoveries; two rows with different names would leave the
   second permanently unrecoverable. Neither existing manifest
   (`pdf_manifest.json`, `pdf_manifest_expanded.json`) has a duplicate name or
   SMILES inside a group; this one does not either. Where a compound is drawn more
   than once, its `page` field lists every page.

`confidence` values used here: `name_match` (a name or CAS printed in the
document resolves to the CID and the drawing agrees), `drawing_read` (the
document prints no name; the structure was read off the drawing and then
confirmed against a PubChem record by structure search), `unresolved`, `generic`.
`pixel_verified` is `false` everywhere — the pixel-exact method in
`build_ground_truth.py` only works on the synthetic PubChem-grid PDFs.

## Per document

### ntp_roc_cisplatin — 1 drawn, 1 resolved
One drawing, in the p1 header box. p2 is text and references.
**Caveat.** PubChem's cisplatin record (CID 5702198 / 5460033) is *disconnected*:
`N.N.Cl[Pt]Cl`. The drawing shows explicit Pt–N and Pt–Cl bonds in cis
square-planar geometry. A bonded reading canonicalises to
`[NH2][Pt]([NH2])([Cl])[Cl]` (InChIKey `DQLATGHUWYMOKM-UHFFFAOYSA-L`), which does
**not** match the reference string `N.N.[Cl][Pt][Cl]`
(`LXZZYRPGZAFOLE-UHFFFAOYSA-L`). Neither form encodes cis vs trans, so this entry
cannot tell cisplatin from transplatin.

### ntp_roc_heterocyclicamines — 4 drawn, 4 resolved
MeIQ, MeIQx, IQ, PhIP, each under its printed name and CAS number; CAS→CID and
name→CID agree for all four.
**Caveat.** The page numbers in the round-4 selection record are wrong. The
drawings are MeIQ + MeIQx on **p1** and IQ + PhIP on **p2** (the record says
p1/p2/p3). pp3–5 are text, one properties table and references.

### ntp_roc_pahs — 15 drawn, 15 resolved
All 15 on pp1–2 (8 on p1, 7 on p2); pp3–9 are text plus one properties table.
For every one, the printed name and the printed CAS number resolve to the *same*
CID by two independent PUG-REST routes.
**Caveat.** These are unsubstituted (or singly methylated) polycyclics with no
atom labels except the acridine/carbazole N. Reading the drawing confirms ring
count, ring sizes and gross fusion topology; the fine isomer assignment
(b/j/k-fluoranthene, a,e/a,h/a,i/a,l-pyrene) rests on the printed CAS number.

### DE60100786T2_citalopram_german — 5 drawn, 2 resolved, 1 generic
German-language DPMA translation of EP 1 227 088 B1. Nine CCITT **stencil**
clippings are embedded; five are structures (p2 ×1, p3 ×2, p4 ×1, p9 ×1) and four
are tablet-formulation **tables** (p7 ×1, p8 ×2, p9 ×1) — a non-structure figure
class inside a structure document.
The five structure drawings are only three distinct things: citalopram drawn
twice (p2, p3), the Markush formula (II) drawn twice (p3, p9), and a
1-butyl-3-methylimidazolium hexafluorophosphate ionic liquid once (p4).
Formula (II) is the citalopram skeleton with the 5-substituent left as a variable
Z (halogen, `-O-SO2-(CF2)n-CF3`, `-CHO`, `-NHR1`, `-COOR2`, `-CONR2R3`); it is
`generic: true` with `smiles: null`.
**Caveat.** The ionic liquid is never named in the document — it is a
`drawing_read`. The drawing also puts the `+` on the *butylated* nitrogen while
PubChem CID 2734174 puts it on the methylated one: same InChIKey
(`IXQYBUDWDLYNMA-UHFFFAOYSA-N`), different RDKit canonical SMILES. A tool that
reproduces the drawing exactly scores `wrong` under string-equality grading.
Citalopram is drawn flat and [0018] states the composition is the racemate, so
CID 2771 (no stereocentre) is right and an escitalopram-style (S) prediction is
correctly a stereo-level match, not exact.

### CN108503621B_vonoprazan — 29 drawn, 12 resolved
Chinese-language granted patent; every scheme is a 150-ppi indexed raster
clipping. 29 drawn structure boxes across five clippings — p2 claims scheme (7),
p3 standalone vonoprazan fumarate (1) and p3 prior-art scheme (7), p4 prior-art
scheme (7), p6 the claimed route (7). p2 and p6 are the *same* scheme at two
sizes. Counting each component of a drawn salt separately gives 34 species.
Those 29 boxes are 12 distinct compounds.
Compounds (1)–(7) carry printed Chinese chemical names → `name_match`.
Compounds (I)–(V) of the prior-art route carry Roman numerals only → all five are
`drawing_read`, confirmed by PubChem SMILES→CID search (two of them,
CID 137538277 and CID 141422934, matched the drawn reading's InChIKey exactly).
**Caveat.** Vonoprazan fumarate is drawn as a two-component salt (base · fumaric
acid). A pipeline that segments the two components separately emits two
structures that match *different* manifest rows (`vonoprazan`, `fumaric acid`),
not the `vonoprazan fumarate` row. Non-structure figures inside this structure
document: the p1 abstract HPLC chromatogram with peak table, the CNIPA logo, and
pp10–11 Figures 1–4, four more HPLC chromatograms with peak tables.

### PMC10180415_approved2022_aa_fluorine — 100 drawn, 41 resolved, 43 unresolved
MDPI review, 21 pages. 100 drawn depictions counted box by box across pp2–15
(±2 depending on whether the components of a drawn salt are counted separately;
counting components gives about 104). Page tally: p2 Fig 1 = 4, p3 Fig 2 = 6,
p4 Fig 3 = 2, p5 Scheme 1 = 8, p6 Scheme 2 = 15, p7 Fig 4 = 2,
p8 Scheme 3 = 9 + Scheme 4 = 7, p10 Scheme 5 = 8, p11 Scheme 6 = 7,
p12 Scheme 7 = 11, p13 Scheme 8 = 7, p14 Fig 5 = 3 + Scheme 9 = 5,
p15 Fig 6 = 2 + Scheme 10 = 4. pp1, 9 and 16–21 carry no drawings.
Those 100 depictions are 84 distinct compounds: 41 resolved, 43 unresolved.

**This is the biggest caveat in the file.** The 43 are not missing by accident.
They are numbered-only intermediates — the paper prints a number and no chemical
name — plus five resin-bound solid-phase structures and two metal chelates. With
no printed name there is no second independent view to check a hand-read SMILES
against, and a wrong reference silently converts a correct prediction into a
scored failure. **Consequence: `molecules` covers 41 of the 84 compounds actually
drawn, so precision computed over this group is a lower bound — every correct
prediction of an unresolved intermediate is counted `wrong`. Score this group
recall-only, or exclude it from precision.**

Two specific disagreements were resolved against the printed text, both noted in
the entries:
- Compound **48**: the p10 text calls it `6-chloro-3-isopropylpyridine-2,4(1H,3H)-dione`,
  but the drawing has two ring nitrogens. The drawing wins — 47 (a barbituric
  acid) and the product mavacamten (a pyrimidinedione) both require it. The
  printed "pyridine" is a typo for "pyrimidine".
- Compound **5** (`177Lu` vipivotide tetraxetan) is left **unresolved**. It is
  drawn as the `177Lu(III)` chelate; PubChem's `vipivotide tetraxetan`
  CID 122706786 is the *metal-free* ligand. The two views disagree on the metal,
  and using the ligand CID would score a correct reading of the drawing as wrong.
- **gadopiclenol (8)** *is* resolved (CID 16223405 contains the Gd), but PubChem
  writes `[Gd+3]` as a separate component while the drawing bonds it inside the
  macrocycle. Same composition, different connectivity string. The paper also
  states gadopiclenol's six stereocentres were never disclosed; neither the
  drawing nor the CID specifies them.

## Validation performed

- All 75 `molecules` parse under RDKit, are already RDKit-canonical, and match
  their recorded InChIKey. All `unscoreable` rows have `smiles: null`.
- `score_run.py` was run against each of the six completed runs with this
  manifest; it loads cleanly and `group_key()` resolves figures for every group,
  i.e. the six group keys are the real figure-filename prefixes.
- One post-hoc agreement check (not used to derive anything): on
  `ntp_roc_pahs` the pipeline emitted 6 structures and all 6 matched these
  references exactly. On the other five, the only two `wrong` predictions with
  Tanimoto ≥ 0.90 to a reference were both pipeline-side errors — a `CH2Br` read
  as `CH3` plus a loose `Br` atom, and a neutral `[Na]` radical where the
  reference has `[Na+]` — not reference errors.
