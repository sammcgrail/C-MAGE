# Score: run_20260909-005959

Manifest `PMC13390035_patent_ocsr_benchmark.json` (pdfs); threshold 0.8431.

- Drawn molecules (recall denominator): **4**
- Structures emitted for those groups (precision denominator): **32**
- Stage 1 figures: 6; stage 2 segments: 32

| metric | stereo required | stereo relaxed |
|---|---|---|
| recall | 2/4 = 0.5 | 2/4 = 0.5 |
| precision | 2/32 = 0.0625 | 2/32 = 0.0625 |

Structures by verdict: exact 2, stereo 0, wrong 29, invalid 1

## Confidence split vs correctness

| tier | n | exact | stereo | wrong | invalid | wrong+invalid | exact |
|---|---|---|---|---|---|---|---|
| high | 17 | 1 | 0 | 16 | 0 | 0.9412 | 0.0588 |
| low | 15 | 1 | 0 | 13 | 1 | 0.9333 | 0.0667 |

## Per group

| group | drawn | figs | segs | structs | rec.exact | rec.stereo | exact | stereo | wrong | invalid | high | low |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| PMC13390035_patent_ocsr_benchmark | 4 | 6 | 32 | 32 | 2 | 0 | 2 | 0 | 29 | 1 | 17 | 15 |
