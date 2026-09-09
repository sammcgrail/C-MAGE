# Score: run_20260909-010232

Manifest `PMC9185882_decimer_handdrawn_dataset.json` (pdfs); threshold 0.8431.

- Drawn molecules (recall denominator): **2**
- Structures emitted for those groups (precision denominator): **35**
- Stage 1 figures: 4; stage 2 segments: 35

| metric | stereo required | stereo relaxed |
|---|---|---|
| recall | 1/2 = 0.5 | 1/2 = 0.5 |
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
| PMC9185882_decimer_handdrawn_dataset | 2 | 4 | 35 | 35 | 1 | 0 | 1 | 0 | 27 | 7 | 3 | 32 |
