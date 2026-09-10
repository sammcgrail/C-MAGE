# Round 6 PDF ground truth — oncology patents

Ten recent oncology patent documents, priority dates 2011–2024, one or two per
modern small-molecule oncology scaffold class. Selection provenance is in
`pdf_corpus_round6_manifest.json`; this file and `pdf_manifest_round6.json` are
the scoreable half, in the `pdf_manifest_expanded.json` schema that
`score_run.py` reads.

Nothing here was derived from a pipeline prediction. Every structure was located
by reading the PDF — `pdftotext -layout` and `pdfimages -png` on the four
documents that have a text layer, `pdftoppm` page renders at 100–250 dpi on the
six that do not. Every resolved molecule needed two independent views to agree:
a PubChem lookup keyed on something **printed in the document** — an INN, a full
IUPAC name, a Chinese chemical name, or a molecular weight — **and** a reading of
the drawing. Where the document prints no name, the SMILES read off the drawing
was submitted to PUG-REST `/compound/smiles/` and accepted only when the returned
InChIKey matched the hand reading exactly. Every SMILES round-trips through RDKit
and its InChIKey was recomputed with RDKit and checked against PubChem's.

## Counts

`drawn` counts **depictions**. `resolved`, `generic` and `unresolved` count
**rows** — distinct compounds, or named classes of depiction. The four columns do
not sum, for the same reason they do not in `pdf_manifest_round34.json`: a
compound drawn twenty-six times is one row.

| group | drawn | resolved (`molecules`) | generic | unresolved |
|---|---|---|---|---|
| `EP2736895B1_osimertinib` | 50 | 10 | 6 | 1 |
| `EP3630761B1_sotorasib` | 46 | 13 | 1 | 1 |
| `US12011442B2_abemaciclib` | 1 | 1 | 0 | 0 |
| `WO2021259732A1_zanubrutinib` | 12 | 4 | 3 | 0 |
| `WO2017215166A1_talazoparib` | 48 | 10 | 0 | 2 |
| `US11629137B2_niraparib` | 179\* | 14 | 0 | 3 |
| `CN114085213A_vepdegestrant` | 67\* | 6 | 0 | 1 |
| `WO2025055671A1_elacestrant` | 74\* | 2 | 1 | 2 |
| `US9463252B2_auristatin_MMAF` | 88\* | 0 | 3 | 2 |
| `US12018032B2_icovamenib` | 33\* | 1 | 0 | 3 |
| **total** | **598** | **61** | **14** | **15** |

\* **starred counts are estimates**, made from a 40–110 dpi contact sheet rather
than a box-by-box count at full resolution. They are flagged per group by
`structures_drawn_is_estimate`. No estimated number can move a score: recall is
computed over `molecules` and precision over what a pipeline emits, and both of
those are exact. Every starred group should be scored recall-only anyway,
because most of what it draws is uncatalogued.

**The denominator to quote with any recall figure from this round is 61**, and
only if you score all ten groups. If you exclude the recall-only groups, the
denominator is 38 across `EP2736895B1`, `EP3630761B1`, `US12011442B2`,
`WO2021259732A1` and `WO2017215166A1`.

## Three schema decisions a reader must know

1. **Rows with no SMILES are not in `molecules`.** `score_run.py` calls
   `Chem.MolFromSmiles(m["smiles"])` on every entry and a `None` raises
   `TypeError` before the script's own error message. Generic, fragment,
   resin-bound, variable-stoichiometry and unresolved structures live in a
   sibling per-group `unscoreable` array, which the scorer ignores.
2. **Repeat drawings of one compound are collapsed to one row.** Sotorasib is
   drawn 31 times in its document and is one row. Two rows would let one
   prediction score two recoveries.
3. **`unscoreable` also carries bookkeeping rows.** Two entries — the 26 sotorasib
   claim redraws, and the ~25 uncatalogued osimertinib scheme members — describe a
   *set* of depictions rather than a compound, so that the arithmetic between
   `drawn` and the row counts is legible rather than mysterious.

`confidence` values used: `name_match` (a name printed in the document resolves to
the CID and the drawing agrees), `drawing_read` (no name printed; the structure was
read off the drawing and confirmed against a PubChem record by structure search or
by a printed molecular weight), `generic`, `unresolved`. `pixel_verified` is
`false` everywhere.

## Per document

