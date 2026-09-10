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
