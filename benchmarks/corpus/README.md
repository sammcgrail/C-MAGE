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
