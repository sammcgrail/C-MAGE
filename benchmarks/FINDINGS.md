# What the benchmark actually found

Four results, all of which change how you should read this pipeline's output.
None is ARM-specific. Sections 1-3 are three separate occasions on which a low
number turned out to be the metric measuring representation rather than
recognition; section 4 is the fourth, and quantifies how much of the strict
`wrong` pile that accounts for.

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

This is **deliberate**, and it is a modification C-MAGE's vendored MolScribe carries
— present in upstream C-MAGE's first commit, not introduced by this fork:
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
molecule — so most of the 148 predictions carrying an abbreviation scored "wrong"
with nothing whatever wrong with the recognition. Expansion belongs at
**comparison** time, using the same `ABBREVIATIONS` table the model was trained
against. `benchmarks/cxsmiles.py` does it, and never guesses: a label it cannot
expand is reported rather than approximated.

Recall on the 11-document corpus, per-document denominators, one variable,
**stereochemistry required throughout**:

| scoring | recall |
|---|---|
| raw CXSMILES vs expanded reference | 9/34 = **26.5%** |
| + CXSMILES abbreviations expanded | 18/34 = **52.9%** |
| + largest fragment as well | 18/34 = 52.9% — **it adds nothing here** |

Two documents flip entirely: aglacin B goes 0/3 → 3/3, and the patent OCSR
benchmark 2/4 → 4/4. The pipeline had read them correctly all along.

The third row is worth reading as a **control**, not as a step. Largest-fragment
stripping recovers nothing on this corpus — scored on its own, without expansion,
it moves the naive figure from 9/34 to 9/34 — even though 21 of the 242
predictions do carry a phantom fragment. That artifact belongs to 300-px
thumbnails, where it is worth 53 of 97; on documents at publication resolution it
is worth zero. Both numbers come from the same code path, so the contrast is
real rather than rhetorical.

**An earlier version of this table read 16/34 = 47.1% in the middle row and put
the remaining two molecules under "+ largest fragment".** Both halves of that were
wrong, and the way they were wrong is the subject of the next section.

### The expander had a stereochemistry bug, and it looked exactly like a lower score

The first expander joined the substituent with `RWMol.RemoveAtom` plus `AddBond`.
That appends the new bond at the END of the anchor atom's bond list — and `@`/`@@`
and `/`-`\` are both defined *relative to that order*. So the join silently
emitted a different stereoisomer while producing a perfectly valid molecule: five
of seven tetrahedral centres flipped, four of five alkene geometries lost.

Nothing raised. The only symptom was two molecules scoring "same skeleton, wrong
stereochemistry" — which reads exactly like a recogniser that is bad at wedge
bonds. `Chem.molzip` preserves the anchor's own bond object, and with it parity,
geometry and bond order; it recovers both:

```
sorbic acid   */C=C/C=C/C |$COOH;;;;;$|
  molzip      C/C=C/C=C/C(=O)O     == PubChem CID 643460
  superseded  C/C=C/C=CC(=O)O      one geometry dropped at the attachment point
