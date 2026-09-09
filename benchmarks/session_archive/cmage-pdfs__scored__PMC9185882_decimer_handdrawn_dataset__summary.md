# Score: run_20260909-010232

Manifest `pdf_manifest_expanded.json` (pdfs); threshold 0.8431.

- Drawn molecules (recall denominator): **34**
- Structures emitted for those groups (precision denominator): **35**
- Stage 1 figures: 4; stage 2 segments: 35

| metric | stereo required | stereo relaxed |
|---|---|---|
| recall | 1/34 = 0.0294 | 1/34 = 0.0294 |
| precision | 1/35 = 0.0286 | 1/35 = 0.0286 |

Structures by verdict: exact 1, stereo 0, wrong 27, invalid 7

## Confidence split vs correctness

| tier | n | exact | stereo | wrong | invalid | wrong+invalid | exact |
|---|---|---|---|---|---|---|---|
| high | 3 | 1 | 0 | 2 | 0 | 0.6667 | 0.3333 |
| low | 32 | 0 | 0 | 25 | 7 | 1.0 | 0.0 |

## Per group

| group | drawn | figs | segs | structs | rec.exact | rec.stereo | exact | stereo | wrong | invalid | high | low |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| US4231938A_lovastatin | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| EP0641330B1_pregabalin | 5 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| bjoc_21-197_aglacinB | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| bjoc_18-169_macarpine | 9 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| bjoc_19-15_pheromones | 5 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| PMC11227129_decimer_handdrawn_caffeine | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| PMC13390035_patent_ocsr_benchmark | 4 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| PMC9185882_decimer_handdrawn_dataset | 2 | 4 | 35 | 35 | 1 | 0 | 1 | 0 | 27 | 7 | 3 | 32 |
| ntp_roc_basicred9 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| ntp_roc_adriamycin | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| ntp_roc_azacitidine | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