### `EP2736895B1_osimertinib` — 50 drawn, 10 resolved, 6 generic
AstraZeneca's osimertinib (TAGRISSO) compound and polymorph patent, granted
2016-01-06. EPO B1: vector A4 text with 25 structure clippings at 300 dpi on
pp3–81, plus **21 full-page instrument plots on pp83–103** — XRPD patterns and
DSC/TGA thermograms, one per page. Formulae (I)–(VI) on pp3–7 are Markush.
**Caveat.** The mesylate is drawn as an **ion pair** — the anilide nitrogen
protonated, a separate `CH3SO3-` — while PubChem CID 78357807 stores the neutral
two-component adduct. A tool that reproduces the drawing exactly scores `wrong`
on that row under string equality, and a tool that segments the two components
separately matches the `osimertinib` and `methanesulfonic acid` rows instead. The
INN is never printed; the document says "Compound X" and a full IUPAC name.

### `EP3630761B1_sotorasib` — 46 drawn, 13 resolved, 1 generic
Amgen's KRAS G12C patent. 26 pages, 407 KB, and it carries a complete named
seven-step route, which is why 13 of its 46 depictions resolve.
**Caveat, and the most interesting one in the round.** Claims 3–6 claim
*Atropisomer 1* and *Atropisomer 2* as separate inventions and draw them with 2D
structures identical to the ones in claims 1, 2, 7 and 8. The axial chirality is
stated in words only; neither the drawings nor any SMILES reference encodes it.
No reading of this document can tell the two atropisomer claims apart, and all 26
claim depictions collapse to the single `sotorasib` row.
**Second caveat.** p12 embeds 25 copies of one 63×61 raster that is a punctuation
glyph inside a long list of cancer types. A per-page image count reports 25
phantom structures on a page that has none.
**Third.** The Step 5 intermediate exposes how brittle name lookup is: the printed
name resolves to CID 135379105, but the *same* name with the stereodescriptor
moved from `(S)-tert-butyl` to `tert-butyl (3S)-` returns HTTP 404. The structure
route returned the same CID and did not care.

### `US12011442B2_abemaciclib` — 1 drawn, 1 resolved
Macfarlan Smith's abemaciclib solid-state forms, granted 2024. Fourteen pages,
937 KB, **nine numbered drawing sheets and exactly one 2D structure**, inline on
p11.
**Caveat.** Eight of the nine sheets are XRPD, DSC, TGA, DVS and a sorption
isotherm; p4 is a polarised-light photomicrograph; and p3 — the trap — is a
**three-dimensional ball-and-stick single-crystal structure** of abemaciclib with
its methanol of solvation. It is genuinely a molecular depiction, just not a 2D
one, and the methanol is not part of the claimed compound. Score this group as a
false-positive test as much as a recall test.

### `WO2021259732A1_zanubrutinib` — 12 drawn, 4 resolved, 3 generic
BeiGene co-crystals of zanubrutinib with a benzoic acid derivative.
**Caveat.** The claimed compound has **non-integer stoichiometry** — n from 0.8 to
1.2, and for the hydrate a second independent subscript m. A two-component SMILES
asserts exactly 1:1, which the document explicitly does not, so the co-crystal is
`generic` while its three components (zanubrutinib, 4-hydroxybenzoic acid,
3,4-dihydroxybenzoic acid) and its water are each clean rows.
**Second caveat.** Zanubrutinib's single stereocentre is drawn with a hashed
wedge, but the **absolute (7S) assignment rests on the printed INN**, not on a CIP
analysis of the 2D layout. Non-structure figures: 16 sheets on pp43–58 including
two 3D ORTEP renderings and, on p58, a manufacturing flowchart; pp59–60 are the
International Search Report bound into the same file.

