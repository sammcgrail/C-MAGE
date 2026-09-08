# What the benchmark actually found

Two results, both of which change how you should read this pipeline's output.
Neither is ARM-specific.

## 1. Scoring the whole SMILES string measures an artifact, not recognition

97 PubChem-verified depictions, stage 3 only, 300x300 PNG input:

| scoring | exact | exact or stereo |
|---|---|---|
| whole predicted SMILES | **14.4%** | 18.6% |
| largest fragment only | **66.0%** | 73.2% |

That is not a scoring trick, and the gap is the finding. 63 of the 97
predictions carry phantom **disconnected** atoms appended to a correct core,
almost all of them `I` or `[HH]`:

```
oxalic acid   I.I.I.O=C(O)C(=O)O.[HH].[HH]                core exact
proline       I.I.I.O=C(O)[C@@H]1CCCN1                    core exact
melatonin     COc1ccc2[nH]cc(CCNC(C)=O)c2c1.[HH].[HH]     core exact
epinephrine   CNC[C@H](O)c1ccc(O)c(O)c1  + 105 x I        core exact
```

Report both numbers. The strict one is what a caller gets if it pastes the
SMILES straight out; the fragment one is what the recogniser actually achieved,
and therefore what a one-line post-process could deliver.

The confidence split is meanwhile doing real work: scored on the main fragment,
**high confidence is 25/26 correct (96.2%)** against 64.8% for low. The model
knows when it has produced rubbish — epinephrine's 106-fragment answer scored
0.045. Use the tier; do not use the third decimal.

## 2. The phantom fragments are largely an input-RESOLUTION artifact

Hypothesis: at 300x300, PubChem's heteroatom labels are a few pixels tall and
get read as unbonded `I` and `H` atoms. Test: take the 24 worst offenders,
upscale 4x with LANCZOS, change nothing else.

| | 300x300 | 1200x1200 |
|---|---|---|
| total fragments across the 24 | 257 | **56** (78% fewer) |
| largest single prediction | 106 fragments | **5** |
| phantoms eliminated entirely | — | 10 of 24 |
| reduced but still present | — | 14 of 24 |
| unchanged | — | 0 |
| **worse** | — | **0** |

Every one of the 24 improved and none regressed, which is about as clean as this
kind of result gets. Largest-fragment accuracy on that subset rises to 79.2%.

Two things follow:

- **Feed this pipeline images bigger than 300 px.** A depiction that small is
  below what stage 3 can read reliably, and the failure is silent — you get a
  plausible molecule with junk welded to it, not an error.
- **Resolution is not the whole story.** Phantoms survive in 14 of 24 even at
  1200 px, so a fragment-strip post-process is still worth having. Take the
  largest fragment by heavy-atom count; `rescore_fragments.py` shows the method.

## Reproducing

```bash
benchmarks/run_stage3_only.sh --images DIR --out OUT --device cpu
benchmarks/score_run.py --run-dir OUT/run_* --manifest benchmarks/ground_truth/images_realworld_every7.json --out SCORED
benchmarks/rescore_fragments.py --scored SCORED
```

Ground truth is PubChem-resolved and pixel-verified; 95 of the 97 carry a
confirmed CID. Comparison is by RDKit canonical SMILES, never string equality.
