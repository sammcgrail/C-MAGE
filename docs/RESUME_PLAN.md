# READ THIS FIRST — state as of 2026-09-09 ~23:00 UTC

This file is append-only and the OLDEST sections are the most wrong. Three of its
original headline claims have been retracted; the corrections are further down and
in these files, which are the current word:

| what | where |
|---|---|
| what segmentation actually costs, matched scope | `benchmarks/ARM_GAP.md` |
| the denominator problem — 32% of "figures" are text | `benchmarks/FIGURE_CLASSIFICATION.md` |
| six real documents, first honest scores | `benchmarks/REAL_DOCUMENT_RESULTS.md` |
| where the lost ink sits, on real documents | `benchmarks/INK_LOCATION_REAL_DOCUMENTS.md` |
| two upstream colour bugs + the noise floor | `docs/UPSTREAM_BUGS.md` |

**Retracted from the sections below:** "stage 2 destroys most real figures"
(the denominator was a third text); the whole-figure fallback for zero-segment
figures (measured: recovers ink, recovers no molecules); the 37.8/62.2
outside/inside ink split (synthetic-only, does not survive real figures).

**Standing numbers, all matched-scope:** segmentation costs 8.6 points strict /
19.9 graded on synthetic; stage-3-only over 1031 cells is 58.0% strict exact and
77.6% graded; six real documents are 39.3% strict / 69.6% graded precision over
the five with complete manifests. CXMolScribe is **not deterministic** — 4 of 494
byte-identical inputs flip, ~1 in 125 — so a difference of a few structures is not
a difference.

**In flight at this line:** the 7-arm, 3,920-image depiction corpus and a
channel-swapped copy of one arm (560 PubChem depictions, 97% coloured, all with
InChIKey-verified answers) — the test that can actually measure what the colour
bug costs.

---

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

---

# Correction to the harvest, 2026-09-09 ~21:0x UTC (post-restart, verified on disk)

The harvest table above **overcounts what was actually scoreable**. It counted
directories; the check that matters is whether a run wrote
`03_CXMS_Results/Completed_HighConfidence_CMAGE.xlsx`. Re-inventoried:

| harvest claimed | actually on disk |
|---|---|
| 7 of 17 documents reached stage 3 | **6** did. The 7th (`PMC11771699_macrocycle_drugs`) stopped after stage 2. |
| synthetic full arm: 6 batches have stage-3 output | **1** (b01). b02/b05/b06 have segments only; b03/b04 have neither. |
| synthetic stage-3 arm: 4 batches have output | **2** (c01, c02). c03 died `rc=137` (OOM on the old 16 GB box), c04 was staged and never started. |

And the instruction "scoring these is cheap, just run the scorer against the right
manifest" **does not hold for the six documents at all**, because no manifest
contains their ground truth:

- `pdf_corpus_round3_manifest.json`, `..._round4_...`, `..._expanded_...` are
  **corpus-SELECTION records**. Entries sit under `accepted` and carry
  `filename, id, source_url, licence, drawing_style, structure_pages,
  est_structures` — **provenance only, no SMILES**.
- The scoreable manifests are `pdf_manifest.json` and `pdf_manifest_expanded.json`,
  which have a `groups` dict with `molecules: [{index, name, cid, smiles, ...}]`.
  None of the six documents appear in either.

Running `score_run.py` against a selection record would have produced a full set
of `no-truth` verdicts and a summary that renders as a real report — the ninth
instance of this project's recurring signature: **a failure whose output is
indistinguishable from the measurement**. Ground truth for those six has to be
built first; that work is under way, output at
`benchmarks/ground_truth/pdf_manifest_round34.json`.

Also corrected: b01/c01/c02 were scored with `score_cx.py` only. There are no
`score_run.py` outputs (`structures.csv`, `molecules.csv`, `summary.json`) for
any synthetic v2 batch. Both scorers answer different questions and both are
needed.

## What was started instead

- **Stage-3-only arm over the whole 1031-cell corpus** — `/root/cmage-work/s3arm/`,
  4 shards, round-robin over `crop_order.txt` so every shard and every prefix of
  a shard is a valid interleaved sample (R2). Supersedes the c01–c04 batching.
- **Full arm completed offline for b02/b05/b06** — `/root/cmage-work/fullarm/`.
  Their existing `02_DIS_Segments` fed to stage 3, which is exactly what the full
  pipeline would have done next. 302 segments, taking the full arm from 143
  structures to 445. **Label it the full arm, not the stage-3-only arm** — the
  inputs are segments, not whole cells.

## Durability change

`/tmp` was wiped by the reboot, as predicted. The preserved snapshot is now
restored to **`/root/cmage-work/`** (durable), with `/tmp/cmage-*` symlinked to it
so every committed path and `crop_order.txt` entry still resolves.
`/root/cmage-tmp-preserve/` is untouched as the pristine copy.

## Hardware

8 -> 16 vCPU, 16 -> 32 GB, 153 -> 305 GiB. Measured on the new box: 7 concurrent
stage-3 workers at ~1 GB RSS each, load ~8/16, ~1 image/s aggregate with
`OMP_NUM_THREADS` capped at 3-4 per worker. The c03 `rc=137` OOM should not recur.

