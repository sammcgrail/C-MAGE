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
# The scoring scripts need RDKit and openpyxl, which live ONLY in the stage-3
# venv. Their #!/usr/bin/env python3 resolves to whatever python3 is on PATH,
# which is NOT that interpreter -- so call them through it explicitly.
PY=.venv-ms/bin/python

benchmarks/run_stage3_only.sh --images DIR --out OUT --device cpu
$PY benchmarks/score_run.py --run-dir OUT/run_* --manifest benchmarks/ground_truth/images_realworld_every7.json --out SCORED
$PY benchmarks/rescore_fragments.py --scored SCORED
```

Ground truth is PubChem-resolved and pixel-verified; 95 of the 97 carry a
confirmed CID. Comparison is by RDKit canonical SMILES, never string equality.

## 3. CXSMILES stores abbreviations on purpose — score against it, not around it

**This section previously recorded a pipeline shortcoming. That was my error, and
the correction roughly doubles the measured accuracy.** Keeping the wrong version
described here because the mistake is an easy one to repeat.

CXMolScribe emits **CXSMILES**, not plain SMILES, and that is the whole point of
it. Where a drawing says `OMe`, the prediction is a dummy atom carrying the label
in the CXSMILES extension block:

```
*c1cc2c(cc1-c1cc(O)c3cc4c(cc3c1)OCO4)OCO2 |$OMe;;;;;;;;;;;;;;;;;$|
```

This is **deliberate**, and it is a modification this fork's MolScribe carries:
`chemistry.py:_expand_abbreviation` has its `ABBREVIATIONS` lookup commented out,
where upstream MolScribe substitutes a guess. Compare:

```python
# upstream MolScribe — destroys the abbreviation
if abbrev in ABBREVIATIONS:
    return ABBREVIATIONS[abbrev].smiles

# CXMolScribe — preserves it as a labelled superatom
    return f'[{abbrev}]'
```

Preserving it is strictly more information. The abbreviation as drawn stays
recoverable, and an abbreviation the vocabulary does not know becomes **visible**
instead of silently wrong.

### The scoring error, and what it cost

I compared those CXSMILES against fully-expanded reference SMILES. That
comparison can only ever fail — they are different representations of the same
molecule — so 162 of 242 predictions scored "wrong" with nothing whatever wrong
with the recognition. Expansion belongs at **comparison** time, using the same
`ABBREVIATIONS` table the model was trained against. `benchmarks/cxsmiles.py`
does it, and never guesses: an unknown label is reported rather than approximated.

Recall on the 11-document corpus, per-document denominators, one variable:

| scoring | recall |
|---|---|
| raw CXSMILES vs expanded reference | 9/34 = **26.5%** |
| + CXSMILES abbreviations expanded | 16/34 = **47.1%** |
| + largest fragment as well | 18/34 = **52.9%** |

Two documents flip entirely: aglacin B goes 0/3 → 3/3, and the patent OCSR
benchmark 2/4 → 4/4. The pipeline had read them correctly all along.

```bash
.venv-ms/bin/python benchmarks/cxsmiles.py --smiles '*C |$Ph;$|'   # -> Cc1ccccc1
.venv-ms/bin/python benchmarks/cxsmiles.py --csv SCORED/structures.csv --out X.csv
```

### The lesson, stated generally

This is the **third** time this corpus has produced the same failure, and by now
it deserves a name: *the metric measured representation, not recognition.* First
whole-string versus largest-fragment (14.4% vs 66.0%), then the resolution
artifact, now CXSMILES versus plain SMILES. Every time, the pipeline was better
than the number said, and every time the tell was the same — a hand-check of one
prediction showed a chemically sensible answer scored wrong.

**Before reporting any accuracy figure, expand abbreviations, strip phantom
fragments, and hand-check one "wrong" answer.** If it looks right to a chemist,
the metric is the thing that is broken.

### What the corpus does say, corrected

Precision remains **not reportable** here: 242 structures emitted against 34
ground-truth molecules, because these documents draw dozens of compounds each and
only the PubChem-resolvable ones were recorded. An emitted structure absent from
a partial ground truth scores "wrong" regardless of correctness.

Genuine weaknesses, on documents with complete ground truth and after expansion:
charged benzo[c]phenanthridinium alkaloids **2 of 9**, and the 1980 hand-inked
patent scan **0 of 2**. Phantom fragments were rare (0-8 per document against 63
of 97 on 300 px thumbnails), independently confirming finding 2.

Total-synthesis papers are still a poor benchmark corpus, but for a narrower
reason than I first wrote: not because the abbreviations are unscoreable — they
are, now — but because the intermediates they draw have no reference to score
against.
