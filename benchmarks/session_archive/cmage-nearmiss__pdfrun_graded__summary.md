# Score: 11 documents, all 3 stages

Manifest `pdf_manifest_expanded.json` (pdfs_expanded); threshold 0.8431.

- Drawn molecules (recall denominator): **34**
- Structures emitted for those groups (precision denominator): **242**
- Stage 1 figures: 73; stage 2 segments: n/a

| metric | stereo required | stereo relaxed |
|---|---|---|
| recall | 9/34 = 0.2647 | 9/34 = 0.2647 |
| precision | 14/242 = 0.0579 | 14/242 = 0.0579 |

Structures by verdict: exact 14, stereo 0, wrong 212, invalid 16

## Confidence split vs correctness

| tier | n | exact | stereo | wrong | invalid | wrong+invalid | exact |
|---|---|---|---|---|---|---|---|
| high | 132 | 10 | 0 | 122 | 0 | 0.9242 | 0.0758 |
| low | 110 | 4 | 0 | 90 | 16 | 0.9636 | 0.0364 |

## Graded verdicts -- what the strict `wrong` pile is made of

The strict counts above are unchanged. Below, each structure is graded by the
LOOSEST relaxation needed before it and the drawn molecule agree. `near` (Tanimoto >= 0.85) is a **diagnostic, not a pass** -- Morgan fingerprints
are stereo-blind, so two diastereomers score 1.000. Gate: `graded_selftest.py`.

| grade | structures | % | + largest fragment | needed decode | needed dephantom |
|---|---|---|---|---|---|
| exact | 33 | 13.6% | 33 | 19 | 0 |
| charge | 1 | 0.4% | 1 | 1 | 0 |
| wrong | 192 | 79.3% | 192 | 0 | 0 |
| invalid | 16 | 6.6% | 16 | 0 | 0 |

Of the **212** structures the strict metric calls `wrong`:

- same molecule, different representation: **20** (9.4%)
- near-miss (skeleton match or Tanimoto >= 0.85): 0
- genuinely different molecule: 192

| recall | molecules |
|---|---|
| strict, stereo required | 9/34 |
| any matched grade (exact/stereo/tautomer/charge/salt) | 18/34 |

Recall by grade: exact 18, no 16


## Per group

| group | drawn | figs | segs | structs | rec.exact | rec.stereo | exact | stereo | wrong | invalid | high | low |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| US4231938A_lovastatin | 2 | 13 | None | 8 | 0 | 0 | 0 | 0 | 6 | 2 | 0 | 8 |
| EP0641330B1_pregabalin | 5 | 14 | None | 42 | 3 | 0 | 8 | 0 | 33 | 1 | 25 | 17 |
| bjoc_21-197_aglacinB | 3 | 6 | None | 24 | 0 | 0 | 0 | 0 | 23 | 1 | 20 | 4 |
| bjoc_18-169_macarpine | 9 | 7 | None | 44 | 0 | 0 | 0 | 0 | 41 | 3 | 35 | 9 |
| bjoc_19-15_pheromones | 5 | 8 | None | 41 | 2 | 0 | 2 | 0 | 39 | 0 | 28 | 13 |
| PMC11227129_decimer_handdrawn_caffeine | 1 | 8 | None | 9 | 1 | 0 | 1 | 0 | 7 | 1 | 2 | 7 |
| PMC13390035_patent_ocsr_benchmark | 4 | 6 | None | 32 | 2 | 0 | 2 | 0 | 29 | 1 | 17 | 15 |
| PMC9185882_decimer_handdrawn_dataset | 2 | 4 | None | 35 | 1 | 0 | 1 | 0 | 27 | 7 | 3 | 32 |
| ntp_roc_basicred9 | 1 | 2 | None | 3 | 0 | 0 | 0 | 0 | 3 | 0 | 1 | 2 |
| ntp_roc_adriamycin | 1 | 2 | None | 3 | 0 | 0 | 0 | 0 | 3 | 0 | 1 | 2 |
| ntp_roc_azacitidine | 1 | 3 | None | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