```

`benchmarks/cxsmiles_selftest.py` is the standing guard. It checks six real
predictions against an independent reference — the label substituted into the
string *as text*, which cannot reorder anyone's bonds — and it runs the superseded
algorithm beside the current one as a negative control. The gate closes if a case
fails **or** if a case that is supposed to discriminate stops discriminating,
because a control that agrees with the thing it controls for has stopped being
evidence. The web app asks it before publishing any expanded figure and withholds
them if it says no; a wrong expansion does not fail loudly, it reports a plausibly
lower accuracy, and that is indistinguishable from the pipeline being worse.

```bash
.venv-ms/bin/python benchmarks/cxsmiles.py --smiles '*C |$Ph;$|'   # -> Cc1ccccc1
.venv-ms/bin/python benchmarks/cxsmiles.py --csv SCORED/structures.csv --out X.csv
```

### Which corpora this actually changed — measured, not assumed

Before rewriting every number, I checked where abbreviations even occur. The fix
matters for exactly one corpus, and saying so is more useful than restating all
of them:

| corpus | predictions carrying abbreviations | effect of expanding |
|---|---|---|
| 97 PubChem depictions, stage 3 only | **0 of 97** | none — 66.0% / 96.2% stand |
| 24 upscaled worst offenders | **0 of 24** | none — 79.2% stands |
| 11 known-answer PDFs, full pipeline | 8 of 70 (11%) | **none** — 16/70 and 42.9% high tier are identical either way |
| 11-document expanded PDF corpus | **148 of 242 (61%)** | recall 26.5% → **52.9%** |

Two things follow. Rendered depictions of single named compounds carry no
abbreviations at all, so the earlier image-corpus figures were never affected.
And the known-answer PDFs do contain a few, but expanding them changes nothing —
those predictions were not near-misses. It is **real documents with synthesis
content** where this dominates, which is also where the pipeline is most likely to
be used in anger.

`rescore_fragments.py` now expands by default; `--no-expand-cxsmiles` shows the
misleading version if you want to see the difference.

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

The alkaloid document deserves one qualification, because its 2 of 9 is partly a
property of the document. Its Scheme 1 is a classification *panel* — generic
skeletons carrying `OR1`/`OR2`/`OR3`, with the individual alkaloids named in a
substituent legend underneath rather than drawn — so several of its nine reference
molecules were never drawn explicitly and could not have been matched by any
output. It is left in the denominator rather than dropped, which makes the
headline a floor. The genuine finding underneath survives: quaternary aromatic
nitrogen is hard for this reader.

Two kinds of label stay unexpanded and they must not be added together. A
**Markush variable** (`R1`, `X`, `OR2`) denotes a set of molecules rather than one,
so nobody can expand it and no scorer should be marked down for it. A **missing
abbreviation** (`OTBS`, `OTHP`, the phosphate esters) denotes a perfectly definite
group that is simply absent from MolScribe's 75-entry vocabulary — a closable
coverage gap. `cxsmiles.py:label_class()` makes the split; on this corpus it is 23
predictions and 36 predictions respectively, plus 3 the expander itself failed on,
and those counts overlap because one prediction can carry several labels.

Total-synthesis papers are still a poor benchmark corpus, but for a narrower
reason than I first wrote: not because the abbreviations are unscoreable — they
are, now — but because the intermediates they draw have no reference to score
against.

## 4. Most of `wrong` is not a wrong molecule — the fourth time this has happened

Section 3 ended by naming the pattern: *the metric measured representation, not
recognition*, three times over. This is the fourth, found by grading every
prediction the scorer calls `wrong` on four axes it had never looked at —
tautomer, protonation, counter-ion, and InChIKey connectivity — rather than
looking for another whole-corpus post-process.

| | 675 PubChem depictions, stage 3 only | 11 published documents, all 3 stages |
|---|---|---|
| structures with ground truth | 675 | 242 |
| **strict `wrong`** | **504** | **212** |
| of those, the same molecule written differently | **426 = 84.5%** | **20 = 9.4%** |
| near-miss (skeleton match, or Tanimoto ≥ 0.85) | 16 | 0 |
| genuinely a different molecule | 62 | 192 |

The two corpora are worth reading against each other, because the *reason* differs
completely and neither lever helps the other — the same asymmetry section 3 found:

| what had to be relaxed | images | documents |
|---|---|---|
| phantom `I`/`[HH]` fragments dropped | 409 | 0 |
| CXSMILES abbreviation decoded | 0 | 20 |
| tautomer | 3 | 0 |
| protonation (`charge`) | 9 | 1 |
| counter-ion or solvate (`salt`) | 20 | 0 |

`benchmarks/graded.py` computes this and `score_run.py` now reports it in every
`summary.json`, `summary.md` and `structures.csv`, beside the strict counts and
never merged with them. `--no-graded` reproduces the previous output byte for
byte; that was verified against a pre-existing scored directory, file by file.

Independent agreement worth noting: graded recall on the document corpus is
**18/34**, which is the same number `rescore_fragments.py --expand-cxsmiles`
reports by a completely different code path, and the strict 9/34 is unchanged.

### Six new residual classes, each small and each real

Naming them matters more than their size, because each one is a thing a reader
would otherwise rediscover as "poor recognition":

```
tautomer    sildenafil   pred  CCCc1nn(C)c2c(=O)nc(-c3cc(S(=O)(=O)N4CCN(C)CC4)ccc3OCC)[nH]c12
                         ref   CCCc1nn(C)c2c(=O)[nH]c(-c3cc(S(=O)(=O)N4CCN(C)CC4)ccc3OCC)nc12
