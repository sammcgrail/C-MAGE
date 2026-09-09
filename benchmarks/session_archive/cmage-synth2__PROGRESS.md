# Progress — synthetic corpus v2 scale-up
started: 2026-09-09T19:07:33+00:00

## Facts established (read from live system)
- v1 run timings (100 cmpds / 10 PDFs / 20 pages): stage1 106.7s (5.3 s/page),
  stage2 161.3s (8.0 s/figure), stage3 247.2s (2.4 s/segment). Total 8.6 min.
  The 64 s/page budget in the brief is for REAL literature pages, not these.
- Stage-2 segments are 1:1 with page pixels (fig 1507 px wide from a 1700 px page;
  segments 619x476 vs a 700x552 cell). So ink(segment)/ink(clean cell crop) is a
  directly comparable ratio with NO scale correction. Verified on v1 outputs.
- MolScribe vocab = 75 labels. Mirrored-but-absent: EtO2C EtOOC AcO BnO BzO tBuO
  iBuO MsO TfO AcHN BocHN H3CS CH3O C2H5O HOOC Cl3C HO3S HCO.
- ringleader pool 764: 691 parse. size <=15:112  16-30:356  31-50:186  51+:37.
  stereo 0:326 1:100 2-3:97 4-7:111 8+:57. multifrag-or-charged: only 21.
  => 51+ and salt must be topped up from PubChem by name.
- Other writers: agent `synth-corpus` owns make_synthetic_corpus.py etc.
  ALL v2 work goes in NEW files (*_v2.py, corpus_synth2/, synthetic_manifest_v2.json).
- A full-corpus PDF run is live (pid 1294039, CN108503621B_vonoprazan). Do not kill.