---

# Session 2026-09-09 post-restart — what changed, and what is now false

Three of this document's own headline claims were retracted this session. Read
this block before quoting anything above it.

## 1. "Stage 2 destroys most real figures" — FALSE as stated

All 139 real stage-1 figures were classified by eye (`benchmarks/FIGURE_CLASSIFICATION.md`,
labels committed at `benchmarks/figure_labels_real_documents.tsv`). 44 of 139 (32%)
contain no chemistry at all — body text, data tables, IR/NMR spectra, journal
boilerplate, a bar chart. Every retention number above used all 139 as its
denominator.

| | all 139 (as quoted above) | structure-bearing 95 |
|---|---|---|
| zero-segment | 26.6% | **4.2%** |
| median ink retained | 0.291 | **0.590** |
| pooled ink retained | 30.1% | 47.6% |

Stage 2 is a good filter: 75% of non-chemistry figures yield nothing, 0.9% of
non-chemistry ink survives. **What survives the correction:** of the 91
structure-bearing figures that produced segments, median retention is 0.595 and
38 (41.8%) retain under half their ink. Real, and half the size of the old claim.

**New, previously unmeasured:** 11 non-chemistry figures DO produce segments — 15
in total, incl. a properties table (4), two table-of-contents strips and an IR
spectrum. Every structure stage 3 emits from those is a false positive by
construction and sits in the precision denominator.

## 2. "Add a retention guard, fall back to the whole figure" — MEASURED, DOESN'T WORK

Item 2 of "Do this, in order" assumed the whole-figure fallback would help because
"the single-structure path already works". It works for an IMAGE UPLOAD, which is
one already-cropped structure. It does not transfer to a document figure, which is
a multi-panel page region. Matched-scope A/B on the 11 ground-truthed documents,
identical segments in both arms, only 26 whole-figure rows added:

    recall     9/34 strict, 18/34 graded   IDENTICAL
    precision  5.79% -> 5.22%
    the 26 recovered figures: 22 wrong, 4 invalid, all low-confidence, median Tanimoto 0.000

`tools/retention_guard.py` is shipped as a MEASUREMENT tool; every rewrite is
opt-in and off by default.

## 3. "Scoring the harvested runs is cheap" — NO GROUND TRUTH EXISTED

See the earlier correction block. Also: precision against `pdf_manifest_expanded.json`
is **not interpretable in any arm**. That manifest excludes "molecules with no
resolvable PubChem CID and no printed SMILES", so a correctly-read structure that
is not among the 34 is scored `wrong`, not `no-truth`. **Only recall is comparable
across arms on real documents.**

## What was measured and stands

**The paired arm gap, matched scope** (`benchmarks/ARM_GAP.md`) — 38 synthetic
documents, 451 molecules, both arms:

| arm | strict exact | graded exact | graded recall |
|---|---|---|---|
| full pipeline | 46.3% | 60.9% | 65.2% |
| stage 3 only | 54.3% | 79.2% | 85.1% |

Segmentation costs 8.6 points strict, 19.9 graded, on the cleanest input available.

**The complete stage-3-only arm**, all 1031 synthetic v2 cells: 58.0% strict exact,
77.6% graded exact, 83.3% allowing stereo and salt, 8.6% genuinely a different
molecule, 5.3% unparseable. High-confidence 67.6% exact vs low 35.0%. Of the 325
strict-`wrong`, 220 (67.7%) are the drawn molecule written differently.

Both selftest gates were run before any graded number was quoted: `graded_selftest`
13/13, `cxsmiles_selftest` 6/6 with the superseded algorithm disagreeing on exactly
the two cases that must disagree.

## Next, in order

1. **Where the lost ink sits, over structure-bearing figures only** — in flight.
   The 37.8/62.2 synthetic split still must not be acted on.
2. **Ground truth for the 6 round-3/4 documents** — in flight, output at
   `benchmarks/ground_truth/pdf_manifest_round34.json`.
3. **Suppress the non-chemistry figures at stage 1**, or filter them before stage 2.
   32% of what VisualHeist emits is text, and 11 of those figures leak 15 false-
   positive segments into stage 3. This is a bigger, cheaper win than anything in
   stage 2, and nothing upstream does it.
4. **Rebuild both pages** from `ARM_GAP.md` + the corrected real-document numbers.
   Lead the benchmark page with the matched-scope arm gap. Label CXSMILES as
   CXSMILES. Keep it short.
5. `/root/cmage-work/cmage-img/` — 560 compounds x 7 arms, still only smoke-tested.

## Where things live now

`/tmp` is wiped at boot. The work tree is **`/root/cmage-work/`** with `/tmp/cmage-*`
symlinked to it so committed paths and `crop_order.txt` still resolve.
`/root/cmage-tmp-preserve/` is the untouched pristine snapshot.
Scored runs: `/root/cmage-work/scored/{fullarm_merged,s3arm_merged}/`,
`/root/cmage-work/guardtest/{armA,armB}/`, sweep in `/root/cmage-work/guardsweep/`,
figure labels + contact sheets in `/root/cmage-work/figclass/`.
