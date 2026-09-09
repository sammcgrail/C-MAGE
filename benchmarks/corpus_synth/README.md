# Synthetic CXSMILES corpus — 100 compounds, 10 PDFs

A corpus drawn by RDKit so that the **CXSMILES ground truth is known by
construction**, appendix included. It exists because
[`../FINDINGS.md`](../FINDINGS.md) §5 established that our document corpus is
scored against the wrong *kind* of reference: PubChem SMILES has no appendix, so
148 of 242 predictions there cannot be graded at all, and the C-MAGE paper grades
skeleton and appendix separately against a hand-written reference CXSMILES per
segment.

The mechanism, in three lines:

```python
cond = rdAbbreviations.CondenseMolAbbreviations(mol, abbrevs, maxCoverage=0.8)
cx   = Chem.MolToCXSmiles(cond)   # '*c1ccc(*)c(...)c1 |$CF3;;;;;OMe;...$|'
draw(cond)                        # the picture and the string are one object
```

The drawing and the reference come from the same molecule object, so they cannot
disagree — which is exactly what a hand-written reference cannot guarantee.

## Read this before quoting any number from it

**RDKit line art on pure white is cleaner than any real literature figure.** One
drawing convention throughout, no scanner noise, no overlapping labels, no
hand-inked bonds, every structure alone in its own cell. Every figure this corpus
produces is an **upper bound** on what the pipeline does on real documents, and
the `basic` stratum is a **control that should sit near ceiling** — if it does
not, something upstream is broken. Per-stratum numbers are the only honest way to
read it; a single blended figure over these 100 compounds would be meaningless,
because the mix of strata is a choice we made rather than a property of the world.

## Composition

| stratum | n | what it isolates |
|---|---|---|
| basic | 22 | floor control: ≤26 heavy atoms, one fragment, neutral, no stereocentre, no superatom |
| stereo | 22 | ≥3 defined centres, wedge/hash bonds drawn |
| abbreviated | 22 | drawn **condensed** — the picture says `OMe`, `CF3`, `CO2H`. The only stratum that can grade an appendix, and the reason this corpus exists |
| complex | 12 | ≥55 heavy atoms or a macrocycle: taxanes, glycopeptides, macrolides, peptides |
| salt | 11 | counter-ions and permanent charges, drawn as multi-fragment species |
| markush | 11 | explicit `R1`/`R2`. No single molecule exists, so **skeleton only** |

Ten PDFs of ten compounds, two pages each (6 + 4). Nine groups are
**stratum-pure**, so a prediction that matches nothing can still be attributed to
a stratum by its group; `synth_mixed` puts all six strata on the same pages,
which is what a real document looks like, and is reported separately for that
reason.

Every compound is a real one resolved on PubChem: CID, isomeric SMILES, InChIKey
and molecular formula are recorded per compound in
[`../ground_truth/synthetic_manifest.json`](../ground_truth/synthetic_manifest.json),
alongside the drawn CXSMILES, its skeleton, and its appendix labels. Markush
entries carry no CID of their own — a generic scaffold is not a compound — but do
carry the CID of the drug they are asserted (by substructure match, at build
time) to generalise.

## Drawing decisions that are not cosmetic

* **Pure white background**, exactly `(255,255,255)`. DECIMER's `CropWhite` tests
  for exact white; the near-white panel behind PubChem's own depictions in the
  older test PDFs measurably costs accuracy.
* **Page geometry in units of 1/200 inch.** Stage 1 renders pages at pdf2image's
  *default* 200 dpi — `MERMaid/src/visualheist/methods_visualheist.py`
  `_pdf_to_image` calls `convert_from_path(path)` with no dpi argument — so one
  page user unit is one pixel as stage 1 will see it, and structure size in page
  inches is the thing that matters.
* **`fixedBondLength = 80`** (0.40 inch at 200 dpi) caps the scale of *small*
  molecules. Without a cap RDKit inflates aspirin to fill its 700×552 box at a
  bond length no journal would print. Large molecules are unaffected: they scale
  down to fit. Measured at stage-1 resolution, all 100 drawings have their
  largest dimension ≥ 384 px (the side of stage 3's input tensor) and 68 have
  both dimensions ≥ 300 px.
* **Vector PDF** (RDKit SVG → `rsvg-convert`), not a rasterised one: no JPEG
  ringing to turn the background off-white, and ~50 KB per file.

## Rebuild, gate, run, score

```bash
PY=.venv-ms/bin/python          # the only interpreter with RDKit

# rebuild (PubChem lookups are cached; --from-manifest rebuilds with no network)
$PY benchmarks/make_synthetic_corpus.py \
    --out-pdfs benchmarks/corpus_synth \
    --out-manifest benchmarks/ground_truth/synthetic_manifest.json

# gate: corpus integrity AND that the grader still says no. Run before quoting.
$PY benchmarks/synthetic_selftest.py     # must print GATE: open

DECIMER_WEIGHTS=/path/to/mask_rcnn_molecule.h5 \
  ./run_pipeline.sh --pdfs benchmarks/corpus_synth --out results --device cpu --local

# the paper's grade: skeleton and appendix, separately
$PY benchmarks/score_cx.py  --run-dir results/run_X \
    --manifest benchmarks/ground_truth/synthetic_manifest.json --out SCORED_CX
# the plain-SMILES grade, for the same predictions, from the existing code path
$PY benchmarks/score_run.py --run-dir results/run_X \
    --manifest benchmarks/ground_truth/synthetic_manifest.json --out SCORED

# the no-segmentation arm: crop each structure from its page by known geometry,
# feed stage 3 directly. The difference between the two runs is what stage 2 costs.
$PY benchmarks/crop_synthetic_cells.py \
    --manifest benchmarks/ground_truth/synthetic_manifest.json \
    --pdfs benchmarks/corpus_synth --out /tmp/synth_cells
benchmarks/run_stage3_only.sh --images /tmp/synth_cells --out results --device cpu
```

Scored output for both arms is committed under
[`../scored/synthetic_cx_full`](../scored/synthetic_cx_full) and
[`../scored/synthetic_cx_stage3only`](../scored/synthetic_cx_stage3only) — the
per-prediction CSVs, not the segment images, so every number can be re-derived
without republishing 4 MB of crops.

`--from-manifest` was verified rather than asserted: rebuilding from the
committed manifest with an empty PubChem cache reproduces all 20 pages
**pixel-identical**. It did not at first. The manifest recorded our *canonical*
rewrite of each SMILES rather than PubChem's string, and `Compute2DCoords` is
atom-order dependent, so the rebuild reproduced the ground truth exactly and the
drawing not at all on 18 of 20 pages. `source_smiles` now carries PubChem's
string verbatim.

`synthetic_selftest.py` is the standing gate and it has already earned its keep
twice: it rejected a stratum predicate that was wrong about erythromycin, and it
caught a negative control that had quietly stopped discriminating (aspirin's
condensed skeleton is an ortho-disubstituted benzene, so swapping its two
superatoms is a graph symmetry and *must* still grade correct — the swap control
now has to prove it can detect the swap before it is allowed to be a control).

## Licensing and provenance

Nothing here is redistributed third-party content. The structures are drawn from
scratch by RDKit from SMILES retrieved from PubChem, which places its data in the
public domain. Compound identity is recorded by CID and InChIKey so any claim in
the manifest can be checked against PubChem directly.