## [step 1] PLAN BUILT  (benchmarks/_v2work/synthetic_plan_v2.json)
854 distinct candidates (ringleader 691 parsed + 244 PubChem-by-name supplements,
deduped by InChIKey). 884/887 PubChem lookups resolved.
Selected 504 distinct compounds -> 1032 drawings in 87 PDFs.
strata: basic 66, stereo 120, abbreviated 120, complex 66, salt 66, markush 66
size buckets overall: <=15:126  16-30:187  31-50:109  51+:82   (all >= 60)
stereo depth overall: s1:58 s2-3:57 s4-7:80 s8+:93 (40 each inside the stereo stratum)
abbrev depth: a1:179 a2:126 a3+:90 (40 each inside the abbreviated stratum)
panel for the crossed arms: 48 compounds (16 basic/16 stereo/16 abbreviated)
vocab arm: 60 compounds x 2 spellings
Files written so far (all NEW, no other agent's file touched):
  benchmarks/synthetic_compounds_v2.py
  benchmarks/select_synthetic_v2.py
  benchmarks/make_synthetic_corpus_v2.py
  benchmarks/_v2work/{supplemental_names.py,resolve_pubchem.py,pubchem_cache_v2.json}

## [step 2] CORPUS BUILT  benchmarks/corpus_synth2/  (87 PDFs, 207 pages, 5.5 MB)
1032 drawings of 504 distinct compounds, ZERO build-time rejects.
Manifest: benchmarks/ground_truth/synthetic_manifest_v2.json
  core       std          504 drawings  84 pages
  crossed    dens_1        48            48
  crossed    dens_4        48            12
  crossed    dens_std      48             8
  crossed    dens_12       48             4
  crossed    dens_20       48             3
  crossed    ink_thin      48             8
  crossed    ink_thick     48             8
  crossed    space_tight   48             8
  mixed      std           24             4
  vocab_in   std           60            10
  vocab_out  std           60            10
Vocab pairing verified exact: same members, same skeletons, same expanded SMILES,
88 of 114 superatoms flipped to a spelling outside the model vocabulary
(CH3O 44, HOOC 34, AcO 7, EtO2C 2, H3CS 1); in-arm 114/114 in vocabulary.

### Corpus-construction finding (v1 never surfaced it)
Of 583 condensable candidates: 13 LOSE a defined stereocentre when RDKit
condenses them (valine -> `*C(*)N |$iPr;;CO2H;$|`, no centre at all), and 38
condense to a label CXMolScribe has never heard of (nPent, nNon, CO2-).
Both are now selection-time filters, so the abbreviated stratum cannot contain a
drawing that is not the molecule the manifest names.

## [step 3] FULL-PIPELINE ARM LAUNCHED  pid in /tmp/cmage-synth2/full.pid
/tmp/cmage-synth2/run_full.sh -> /tmp/cmage-synth2/full/{b01..}/out
batched at <= 25 pages, resume-safe, status /tmp/cmage-synth2/full/RUN_STATUS.md

## [step 4] CORPUS INTEGRITY BUGS FOUND BY THE GATE, FIXED, REBUILT
synthetic_selftest_v2.py: 20163 checks, 0 failures (self-grade 441 Y + 590 YS = 1031).
Two real defects it caught, both of which would have silently corrupted a stratum:
 1. /root/ringleader/tests/pubchem_ground_truth.json contains BRAND-NAME
    DUPLICATES of the same molecule -- 48 pool entries share an InChIKey with
    another (anastrozole/arimidex, budesonide/pulmicort/rhinocort,
    acalabrutinib/calquence, azd6140/brilinta, bicalutamide/casodex,
    cortisol/hydrocortisone, faslodex/fulvestrant, azd5363/capivasertib ...).
    Its real size is 764 rows -> 691 parse -> 643 distinct molecules.
 2. Two DIFFERENT compounds can share one drawn skeleton once condensed:
    cefotaxime's OAc and cefpodoxime's OMe both collapse to one dummy at the
    same position. score_cx ties at the top assignment score and its `ambiguous`
    flag only fires on LOW scores, so the tie is invisible and the second
    compound scores as a miss however well it was read. Same for three markush
    scaffolds (aripiprazole/brexpiprazole/buspirone all cut to one core) and
    three amino acids in the vocab arm.
    -> both now deduped at selection time; 1031 drawings / 503 compounds.
Also fixed two of my own selftest CONTROLS that were wrong, not the code:
 - a label swap between symmetry-equivalent positions is not a wrong answer
 - the "other group" negative control must use a group that does NOT contain the
   compound (v2 draws the same compound in several groups on purpose)

## [step 5] BOTH ARMS RELAUNCHED on the corrected corpus

## [step 6] THE CROSSED FACTORS ARE ACTUALLY SEPARATED (measured, not assumed)
Nearest-neighbour ink-to-ink gap and ink density per drawing, over the 48-compound
panel, measured from the rendered pages:

  condition      n   median gap px   ink density   <- what varies
  ink_thin      48        130           0.0312     geometry FIXED, ink varies
  dens_std      48        130           0.0401
  ink_thick     48        130           0.0531
  space_tight   48         79           0.0401     ink FIXED, distance varies
  dens_4        48        120           0.0399
  dens_12       48         76           0.0541     both vary (as a real page does)
  dens_20       48         54           0.0684
  dens_1        48        n/a           (single structure per page, no neighbour)

So the ink arm holds the gap at 130 px and moves ink density 0.031 -> 0.053;
the spacing arm holds ink density at 0.0401 and moves the gap 130 -> 79 px.
That is the separation the experiment needs, and it is measured rather than
asserted. NOTE for the report: in the DENSITY arm font size does not shrink in
proportion to the drawing, so at 20 per page labels dominate the ink -- density
changes the label-to-bond ratio as well as the size. That is what a dense
journal page really does, but it must be stated, not hidden.

## [step 7] READY TO SCORE (commands, so a fresh session can finish this)
  # merge the batch runs into one run dir per arm
  .venv-ms/bin/python benchmarks/merge_runs.py --runs-root /tmp/cmage-synth2/full \
      --dest /tmp/cmage-synth2/merged_full --force
  .venv-ms/bin/python benchmarks/merge_runs.py --runs-root /tmp/cmage-synth2/stage3 \
      --dest /tmp/cmage-synth2/merged_stage3 --force
  # grade both arms
  .venv-ms/bin/python benchmarks/score_cx.py --run-dir /tmp/cmage-synth2/merged_full \
      --manifest benchmarks/ground_truth/synthetic_manifest_v2.json \
      --out benchmarks/scored/synthetic_v2_full --label "synthetic v2, full pipeline"
  .venv-ms/bin/python benchmarks/score_cx.py --run-dir /tmp/cmage-synth2/merged_stage3 \
      --manifest benchmarks/ground_truth/synthetic_manifest_v2.json \
      --out benchmarks/scored/synthetic_v2_stage3only --label "synthetic v2, stage 3 only"
  # ink loss (reads the UNMERGED full arm; segments are per batch)
  .venv-ms/bin/python benchmarks/ink_loss_v2.py --run-root /tmp/cmage-synth2/full \
      --cells /tmp/cmage-synth2/cells --cell-ink /tmp/cmage-synth2/cell_ink.json \
      --manifest benchmarks/ground_truth/synthetic_manifest_v2.json \
      --scored benchmarks/scored/synthetic_v2_full --out /tmp/cmage-synth2/ink
  # every cut of the result
  .venv-ms/bin/python benchmarks/analyze_synth_v2.py \
      --manifest benchmarks/ground_truth/synthetic_manifest_v2.json \
      --full benchmarks/scored/synthetic_v2_full \
      --stage3 benchmarks/scored/synthetic_v2_stage3only \
      --ink /tmp/cmage-synth2/ink --out benchmarks/scored/synthetic_v2_report
  # stage-3-only arm runner (start AFTER the full arm; box is at load 10 already)
  /tmp/cmage-synth2/run_stage3.sh

## v1 -> v2 bridge
78 of v1's 100 compounds are in the v2 core, including ALL 22 of v1's `basic`
control set in v2's `basic` stratum -- so the control comparison is on identical
molecules. v1's `abbreviated` names were absorbed into v2's `basic`/`stereo`
(v2 selects basic first); v2's abbreviated stratum is a different, larger and
better-spread sample: 123 drawings, 267 superatoms, 17 distinct labels
(OMe 69, CO2H 44, Et 33, iPr 33, Ph 28, CF3 12, OAc 10, tBu/nPr/NO2/CN/NMe/nBu/
CO2Et/SMe/Ac/CHO the rest). v1 had 22 compounds.
Committed: 4d7e146 (corpus + generator + gate + tools).

## [step 8] COORDINATOR PRIORITIES RECEIVED -> replan (19:42)
Priority: (1) ink-loss correlation, (2) BOTH arms on every stratum, (3) size by
heavy-atom count. `basic` on clean crops is the control and outranks headlines.
Decision: run the two arms CONCURRENTLY rather than sequentially. Total CPU work
is the same on a saturated box, but a cutoff at 2 h under the sequential plan
would have produced a complete full arm and ZERO stage-3 arm -- which fails
priority 2 outright. Interleaving gives partial BOTH, and the arm gap is the
finding. stage-3 arm niced to 10 so it yields to the full arm.
  FULL_ARM_PID   1306463  -> /tmp/cmage-synth2/full/RUN_STATUS.md   (9 batches)
  STAGE3_ARM_PID 1311965  -> /tmp/cmage-synth2/stage3/RUN_STATUS.md (11 batches of 100)
Wall-clock estimate on the contended box: 207 pages x ~50 s = ~2.9 h full arm;
stage-3 arm ~41 min of compute, longer contended.
Plan: compute the ink-loss correlation INCREMENTALLY on completed batches rather
than waiting for the whole arm, so priority 1 lands early.
NOTE ON WAITING: every waiter here polls a FILE (grep -q on RUN_STATUS.md) or a
recorded PID. No `pgrep -f` anywhere -- it matches its own waiter and hangs.

## [step 9] INK-LOSS TOOL VALIDATED EARLY ON PARTIAL DATA (19:47, 12 of 87 groups)
Ran ink_loss_v2.py against b01's segments before the data mattered. Three things
established, and one reporting bug caught that would have inverted the finding:

1. SCALE: median segment/cell bbox width ratio = 1.0000 over n=142. Stage-2
   segments really are 1:1 with page pixels on THIS run, not just on v1's.
   So ink(segment)/ink(clean cell) is a ratio of two counts of the same pixels.
2. BUG CAUGHT: the denominator was every drawing in the MANIFEST, so the 912
   drawings whose PDFs had not been run yet each contributed retention 0.0 and
   the tool reported "912 structures totally erased". A not-yet-run drawing and
   a totally-erased one looked identical. Now the tool derives which groups
   reached stage 1 from 01_VH_Figures and restricts the denominator to those,
   and reports `groups_with_fewer_figures_than_pages` separately so a stage-1
   miss can never be reported as stage-2 erasure.
3. WHERE THE SIGNAL LIVES: on 143 std-render drawings, mean retention 0.9931,
   MEDIAN 1.0, median absolute loss 0 px. 19 of 143 lost >2%; exactly 1 lost
   >10%; none lost everything; none GAINED ink (no caption bleed).
   Worst absolute losses: carbamazepine 772 px of 10303, menthol 678 of 4431,
   diflunisal 550 of 7214, pramipexole 543 of 6415, glecaprevir 475 of 12801.
   => The mechanism is a THIN TAIL, not gross erasure. A benzene double bond is
   ~1-2% of a structure's ink, so the ibuprofen failure is retention ~0.98.
   Bins were therefore re-cut dense at the top (<0.9, .9-.95, .95-.98, .98-.99,
   .99-.995, .995-.999, >=.999) and an ABSOLUTE `ink_lost_px` added -- a
   fraction alone hides that a large molecule can lose a whole bond and still
   read as 0.99 retained.

## [step 10] MATCHER BUG FOUND AND FIXED (19:52) -- profile match -> pixel overlap
The 24x24 profile matcher MIS-ASSIGNED segments and the error was invisible in
the headline: phenytoin's segment overlays its assigned drawing at ratio 0.229
(a different molecule of similar coarse shape), yet retention -- a ratio of ink
COUNTS -- still read a plausible 0.967. Only the pixel-wise mechanism split
disagreed loudly (8667 px "lost" vs 366 px by count), which is how it surfaced.
Fix: profile is now a PREFILTER; exact FFT cross-correlation overlap is the
arbiter, over all offsets. Verified: every drawing that lost no ink by count
aligns at overlap ratio exactly 1.000, so the two renders are pixel-identical
and overlap is a gold standard. Segments below --min-overlap are counted and
EXCLUDED, never attributed.
After the fix (143 segments, std render, 29 of them lossy):
  median align overlap ratio 1.0000 ; 0 segments below threshold
  total real ink lost 7976 px  (the misaligned version said 42181 px)
  37.8% of loss is OUTSIDE the segment's crop rectangle -> a bbox pad fixes it
  62.2% is INSIDE the rectangle, removed by the instance mask, median 27 px
       from the rectangle edge -> only mask dilation fixes that
=> Two mechanisms, two different fixes. This is also why a wholesale CropWhite
   threshold change made things worse: it moves both, partly cancelling.

## [step 11] TWO-VIEW AGREEMENT IS NOW A STANDING GATE (19:53)
`drawings_where_the_two_views_disagree` = 0 of 29 and must stay 0. Count-view
loss (ink count difference) vs pixel-view loss (XOR after exact alignment). The
phenytoin mis-assignment was caught only because both happened to be printed;
it is now asserted every run.
AUTOJOIN armed (pid in /tmp/cmage-synth2/autojoin.pid): waits for the first
full-arm workbook, merges, runs score_cx, then re-runs ink_loss WITH --scored to
produce the correlation. Marker: /tmp/cmage-synth2/AUTOJOIN_DONE, log
/tmp/cmage-synth2/autojoin.log.

## [step 12] TAIL-CLUSTERING CONTRAST ADDED (19:54)
Coordinator wants the tail question, not the overall coefficient. Retention's
median is exactly 1.0, so a Pearson r is dominated by the untouched majority and
would read weak regardless of the tail. Added:
  outcome.tail_clustering  = 2x2 lost-nothing vs lost-anything, relative risk of
                             a wrong skeleton, Fisher exact p
  outcome.by_absolute_px_lost = 0 / 1-100 / 101-500 / 501+
Absolute px, not fraction: the same 300 px is 6% of a small structure and 0.4% of
a large one, and one bond is ~a few hundred px. Retention bins kept beside it for
the dose-response shape.
Run state 19:54: b01 stage3 50/143 segments; c01 21/100. load 15, mem 9.8G free.

## [step 13] OUTCOME/JOIN PATH DRY-RUN VERIFIED (19:58) -- fabricated verdicts, shape only
Ran ink_loss_v2 --scored against a FABRICATED cx_molecules.csv to exercise the
2x2, Fisher exact and the absolute-px bins before the real verdicts arrive.
rc=0, every cell populates, no crash. Fabricated inputs then DELETED so they
cannot be mistaken for results.
Two things learned that matter for the real run:
 * the dry run's "matcher agrees with scorer on YYS = 143/0" is MEANINGLESS --
   I built cx_structures.csv from the matcher's own output, so it is
   self-referential. Only the real scorer makes that an independent check.
 * split on b01: 108 lost-nothing vs 29 lost-anything. Extrapolating to the full
   1031 drawings gives roughly 820 vs 210 -- ample for a Fisher p. At b01 alone,
   29 lossy can only detect a LARGE effect; raw counts get reported either way.
 * `ink_lost_px_when_correct/wrong` are both 0.0 because the median drawing
   loses nothing. Those two medians are uninformative by construction; the 2x2
   is the answer, not them.
Rate at 19:57 (load 16.5): b01 67/143 segments, c01 29/100. Correlation ~20:35.

## [step 14] THROUGHPUT + COVERAGE FIX (20:00)
Two problems, both of which would have cost the arm gap rather than just time.

1. THREAD THRASH. Nothing in the stack sets an OMP limit, so every torch/TF
   process grabbed all 8 cores. Two arms plus the parallel real-PDF run = ~24
   threads on 8 cores; the stage-3 arm had collapsed to ~2 images/min against a
   quiet-box rate of ~25. Now capped: stage-3 arm 3 threads, full arm 4.
2. ALPHABETICAL CROP ORDER in the stage-3 arm. salt, stereo, markush and vocab
   all sort late, so a cutoff would have left exactly those strata missing from
   the clean-crop arm -- and the arm GAP can only be reported for a stratum both
   arms covered. Crops are now processed ROUND-ROBIN across all 87 groups, so
   any prefix is a stratified sample. First 100 now cover abbreviated 38,
   basic 25, stereo 18, complex 7, markush 6, salt 6 (was 100% abbreviated).
3. RESUME BUG in both runners, latent but nasty: resume keyed on the batch's
   out/ DIRECTORY existing. A batch killed mid-run leaves out/ behind and would
   have been skipped forever, putting a silent hole in the corpus -- which the
   scorer reports as failures, not as missing data. Resume now keys on the
   stage-3 WORKBOOK, i.e. on a batch that actually finished.
Full arm swap is armed (swap_full.sh): waits for b01's completion row so the
swap lands BETWEEN batches, kills only the old wrapper's descendant tree, then
relaunches thread-capped. b01's work is preserved.

## [step 15] TWO TRANSFERABLE RULES, for the report (not footnotes)
R1. TWO INDEPENDENTLY-CONSTRUCTED VIEWS OF THE SAME QUANTITY, REQUIRED TO AGREE.
    A single view cannot report its own failure. Every bug on this task was
    caught this way, and the ones caught by luck are now assertions.
R2. IF A JOB CAN BE INTERRUPTED, PROCESS IN AN ORDER WHERE EVERY PREFIX IS A
    VALID SAMPLE OF THE WHOLE. Alphabetical batch order made the stage-3 arm's
    coverage a function of when it happened to be stopped; round-robin makes any
    prefix stratified. The failure this prevents is not a wrong number but a
    silently narrowed SCOPE -- the arm gap can only be reported where both arms
    covered a stratum.

## Failure-mode census (six instances of ONE signature)
The dominant failure mode here is not code that crashes or numbers that look
wrong. It is a measurement whose broken state and whose working state produce
IDENTICALLY PLAUSIBLE output.
 1. unrun PDFs scored as total stage-2 erasure (ink_loss denominator)
 2. mis-assigned segments returning a plausible 0.967 retention (count ratio
    cannot separate two molecules of similar total ink)
 3. a Pearson r over a variable whose median is exactly 1.0 -- structurally
    blind to the tail it was meant to measure; a weak r would have been read as
    "ink loss does not predict failure"
 4. unrun PDFs scored as per-stratum failures (analyzer denominator)
 5. *** THE WORST *** two arms scored over DIFFERENT corpora and printed side by
    side. The stage-3 arm is mechanically slower, so its unrun surplus inflates
    exactly the full-vs-stage-3 gap we predicted. A bug that produces noise gets
    caught by anyone who looks twice; a bug that produces THE EXPECTED ANSWER
    does not get looked at twice.
 6. resume keyed on out/ existing -> a batch killed mid-run skipped forever, and
    the scorer renders the hole as failures rather than as missing data.
Plus one applied to MYSELF: the dry-run "matcher agrees with scorer 143/0" was
self-referential (the structures file was built from the matcher's own output),
so it was a validation that could only pass. Must be flagged wherever that
statistic appears, or a reader will assume it meant something.

## Runbook line worth keeping
Nothing in this stack sets OMP/MKL thread limits, so every torch/TF process
grabs all cores and concurrent runs thrash rather than share. Cap them:
OMP_NUM_THREADS/MKL_NUM_THREADS/OPENBLAS_NUM_THREADS/NUMEXPR_NUM_THREADS.
Measured: stage-3 throughput 2.3 -> 5.6 segments/min, load 16.5 -> 12.2.

## [step 16] ARM-GAP FABRICATION, SUBTLER FORM (20:08) -- instance 7
Restricting each arm to the groups IT processed was necessary, not sufficient.
The arms cover the corpus at different RATES and in different ORDERS (full arm
alphabetical over PDFs; stage-3 arm round-robin over crops, by design so any
prefix is stratified). So before both finish they are scoring DIFFERENT SUBSETS.
Both columns are individually correct; only their comparison is wrong -- which
is why it would have survived review. The report now leads with PAIRED tables
over drawings BOTH arms scored; per-arm tables kept but labelled not comparable.
Measured: stage-3 c01 = 100 crops in 412 s = 4.1 s/image after the thread cap,
against ~30 s/image before it. 11 batches => ~75 min for the whole clean-crop arm.

## [step 17] R3 -- the rule instance 7 generates (R1 would NOT have caught it)
R3. WHEN A FINDING IS A DIFFERENCE BETWEEN TWO MEASUREMENTS, THE COMPARISON
    NEEDS ITS OWN VALIDITY CHECK -- MATCHED SCOPE -- INDEPENDENT OF EITHER
    MEASUREMENT'S CORRECTNESS. Two independently-constructed views agreeing (R1)
    cannot catch it, because both views were CORRECT. Only the comparison was
    invalid.
HONEST PROVENANCE, to be stated in the report: six of the seven instances were
caught by method. INSTANCE 7 WAS NOT. It surfaced as a side effect of an
unrelated throughput optimisation -- capping OMP threads made the two arms'
coverage diverge fast enough to be visible. Had both arms crawled at the old
rate their coverage would have looked superficially similar and it would have
shipped. A census that claims all seven were caught by method teaches the wrong
lesson.

## [step 18] *** INSTANCE 8, CAUGHT AT THE MOMENT OF REPORTING (20:12) ***
The first correlation run produced EXACTLY the hoped-for result -- RR 2.4,
p=0.0, "100% of ink-losing drawings graded wrong" -- and it was FABRICATED.
b02 was mid-pipeline: 18 stage-1 figures, 12 segments, no workbook. Its 96
drawings read retention 0.0 (never segmented) AND not-recovered (score_cx walks
the whole manifest). Both artefacts land in the same 2x2 cell, so they inflate
the association under test. Tell: 239 drawings vs 143 segments.
FIX: measurable == COMPLETED batch (stage-3 workbook present), not stage-1 reached.

## [step 19] THE CORRELATION, corrected and confound-checked (b01 only)
SCOPE: 1 completed batch, 12 of 87 groups, 143 drawings, 143 segments,
0 never-segmented, median align overlap 1.0000, 0 segments below threshold.
Matcher vs scorer on Y/YS: 63 agree, 0 disagree -- GENUINE (not self-referential).
RETENTION: mean 0.9931, median 1.0, 19 lost >2%, 1 lost >10%, 0 lost everything.
TAIL 2x2 (skeleton correct):
    lost nothing   63/108 = 58.3%
    lost anything   0/29  =  0.0%
    relative risk of a wrong skeleton 2.4 ; Fisher exact p = 8.4e-10
BY ABSOLUTE PX LOST: 0 px 63/108=58.3% | 1-100 0/1 | 101-500 0/24 | 501+ 0/4
BY RETENTION BIN: >=0.999 63/113=55.8% ; every bin below 0.999 is 0/30.
CONFOUNDS TESTED AND REJECTED:
  * not a size effect: lossy median 23 heavy atoms vs clean 30 (Mann-Whitney
    p=0.24) -- lossy are if anything SMALLER
  * not a missing-prediction effect: all 29 lossy drawings got exactly one
    assigned prediction; they were read, and read wrong
  * CONTROL STRATUM, perfect separation: basic clean 17/17 = 100%, basic lossy
    0/7. So `basic` sits at ceiling exactly when stage 2 leaves it alone, and
    every one of its full-pipeline failures is an ink-loss case.
MECHANISM OF THE WRONG ANSWERS: of the 29, 11 differ from truth ONLY in bond
orders (identical atom connectivity) and 18 differ in connectivity. Consistent
with the two loss modes: mask-interior loss erases a bond; crop-rectangle loss
removes atoms outright (menthol lost 654 px OUTSIDE the rect).
LIMIT: b01's 12 groups are alphabetically first, so only `abbreviated` and
`basic` are represented. Not yet a statement about salt/stereo/complex/markush.
