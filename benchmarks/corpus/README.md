# Benchmark corpus

The PDFs the benchmark actually runs on, committed so a clone can reproduce every
number in [`../FINDINGS.md`](../FINDINGS.md) without re-fetching anything. Earlier
revisions gitignored these and documented them instead; that was a mistake — a
benchmark you cannot re-run is an anecdote.

Every file is redistributable: CC BY 4.0 journal articles, US Government works, or
published patent documents, which are public records. Provenance URLs and PubChem
CIDs for the ground truth are in
[`../ground_truth/pdf_corpus_expanded_manifest.json`](../ground_truth/pdf_corpus_expanded_manifest.json).

## Choosing what goes in here

Two lessons, both learned by getting it wrong:

- **Total-synthesis papers are weak, but not for the reason first written here.**
  The claim used to be that a SMILES containing `*` can never match a
  fully-expanded reference. That is **wrong** and is corrected in
  [`../FINDINGS.md`](../FINDINGS.md) finding 3: CXMolScribe preserves `OMe`/`Ph`/
  `OTBS` as CXSMILES labels *on purpose*, and `benchmarks/cxsmiles.py` expands
  them at comparison time. The real problem is narrower — a synthesis scheme's
  intermediates have **no reference to score against**. So such a paper is worth
  taking only if its final compounds are named and PubChem-resolvable, and expect
  most of its structures to be unscoreable regardless.
- **Avoid Markush-only patents.** The omeprazole patent looked ideal at a glance —
  ~18 clean drawings — and every one was an R1–R5 generic formula with the
  explicit compounds given only as text. Nothing scorable. Check at 100 dpi
  before accepting.

What works: documents where the *drawn* structures are the named compounds
themselves, at 300 dpi or better, with names resolvable to a PubChem CID.

- **Resolve by the printed CAS number, never the name.** `name/cisplatin` returns
  CID 5702198, "azane;dichloroplatinum"; the CAS 15663-27-1 returns CID 5460033,
  actual cisplatin — and CID 441203 is the *trans* isomer. Some INNs 404
  entirely: `lutetium Lu 177 vipivotide tetraxetan` resolves only via the synonym
  `177Lu-PSMA-617`.
- **Metal complexes need largest-fragment scoring on BOTH sides.** Every
  metal-containing PubChem reference is a disconnected multi-fragment SMILES —
  gadopiclenol is 57 heavy atoms plus `[Gd+3]`, cisplatin is `[Cl][Pt][Cl]` plus
  two `N` — while the *drawing* shows the metal inside the ring, bonded. The
  drawing is connected and the reference is not, and charge states differ. Same
  family as findings 1-3: the metric measures representation.

## Diversity, which is the point

The first corpus was almost entirely PubChem-rendered depictions, which is why its
96.2% high-confidence figure did not generalise. These deliberately are not.

