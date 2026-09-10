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

### That mechanism was tested and it is WRONG — or nowhere near sufficient

The paragraph that used to sit here said "the lever is stroke width relative to
canvas". So five interventions were built to move exactly that, and scored against
the same 560 answers:

| intervention | ink fraction reached | graded exact |
|---|---|---|
| PubChem 300 px + background remapped (the existing best) | ~0.0180 | **72.3%** |
| PubChem 300 px, untouched | 0.0151 | 57.9% |
| PubChem 300 px + 3 px ink dilation | 0.0408 | 36.1% |
| autoscale until ink fraction hits RDKit's | 0.0060 | 2.0% |
| **1500 px + proportional dilation** | **0.0130 — identical to RDKit 1500** | **0.0%** |
| 1500 px downscaled to 300 px (± remap) | 0.0042 | 0.0% |

The fifth row settles it. Ink fraction was raised to exactly the value of the
best-scoring arm and the score stayed at zero. **Ink fraction correlates with score
across natively-rendered arms and does not cause it.** Every intervention that
moved ink fraction alone made things worse.

Two facts to keep, and the honest gap between them:

- PubChem's 1500 px render scores 0/560; RDKit's 1500 px render scores 82.9%. So it
  is not resolution.
- Native PubChem 300 px scores 57.9%, but the 1500 px render **downscaled** to
  300 px scores 0.0%. So whatever the 1500 px render lacks is not recoverable by
  resampling — and it is not merely thinness, because thickening does not help
  either.

What the downscale measurement does show: LANCZOS resampling of a hairline turns it
into faint grey rather than a thin black line — ink fraction *fell* to 0.0042
because the strokes rose above the 200 threshold entirely. So the strokes are faint
as well as thin, which is why contrast-restoring transforms were tried next
(recorded below). Whether they help is a measurement, not a deduction; the last
deduction on this page cost five arms.

**Practical guidance, which is boring and holds:** request 300 px from PubChem and
remap the near-white background to true white. 72.3% against 57.9% untouched and
0.0% for the 1500 px render. Nothing invented here beat it.

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

---

## Replication on 250 independent compounds

The seven arms were repeated on **250 new compounds**, disjoint from the 560 by both
CID and InChIKey (verified 250/250, zero overlap), deliberately weighted toward
classes the first set was thin on — organometallics, boron and phosphorus drugs,
large peptides, fused polyheterocycles, deuterated drugs.

| rendering | new 250, graded exact | original 560, graded exact |
|---|---|---|
| RDKit 300 px | 67.6% | 78.8% |
| PubChem 300 px + background remapped | 59.6% | 72.3% |
| PubChem 300 px + remap, upscaled | 60.4% | 70.5% |
| PubChem 300 px LANCZOS-upscaled | 57.2% | 69.6% |
| PubChem 300 px, as supplied | 49.2% | 57.9% |

Every arm falls about ten points, because the new compounds are harder — and the
**ordering is unchanged**. The rendering effect is a property of the rendering, not
of which molecules happened to be in the first corpus.

## A mechanism that was nearly published on manufactured evidence

After the ink-fraction explanation failed, a contact sheet of PubChem 1500 px
figures appeared to show **no atom labels at all** — no N, no O, 15-crown-5 reduced
to a bare circle, glucose to a plain hexagon. It is a clean, satisfying story: the
model is handed an unlabelled carbon skeleton, so of course it scores zero, and no
resampling could ever fix it.

It is false. Cropping one image at **1:1** instead of viewing a thumbnail shows the
N and O glyphs drawn perfectly. The contact sheet had scaled 1500 px down to 190 px,
which erases small glyphs — **the inspection method had produced the evidence for
its own conclusion.**

Recorded because the near-miss is the lesson: three explanations for this failure
have now been advanced and two of them were wrong, one of them refuted by a
measurement designed to confirm it. The remaining honest statement is at the top of
this file: PubChem's 1500 px render scores zero, RDKit's does not, and resampling
does not recover it. **Why is not established.** Do not fill that gap with a story.
