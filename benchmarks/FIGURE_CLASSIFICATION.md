# The denominator was wrong: a third of the "figures" are not chemistry

All 139 stage-1 figures from 20 real-document runs were classified by eye. Labels
are in `/root/cmage-work/figclass/labels_all.tsv`, the contact sheets used to make
them in the same directory, and the joined data in `figures_labelled.json`.

| label | n | zero-segment |
|---|---|---|
| structure | 88 | 2 (2%) |
| structure_in_diagram | 4 | 0 (0%) |
| structure_generic (Markush, R groups) | 3 | 2 (67%) |
| table | 20 | 15 (75%) |
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
