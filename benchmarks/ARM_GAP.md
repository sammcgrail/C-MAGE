# What segmentation costs — the paired arm gap, matched scope

Two arms of the same pipeline, over **exactly the same 38 synthetic documents**:

- **full pipeline** — stage 1 (VisualHeist) → stage 2 (DECIMER segmentation) → stage 3 (CXMolScribe)
- **stage 3 only** — the same 38 documents' cells fed straight to CXMolScribe, one
  already-cropped structure per image. Same model, same script, one variable removed.

451 molecules are drawn in those 38 documents.

| arm | structures emitted | strict exact | graded exact | recall strict | recall graded |
|---|---|---|---|---|---|
| full pipeline | 445 | 206/445 = 46.3% | 271/445 = 60.9% | 206/451 = 45.7% | 294/451 = 65.2% |
| stage 3 only | 451 | 245/451 = 54.3% | 357/451 = 79.2% | 245/451 = 54.3% | 384/451 = 85.1% |

**Segmentation costs 8.6 points strict and 19.9 points graded.** On graded recall the
gap is 65.2% → 85.1%.

## Why the scope had to be matched

The first version of this table on this project put two arms side by side that had
been scored over **different corpora**, and the gap between them *was* the finding.
Both columns were individually correct. This one restricts both arms to the 38
documents the full arm actually reached, and states the denominator (451) that both
share. If you extend either arm, re-derive the intersection — do not append a row.

The full arm emits 445 structures for 451 drawn molecules, near 1:1, so on clean
synthetic input segmentation is **degrading** structures rather than shredding them
into fragments. That is not true of real documents, where 242 structures come back
for 34 curated molecules.

## The complete stage-3-only arm

Over all 1031 cells of synthetic v2 (one structure per image, so recall = precision):

| | |
|---|---|
| strict exact | 598/1031 = 58.0% |
| strict exact + stereo-relaxed | 651/1031 = 63.1% |
| graded exact | 800/1031 = 77.6% |
| graded exact + stereo + salt | 859/1031 = 83.3% |
| genuinely different molecule | 89 = 8.6% |
| unparseable | 55 = 5.3% |

By the pipeline's own confidence split (threshold 0.8431): **492/728 = 67.6% exact
among high-confidence outputs**, against 106/303 = 35.0% among low-confidence. The
confidence score separates.

Of the 325 structures the strict metric calls `wrong`, **220 (67.7%) are the drawn
molecule written differently**; only 89 are a different molecule.

## What this is not

Synthetic. RDKit line art, one structure per cell, pure white, generous spacing.
Every number here is an upper bound, and the `basic` stratum is a control that
should sit near ceiling rather than a result. The real-document gap is larger and
is measured separately — see `docs/RESUME_PLAN.md` and `tools/retention_guard.py`
for why the real-document ink figures need a structure-bearing denominator before
they can be quoted.

Runs: `<work>/scored/fullarm_merged/` and `<work>/scored/s3arm_merged/`.
The stage-3 arm was sharded 4 ways round-robin over `crop_order.txt`, so every shard
and every prefix of a shard is a valid interleaved sample of the whole.
