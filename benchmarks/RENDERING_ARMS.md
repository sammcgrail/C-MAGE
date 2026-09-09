# The same 560 molecules, drawn seven ways

560 compounds, InChIKey-verified against PubChem on 560/560, rendered under seven
conditions and one channel-swapped control. Every arm is stage-3-only — one
already-cropped structure per image — so recall and precision are the same number
and segmentation is not in the way. **The molecules are identical across arms, so
any difference is the rendering and nothing else.**

| arm | strict exact | graded exact | unparseable | high-confidence | graded exact among high |
|---|---|---|---|---|---|
| RDKit, 1500 px | 82.9% | **82.9%** | 6.6% | 404/560 | 380/404 = **94.1%** |
| RDKit, 300 px | 78.6% | 78.8% | 8.8% | 376/560 | 346/376 = 92.0% |
| PubChem 300 px, background remapped to white | 56.6% | 72.3% | 11.2% | 373/560 | 337/373 = 90.3% |
| the same, upscaled to 1200 px | 56.8% | 70.5% | 12.3% | 369/560 | 326/369 = 88.3% |
| PubChem 300 px, LANCZOS-upscaled to 1200 px | 47.9% | 69.6% | 13.8% | 391/560 | 349/391 = 89.3% |
| PubChem 300 px, R and B swapped (control) | 12.3% | 59.1% | 17.9% | 112/560 | 99/112 = 88.4% |
| **PubChem 300 px, as supplied** | 11.2% | 57.9% | 17.1% | 111/560 | 98/111 = 88.3% |
| **PubChem 1500 px, as supplied** | **0.0%** | **0.0%** | **59.6%** | **0/560** | — |

## Three things this says

### 1. The confidence score is well calibrated, and that is the stable result

Graded accuracy among high-confidence outputs sits between **88.3% and 94.1%** on
every arm that produces any — across arms whose overall accuracy differs by a
factor of eight. What the rendering changes is not how right the model is when it
commits; it is **how often it commits at all**: 111 of 560 on PubChem's own 300 px
render, 404 of 560 on RDKit at 1500 px.

That is the number to quote, and it is the one the paper quotes: precision after
confidence filtering. Reporting raw accuracy across renderings mixes two different
things.

### 2. PubChem's 1500 px render breaks the recogniser completely

Zero correct out of 560, 59.6% unparseable, and **not one output above the
confidence threshold**. It is not resolution: RDKit at the same 1500 px scores
82.9%. The difference is ink.

| arm | ink fraction (px darker than 200) | graded exact |
|---|---|---|
| RDKit 300 px | 0.0180 | 78.8% |
| PubChem 300 px | 0.0151 | 57.9% |
| RDKit 1500 px | 0.0130 | 82.9% |
| **PubChem 1500 px** | **0.0030** | **0.0%** |

PubChem holds stroke width roughly constant in absolute pixels while the canvas
grows five-fold, so the drawing becomes hairline-thin relative to the image.
MolScribe resizes its input down to a fixed working size; a line that is one or
two pixels wide in a 1500 px image is sub-pixel by then, and it is gone.

**The lever is stroke width relative to canvas, not canvas size.** A bigger render
of the same molecule is worse unless the strokes scale with it.

### 3. Remapping the background is worth 45 points, and it is not a pipeline change

PubChem's PNGs have a near-white background — 245, not 255. Mapping it to true
white takes strict accuracy from **11.2% to 56.6%** and graded from 57.9% to 72.3%
on identical molecules. Nothing in the pipeline changes; only the input does.

The strict/graded gap on the raw arm (11.2% against 57.9%) is almost entirely
phantom fragments: the model welds a disconnected `I` or `[HH]` onto an otherwise
correct molecule. That is why the two columns must both be reported — the strict
number is what a caller gets if they paste the string into a database.

## What this is not

Isolated single-molecule depictions, no page, no caption, no neighbour. It measures
the recogniser, not the pipeline. For what the pipeline costs on top, see
`ARM_GAP.md`; for real documents, `REAL_DOCUMENT_RESULTS.md`.

Scored runs: `<work>/scored/img_*` and `<work>/scored/colour_*`.