### `WO2017215166A1_talazoparib` — 48 drawn, 10 resolved
A Chinese-origin PCT in English, "Synthesis of PARP inhibitor talazoparib".
Twenty-six pages carrying three routes: two prior-art ones on pp3–4 and the
invention's on p5, restated on pp8–12 and again in the claims on p21.
**Caveat.** ChemDraw has stamped a **`(Z)` descriptor on ring bonds inside the
aromatic 1-methyl-1,2,4-triazole** of compounds 13 and 1. Those are meaningless
double-bond stereodescriptors on a five-membered aromatic ring; a tool that tries
to honour them emits a molecule that cannot exist. The document also prints
explicit CIP letters beside every stereocentre in addition to the wedges.
**Second caveat.** Compound 17 is the single enantiomer of compound 16 and has **no
PubChem record at all** — a SMILES search on the (S) form returns CID 0. Giving it
16's stereo-unspecified CID would put a duplicate SMILES in the group, so it sits
in `unscoreable`. Compound 13 has the opposite problem: it is drawn with two
stereo bonds and two printed `(S)` labels, and the only PubChem record for that
connectivity is stereo-unspecified, so a **faithful reading of the drawing scores
`stereo`, not `exact`**. That is a property of the reference, not a failure of the
prediction.

### `US11629137B2_niraparib` — ~179 drawn, 14 resolved
The ZEJULA tosylate-monohydrate manufacturing patent. A USPTO scan with **zero
text layer** — `pdftotext` returns 0 characters.
**The best feature in the round:** FIG 2 on p5 prints a **molecular weight under
every structure**. That is a second view independent of both the name and the
drawing, and it is why nine of this document's fourteen molecules are honest
`drawing_read` entries. Every printed weight matched the RDKit weight of the resolved
formula to within 0.01 - four exact, two off by 0.01 in the last place.
**Caveat.** Only the three drawing sheets (pp4–6, 29 boxes counted exactly) are
catalogued. The 40-page specification body pp7–46 draws structures on nearly every
page — including a gallery of **named phosphine ligands on p14** (Xantphos,
DavePhos, JohnPhos, SPhos) with `PPh2` and `t-Bu` drawn as condensed labels — and
none of it is catalogued. **Precision over this group is a lower bound; score it
recall-only, or restrict it to pp4–6.** The ~150 body depictions in the 179 total
are an estimate.
**Second caveat.** Niraparib itself is never drawn alone, only as a component of
the drawn tosylate monohydrate. A pipeline that splits the salt matches the
`niraparib`, `p-toluenesulfonic acid monohydrate` and `water` rows, not the
`niraparib tosylate monohydrate` row.

### `CN114085213A_vepdegestrant` — ~67 drawn, 6 resolved
A CNIPA application, "A method for preparing ARV-471", with a vector Chinese text
layer and 48 raster structure clippings. Vepdegestrant is the largest molecule in
the round: C45H49N5O4, 54 heavy atoms, three stereocentres, an oestrogen-receptor
ligand joined through a piperidine–piperazine linker to a cereblon-binding
glutarimide.
**Caveat, and the one to quote.** The cereblon fragment is a live demonstration of
the failure mode this corpus exists to catch. Writing its glutarimide stereocentre
the wrong way round — `[C@@H]` instead of `[C@H]` — returns a **different real
PubChem record**, CID 177775766, `(3R)-3-(3-oxo-5-piperazin-1-yl-1H-isoindol-2-yl)
piperidine-2,6-dione`: same formula, same skeleton InChIKey block `CFOMGFBCZSPWCX`,
different stereo layer, and nothing in the API response says you asked for the
wrong enantiomer. Only the printed Chinese name settles it as (3S), CID 170331923.
Treat every stereocentre in this group as name-derived, not drawing-derived.
**Second caveat.** Every page embeds two small rasters, 116×17 and 160×18, which
are the running header and the footer page stamp. A pipeline counting embedded
images per page reports 4–9 "structures" on p23, which is claims text with none.

### `WO2025055671A1_elacestrant` — ~74 drawn, 2 resolved, 1 generic
A Chinese-language WIPO A1, "A method for synthesising elacestrant and its
intermediates". A different Chinese document class from both `CN114085213A` and
the corpus's existing `CN108503621B`: this one is a **full-page raster with no
text layer at all**.
**Caveat.** Only two of ~74 depictions are scoreable — the free base and the
marketed dihydrochloride — and the two are distinguished by **nothing but the
condensed text `2HCl`** beside the structure, which is the minimal possible salt
cue. Everything else is either a lettered Markush formula (I)–(VII) with three
protecting-group variables, or a bare code (A1–A9, B1–B7, V-1, VII-2) with no
name and no mass. Score recall-only against 2. Non-structure figures: five sheets
of ¹H NMR and mass spectra on pp16–20, and the International Search Report on
pp21–28.

