# Resume plan — written at the pause, 2026-09-09 ~21:00 UTC

The box is being taken down for more RAM, CPU and disk. This is the state and
the plan, written so the next session does not re-derive any of it.

## The finding that changes everything, and why it was late

**Stage 2 destroys most real figures.** Measured across 135 stage-1 figures in
18 real documents:

| | |
|---|---|
| mean ink retained | 39.8% |
| **median ink retained** | **29.8%** |
| figures producing ZERO segments | 35 (26%) |
| figures retaining over 90% | 1 (1%) |

A quarter of figures are lost outright. The pregabalin patent lost five,
including one carrying 49,346 px of structure.

**This is stock C-MAGE.** `complete_structure.py` and `pipeline_dis.py` are
byte-identical to upstream; `decimer_segmentation.py` differs by three deleted
lines, all of them the unguarded Zenodo download. `DECIMER_BBOX_PAD` was off in
every run.

**Why it took so long to see:** the synthetic corpus reported mean retention
99.3% and median 100%, and that was true — of RDKit line art, one structure per
cell, pure white, generous spacing. It does not exercise the failure. A corpus
built to give exact ground truth gave false comfort on the one axis that
mattered most, and the gallery showed it in a single screenshot.

**Rule to carry:** a corpus that cannot reproduce a failure cannot report its
absence. Check any headline number against real inputs before trusting it.

## What is true and measured

- **Image uploads now skip stage 2** (shipped, verified in production). The
  reported caffeine figure went from `C=C1C(N)=C(N)NC(=O)N1C` to
  `Cn1c(=O)c2c(ncn2C)n(C)c1=O` at 0.898. An image upload is one already-cropped
  structure; segmenting it can only lose ink.
- **Ink loss predicts failure.** On 143 synthetic drawings: lost nothing
  63/108 = 58.3% correct, lost anything **0/29 = 0.0%**. RR 2.4, Fisher
  p = 8.4e-10. Size and missing-prediction confounds rejected; `basic` separates
  17/17 clean vs 0/7 lossy. **Synthetic only — must be repeated on real documents.**
- **Where the lost ink sits (synthetic only):** 37.8% outside the crop rectangle
  (a bbox pad reaches it), 62.2% inside at a median 27 px from the edge (only
  mask dilation reaches it).
- **We match the paper where the comparison is valid.** Precision after
  confidence filtering: paper 77.6% (CM-DB) / 82.9% (MEP), this box **84.0%** on
  675 PubChem depictions. Those ran stage-3-only, so they carry no segmentation
  damage — which is exactly why they are comparable and the PDF numbers are not.

## Do this, in order

1. **Re-measure the 37.8/62.2 split on real documents.** It decides whether bbox
   padding or mask dilation is the lever, and it is currently a synthetic-only
   number. Until it is repeated on real figures, do not act on it.
2. **Add a retention guard to the pipeline.** After stage 2, compare segment ink
   against the source figure. Below a threshold, fall back to feeding stage 3 the
   whole figure — the single-structure path that already works. A figure that
   lost 70% of its ink should never be silently scored as a recognition failure.
3. **Re-run everything on the fixed system**: 28 committed PDFs, the synthetic
   corpus (both arms), and the 743 ringleader images. With more cores, run the
   arms concurrently and cap OMP threads (measured: 4.1 s/image against ~30 s
   uncapped).
4. **Rebuild both pages from the new runs.** Show crop-versus-source ink
   retention on every gallery card — it is cheap and it is what a reader needs to
   judge a result. Label CXSMILES as CXSMILES, never as SMILES.
5. **Then** revisit the paired arm-gap tables and the per-stratum results, which
   were mid-flight at the pause.

## Traps that have already cost time — do not rediscover them

Nine bugs on this project shared one signature: **a failure whose output is
indistinguishable from the measurement itself.** Eight returned a plausible
number; only one crashed. In order of how much they cost:

- Two arms scored over **different corpora**, printed side by side, where the gap
  between them *is* the finding. Both columns individually correct.
- Unrun PDFs reading as **total erasure** — a drawing stage 1 never saw and one
  stage 2 wiped out both emit retention 0.0.
- A **mis-assigned segment** returning a plausible 0.967 retention while
  comparing two different molecules, because retention is a ratio of counts.
- A **Pearson coefficient** over a variable whose median is exactly 1.0 — an
  estimator structurally blind to the tail it was meant to measure.
- A **self-referential validation**: "matcher agrees with scorer 143/0", where
  the scorer's input was built from the matcher's own output.
- **`ast.parse` passing** on a dataclass with a defaulted field before a
  non-defaulted one. Parsing is not constructing; it 502'd the live site.

The disciplines that caught them, worth keeping:

- **R1.** Two independently-constructed views of the same quantity, required to
  agree. A single view cannot report its own failure.
- **R2.** If a job can be interrupted, process in an order where every prefix is a
  valid sample of the whole.
- **R3.** When a finding is a *difference* between two measurements, the
  comparison needs its own validity check — matched scope — independent of either
  measurement being correct.

## Operational notes

- `DECIMER_WEIGHTS=/root/cmage-models/decimer/mask_rcnn_molecule.h5`. Never
  Zenodo; it 504'd three times in one day.
- Nothing in this stack caps OMP threads, so concurrent runs thrash rather than
  share.
- Deploy from `/root/cmage` with `--build`. A plain `up -d` recreates from a
  stale image and silently reverts.
- The repo has had several concurrent writers. Commit by explicit path.
