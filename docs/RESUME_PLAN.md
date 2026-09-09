# Resume plan — written at the pause, 2026-09-09 ~21:00 UTC

The box is being taken down for more RAM, CPU and disk. This is the state and
the plan, written so the next session does not re-derive any of it.

## The finding that changes everything, and why it was late

**Stage 2 destroys most real figures.** Measured across 135 stage-1 figures in
18 real documents:

| | |
|---|---|
| mean ink retained | 34.3% |
| **median ink retained** | **29.1%** |
| figures producing ZERO segments | 37 (27.4%) |
| figures retaining over 90% | 1 (1%) |

A quarter of figures are lost outright. The pregabalin patent lost six, including one carrying 145,947 px — the largest
figure in the document, and hidden by the matching bug described below.

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

## Corrections applied at the pause — read before trusting an earlier number

- The first ink-retention JSON matched segments to figures by name **prefix**, so
  `image_1` claimed the segments of `image_10..19`. Three figures reported
  retention above 1.0 (up to 3.49), which is impossible and was the missed tell.
  Recomputed with an anchored `<figure>_molecule_<n>.png` match and verified by
  segments-counted == segments-on-disk (569 == 569).
- **84.0% was mispaired** (see above). Over the images with a reference it is 90.8%.
- **"Comparable to the paper" was too generous.** The paper's 77.6% is
  post-segmentation on real documents graded against the segment image; ours is
  pre-segmentation on clean renders graded against PubChem SMILES. Same range,
  easier input, different grading — not like-for-like.
- **Everything under /tmp was copied to `/root/cmage-tmp-preserve/`** (958 MB).
  `/tmp` is wiped at boot by `systemd-tmpfiles-setup --boot`; this is certain.
- `benchmarks/report_partial/report.md`'s paired arm-gap table is contaminated —
  the stage-3 column's denominator covers drawings it never processed, which
  inverts the direction. **Do not read it; recompute** with stage-3 coverage
  defined as crops that produced a workbook row.

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

---

# Harvest at the stop, 2026-09-09 ~21:45 UTC

Everything below exists on disk and is **unscored or partially scored**. None of
it is lost; none of it is finished. `/tmp` is wiped at boot, so a full copy is at
**`/root/cmage-tmp-preserve/`** (958 MB) — check there first if `/tmp` is empty.

## Runs that completed but were never scored

| what | where | state |
|---|---|---|
| 17 previously-unrun committed PDFs | `/tmp/cmage-rest/<doc>/out/run_*/` | **7 of 17 documents** reached stage 3. Row-by-row status in `RUN_STATUS.md`. The rest were killed mid-run. |
| synthetic v2, full arm | `/tmp/cmage-synth2/full/b0*/out/run_*/` | **6 batches** have stage-3 output; b01 is the only one scored. b02–b05 were killed (`rc=137`). |
| synthetic v2, stage-3 arm | `/tmp/cmage-synth2/stage3/c0*/out/run_*/` | **4 batches** have output; c01+c02 (200 crops) scored, c03 killed mid-run, c04 staged. |

Scoring these is cheap — no pipeline re-run needed, just `score_run.py` /
`score_cx.py` against the right manifest. **Do this before starting anything new**,
because it may answer questions currently listed as open.

## Corpora built but never run

- `/tmp/cmage-img/` (234 MB) — **3,920 PNGs, 560 compounds × 7 aligned arms**
  (PubChem 300px and 1500px, background-remapped, LANCZOS-upscaled, RDKit at two
  sizes). Ground truth verified: InChIKey matches PubChem on 560/560. Only a
  50-image smoke test was ever run. This is the corpus that showed a bigger
  canvas makes things *worse*, and it is ready to run at full size.
- `/tmp/cmage-nearmiss/` — the graded-verdict analysis inputs; the scorer changes
  it produced are already committed.
- `/tmp/cmage-charts/` — the assertion harnesses (`assert-bench.js`,
  `assert-gallery.js`, `assert-detail.js`) used to verify the site against the
  rendered DOM. Reusable; not committed.

## Known-contaminated artefacts — do not read

- `benchmarks/report_partial/report.md` — the paired arm-gap table's stage-3
  column has a denominator covering drawings it never processed, which **inverts
  the direction** and makes segmentation look helpful. Recompute with stage-3
  coverage defined as *crops that produced a workbook row*.
- Any pre-`3ce8da6` copy of `ink_retention_real_documents.json` — prefix-matching
  bug, see the corrections section above.

## Scheduling

The automatic continuation cron was **removed** at the stop. Restart is manual.
