# Re-rendering PubChem depictions: 0.0% → 61.1%

PubChem's own 1500 px PNG scores **0 of 1010** across three independently built
compound sets, and **nine** attempts to repair those images by resampling all
failed (`RENDERING_ARMS.md`). Re-rendering works.

## What was done

PubChem cannot serve a usable large image at all — its PUG SVG endpoint returns 400,
and the `imgsrv` service its own website uses ignores `width`/`height` and always
returns 300×300. So the image has to be redrawn.

To make this a **re-render of PubChem's depiction** rather than a fresh drawing,
each compound's 2D SDF is fetched — which carries the atom coordinates PubChem
itself laid out — and redrawn from those coordinates. Same layout, same orientation.
The only thing changed is **stroke width, scaled to the canvas** instead of held
constant in absolute pixels.

`used_pubchem_coords` is reported by the build for exactly this reason: a run where
that number is low is a fresh RDKit layout wearing this arm's name. Final build:
**560/560**.

## Result, all on the same 560 compounds

| arm | strict | graded | high-conf outputs | right among high | phantom frags | unparseable |
|---|---|---|---|---|---|---|
| RDKit 1500, fresh layout | 82.9% | 82.9% | 404 | 94.1% | 9.1% | 6.6% |
| **PubChem 1500, re-rendered** | **61.1%** | **61.1%** | **353** | **88.7%** | **10.5%** | 11.4% |
| PubChem 300 + background remap | 56.6% | 72.3% | 373 | 90.3% | 24.1% | 11.2% |
| PubChem 300, as supplied | 11.2% | 57.9% | 111 | 88.3% | 68.6% | 17.1% |
| PubChem 1500, as supplied | 0.0% | 0.0% | **0** | — | 12.5% | 59.6% |

## What it actually fixed, which is not what the headline suggests

Against the realistic baseline — PubChem at 300 px, the size a user would fetch —
re-rendering moves **graded accuracy barely at all: 57.9% → 61.1%**. It moves
**strict accuracy by fifty points: 11.2% → 61.1%**.

The difference between those two columns is phantom fragments, and that is what was
repaired: **68.6% → 10.5%** of predictions carry a disconnected `I` or `[HH]` welded
on beside the molecule. Re-rendering does not make the reader recognise *more*
molecules. It makes the output **clean** — it stops corrupting answers that were
already right.

That distinction matters to a caller: strict is what you get pasting the string into
a database, and it is the column that went from unusable to usable.

The unparseable rate also collapses, 59.6% → 11.4%, and the arm goes from **zero**
high-confidence outputs to 353.

## The 22 points that remain

Re-rendered PubChem reaches 61.1%; RDKit's own layout reaches 82.9%, on the same
molecules with the same stroke scaling. The gap is not stroke width — that is now
identical — it is the **layout itself**: bond lengths, angles and atom placement.
PubChem's depiction is measurably harder to read than RDKit's even when drawn
properly. That is a finding about depiction style, and it is not explained here.

## Practical guidance

- Fetch PubChem at **300 px**, not larger, and remap the near-white background.
- If a larger image is needed, **re-render from the compound's 2D SDF** with stroke
  width scaled to the canvas. Do not resample the 1500 px PNG; nine ways of doing
  that were measured and all of them score 0–36%.

Build: `<work>/rerender.py`. Scored run: `<work>/scored/pubchem_rerender/`.
