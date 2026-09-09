# The denominator was wrong: a third of the "figures" are not chemistry

All 139 stage-1 figures from 20 real-document runs were classified by eye. Labels
are in `/root/cmage-work/figclass/labels_all.tsv`, the contact sheets used to make
them in the same directory, and the joined data in `figures_labelled.json`.

| label | n | zero-segment |
|---|---|---|
| structure | 87 | 1 (1%) |
| structure_in_diagram | 4 | 0 (0%) |
| structure_generic (Markush, R groups) | 3 | 2 (67%) |
| table | 21 | 16 (76%) |
| text | 18 | 15 (83%) |
| spectrum | 5 | 2 (40%) |
| chart | 1 | 1 (100%) |

**95 of 139 figures (68%) carry a drawn structure. 44 (32%) are body text, data
tables, IR/NMR spectra, journal boilerplate and a bar chart** — VisualHeist
extracts them as figures; they contain no chemistry.

## What this does to the headline numbers

| | over all 139 figures | over the 95 structure-bearing |
|---|---|---|
| figures producing zero segments | 37 = **26.6%** | 4 = **4.2%** |
| median ink retained | **0.291** | **0.590** |
| mean ink retained | 0.344 | 0.496 |
| pooled ink retained | 30.1% | 47.6% |
| figures retaining under half | 61.9% | 44.2% |

**"Stage 2 deletes a quarter of all figures" is false.** It deletes 4.2% of the
figures that contain a structure, and two of those four are Markush generics with
R groups. What it deletes is mostly text: 75% of non-chemistry figures produce no
segment, and only 0.9% of non-chemistry ink survives into stage 3. On that axis
stage 2 is behaving as a filter and behaving well.

## A label these numbers depended on, which was wrong

`ntp_roc_pahs_image_3` was labelled `structure` by BOTH by-eye passes. It is a pure
data table — PAH melting points, boiling points, vapour pressures — with no
structure anywhere on it. `tools/figure_filter.py` found it by disagreeing with
both, and opening the file settles it in one look.

Two independent readers agreeing is only evidence if they are independent in the
way that matters. Both had read the same low-resolution contact sheets, so they
shared a failure mode and the agreement measured nothing. The label is corrected
above (structure-bearing 95 → 94, tables 20 → 21). That figure was also the one
cited elsewhere as "the largest figure in the document produced zero segments",
71,412 px. It is a table; zero segments is the right answer.

## Every zero-segment structure figure that is left, at full resolution

Three, and they are all the same thing:

| figure | label | ink |
|---|---|---|
| `EP0641330B1_pregabalin_image_10` | structure | 16,604 |
| `EP0641330B1_pregabalin_image_11` | structure_generic (Markush) | 7,723 |
| `EP0641330B1_pregabalin_image_8` | structure_generic (Markush) | 13,470 |

All three are from the same 1994 EPO patent and share a drawing style: a skeletal
structure written mostly as typeset atom labels (`N3CH2`, `CH2CH(CH3)2`, `CO2H`)
joined by a few plain lines and one solid wedge, with a caption line under it.
`image_10` is a real, fully specified molecule — the azide precursor to pregabalin
— and stage 2 returns nothing for it.

So the sharp version of the finding is not "a quarter of figures are deleted". It
is: **3 of 94 structure-bearing figures produce no segment, and all three are one
drawing style in one patent** — sparse label-and-line skeletal drawings. That is a
detection gap with a shape, which is worth more to a maintainer than a percentage.

## What survives the correction

Over structure-bearing figures that did produce segments (91):

- **median retention 0.595** — half the structural ink is gone at the median
- **38 of 91 (41.8%) retain under half their ink**

That is the real problem, and it is half the size of the number this project has
been carrying. The azacitidine figure Sam flagged from a single screenshot is in
this population, not in the deleted one.

## The other leak, in the opposite direction

11 non-chemistry figures DID produce segments — 15 segments in total, fed to a
molecule recogniser: a properties table (4 segments), two Table-of-Contents text
strips, an IR spectrum, two data tables. Every structure stage 3 emits from those
is a false positive by construction, and they land in the precision denominator.

## Why this took so long to see

Ink is easy to sum and does not know what it is. Every retention statistic on this
project used all of stage 1's output as its denominator, so a paragraph of German
patent text and a transmittance spectrum counted exactly like a drawn molecule.
The measurement was correct; the population was not the population of interest.

**Rule to carry:** state the denominator in the same breath as the number, and
check that it contains only the thing the number is about. "Measure the thing that
can change, not the thing that is easy to sum" — the ink was easy to sum.
