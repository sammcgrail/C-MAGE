# Score: synthetic 100 plain-SMILES, stage3only

Manifest `synthetic_manifest.json` (synthetic_cx); threshold 0.8431.

- Drawn molecules (recall denominator): **100**
- Structures emitted for those groups (precision denominator): **100**
- Stage 1 figures: n/a; stage 2 segments: 100

| metric | stereo required | stereo relaxed |
|---|---|---|
| recall | 58/100 = 0.58 | 63/100 = 0.63 |
| precision | 58/100 = 0.58 | 63/100 = 0.63 |

Structures by verdict: exact 58, stereo 5, wrong 31, invalid 6

## Confidence split vs correctness

| tier | n | exact | stereo | wrong | invalid | wrong+invalid | exact |
|---|---|---|---|---|---|---|---|
| high | 72 | 50 | 5 | 16 | 1 | 0.2361 | 0.6944 |
| low | 28 | 8 | 0 | 15 | 5 | 0.7143 | 0.2857 |

## Graded verdicts -- what the strict `wrong` pile is made of

The strict counts above are unchanged. Below, each structure is graded by the
LOOSEST relaxation needed before it and the drawn molecule agree. `near` (Tanimoto >= 0.85) is a **diagnostic, not a pass** -- Morgan fingerprints
are stereo-blind, so two diastereomers score 1.000. Gate: `graded_selftest.py`.

| grade | structures | % | + largest fragment | needed decode | needed dephantom |
|---|---|---|---|---|---|
| exact | 77 | 77.0% | 77 | 18 | 1 |
| stereo | 1 | 1.0% | 1 | 0 | 0 |
| near | 5 | 5.0% | 5 | 1 | 0 |
| wrong | 11 | 11.0% | 11 | 0 | 0 |
| invalid | 6 | 6.0% | 6 | 0 | 0 |

Of the **31** structures the strict metric calls `wrong`:

- same molecule, different representation: **19** (61.3%)
- near-miss (skeleton match or Tanimoto >= 0.85): 1
- genuinely different molecule: 11

| recall | molecules |
|---|---|
| strict, stereo required | 58/100 |
| any matched grade (exact/stereo/tautomer/charge/salt) | 78/100 |

Recall by grade: exact 77, stereo 1, no 22


## Per group

| group | drawn | figs | segs | structs | rec.exact | rec.stereo | exact | stereo | wrong | invalid | high | low |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| synth_basic_1 | 10 | None | 10 | 10 | 10 | 0 | 10 | 0 | 0 | 0 | 10 | 0 |
| synth_basic_2 | 10 | None | 10 | 10 | 10 | 0 | 10 | 0 | 0 | 0 | 9 | 1 |
| synth_stereo_1 | 10 | None | 10 | 10 | 6 | 0 | 6 | 0 | 2 | 2 | 5 | 5 |
| synth_stereo_2 | 10 | None | 10 | 10 | 8 | 1 | 8 | 1 | 1 | 0 | 8 | 2 |
| synth_abbrev_1 | 10 | None | 10 | 10 | 0 | 0 | 0 | 0 | 10 | 0 | 7 | 3 |
| synth_abbrev_2 | 10 | None | 10 | 10 | 1 | 0 | 1 | 0 | 9 | 0 | 5 | 5 |
| synth_complex | 10 | None | 10 | 10 | 3 | 0 | 3 | 0 | 4 | 3 | 3 | 7 |
| synth_salt | 10 | None | 10 | 10 | 9 | 0 | 9 | 0 | 1 | 0 | 8 | 2 |
| synth_markush | 10 | None | 10 | 10 | 3 | 3 | 3 | 3 | 3 | 1 | 9 | 1 |
| synth_mixed | 10 | None | 10 | 10 | 8 | 1 | 8 | 1 | 1 | 0 | 8 | 2 |
