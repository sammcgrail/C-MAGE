# Score: synthetic 100 plain-SMILES, full

Manifest `synthetic_manifest.json` (synthetic_cx); threshold 0.8431.

- Drawn molecules (recall denominator): **100**
- Structures emitted for those groups (precision denominator): **103**
- Stage 1 figures: 20; stage 2 segments: 103

| metric | stereo required | stereo relaxed |
|---|---|---|
| recall | 32/100 = 0.32 | 35/100 = 0.35 |
| precision | 32/103 = 0.3107 | 35/103 = 0.3398 |

Structures by verdict: exact 32, stereo 3, wrong 60, invalid 8

## Confidence split vs correctness

| tier | n | exact | stereo | wrong | invalid | wrong+invalid | exact |
|---|---|---|---|---|---|---|---|
| high | 73 | 28 | 2 | 42 | 1 | 0.589 | 0.3836 |
| low | 30 | 4 | 1 | 18 | 7 | 0.8333 | 0.1333 |

## Graded verdicts -- what the strict `wrong` pile is made of

The strict counts above are unchanged. Below, each structure is graded by the
LOOSEST relaxation needed before it and the drawn molecule agree. `near` (Tanimoto >= 0.85) is a **diagnostic, not a pass** -- Morgan fingerprints
are stereo-blind, so two diastereomers score 1.000. Gate: `graded_selftest.py`.

| grade | structures | % | + largest fragment | needed decode | needed dephantom |
|---|---|---|---|---|---|
| exact | 45 | 43.7% | 45 | 13 | 0 |
| stereo | 1 | 1.0% | 1 | 0 | 0 |
| salt | 6 | 5.8% | 6 | 0 | 0 |
| near | 5 | 4.9% | 5 | 1 | 0 |
| wrong | 38 | 36.9% | 38 | 0 | 0 |
| invalid | 8 | 7.8% | 8 | 0 | 0 |

Of the **60** structures the strict metric calls `wrong`:

- same molecule, different representation: **19** (31.7%)
- near-miss (skeleton match or Tanimoto >= 0.85): 3
- genuinely different molecule: 38

| recall | molecules |
|---|---|
| strict, stereo required | 32/100 |
| any matched grade (exact/stereo/tautomer/charge/salt) | 52/100 |

Recall by grade: exact 45, stereo 1, salt 6, no 48


## Per group

| group | drawn | figs | segs | structs | rec.exact | rec.stereo | exact | stereo | wrong | invalid | high | low |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| synth_basic_1 | 10 | 2 | 10 | 10 | 5 | 0 | 5 | 0 | 5 | 0 | 9 | 1 |
| synth_basic_2 | 10 | 2 | 10 | 10 | 5 | 0 | 5 | 0 | 5 | 0 | 6 | 4 |
| synth_stereo_1 | 10 | 2 | 10 | 10 | 5 | 0 | 5 | 0 | 2 | 3 | 7 | 3 |
| synth_stereo_2 | 10 | 2 | 10 | 10 | 6 | 1 | 6 | 1 | 2 | 1 | 7 | 3 |
| synth_abbrev_1 | 10 | 2 | 10 | 10 | 0 | 0 | 0 | 0 | 10 | 0 | 8 | 2 |
| synth_abbrev_2 | 10 | 2 | 10 | 10 | 1 | 0 | 1 | 0 | 9 | 0 | 6 | 4 |
| synth_complex | 10 | 2 | 10 | 10 | 3 | 0 | 3 | 0 | 4 | 3 | 4 | 6 |
| synth_salt | 10 | 2 | 12 | 12 | 0 | 0 | 0 | 0 | 12 | 0 | 9 | 3 |
| synth_markush | 10 | 2 | 11 | 11 | 1 | 1 | 1 | 1 | 8 | 1 | 10 | 1 |
| synth_mixed | 10 | 2 | 10 | 10 | 6 | 1 | 6 | 1 | 3 | 0 | 7 | 3 |
