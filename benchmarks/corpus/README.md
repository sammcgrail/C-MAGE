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

- **Avoid total-synthesis papers.** They draw dozens of *abbreviated*
  intermediates per scheme, MolScribe preserves `OMe`/`Ph`/`OTBS` as R-group
  placeholders, and a SMILES containing `*` can never match a fully-expanded
  reference — 42 of 44 emitted structures for the macarpine paper were
  unscoreable for this reason, with nothing wrong with the recognition.
- **Avoid Markush-only patents.** The omeprazole patent looked ideal at a glance —
  ~18 clean drawings — and every one was an R1–R5 generic formula with the
  explicit compounds given only as text. Nothing scorable. Check at 100 dpi
  before accepting.

What works: documents where the *drawn* structures are the named compounds
themselves, at 300 dpi or better, with names resolvable to a PubChem CID.

## Diversity, which is the point

The first corpus was almost entirely PubChem-rendered depictions, which is why its
96.2% high-confidence figure did not generalise. These deliberately are not.

| file | pages | licence | drawing style | GT mols |
|---|---|---|---|---|
| [`EP0641330B1_pregabalin.pdf`](EP0641330B1_pregabalin.pdf) | 22 | Patent, public record | EPO B1 hybrid: vector Arial text with 15 inline 300-dpi  | 5 |
| [`PMC11227129_decimer_handdrawn_caffeine.pdf`](PMC11227129_decimer_handdrawn_caffeine.pdf) | 11 | CC BY 4.0 | Springer/BMC typesetting | 1 |
| [`PMC13390035_patent_ocsr_benchmark.pdf`](PMC13390035_patent_ocsr_benchmark.pdf) | 8 | CC BY 4.0 | ACS typesetting | 7 |
| [`PMC9185882_decimer_handdrawn_dataset.pdf`](PMC9185882_decimer_handdrawn_dataset.pdf) | 4 | CC BY 4.0 | Genuinely HAND-DRAWN structures (pen on paper, scanned | 2 |
| [`US4231938A_lovastatin.pdf`](US4231938A_lovastatin.pdf) | 10 | Patent, public record | 1980 USPTO scan, 300-dpi CCITT page raster | 2 |
| [`bjoc_18-169_macarpine.pdf`](bjoc_18-169_macarpine.pdf) | 7 | CC BY 4.0 | ChemDraw vector, Beilstein typesetting | 9 |
| [`bjoc_19-15_pheromones.pdf`](bjoc_19-15_pheromones.pdf) | 9 | CC BY 4.0 | ChemDraw vector | 5 |
| [`bjoc_21-197_aglacinB.pdf`](bjoc_21-197_aglacinB.pdf) | 5 | CC BY 4.0 | ChemDraw vector, Beilstein two-column typesetting | 4 |
| [`ntp_roc_adriamycin.pdf`](ntp_roc_adriamycin.pdf) | 2 | US Government work, public domain | Vector line art | 1 |
| [`ntp_roc_azacitidine.pdf`](ntp_roc_azacitidine.pdf) | 2 | US Government work, public domain | Vector line art | 1 |
| [`ntp_roc_basicred9.pdf`](ntp_roc_basicred9.pdf) | 2 | US Government work, public domain | Vector line art in a 2-column government report | 1 |
The four `US*` patents are the original corpus and are described in
[`../../MERMaid/pdfdir/SOURCES.md`](../../MERMaid/pdfdir/SOURCES.md).

## Verifying integrity

```bash
cd benchmarks/corpus && sha256sum -c SHA256SUMS
```