### `US9463252B2_auristatin_MMAF` — ~88 drawn, **0 resolved**, 3 generic
**The round's Markush stratum, and it scores nothing by design.** Seattle
Genetics' auristatin drug-linker conjugates. Not one depiction in the patent is a
fully specified molecule, which makes it the corpus's cleanest measurement of
whether a tool knows a Markush from a molecule. Three separate non-molecule
classes are present, each a different failure mode:
- the Formula (I) auristatin skeleton with **twelve independent R-groups**;
- roughly 45 **substituent-fragment sketches drawn with squiggly open valences**,
  the largest depiction class in the document and the one most likely to be
  emitted as a molecule;
- **solid-phase intermediates whose C-terminus ends in a shaded circle** meaning
  resin bead, with `AA1(x)`/`AA2(y)` amino-acid placeholders mid-chain.

MMAE and MMAF are defined **in words** in the abbreviations list and never drawn
without a variable, so they are `unresolved`, not `molecules` — named but not
drawn is not a scoreable molecule for an OCSR benchmark. The nine drawing sheets
are pharmacology curves with no chemistry.
**Caveat.** `structures_drawn` here is the least precise number in the file and it
is the only one that cannot matter, because `molecules` is empty: precision and
recall for this group are both undefined. **Score this group for false positives
only.** The file in the corpus is a **page extract**, not the whole grant — see
below.

### `US12018032B2_icovamenib` — ~33 drawn, 1 resolved
Biomea Fusion's crystalline forms of BMF-219 / icovamenib, a covalent menin–MLL
inhibitor. Ninety-eight pages.
**Caveat.** **37 of them (pp4–40) are numbered drawing sheets and not one is a
chemical structure**: XRPD, DSC, TGA and DVS traces, a polarised-light
photomicrograph on p20, and on pp31–40 cell-biology dose-response curves and bar
charts. A pipeline that treats "numbered drawing sheet" as "structure" scores 37
false positives here — more than the document's entire true structure count. This
is the `US12011442B2` figure-class problem scaled up four-fold.
**Second caveat.** pp81–84 draw about twenty **deuterated analogues** with explicit
`D` atom labels, and the surrounding text enumerates the deuteration patterns as
*sets* ("deuterium is attached to any one or more positions selected from 13 and
15"). Several depictions therefore correspond to a family of compounds rather than
to one, and a prediction naming a single deuteroisomer for such a box is neither
right nor wrong in any way this manifest can grade.
**Third.** Fig. 33 on p41 draws "Compound P" with **numbered atom positions printed
on the skeleton**, putting stray digits inside the structure box. Compound P is
left `unresolved`: it is labelled only with a document-internal letter, and the
urea's attachment point on the central pyridine could not be read with certainty.

## One page-extract to declare

`US9463252B2_auristatin_MMAF.pdf` is **not the whole grant.** It was cut from the
63-page original with

```
mutool merge -o US9463252B2_auristatin_MMAF.pdf US9463252.pdf 1-11,20-28,41-44,60-62
```

keeping the front page and references (pp1–2), all nine drawing sheets (pp3–11),
Formula (I) and the substituent-fragment pages (pp20–28), the solid-phase schemes
(pp41–44) and the claims (pp60–62); 6.63 MB reduced to 1.71 MB. The dropped pages
are running specification text and example write-ups that introduce no new
depiction class. Every other file in this round is the complete document as
published.

## Two notes on retrieval, for whoever adds round 7

Both round-4 routes have degraded. `patents.google.com` now returns HTTP 503 to
`curl` **and** to a server-side fetcher, and
`https://patentimages.storage.googleapis.com/pdfs/US<number>.pdf` now returns 403
`AccessDenied` for modern numbers while still serving the old ones round 4 used.
USPTO `image-ppubs`, Espacenet and Justia all return 403. Two routes do work and
are recorded in `pdf_corpus_round6_manifest.json`'s `retrieval_note`: the EPO
publication server for any granted EP (B1 only — an A1 request returns HTTP 500),
and a read-through proxy with an HTML return format, which reaches both the
Google Patents page and its `xhr/query` search endpoint and yields the hashed
`patentimages` URL that plain `curl` can then fetch.

**A web-search summary is not a patent number.** `EP2989196B1` was returned as the
zanubrutinib patent; it is in fact *Nouvelle algue radiorésistante du genre
Coccomyxa*. Every number in this round was verified by fetching the document and
reading its own title page.
