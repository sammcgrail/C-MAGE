# Synthetic benchmark corpus — progress log
started 2026-09-09T17:39:52+00:00

## Recon complete (step 0)
- Stage 1 (VisualHeist) renders pages at pdf2image DEFAULT dpi = **200**, not 300
  (`MERMaid/src/visualheist/methods_visualheist.py:65` -> `convert_from_path(str(pdf_path))`).
  DECIMER's own pipeline_dis uses 300 but stage 2 here consumes stage-1 PNGs.
  => structures must be large in PAGE INCHES; 200 dpi is the effective raster.
- Known-answer PDFs (2x2 PubChem grid, ~115 ppi embedded) gave VH figures 1343x1345
  and segments only ~250x300 px. Too small. Target >=600 px segments.
- Existing test PDFs have a NEAR-WHITE (#f5f5f5) box behind each depiction -> exactly
  the CropWhite trap. Ours must be pure 255,255,255.
- RDKit 2025.03.3 in /root/C-MAGE/.venv-ms. 37 default abbreviations; MolScribe vocab
  is 75. Intersection includes OMe/CF3/CO2H/OEt/OAc/NO2/tBu/iPr/NHAc/SMe/CN/CHO/Et/nBu.
  Ph is in MolScribe but NOT RDKit defaults -> add via ParseAbbreviations.
- No img2pdf/reportlab/cairosvg. rsvg-convert + gs ARE present -> vector SVG->PDF route.
- Manifest schema for score_run.py: {corpus, groups: {stem: {source, pages, molecules:[{index,label,name,smiles,...}]}}}

## Step 1 DONE: corpus generated (2026-09-09)
- benchmarks/synthetic_compounds.py  (data: names + markush scaffolds + page plan)
- benchmarks/make_synthetic_corpus.py (generator)
- 100 compounds / 10 PDFs / 2 pages each, in /tmp/cmage-synth/pdfs, manifest /tmp/cmage-synth/manifest.json
- strata: basic 22, stereo 22, abbreviated 22, complex 12, salt 11, markush 11
- Guards that fired and were fixed (all real bugs in MY corpus, not the pipeline):
  * MolToCXSmiles emitted `atomProp:0.dummyLabel.*` for markush dummies -> reference
    was not idempotent under reparse. Fixed by clearing dummyLabel.
  * ciprofloxacin: R2 sat on a piperazine N-H -> a dummy is a wildcard for an ATOM,
    never for an implicit hydrogen. Parent changed to enrofloxacin.
  * naproxen: para position of the scaffold benzene is a naphthalene FUSION carbon,
    query bond single vs target aromatic. Parent changed to ibuprofen.
  * every abbreviated compound must expand back to its parent through cxsmiles.expand
    (the same table the scorer uses) - all 22 pass.

## Step 2 DONE: smoke test (synth_abbrev_1, all 3 stages, CPU)
run /tmp/cmage-synth/smoke/out/run_20260909-175555
- stage 1 found exactly 2 figures (one per page), 1507x1914 and 1507x1106
- stage 2 produced exactly 10 segments (6 + 4), sizes 318x214 .. 638x448
- stage 3 emitted 10 CXSMILES, 7 high / 3 low
- 5 of 10 are EXACT CXSMILES including appendix (atenolol albuterol amlodipine
  benzocaine capsaicin). anastrozole: skeleton exact, appendix CN read as NC
  (nitrile vs isocyanide) -> a genuine grade `A`. atrazine/bosentan/bicalutamide:
  the model WROTE OUT a superatom (CC for Et, OC for OMe, C(F)(F)F for CF3)
  instead of labelling it -> skeleton differs though the molecule is right.
  THAT is the CXSMILES-vs-SMILES gap, visible in the first ten predictions.
- => corpus works end to end. Raising FIXED_BOND_LENGTH 60 -> 80 (smallest
  segment was 318x214, near the <300px misread threshold from FINDINGS 2).

## Step 3: full run LAUNCHED 2026-09-09T18:01:39Z
- FIXED_BOND_LENGTH raised 60 -> 80. Re-measured ink per cell at stage-1 dpi (200):
  100/100 cells have ink; width min 397 median 630; height min 146 median 384;
  every drawing's LARGEST dimension >= 384 (the stage-3 tensor side); 68/100 have
  both dims >= 300. Smallest is aspirin at 397x270 (its condensed skeleton is 8 atoms).
- run dir /tmp/cmage-synth/full/run_20260909-180134 ; log /tmp/cmage-synth/full.log
- benchmarks/score_cx.py written and validated on the smoke run:
  skeleton 6/10, appendix 6/6, expanded-skeleton 8/10, 0 ambiguous assignments.
- IMPORTANT finding while validating: CXMolScribe's vocabulary maps BOTH `CN` and
  `NC` to [C]#N (the nitrile drawn facing either way) -- so anastrozole's `NC`
  prediction is NOT an isocyanide error, it is the same superatom mirrored, and
  score_cx grades the appendix by MEANING via that table. `appendix_labels_exact`
  records the literal string difference separately.
- Reference label inventory: OAc1 CO2H5 Et5 iPr4 tBu2 CN4 OMe6 CO2Et3 CF3 2 nBu1
  NO2 1 nPr1 Ph3 CHO1 + R1 x11, R2 x6. No `NC` in any reference (RDKit's NC is
  isocyanide, MolScribe's is nitrile -- they DISAGREE, so a drawn `NC` would have
  been unscoreable. It does not occur).

## Step 4: gates
- benchmarks/synthetic_selftest.py written. FIRST RUN CLOSED THE GATE on 3 things:
  * erythromycin/azithromycin "filed complex but only 51/52 heavy atoms" - the
    SELFTEST was wrong, not the corpus: `complex` is 55+ heavy atoms OR a
    macrocycle, and erythromycin is 51 atoms round a 14-membered lactone.
    Fixed by recording largest_ring in the manifest and testing the real predicate.
  * "CONTROL swapped positions: aspirin graded Y, expected A" - the CONTROL was
    wrong: aspirin's condensed skeleton is an ortho-disubstituted benzene, so
    exchanging OAc and CO2H is a graph symmetry and Y is correct. The probe now
    has to PROVE the swap is detectable before it is used as a control.
- After fixes: 742 checks, 0 failures, GATE: open.
- Probe is amlodipine: self->Y, swap two labels->A, OMe->CF3->A. Discriminates.
- Manifest regenerated (adds largest_ring); all 20 pages verified PIXEL-IDENTICAL
  to the PDFs the pipeline is currently reading, so the manifest is valid for the run.

## Step 5: docs
- benchmarks/corpus_synth/README.md written (composition, drawing decisions,
  reproduction commands, the upper-bound caveat).
- graded_selftest.py GATE: open (13/13) before quoting any graded number.
- Pipeline: stage 1 gave exactly 20 figures (1 per page). Stage 2 running, 89
  segments at 18:06.

## Step 6: stage 1+2 results (before stage 3 finished)
- stage 1: 20 figures, exactly one per page, no misses.
- stage 2: 103 segments for 100 drawn structures.
  per group: basic_1 10, basic_2 10, stereo_1 10, stereo_2 10, abbrev_1 10,
  abbrev_2 10, complex 10, salt 12, markush 11, mixed 10.
  => segmentation recall looks like 100%; the 3 extras are
     (a) sitagliptin phosphate's H3PO4 counter-ion cropped as its own structure,
     (b) another salt fragment,
     (c) a CAPTION LINE ("1,4-dihydropyridine core", 323x33) cropped as a structure.
- segment sizes: width median 637, height median 346; 4 of 103 have max-dim < 300,
  all of them fragments/captions rather than whole drawn structures.

## Step 7: FULL RUN SCORED  (run_20260909-180134, 103 predictions / 100 drawn)
### paper-style (score_cx.py)
skeleton 42/103 = 40.8%   appendix 12/13 = 92.3%   expanded-skeleton 45/103 = 43.7%
letters Y12 YS29 A1 N20 NS33 invalid8 ; 5 ambiguous assignments (ALL graded N/NS,
so ambiguity never produced a pass)
per stratum (n / Y / YS / A / N / NS / skeleton / appendix / expanded-skel):
 abbreviated 22 12 0 0 10 0  12/22=54.5%  12/12=100%  15/22=68.2%
 basic       22  0 12 0  0 10 12/22=54.5%  -           12/22=54.5%
 stereo      22  0 12 0  0  6 12/22=54.5%  -           12/22=54.5%
 complex     12  0  5 0  0  4  5/12=41.7%  -            5/12=41.7%
 markush     12  0  0 1 10  0  1/12= 8.3%  0/1=0%       1/12= 8.3%
 salt        13  0  0 0  0 13  0/13= 0.0%  -            0/13= 0.0%
### plain-SMILES (score_run.py + graded.py)
strict exact 32/103 = 31.1%; graded exact 45, +1 stereo, +6 salt; recall 52/100
"same molecule"; strict-wrong pile is 60, of which 19 are the same molecule.
### CXSMILES-vs-SMILES gap, same 103 predictions
strict skeleton 42, expanded skeleton 45, plain exact 45.
ONLY 3 predictions are the right molecule but the wrong skeleton-as-drawn, and all
3 are in `abbreviated` (the model wrote a superatom out as atoms: Et->CC, OMe->OC,
CF3->C(F)(F)F). 0 go the other way.
### THREE ARTEFACTS FOUND, each verified rather than assumed
1. SALT 0/13 IS NOT A RECOGNITION FAILURE. Stage 2 splits a drawn salt into its
   fragments, so no segment ever contains the whole reference. 10 of 13 salt
   predictions match EXACTLY ONE FRAGMENT of the drawn species; 9 of 11 drawn
   salts had a fragment recovered. graded.py independently calls 6 of them `salt`.
2. STAGE 2'S MASK ERASES INTERIOR LINE ART. ibuprofen: the stage-1 FIGURE has all
   three benzene double bonds, the stage-2 SEGMENT is missing the bottom one, and
   stage 3 faithfully returned a cyclohexadiene. Verified pixel-wise + visually.
   10 of the 53 failed-skeleton predictions have IDENTICAL connectivity and differ
   only in bond orders, all at conf 0.84-0.91 (aspirin candesartan ibuprofen
   warfarin melatonin lamotrigine thalidomide spironolactone simvastatin quinine).
   Matched-segment ink loss: median 0.27%, but 18 of 77 lose >1% and the worst
   lose 16-27% (warfarin 26.7%, thalidomide 24.0%, carbamazepine 15.9%).
3. MARKUSH R-LABEL CONVENTION. CXMolScribe writes R groups as `1*`/`2*`, not
   `R1`/`R2` (penicillin core: skeleton exact, appendix graded A on the convention
   alone). markush 1/12 skeleton is mostly other errors, but the appendix column
   for markush is measuring a naming convention, not a translation.
### ablation running: stage 3 ONLY, on 100 clean cell crops cut from the pages
   (benchmarks/crop_synthetic_cells.py) -> /tmp/cmage-synth/nostage2

## Step 8: ABLATION + COMMIT (DONE)
### stage 3 only, 100 clean cell crops (no DECIMER segmentation)
skeleton 73/100 = 73.0%   appendix 16/20 = 80.0%  expanded-skeleton 75/100
letters Y16 YS53 A4 N12 NS9 invalid6, 1 ambiguous
 basic       22/22 = 100.0%   <- THE FLOOR CONTROL IS AT CEILING
 abbreviated 17/22 =  77.3%   appendix 16/17 = 94.1%
 stereo      16/22 =  72.7%
 salt        10/11 =  90.9%
 complex      5/12 =  41.7%
 markush      3/11 =  27.3%
plain SMILES: strict exact 58/100, graded exact 77, recall same-molecule 78/100
### full pipeline vs stage 3 only -> SEGMENTATION COSTS 31-32 POINTS
skeleton recall 42/100 -> 73/100 ; plain strict 31.1% -> 58.0% ;
graded same-molecule recall 52/100 -> 78/100
### committed 156452b.. (36 files, 856 KB) - only my own files, by explicit path

## Step 9: final numbers verified against the committed manifest
commit afd3997 (36 files, 856 KB). GATE open (742 checks). graded_selftest GATE open.
The one appendix error on a real superatom (benazepril, ref CO2Et / pred EtO2C) is a
VOCABULARY GAP, not a translation error: EtO2C is absent from CXMolScribe's own
75-entry table, so its meaning cannot be resolved and it cannot compare equal to
CO2Et. The other 3 grade-A cases are all markush R-label convention (1*/2*/Ri).
ALSO FOUND: graded.py's dedup rung collapses a repeated SOLVATE fragment, so a
predicted DIHYDRATE grades `exact` against a monohydrate reference (sitagliptin
phosphate). Strict verdict is correctly `wrong`; the CSV shows dedup=True,
duplicate_frags=O, so it is visible, but the graded column is a false pass. 1 in 100.
DONE.