charge      ciprofloxacin  C(=O)[O-] drawn where the reference has C(=O)O   (9 cases: 6 carboxylates, 3 ammonium)
salt        osimertinib  free base predicted, reference is the mesylate     (20 cases; 15 are a stray `Cl` fragment on the prediction, 2 lithium, 1 iodide)
skeleton    thiamine pyrophosphate: one phosphate O drawn protonated. The Uncharger
            cannot fix it because the thiazolium is a permanent cation, so only the
            InChIKey connectivity block catches it.
near        carboplatin without its platinum, Tanimoto 0.889 — CLOSE AND WRONG
decoded     pregabalin  *C[C@@H](CN)CC(C)C |$CO2H;;;;;;;;$|  (documents only, 19 cases)
```

### Where the lines are, and the two ways a grader like this goes bad

A grading scheme loose enough to pass a genuinely different molecule is worse than
the strict metric it replaces, because it yields a friendlier number and no error.
Both failures below were **live false passes** in the first draft, and both were
found by hand-checking, not by a test:

- **Reference-side fragment selection.** Comparing the prediction's largest
  fragment against the *reference's* largest fragment graded carboplatin `exact`
  while the prediction had dropped the platinum. Gone: the reference is only ever
  normalised by rules that name what they remove.
- **`rdMolStandardize.FragmentParent` is `LargestFragmentChooser`** wearing a
  chemistry name. Using it for the `salt` rung silently reintroduced the hammer —
  33 image predictions reached `salt` only because it binned their phantom
  `I`/`[HH]` — and it strips `[Pt+2]` clean off carboplatin's reference.
  `SaltRemover`'s curated patterns take a mesylate and an iodide and leave
  `[Pt+2]`, propylene glycol and succinic acid alone.

Consequences, stated as rules:

- **`near` is a diagnostic, never a pass.** Morgan fingerprints are stereo-blind:
  on this manifest, 18 of 197,506 distinct molecule pairs reach Tanimoto ≥ 0.85 and
  **seven of them sit at exactly 1.000 because they are enantiomer pairs**
  (levomilnacipran/milnacipran, esketamine/ketamine, citalopram/escitalopram,
  cetirizine/levocetirizine, bupivacaine/levobupivacaine, esomeprazole/omeprazole,
  galactose/glucose). A `near` structure does not recover a molecule and is not
  counted in graded recall.
- **0.85 because that is where these corpora separate**, not by convention. Nothing
  graded `wrong` exceeds 0.845 on the images or 0.657 on the documents, so no
  genuine miss is being dressed up; and the near buckets (16 and 0) are small enough
  to read end to end, which is the only way to know a bucket. The closest call is
  strychnine-plus-one-carbon at 0.845 — a real homologue, correctly `wrong`, and
  0.01 from the line. Treat the threshold as arbitrary within ±0.01 and never
  quote `near` as accuracy.
- **A metal blocks the salt rung**, two ways: present on one side only
  (carboplatin), or carrying any bond on either side (oxaliplatin's prediction
  draws Pt covalently, and fragment normalisation then matches the
  diaminocyclohexane *ligand* on both sides). A coordinated metal is the compound,
  not a spectator ion.
- **The phantom rule stays narrow.** Only *neutral* fragments whose atoms are all H
  and/or I. `[I-]` is a genuine counter-ion and survives to be handled by name;
  `CC`, `CCl` and `C` survive too, which is why 11 predictions grade `near` rather
  than `exact` and only the second largest-fragment column rescues them — 6 carrying
  a stray methane, 3 a stray ethane, 1 `CC.CCl`, and atazanavir carrying a real
  14-heavy-atom second fragment that no narrow rule should ever discard. Verified: not one of the 709 reference
  molecules across both manifests carries a neutral H/I-only fragment, so this step
  cannot fabricate a match against a reference that legitimately had one.
- **Duplicate collapse is counted apart from phantom removal.** One crop holding
  two copies of the same drawing (letrozole, disulfiram) is a different claim from a
  misread label. Merging the two counters once put `Cl` in a field labelled
  "phantoms dropped", and naming both fields `dropped_*` produced a row flagged
  `dedup=False` beside a non-empty `dropped_duplicates` — a field lying about its
  own meaning. They are now `phantom_frags` / `duplicate_frags` (what the
  prediction carries) and `dropped_by_largest` (what the hammer actually
  discarded).

### Two negative results, which are the most useful part

- **`rdMolStandardize.Normalizer` rescues nothing.** It was the obvious next rung,
  because three residual misses look like charge-notation errors. They are not:
  isosorbide dinitrate's `O[N+](=O)O`, zidovudine's `N=[N+]=N` and pregabalin's
  `CN=NN` each carry an extra *hydrogen* where the reference has a negative charge.
  RDKit already normalises pentavalent nitro at parse time, so there is no notation
  left to fix and no rung was added.
- **`rescore_fragments.py`'s largest-fragment rule loses a correct answer.**
  Methylene blue's reference is legitimately two fragments (cation + `[Cl-]`) and
  the prediction matches it exactly; reducing the prediction to its largest
  fragment turns an `exact` into a miss. It is one structure in 743 and it does not
  move the headline, but it is the same class of error in the opposite direction:
  a post-process applied to a corpus where its premise does not hold.

Reproduce:

```bash
PY=.venv-ms/bin/python
$PY benchmarks/graded_selftest.py                      # gate: must print GATE: open
$PY benchmarks/score_run.py --run-dir RUN --manifest MANIFEST --out SCORED
$PY benchmarks/graded.py --scored SCORED --manifest MANIFEST
```

## 5. Our ground truth is the wrong KIND of ground truth for documents

Supplied by the C-MAGE author via Sam, and it reframes everything above:

> For all of my ground truth validation I am comparing the DECIMER-Image-
> Segmentation result against the generated CXSMILES string and not against any
> SMILES strings.

The paper grades each prediction **against its own segment image**, by hand,
against a **manually written reference CXSMILES** — and grades it in two parts
(Table 3): the **skeleton** (the CXSMILES minus the appendix) and the
**appendix** (CXMolScribe's translation of the superatoms). `Y` is both correct;
`YS` is skeleton correct with **no appendix present**.

That is not what this benchmark has been doing. We take a PubChem reference
SMILES, expand the prediction's appendix into its skeleton, and compare whole
molecules. Expanding is precisely the "heuristic translation of superatoms to
SMILES subunits" the paper says CXSMILES exists to avoid, using a 75-entry table
where the paper's point is that **no encompassing list can exist**.

How much this matters depends entirely on the corpus, and the split is stark:

| corpus | predictions carrying an appendix |
|---|---|
| 675 PubChem depictions | **5 of 743 (0.7%)** |
| 11 published documents | **148 of 242 (61.2%)** |

**The image numbers stand.** With essentially no appendices, every comparison
there is a `YS`-style skeleton grade and our expansion step is a no-op. 68.4%
and the 82.5%/84.0% tier are legitimate.

**The document numbers do not.** Split by whether the prediction has an appendix:

| | predictions | matched |
|---|---|---|
| no appendix — PubChem SMILES is a valid reference | 94 | 14 (14.9%) |
| appendix present — PubChem SMILES is **not** a valid reference | 148 | 19, and only by expanding |

For those 148 there is nothing legitimate to compare against: the reference has
no appendix, so the only options are to expand (wrong by the paper's own
argument) or to hand-write a reference CXSMILES per segment, which is what the
authors did and what we have not done.

So the honest statement about the document corpus is **not** "52.9% recall". It
is: *61% of predictions cannot be scored at all with the ground truth we have.*
The 18/34 figure was measuring our expansion table as much as the model.

### What would fix it

Write reference **CXSMILES** for the document corpus, appendix included, and
grade skeleton and appendix separately as the paper does. That is manual work —
the authors did exactly this because "the novel datasets do not have established
ground truths". Until then, report document results only over the 94 predictions
with no appendix, and say the other 148 are unmeasured.

The reference figures to aim at, from the paper: skeletal CXMolScribe 87.3% (ACS)
and 89.5% (patent documents); appendix 83.5% and 92.4%.