| file | pages | licence | drawing style | drawn | scored |
|---|---|---|---|---|---|
| [`EP0641330B1_pregabalin.pdf`](EP0641330B1_pregabalin.pdf) | 22 | Patent, public record | EPO B1 hybrid: vector Arial text with 15 inline 300-dpi  | 5 | 5 |
| [`PMC11227129_decimer_handdrawn_caffeine.pdf`](PMC11227129_decimer_handdrawn_caffeine.pdf) | 11 | CC BY 4.0 | Springer/BMC typesetting | 1 | 1 |
| [`PMC13390035_patent_ocsr_benchmark.pdf`](PMC13390035_patent_ocsr_benchmark.pdf) | 8 | CC BY 4.0 | ACS typesetting | 7 | 4 |
| [`PMC9185882_decimer_handdrawn_dataset.pdf`](PMC9185882_decimer_handdrawn_dataset.pdf) | 4 | CC BY 4.0 | Genuinely HAND-DRAWN structures (pen on paper, scanned | 2 | 2 |
| [`US4231938A_lovastatin.pdf`](US4231938A_lovastatin.pdf) | 10 | Patent, public record | 1980 USPTO scan, 300-dpi CCITT page raster | 2 | 2 |
| [`bjoc_18-169_macarpine.pdf`](bjoc_18-169_macarpine.pdf) | 7 | CC BY 4.0 | ChemDraw vector, Beilstein typesetting | 9 | 9 |
| [`bjoc_19-15_pheromones.pdf`](bjoc_19-15_pheromones.pdf) | 9 | CC BY 4.0 | ChemDraw vector | 5 | 5 |
| [`bjoc_21-197_aglacinB.pdf`](bjoc_21-197_aglacinB.pdf) | 5 | CC BY 4.0 | ChemDraw vector, Beilstein two-column typesetting | 4 | 3 |
| [`ntp_roc_adriamycin.pdf`](ntp_roc_adriamycin.pdf) | 2 | US Government work, public domain | Vector line art | 1 | 1 |
| [`ntp_roc_azacitidine.pdf`](ntp_roc_azacitidine.pdf) | 2 | US Government work, public domain | Vector line art | 1 | 1 |
| [`ntp_roc_basicred9.pdf`](ntp_roc_basicred9.pdf) | 2 | US Government work, public domain | Vector line art in a 2-column government report | 1 | 1 |
**drawn** is how many named molecules the document actually draws; **scored** is how
many of those resolve to a PubChem CID or a printed SMILES and therefore enter the
benchmark denominator. They differ for exactly two files — aglacin E is not in
PubChem, and three of PMC13390035's Fig 3 structures have no identity hit — so the
corpus draws **138** molecules and is scored against **133**, across 24 rows.
Quote 133 with any recall
figure from this corpus; that is the denominator
[`../ground_truth/pdf_manifest_expanded.json`](../ground_truth/pdf_manifest_expanded.json)
carries and the one the benchmark recomputes.

The four `US*` patents are the original corpus and are described in
[`../../MERMaid/pdfdir/SOURCES.md`](../../MERMaid/pdfdir/SOURCES.md).

## Verifying integrity

```bash
cd benchmarks/corpus && sha256sum -c SHA256SUMS
```
| [`PMC10180415_approved2022_aa_fluorine.pdf`](PMC10180415_approved2022_aa_fluorine.pdf) | 21 | CC BY 4.0 | MDPI vector, 600-dpi stencil atom labels; 2022 FDA approvals | 12 | 12 |
| [`PMC11771699_macrocycle_drugs.pdf`](PMC11771699_macrocycle_drugs.pdf) | 24 | CC BY 4.0 | Wiley vector ChemDraw; macrocycle overprinted in COLOUR | 19 | 19 |
| [`ntp_roc_cisplatin.pdf`](ntp_roc_cisplatin.pdf) | 2 | US Government work, public domain | Vector line art; square-planar Pt(II) coordination compound | 1 | 1 |
| [`ntp_roc_pahs.pdf`](ntp_roc_pahs.pdf) | 9 | US Government work, public domain | Vector line art, two-column LIST of 15 analogues with CAS numbers | 15 | 15 |
| [`ntp_roc_heterocyclicamines.pdf`](ntp_roc_heterocyclicamines.pdf) | 5 | US Government work, public domain | Vector line art, 4 analogues on one fused-imidazo scaffold | 4 | 4 |
| [`CN108503621B_vonoprazan.pdf`](CN108503621B_vonoprazan.pdf) | 11 | Patent, public record | Chinese CNIPA patent: vector text + 150-ppi raster clippings | 8 | 8 |
| [`PMC12548288_negative_gromacs_metadump.pdf`](PMC12548288_negative_gromacs_metadump.pdf) | 10 | CC BY 4.0 | Springer/BMC typesetting; **no structures at all** | 0 | 0 |
# Proposed rows for benchmarks/corpus/README.md

Append to the diversity table, same column order:

| [`DE60100786T2_citalopram_german.pdf`](DE60100786T2_citalopram_german.pdf) | 10 | Patent, public record | German DPMA translation of an EP B1: vector text + 300-ppi CCITT **stencil** clippings | 2 | 2 |
| [`US4117118A_cyclosporin.pdf`](US4117118A_cyclosporin.pdf) | 17 | Patent, public record | 1978 scan; condensed peptide backbone, stereo printed as D/L/R **letters**, not wedges | 2 | 1 |
| [`US4943590A_escitalopram.pdf`](US4943590A_escitalopram.pdf) | 9 | Patent, public record | 1990 USPTO scan; semi-condensed art — ring skeletons, side chains as inline text | 8 | 8 |
| [`US5273995A_atorvastatin_calcium.pdf`](US5273995A_atorvastatin_calcium.pdf) | 10 | Patent, public record | 1993 USPTO scan; Ph/CONHPh labels, R/S stereo letters, Ca(2+) drawn outside a bracket | 8 | 8 |
| [`US7326708B2_sitagliptin_phosphate.pdf`](US7326708B2_sitagliptin_phosphate.pdf) | 15 | Patent, public record | 2008 USPTO scan; salt drawn as a dot-separated `.H3PO4 .H2O` adduct; 5 instrument plots | 12 | 12 |
| [`US8524733B2_deutetrabenazine.pdf`](US8524733B2_deutetrabenazine.pdf) | 27 | Patent, public record | 2013 USPTO scan; deuterium drawn as explicit `D` atom labels, 6-17 per depiction | 9 | 9 |

Arithmetic for these six rows alone: **41 drawn, 40 scored**. The one gap is deliberate and is
the round's most interesting finding: US4117118A draws two cyclosporins and only one of them can
be identified with confidence (see below).

## Two paragraphs to add under "Choosing what goes in here"

- **"N Claims, No Drawings" on a US front page is not a screen.** It means the patent has no
  formal drawing SHEETS. It says nothing about structures printed inline in the specification.
  US5273995A and US4943590A both say "No Drawings" and are full of them; US4879303A (amlodipine
  besylate) says the same and has none at all — it names every counterion in a table of words,
  which is why the ideal-looking salt-versus-salt comparison was rejected. Render the pages.
- **A document can name one compound and draw another.** US4117118A captions its first structure
  "S 7481/F-1" and its second "S 7481/F-2", then says in the next paragraph that these are
  cyclosporins A and B. At 300 dpi both drawings carry a CH2-CH3 side chain at residue 2, which is
  cyclosporin A's; and the empirical formula the document prints for F-1, C61H109N11O12, is
  PubChem's formula for cyclosporin **B**. Name, formula and drawing are three identity signals
  and they do not agree. Only F-1 enters the denominator; F-2 is drawn and not scored, for the
  same reason aglacin E is.

## One correction to the existing text


## Note on an apparent duplicate

`US7326708B2_sitagliptin_phosphate.pdf` is the same drug as the round-one
`US6699871B2_sitagliptin.pdf`, and that is the point: one draws sitagliptin as an R-substituted
Markush genus and the other draws it as a specific dihydrogenphosphate salt with the counterion
attached. Same molecule, opposite ends of the specific/generic axis, same scanner.

## Round-5 rows (11 pharmaceutical patents: drawing styles and languages)

Append to the diversity table, same column order. `drawn` counts depictions,
`scored` counts distinct compounds that resolve — they differ wherever a document
draws one molecule more than once.

| [`JP6924794B2_afuresertib.pdf`](JP6924794B2_afuresertib.pdf) | 26 | Patent, public record | Japanese JPO vector; two-component salt drawn as free base · HCl; PXRD negatives | 1 | 1 |
| [`KR101146095B1_canagliflozin.pdf`](KR101146095B1_canagliflozin.pdf) | 8 | Patent, public record | Korean KIPO vector — HANGUL, a new script; C-glycoside free base; XRPD/IR negatives | 1 | 1 |
| [`CN103025753A_ezatiostat.pdf`](CN103025753A_ezatiostat.pdf) | 30 | Patent, public record | Chinese CNIPA 300-dpi full-page RASTER scan (iText-wrapped); one tripeptide diethyl ester | 1 | 1 |
| [`RU2405786C2_asenapine.pdf`](RU2405786C2_asenapine.pdf) | 14 | Patent, public record | Russian Rospatent — CYRILLIC, a new script; salt drawn as base + full cis maleic acid | 3 | 2 |
| [`KR102514961B1_edoxaban.pdf`](KR102514961B1_edoxaban.pdf) | 13 | Patent, public record | Korean KIPO vector; salt components juxtaposed with NO dot glyph; XRPD/NMR/DSC negatives | 3 | 2 |
| [`US4110165_clavulanic_acid.pdf`](US4110165_clavulanic_acid.pdf) | 4 | Patent, public record | 1978 HAND-INKED draftsman art (4-pp extract); same molecule flat and stereo-wedged; Na/K salts; IR negative | 5 | 3 |
| [`JP6724082B2_vortioxetine.pdf`](JP6724082B2_vortioxetine.pdf) | 2 | Patent, public record | Japanese JPO vector (2-pp extract of 50); specific API + named reagents + R-group Markush | 7 | 4 |
| [`US3781268_kanamycin.pdf`](US3781268_kanamycin.pdf) | 2 | Patent, public record | 1973 freehand chair-conformation sugars, typewriter labels, no wedges (2-pp extract) | 8 | 2 |
| [`EP0308341NWB1_perindopril.pdf`](EP0308341NWB1_perindopril.pdf) | 17 | Patent, public record | French EPO B1, 300-dpi JBIG2 scan; skeletons with S/R LETTERS + condensed formulae + drawn salts | 14 | 8 |
| [`US4194047_thienamycin.pdf`](US4194047_thienamycin.pdf) | 3 | Patent, public record | 1980 hand-inked carbapenems (3-pp extract); a `Th` bracket abbreviates the whole nucleus | 16 | 5 |
| [`EP3337801B1_finerenone.pdf`](EP3337801B1_finerenone.pdf) | 6 | Patent, public record | German EPO B1 (6-pp extract of 74); dense ChemDraw vector, 21 specific synthesis intermediates | 21 | 21 |

Round-5 arithmetic: **80 drawn, 50 scored**, plus 24 generic and 2 unresolved
depictions held in `unscoreable`. Scripts added: **Cyrillic** and **Korean**, both
new to the corpus, alongside Japanese, a second Chinese in a scanned class, and
native French and German EPO grants. Ground truth and the per-document caveats are
in [`../ground_truth/ROUND5_GROUNDTRUTH_NOTES.md`](../ground_truth/ROUND5_GROUNDTRUTH_NOTES.md).

### Two more lessons, both learned by getting it wrong again

- **A 1970s patent is not automatically a good hand-inked candidate.** Four were
  rejected in this round for the *omeprazole* reason — every drawing is an R-group
  genus and the specific compounds appear only as text in the examples: captopril
  (US4046889), cimetidine (US3950333), acyclovir (US4199574) and finasteride
  (US4760071). What works instead is a *process* or *isolation* patent, which has
  to draw its actual intermediates: clavulanic acid, kanamycin and thienamycin all
  do. Render a structure page before accepting.
- **An abbreviation bracket is not a structure.** US4194047 draws six depictions in
  which a bracket labelled `Th` stands for the entire bicyclic thienamycin nucleus.
  Expanding it yields a chemically correct molecule that was never drawn, so those
  depictions are `generic`, not ground truth. The same discipline excludes
  US3781268's amikacin, which exists only behind a two-member `R3` variable.

## Round 6 — recent oncology patents

Ten patents, priority dates 2011–2024, one or two per modern small-molecule
oncology scaffold class: EGFR, BTK and CDK4/6 kinase inhibitors, KRAS G12C, two
PARP inhibitors, a PROTAC degrader, an ADC payload/linker, a SERD and a menin
inhibitor. Same column order as the table above; **drawn** here is the number of
distinct compounds the ground truth catalogues (resolved + generic + unresolved
rows), **scored** the number carrying a PubChem CID. The *depiction* count is much
larger — 598 across the ten — and is in
[`../ground_truth/ROUND6_GROUNDTRUTH_NOTES.md`](../ground_truth/ROUND6_GROUNDTRUTH_NOTES.md).

| file | pages | licence | drawing style | drawn | scored |
|---|---|---|---|---|---|
| [`EP2736895B1_osimertinib.pdf`](EP2736895B1_osimertinib.pdf) | 104 | Patent, public record | EPO B1 vector + 300-dpi CCITT clippings; 21 full-page XRPD/DSC sheets; mesylate drawn as an ION PAIR | 17 | 10 |
| [`EP3630761B1_sotorasib.pdf`](EP3630761B1_sotorasib.pdf) | 26 | Patent, public record | EPO B1 vector; complete named 7-step route; ATROPISOMER claims drawn identically; trilingual claims | 15 | 13 |
| [`US12011442B2_abemaciclib.pdf`](US12011442B2_abemaciclib.pdf) | 14 | Patent, public record | USPTO scan, NO text layer; 9 figure sheets and ONE 2D structure; FIG 2 is a 3D ORTEP | 1 | 1 |
| [`WO2021259732A1_zanubrutinib.pdf`](WO2021259732A1_zanubrutinib.pdf) | 60 | Patent, public record | WIPO A1 raster, no text layer; VARIABLE-STOICHIOMETRY co-crystal (n = 0.8–1.2); 2 ORTEPs + a flowchart | 7 | 4 |
| [`WO2017215166A1_talazoparib.pdf`](WO2017215166A1_talazoparib.pdf) | 26 | Patent, public record | WIPO A1 raster; wedges AND printed CIP letters; a spurious ChemDraw `(Z)` on an aromatic triazole | 12 | 10 |
| [`US11629137B2_niraparib.pdf`](US11629137B2_niraparib.pdf) | 46 | Patent, public record | USPTO scan, no text layer; FIG 2 prints a MOLECULAR WEIGHT under every structure; named phosphine ligands | 17 | 14 |
| [`CN114085213A_vepdegestrant.pdf`](CN114085213A_vepdegestrant.pdf) | 23 | Patent, public record | CNIPA vector Chinese + 48 raster clippings; a 54-heavy-atom PROTAC; header/footer stamps as decoys | 7 | 6 |
| [`WO2025055671A1_elacestrant.pdf`](WO2025055671A1_elacestrant.pdf) | 28 | Patent, public record | Chinese-language WIPO A1, NO text layer at all; three routes to one drug; salt cued by the text `2HCl` | 5 | 2 |
| [`US9463252B2_auristatin_MMAF.pdf`](US9463252B2_auristatin_MMAF.pdf) | 27 | Patent, public record | USPTO scan (27-pp extract of 63); Markush + squiggly-valence fragments + RESIN-BEAD solid-phase species | 5 | 0 |
| [`US12018032B2_icovamenib.pdf`](US12018032B2_icovamenib.pdf) | 98 | Patent, public record | USPTO scan, no text layer; 37 non-structure figure sheets; ~20 DEUTERATED analogues; atom-numbered figure | 4 | 1 |

Round-6 arithmetic: **90 catalogued compounds, 61 scored**, plus 14 generic and 15
unresolved rows, over 598 depictions. **Quote 61 with any recall figure from this
round**, or 38 if you drop the five recall-only groups. One file,
`US9463252B2_auristatin_MMAF.pdf`, scores **zero by design** — it is the round's
Markush stratum and the corpus's cleanest false-positive test.

### Three more lessons

- **The retrieval routes rot.** The round-4 recipe — fetch
  `patents.google.com/patent/<ID>/en`, or
  `patentimages.storage.googleapis.com/pdfs/US<n>.pdf` — now returns 503 and 403
  respectively for anything modern, as do USPTO `image-ppubs`, Espacenet and
  Justia. Two routes that work are recorded in
  [`../ground_truth/pdf_corpus_round6_manifest.json`](../ground_truth/pdf_corpus_round6_manifest.json):
  the EPO publication server for granted EP documents (B1 only; an A1 request
  returns HTTP 500), and a read-through proxy asked for HTML, which reaches both
  the Google Patents page and its `xhr/query` search endpoint and hands back the
  hashed `patentimages` URL that plain `curl` can then fetch.
- **A search-engine summary is not a patent number.** `EP2989196B1` was returned as
  the zanubrutinib patent and is in fact *Nouvelle algue radiorésistante du genre
  Coccomyxa*. Fetch the document and read its own title page; every number in this
  round was verified that way.
- **A wrong wedge resolves cleanly to the wrong molecule.** The cereblon fragment
  of ARV-471 written `[C@@H]` instead of `[C@H]` returns CID 177775766, a real
  record for the *(3R)* enantiomer — same formula, same skeleton InChIKey block,
  different stereo layer, no warning of any kind. Where a stereocentre matters,
  pin it on a printed name, not on a structure search.


## Round 9 — recent anti-infective patents

Twenty-five granted EPO B1 specifications, priority dates 2010–2022, across the
four anti-infective areas: **ten antibacterial** (two of them antimycobacterial),
**seven antiviral**, **five antifungal** and **three antiparasitic**. Same column
order as the tables above; **drawn** here is the number of distinct compounds the
ground truth catalogues (resolved + generic + unresolved rows), **scored** the
number carrying a PubChem CID. The *depiction* count is much larger — 454 across
the twenty-five — and is in
[`../ground_truth/ROUND9_GROUNDTRUTH_NOTES.md`](../ground_truth/ROUND9_GROUNDTRUTH_NOTES.md).

| file | pages | licence | drawing style | drawn | scored |
|---|---|---|---|---|---|
| [`EP3067355B1_nacubactam.pdf`](EP3067355B1_nacubactam.pdf) | 9 | Patent, public record | EPO B1 vector; a PROCESS patent that draws almost everything generically (R1/R3/P1/P2), incl. a 12-member gallery of protecting-group placeholders | 8 | 2 |
| [`EP3189841B1_cefiderocol.pdf`](EP3189841B1_cefiderocol.pdf) | 13 | Patent, public record | EPO B1 vector; TRILINGUAL claims each redrawing all four formulae; the drug drawn as two different PROTOMERS with one InChIKey | 4 | 2 |
| [`EP3299356B1_pleuromutilin.pdf`](EP3299356B1_pleuromutilin.pdf) | 9 | Patent, public record | EPO B1 vector; 5-6-8 fused DITERPENE, 8 wedge-only stereocentres; one wedge among three ring centres = under-specified | 4 | 2 |
| [`EP3529236B1_eravacycline.pdf`](EP3529236B1_eravacycline.pdf) | 14 | Patent, public record | EPO B1 vector; p25 impurity gallery puts a compound and its C-4 EPIMER 400 px apart, one wedge different; salt written both `2HCl` and as floating `HCl` | 10 | 5 |
| [`EP3592362B1_taniborbactam.pdf`](EP3592362B1_taniborbactam.pdf) | 9 | Patent, public record | EPO B1 vector; a BORONIC ACID drawn in BOTH closed cyclic and open acyclic forms (different formulae); counterions as `(HCl)2` text | 5 | 2 |
| [`EP3643719B1_spiropyrimidinetriones.pdf`](EP3643719B1_spiropyrimidinetriones.pdf) | 10 | Patent, public record | EPO B1 vector; 18 fully drawn, fully NAMED compounds, none in PubChem; genus uses `*`/`**` stereo markers and a DASHED OPTIONAL-RING arc | 2 | 0 |
| [`EP3719020B1_BLI_gallery.pdf`](EP3719020B1_BLI_gallery.pdf) | 9 | Patent, public record | EPO B1 vector; ONE figure draws six named beta-lactamase inhibitors in THREE charge conventions (neutral / external Na+ / inner salt) | 8 | 7 |
| [`EP3868768B1_contezolid_acefosamil.pdf`](EP3868768B1_contezolid_acefosamil.pdf) | 14 | Patent, public record | EPO B1 vector, complete grant; trilingual claims + 3 full-page XRPD/DSC sheets kept as negatives | 3 | 2 |
| [`EP4003521B1_telacebec.pdf`](EP4003521B1_telacebec.pdf) | 7 | Patent, public record | EPO B1 vector; only 3 structures in 156 pp, ~78 of which are instrument plots; ditosylate written as a BRACKET with subscript 2 | 4 | 2 |
| [`EP4121058B1_oxazolidinone_TB.pdf`](EP4121058B1_oxazolidinone_TB.pdf) | 17 | Patent, public record | EPO B1 vector, complete grant; a 7-step named route on ONE page; NHCbz / OAc / NHAc condensed labels | 10 | 9 |
| [`EP3221308B1_olorofim.pdf`](EP3221308B1_olorofim.pdf) | 11 | Patent, public record | EPO B1 vector; three ISOTOPOLOGUES with explicit D labels, plus two competitor drugs drawn as grey halftone scans | 10 | 8 |
| [`EP3247711B1_ibrexafungerp.pdf`](EP3247711B1_ibrexafungerp.pdf) | 8 | Patent, public record | EPO B1 vector; 11-stereocentre triterpene with ATOM POSITION NUMBERS printed inside the skeleton; 17-acid salt table never drawn | 2 | 1 |
| [`EP3720438B1_gwt1_antifungals.pdf`](EP3720438B1_gwt1_antifungals.pdf) | 9 | Patent, public record | EPO B1 vector; a congeneric series of flat, achiral analogues in 500-620 px clippings, 2-4 per page | 8 | 6 |
| [`EP3810115B1_manogepix_prodrugs.pdf`](EP3810115B1_manogepix_prodrugs.pdf) | 10 | Patent, public record | EPO B1 vector; specific and generic drawn on ONE page; a circled `A` ring placeholder; a drawn ISOCYANATE | 5 | 3 |
| [`EP4069690B1_opelconazole.pdf`](EP4069690B1_opelconazole.pdf) | 9 | Patent, public record | EPO B1 vector; a 1,2,4-triazole azole with two adjacent THF stereocentres, one bold and one hashed wedge | 1 | 1 |
| [`EP3578557B1_cipargamin.pdf`](EP3578557B1_cipargamin.pdf) | 8 | Patent, public record | EPO B1 vector; a 6-step route to a SPIRO quaternary centre, drawn almost entirely behind CO2H/NHAc/CO2Me/NHBoc/OMs labels | 8 | 6 |
| [`EP3743419B1_antiparasitic_tetrazoles.pdf`](EP3743419B1_antiparasitic_tetrazoles.pdf) | 7 | Patent, public record | EPO B1 vector; three (2R)/(2S) DIASTEREOMER pairs and two TETRAZOLE N-1/N-2 REGIOISOMER pairs, partners drawn on the same page | 10 | 8 |
| [`EP4061375B1_antimalarial_markush.pdf`](EP4061375B1_antimalarial_markush.pdf) | 9 | Patent, public record | EPO B1 vector; genus-only - floating substituent `R10(m)` whose bond crosses the ring, and a scheme whose protecting group is a variable | 3 | 0 |
| [`EP3321253B1_tecovirimat.pdf`](EP3321253B1_tecovirimat.pdf) | 19 | Patent, public record | EPO B1 vector, complete grant; a rigid POLYCYCLIC CAGE with six explicit stereo hydrogens and no CIP letters | 9 | 9 |
| [`EP3473629B1_baloxavir_route.pdf`](EP3473629B1_baloxavir_route.pdf) | 6 | Patent, public record | EPO B1 vector; a 7-member route with Japanese-style `[Chem. n]` headings and NOT ONE chemical name; every box drawn flat | 9 | 7 |
| [`EP3512863B1_ethynyl_nucleosides.pdf`](EP3512863B1_ethynyl_nucleosides.pdf) | 6 | Patent, public record | EPO B1 vector; a PHOSPHORUS stereocentre drawn as a WAVY bond beside four hard-wedge sugar centres; 2-ethynyl reads as methyl at low dpi | 5 | 3 |
| [`EP3544977B1_pritelivir.pdf`](EP3544977B1_pritelivir.pdf) | 9 | Patent, public record | EPO B1 whose structure clippings are SCANNED GREYSCALE rasters; each captioned with its molecular formula and mass | 3 | 2 |
| [`EP3668859B1_lenacapavir.pdf`](EP3668859B1_lenacapavir.pdf) | 9 | Patent, public record | EPO B1 vector; ATROPISOMERS drawn side by side and claimed separately; the claimed sodium salt is never drawn | 2 | 2 |
| [`EP3953330B1_nirmatrelvir.pdf`](EP3953330B1_nirmatrelvir.pdf) | 7 | Patent, public record | EPO B1 vector; two schemes drawing 16 resolvable species incl. six unlabelled REAGENTS/SOLVENTS; a PROTEIN SEQUENCE LISTING page | 19 | 16 |
| [`EP4079746B1_molnupiravir.pdf`](EP4079746B1_molnupiravir.pdf) | 13 | Patent, public record | EPO B1 vector, complete grant; RIBOFURANOSIDES with an anomeric centre; `NH2.H2SO4` as a condensed atom label | 7 | 5 |

Round-9 arithmetic: **159 catalogued compounds, 110 scored**, plus 18 generic and
31 unresolved rows, over 454 depictions on 251 kept pages totalling 7.7 MB.
**Quote 110 with any recall figure from this round**, or 69 if you drop the seven
recall-only groups. Two files score **zero by design** and are false-positive
tests only — `EP3643719B1_spiropyrimidinetriones.pdf`, where eighteen
fully named compounds have no PubChem record at all, and
`EP4061375B1_antimalarial_markush.pdf`, where almost nothing drawn is a molecule.

Twenty-two of the twenty-five files are page extracts; the kept range is in
`pages_kept` in both round-9 manifests. Three are complete grants because they
were already small (14, 17 and 19 pages).

### Five more lessons

- **The retrieval routes rotted again, and the replacement is better.**
  `patents.google.com` still 503s, and round 6's read-through proxy now returns
  Google's *"automated queries"* interstitial. Two routes carried all
  twenty-five documents and neither touches Google: the **EPO publication
  server** (`data.epo.org/publication-server/.../EP<n>NWB1/document.pdf`, B1
  only), whose `/document.xml` sibling **honours HTTP Range requests** so a 26 KB
  range fetch returns title, applicant and dates for 1/40th of the bytes of the
  PDF; and **PubChem PUG-REST as a patent search engine**,
  `/compound/name/<drug>/xrefs/PatentID/JSON`, which lists every patent
  cross-referenced to a compound. Filter that to `EP…B1` numbered 3xxxxxx or
  4xxxxxx and screen the survivors by title. About 150 candidates were screened
  before one PDF was downloaded.
- **`pdfimages -png` beats re-rendering the page.** Structure clippings in an EPO
  B1 are embedded at 300 dpi or better; pulling them directly gives a sharper
  image than `pdftoppm` at any sane dpi, and it gives the box boundaries for
  free. Two wedges in this round were read wrong at 100 dpi and right at native
  resolution.
- **Derive a variant's SMILES from the parent's PubChem record, not from the
  drawing.** Every close analogue here was built by taking the catalogued drug's
  own SMILES and changing only the substituent in question, so shared
  stereocentres keep a provenance. The one time that discipline was skipped —
  a free-hand 2',3'-O-isopropylidenecytidine — the anomeric centre inverted and
  PubChem returned a **real record for the other anomer** with no warning.
- **A `CID 0` answer from a structure search is a result, not a failure.** It is
  what caught a wrong bicyclo[3.2.1] diastereomer in the nacubactam group. It is
  also what makes five certain-but-uncatalogued compounds honest `unresolved`
  rows here rather than invented references.
- **"N examples with full IUPAC names" is not a screen either.** Two patents were
  rejected in this round because every name was correct and none of them
  resolved: a 2017 Chinese siderophore-monobactam filing (33 examples) and, kept
  as a deliberate zero, an 18-example spiropyrimidinetrione filing. New chemical
  entities from recent filings have no public reference to score against —
  check one name against PubChem before accepting the document.

## Round 7 — recent cardiovascular, metabolic/diabetes and renal patents

Twenty-five patents, priority dates 2012–2024, one per drug: ten cardiovascular
(cardiac myosin activator and inhibitor, sGC stimulator, two TTR stabilisers,
factor XIa inhibitor, CETP inhibitor, ATP-citrate lyase inhibitor, endothelin
antagonist, neprilysin-inhibitor prodrug), eight metabolic/diabetes (two SGLT2
inhibitors, oral GLP-1 agonist, THR-β agonist, pan-PPAR agonist, PPAR-α
modulator, mitochondrial antihyperglycaemic, bile-acid/FXR chemistry) and seven
renal (two HIF-PH inhibitors, NHE3 inhibitor, factor B inhibitor, dual
endothelin/AT-1 antagonist, Nrf2 activator, plus a third HIF-PH inhibitor as the
round's Markush stratum).

**Every file is a page extract.** The originals total 1,210 pages and 66.5 MB;
the committed files total **47 pages and 2.32 MiB**, average 94 KB, largest
237 KB. Pages were picked so that *every depiction on a kept page is catalogued*,
which is why — unlike most of round 6 — **all twenty-five groups are scoreable
for precision as well as recall**. Same column order as the table above; **drawn**
is the exact depiction count on the kept pages (no estimates anywhere in this
round), **scored** the number of distinct compounds carrying a PubChem CID.

| file | pages | licence | drawing style | drawn | scored |
|---|---|---|---|---|---|
| [`EP3525784B1_sparsentan.pdf`](EP3525784B1_sparsentan.pdf) | 2 | Patent, public record | EPO B1, English, vector text + 300-ppi CCITT clippings; condensed `O2S` sulfonyl; 6 intermediates bracketed "not isolated" | 10 | 8 |
| [`US11078230B2_omaveloxolone.pdf`](US11078230B2_omaveloxolone.pdf) | 2 | Patent, public record | USPTO scan, no text layer; pentacyclic triterpenoid, 7 ring-fusion stereocentres; **139 non-chemical drawing sheets** in the original | 1 | 1 |
| [`US11208391B2_tafamidis.pdf`](US11208391B2_tafamidis.pdf) | 1 | Patent, public record | USPTO scan; two-component solids drawn as VERTICAL STACKS with no connector; printed name joins components with an asterisk | 4 | 4 |
| [`US11370739B2_sacubitril.pdf`](US11370739B2_sacubitril.pdf) | 1 | Patent, public record | USPTO scan; the corpus's first WAVY BONDS, alongside a bold and a hashed wedge on one page | 3 | 3 |
| [`US11465970B2_roxadustat_intermediates.pdf`](US11465970B2_roxadustat_intermediates.pdf) | 2 | Patent, public record | USPTO scan; generic and specific structures side by side, same column, same style; "19 Claims, No Drawings" | 9 | 2 |
| [`US11479577B2_chenodeoxycholic_acid.pdf`](US11479577B2_chenodeoxycholic_acid.pdf) | 1 | Patent, public record | USPTO scan; 27 numerals and ring letters A–D printed INSIDE the structure box; 9 wedged stereocentres | 2 | 1 |
| [`US11680058B2_aprocitentan.pdf`](US11680058B2_aprocitentan.pdf) | 2 | Patent, public record | USPTO scan; 13 XRPD sheets BEFORE any text; the corpus's only sulfamide | 1 | 1 |
| [`US12247024B2_aficamten.pdf`](US12247024B2_aficamten.pdf) | 2 | Patent, public record | USPTO scan; a drawn DPPA inversion, a sulfoxide stereocentre, four compounds whose two enantiomers both exist in PubChem | 15 | 12 |
| [`US12269811B2_omecamtiv_mecarbil.pdf`](US12269811B2_omecamtiv_mecarbil.pdf) | 5 | Patent, public record | USPTO scan; Schemes 1–3 + a DVS plot. **The document draws its own drug substance WRONG in Scheme 1** and correctly twice elsewhere | 26 | 13 |
| [`US20240238266A1_iptacopan.pdf`](US20240238266A1_iptacopan.pdf) | 1 | Patent, public record | USPTO pre-grant scan; salt+hydrate cued by two stacked words `HCl`/`H2O` beside identical line art | 2 | 2 |
| [`US20240246949A1_lanifibranor.pdf`](US20240246949A1_lanifibranor.pdf) | 2 | Patent, public record | USPTO pre-grant scan; one structure, eleven XRPD sheets; pages kept in reverse order | 1 | 1 |
| [`US20240391897A1_obicetrapib.pdf`](US20240391897A1_obicetrapib.pdf) | 1 | Patent, public record | USPTO pre-grant scan; **four salt notations on one page**, incl. a bracketed anion with subscript 2 and a Ca²⁺ outside | 9 | 9 |
| [`WO2020051014A1_tenapanor.pdf`](WO2020051014A1_tenapanor.pdf) | 2 | Patent, public record | WIPO A1 scan; 76-heavy-atom SYMMETRIC dimer drawn at a 9:1 aspect ratio; ion-pair di-HCl | 7 | 4 |
| [`WO2021137144A1_ertugliflozin.pdf`](WO2021137144A1_ertugliflozin.pdf) | 1 | Patent, public record | WIPO A1 scan, oversized media box; a CO-CRYSTAL drawn as two complete molecules with no connector | 2 | 2 |
| [`WO2022006427A1_vadadustat_intermediates.pdf`](WO2022006427A1_vadadustat_intermediates.pdf) | 2 | Patent, public record | WIPO A1 scan; a Cl/Br/F halogen triplet, structures set mid-sentence, a quinoid ion pair with no PubChem record | 9 | 3 |
| [`WO2022149161A1_bempedoic_acid.pdf`](WO2022149161A1_bempedoic_acid.pdf) | 2 | Patent, public record | WIPO A1 scan; **the corpus's only ring-free stratum** — six acyclic C15 zigzags where identity is vertex count | 6 | 3 |
| [`WO2023034364A1_vericiguat.pdf`](WO2023034364A1_vericiguat.pdf) | 3 | Patent, public record | WIPO A1 scan; HAIRLINE structure at ~1/3 the stroke weight of the body text; 13 XRPD sheets in the original | 1 | 1 |
| [`WO2023052652A1_acoramidis.pdf`](WO2023052652A1_acoramidis.pdf) | 4 | Patent, public record | WIPO A1 scan; free base and salt separated only by the bare word `HCl` | 2 | 2 |
| [`WO2023209729A1_imeglimin.pdf`](WO2023209729A1_imeglimin.pdf) | 2 | Patent, public record | WIPO A1 scan; **racemate vs single enantiomer, same line art, one wedge apart**; 8–11 heavy-atom molecules | 5 | 4 |
| [`WO2024022998A1_daprodustat.pdf`](WO2024022998A1_daprodustat.pdf) | 1 | Patent, public record | WIPO A1 scan, sans-serif body text; a TAUTOMER PAIR named twice on one page, only one matching the picture | 1 | 1 |
| [`WO2024167899A1_milvexian.pdf`](WO2024167899A1_milvexian.pdf) | 1 | Patent, public record | WIPO A1 scan; the corpus's first MACROCYCLIC drug in a patent, ring closed through three heteroaryls | 1 | 1 |
| [`WO2024201358A1_pemafibrate.pdf`](WO2024201358A1_pemafibrate.pdf) | 2 | Patent, public record | WIPO A1 scan; a Mitsunobu INVERSION drawn with the same hash on both sides of the step | 6 | 6 |
| [`WO2024228213A1_danuglipron.pdf`](WO2024228213A1_danuglipron.pdf) | 1 | Patent, public record | WIPO A1 scan; one stereocentre in 41 heavy atoms, on a four-membered oxetane | 1 | 1 |
| [`WO2025056984A1_bexagliflozin.pdf`](WO2025056984A1_bexagliflozin.pdf) | 1 | Patent, public record | WIPO A1 scan; sugar stereochemistry carried by hash marks INSIDE the `HO`/`OH` labels, not by wedges | 1 | 1 |
| [`WO2025146705A1_resmetirom.pdf`](WO2025146705A1_resmetirom.pdf) | 3 | Patent, public record | WIPO A1 scan; two adjacent-nitrogen heterocycles where only one N of each pair is substituted | 1 | 1 |

Round-7 arithmetic: **126 depictions, 87 scored**, plus 7 generic and 8
unresolved rows. **Quote 87 with any recall figure from this round**, all
twenty-five groups included. Ground truth and the per-document caveats are in
[`../ground_truth/ROUND7_GROUNDTRUTH_NOTES.md`](../ground_truth/ROUND7_GROUNDTRUTH_NOTES.md).

### Five more lessons, four of them learned by getting it wrong

- **A granted patent can draw its own drug wrong, and the corpus has to say so.**
  `US12269811B2` Scheme 1 draws omecamtiv mecarbil's drug substance with an
  acetyl in place of the methyl carbamate and a p-tolyl in place of the
  6-methylpyridin-3-yl, and captions a plain cyclohexanecarboxylate "PIPN". Both
  verified at 320 dpi; pages 1 and 10 of the same document are correct. When the
  caption and the picture describe different molecules, **neither can check the
  other**, so the row goes to `unscoreable` — a refusal to pick a side, not a
  missing reference. Four of this round's eight unresolved rows are of that kind.
- **Trim to what you have catalogued, not to what looks important.** Cutting each
  document down to the pages whose every depiction is in the manifest turned the
  whole round precision-scoreable, which round 6 could not manage for six of ten
  groups — and it took 66.5 MB down to 2.3 MB. A 209-page patent contributing two
  pages beats the whole grant twice over.
- **150 dpi cannot tell a bold wedge from a hashed one on a USPTO bitonal scan.**
  It could on every EPO and WIPO document tried. The aficamten azide read as a
  hash at 150 dpi and is a solid wedge at 400. Render stereocentres at 300–400
  before deciding anything.
- **Assert the InChIKey at manifest build time, not by eye.** Three stereochemical
  transcription errors survived reading and died at the build assertion, the worst
  being a tenapanor dihydrochloride written (4S,4′R) instead of (4S,4′S) — a real
  PubChem record, CID 134153384, same formula, same skeleton block, whose title
  spells out the mistake and which no API response flags.
- **Two OCR passes appending to one file produce interleaved pages that read like
  a valid document.** A 63-page patent came out with 115 `=== PAGE` markers and a
  paragraph from p2 filed under p13; only a page render disagreed. Check the
  marker count against `pdfinfo` before trusting any OCR text.
