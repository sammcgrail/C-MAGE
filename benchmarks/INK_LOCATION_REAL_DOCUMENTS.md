# Where the ink DECIMER segmentation loses actually sits — measured on real documents

Measured 2026-09-09. 18 real documents, 135 stage-1 figures, 569 stage-2 segments.
Code: `<work>/inkloc/measure_inkloc.py` (per-figure JSON), `aggregate.py`,
`final.py`, `composite2.py` (hand-check panels), `classify.py` (figure verdicts).
Interpreter `<repo>/.venv-ms/bin/python`, `OMP_NUM_THREADS=2`.

---

## The answer in one line

**Neither lever is worth pulling.** On all figure ink the split is **95.1 % outside the
crop rectangle / 4.9 % inside it** — the opposite of the synthetic 37.8/62.2 — but
essentially none of that ink belongs to a drawing stage 2 engaged with. Restricted to
ink stage 2 *did* engage with, the recoverable loss is **0.08 %–1.9 % of figure ink**
and the data does **not** separate (a) from (b) within it (40.8 % vs 90.0 % outside
depending on the connectivity rule). Separately: in this codebase `DECIMER_BBOX_PAD>0`
takes a branch that returns the crop **unmasked**, so padding already subsumes mask
dilation — there is no experiment where the two compete.

**Do not act on 37.8/62.2. Do not act on 95.1/4.9 either.**

---

## 1. How a segment is placed back into its figure — byte-exact, not estimated

`decimer_segmentation.apply_mask` (default, unpadded branch) attaches the instance mask
as an alpha channel to the **original** image, crops to the mask's bounding box, and
sets every alpha-0 pixel to pure white. Nothing is resampled or recoloured. So at the
true offset every non-white segment pixel equals the figure pixel **byte for byte**.

Placement therefore has a verifiable answer, not an estimate:

1. locate with `cv2.matchTemplate(TM_SQDIFF, mask=non-white)` — a float FFT correlation;
2. **verify** with an exact integer comparison over all three channels — a different
   computation, not a restatement of the first. A placement one pixel off scores ~0,
   not ~0.99.

**574 / 574 segments placed at exactly 1.000000.** Two segments had more than one
numerically optimal offset (small repeated glyphs, 484 and 688 non-white px); both
resolved to an exact match and both sit in figures whose reading order was reproduced.

The synthetic script's binary-ink FFT correlation (`ink_loss_v2.align_fft`) is **not
usable here**: measured on `PMC11227129_..._image_2` it put 4 of 5 segments on the wrong
copy of a repeated motif. It was safe on synthetic art only because there was one
structure per cell to align to.

### Incidental bug found while doing this: red and blue are swapped in every segment PNG

`pipeline_dis.py` does `Image.fromarray(img)` where `img` is the BGRA array cv2 built.
PIL reads a 4-channel array as RGBA, so the saved segment has R and B transposed.
Invisible on grey line art; decisive on colour — on the caffeine figure the un-swapped
hypothesis matches 3–14 % of pixels and the swapped one 100.000 %. **59 of 135 real
figures carry coloured pixels**, and stage 3 reads those segments colour-inverted.

---

## 2. The denominator, fixed

Stage 1 (VisualHeist) hands stage 2 whatever it extracts. Of 135 figures, **44 contain
no drawn chemical structure at all** — HPLC chromatograms, NMR and IR spectra, culture
medium recipes, formulation tables, patent front pages, journal address blocks, licence
boilerplate, literature-citation columns, bar charts. Stage 2 returning little or
nothing for those is correct, not destruction.

Verdicts were made **by eye** from contact sheets of all 135 figures
(`composites/contact_*.png`, 4 per row, captioned with the index) and recorded with a
reason each in `figure_classification.json`.

| | figures |
|---|---|
| stage-1 figures | 135 |
| **contain a drawn structure** | **91** |
| contain none | 44 |
| produced ≥1 segment | 98 |
| **structure-bearing AND produced ≥1 segment (primary denominator)** | **88** |
| non-structure that still produced segments (false positives) | 10 |
| zero segments | 37 |
| — of those, structure-bearing | **3** (`pregabalin_image_8`, `_10`, `_11`; two are Markush) |
| — of those, non-structure | 34 |

The 3-with-structure / 2-Markush result reproduces the coordinator's independent
eyeball pass exactly.

All 37 zero-segment figures are named individually in their run's `stage2.log` as
`FAILED NO SEGMENT = <figure>`, and every one of the 18 runs ends with
`DECIMER-Image-Segmentation PIPELINE RESULTS COMPLETE!`. That is positive proof stage 2
processed them — not an inference from absent output.

### What the denominator fix does to the project's headline

| retention, threshold 200 | mean | median |
|---|---|---|
| all 135 figures, committed JSON (sum of segment ink) | 0.3426 | 0.2908 |
| all 135 figures, this measurement (spatial, no double count) | 0.3388 | 0.2908 |
| **91 structure-bearing figures** | **0.4960** | **0.5905** |
| **88 structure-bearing with ≥1 segment** | **0.5129** | **0.5959** |

**"Median 29.1 % retained" is a statement about page furniture.** For figures that
actually carry chemistry the median is **59.1 %**.

---

## 3. The (a)/(b) split

Binarisation: the partition itself is **threshold-independent by construction** — ink
kept by the mask is byte-preserved, so a figure ink pixel is retained iff its segment
pixel is not pure white. The threshold only decides which figure pixels count as ink.
Primary threshold is **per-figure Otsu** (`cv2.THRESH_OTSU` on the figure's grey),
because it adapts to each document's paper and scan level and is not the bug's own
ruler. 184 ≈ DECIMER's hardcoded 0.72 (0.72 × 255 = 183.6) is reported alongside to
show that measuring with the bug's own ruler gives the same answer.

### A. All figure ink

| denominator | figures | ink px | retained | lost px | **(a) outside** | **(b) inside** | per-figure median (a) |
|---|---|---|---|---|---|---|---|
| every figure with ≥1 segment | 98 | 3,965,192 | 44.3 % | 2,210,285 | **95.75 %** | 4.25 % | 99.0 % |
| **structure-bearing only** | **88** | **3,613,461** | **48.0 %** | **1,879,791** | **95.06 %** | **4.94 %** | **98.2 %** |
| structure-bearing, minus one diagram figure | 87 | 3,498,105 | 49.2 % | 1,776,627 | 95.55 % | 4.45 % | 98.3 % |

### B. Restricted to ink stage 2 engaged with

"Engaged" = a connected component of figure ink holding at least one retained pixel,
i.e. a drawing stage 2 reached and then clipped. That is the only ink a pad or a mask
dilation can act on: a component with no retained pixel at all was never touched — body
text, a caption, or a structure the detector missed outright, none of which a crop
change reaches. Bracketed at two connectivities because a skeletal drawing is *not* one
component (heteroatom labels are separate glyphs): raw connectivity under-counts
engaged ink, a 7 px closing (DECIMER's own `width/185` kernel) over-counts it by welding
nearby text on.

| set | connectivity | engaged loss px | (a) outside | (b) inside | figures contributing | largest single figure |
|---|---|---|---|---|---|---|
| 88 struct | raw | 31,482 | 50.6 % | 49.4 % | 18/88 | **91 %** from one figure |
| 88 struct | 7 px closed | 68,587 | 74.0 % | 26.0 % | 29/88 | 42 % from one figure |
| **87 (minus that figure)** | **raw** | **2,837** | **40.8 %** | **59.2 %** | 17/87 | 35 % |
| **87 (minus that figure)** | **7 px closed** | **39,942** | **90.0 %** | **10.0 %** | 28/87 | 40 % |

The dominating figure is `PMC11227129_decimer_handdrawn_caffeine_image_2` — the DECIMER
paper's **model-architecture diagram**. Of the 5 "structures" DECIMER found in it, one
is caffeine and four are coloured nodes of a neural-net drawing. A pooled number 91 %
driven by that figure is not a finding about documents.

**The bracket 40.8 %–90.0 % is the honest answer at this level: the data does not
separate (a) from (b) for engaged ink.** Either way the quantity is tiny — 2,837 to
68,587 px against 3.6 M ink px, i.e. **0.08 %–1.9 %**.

The complement of that: **stage 2 retains 96.2 %–99.8 % of the ink of drawings it
engages with.** Mechanism agrees — `complete_structure_mask` flood-fills from the
detection seeds over dilated ink, so a component it touches, it takes nearly whole.
(Partly circular: a component counts as engaged *because* something in it was retained.
The measurement says the mask completes the component; it could have been 5 %.)

### C. Threshold sensitivity — none worth reporting

| threshold | ink px | retained | (a) outside | (b) inside |
|---|---|---|---|---|
| 128 | 2,774,970 | 48.9 % | 95.79 % | 4.21 % |
| 160 | 3,329,912 | 49.2 % | 95.64 % | 4.36 % |
| **184 ≈ DECIMER 0.72** | 3,945,097 | 48.0 % | **95.79 %** | 4.21 % |
| **200 (retention JSON)** | 4,301,436 | 48.0 % | **95.24 %** | 4.76 % |
| 220 | 4,923,373 | 46.2 % | 94.40 % | 5.60 % |
| 240 | 7,109,545 | 36.9 % | 95.15 % | 4.85 % |
| **otsu, per figure** | 3,613,461 | 48.0 % | **95.06 %** | 4.94 % |

The split moves between 94.40 % and 95.79 % across the entire range. **The choice of
threshold does not affect the answer**, including the choice to use the bug's own 0.72.

---

## 4. How far the loss sits from what could reach it

87 structure-bearing figures (diagram figure excluded), Otsu, pooled over **pixels**
(bin 256 is an overflow bin, so p90 = 256 means "≥ 256 px away").

| distribution | n px | p10 | p25 | **p50** | p75 | p90 | ≤10 px | ≤25 px | ≤50 px |
|---|---|---|---|---|---|---|---|---|---|
| (b) inside-loss → crop-rect edge | 79,079 | 3 | 8 | **19** | 46 | 138 | 32.1 % | 58.2 % | 77.0 % |
| (b) inside-loss → nearest **kept ink** (upper bound on the dilation radius needed) | 79,079 | 18 | 27 | **44** | 69 | 111 | 3.9 % | 21.7 % | 58.1 % |
| (a) outside-loss → nearest crop rect (what a pad must reach) | 1,697,548 | 25 | 50 | **106** | 220 | 256 | 2.7 % | 10.6 % | 25.2 % |

The synthetic run reported a median 27 px from the crop edge for the inside-loss; the
real-document figure is **19 px**, which is the one number from the synthetic study that
roughly survives. It is also the least useful of the three: the decision-relevant
distance is to the nearest kept ink (median **44 px** — six times DECIMER's own ~7 px
kernel), and for the outside-loss it is to the nearest rect (median **106 px**, with
only 10.6 % within 25 px).

---

## 5. What each lever would actually deliver

**Read `apply_mask` before reading this table.** With `DECIMER_BBOX_PAD > 0` the
function takes a different branch and returns `image[y0:y1, x0:x1]` **unmasked**. Any
positive pad therefore recovers 100 % of (b) as well as whatever the pad reaches. There
is no "pad without unmasking" setting in this code.

88 structure-bearing figures, Otsu, 3,613,461 ink px:

| setting | retained | vs stock | vs unmask-only |
|---|---|---|---|
| stock (masked, no pad) | 48.0 % | — | — |
| `BBOX_PAD=0.00`+ (unmasked, zero pad) — **the entire ceiling of mask dilation** | 50.6 % | +2.6 pts | — |
| `BBOX_PAD=0.05` | 52.5 % | +4.5 | +1.9 |
| `BBOX_PAD=0.10` | 55.2 % | +7.2 | +4.7 |
| `BBOX_PAD=0.15` | 58.3 % | +10.3 | +7.7 |
| `BBOX_PAD=0.25` | 64.3 % | +16.3 | +13.8 |
| `BBOX_PAD=0.50` | 75.0 % | +27.0 | +24.5 |

And what padding drags in:

| pad | newly included ink | of which **another segment's own ink** |
|---|---|---|
| 0.00 | 141,485 px | 33,174 px (23.4 %) |
| 0.15 | 606,910 px | 162,768 px (26.8 %) |
| 0.25 | 1,087,498 px | 333,467 px (30.7 %) |

Higher retention here is **not** evidence of better recognition. Section 4 says the
outside-loss sits a median 106 px away, and the hand-checks in §6 say what it is: body
text, reagent labels and captions. A pad that raises retention from 48 % to 58 % does it
mainly by swallowing paragraphs, and it hands a quarter to a third of its new ink to the
wrong structure.

---

## 6. Hand-checks (R1, by eye)

Six-panel composites: source / recovered rectangles / three-way partition / lost-inside
painted on the source / engagement / engaged loss only.

| panel | what it settles |
|---|---|
| `<work>/inkloc/composites/hc_PMC11771699_macrocycle_drugs_image_9.png` | The largest (b) bucket in the corpus, 16,092 px. Every red pixel is **reagent text** ("1) 20 % piperidine, DMF", "2) (tBuO)EuE(OtBu)₃ DMF HOBt, TBTU, DIPEA"), compound numbers and the caption — inside the (overlapping) rects and correctly masked out. Engaged loss: 21 px. |
| `<work>/inkloc/composites/hc_PMC11771699_macrocycle_drugs_image_3.png` | Six drug structures, all green. Red = the compound-name labels inside the rects; blue = the figure caption. Engaged loss: 2 px. |
| `<work>/inkloc/composites/hc_PMC11227129_decimer_handdrawn_caffeine_image_2.png` | The figure that dominates every engagement statistic. Panel 2 shows rect 0 on caffeine and rects 1–4 on **neural-network nodes**. |
| `<work>/inkloc/composites/CN108503621B_vonoprazan_image_3.png` | A typical patent scheme. Green sits exactly on the drawings; blue is the Chinese body text, paragraph numbers and reaction annotation. |
| `<work>/inkloc/composites/CN108503621B_vonoprazan_image_1.png` | A stage-1 "figure" that is an **HPLC chromatogram + peak table**. DECIMER cropped the chart; the "lost" 62.8 % is the data table. |
| `<work>/inkloc/composites/hc_CN108503621B_vonoprazan_image_3.png` | Six-panel version of the above scheme. |

Contact sheets for all 135 figures: `composites/contact_000.png` … `contact_132.png`.

---

## 7. Integrity checks

```
figures on disk .................... 135
segments counted (anchored regex) .. 569
segment files on disk .............. 569      <- count identity OK
placements byte-exact .............. 574/574  (574 includes 5 from 2 extra runs)
segments needing >1 offset test .... 2        (both exact, both in order-verified figures)
channel hypothesis != swapRB ....... 0
reading order reproduced ........... 76/76    (DECIMER's own sort, rebuilt from the rects)
partition identity, all thresholds . 714/714  (retained + lost_in + lost_out == total ink)
figures where a PREFIX match would have differed: 5
```

The anchored match is `^Image_DIS_VH_File_<figure>_molecule_\d+\.png$`. A bare prefix
match would have changed 5 figures, some catastrophically:
`PMC11771699_macrocycle_drugs_image_1` has 0 segments and a prefix match claims **95**;
`PMC10180415_..._image_1` has 5 and a prefix claims 39.

Two independently-constructed views, required to agree:
* **placement** — float FFT correlation to locate, exact integer byte comparison to
  verify, plus DECIMER's own reading-order sort rebuilt from the recovered rectangles
  (76/76);
* **totals** — at t = 200 this measurement reproduces the committed
  `ink_retention_real_documents.json` **exactly on 102 of 135 figures**, through a
  different library (cv2 vs PIL) and a different definition (spatial partition vs sum of
  segment ink).

### The 33 that differ, and why

* **22 figures have overlapping crop rectangles** (1,149,202 overlapped px in total).
  The committed JSON sums segment ink, so it **double-counts** the overlap and overstates
  retention: `macrocycle_image_9` 0.860 vs 0.686 here, `macrocycle_image_5` 0.902 vs
  0.741. Counting each figure pixel once is correct; the JSON is high on those figures.
* small differences on coloured figures — the R/B swap of §1 changes the segment's grey.
* a few px from PIL vs cv2 grey rounding at the threshold boundary.

The corpus headline is barely affected (mean 0.3426 → 0.3388, median unchanged), so the
committed summary stands even though 22 per-figure numbers in it do not.

---

## 8. Two claims in `docs/RESUME_PLAN.md` that this measurement contradicts

1. *"The pregabalin patent lost six, including one carrying 145,947 px — the largest
   figure in the document."* `EP0641330B1_pregabalin_image_1` is **two columns of
   literature citations** (contact sheet #17). Of the six pregabalin zero-segment
   figures, three are text or tables; the three that do carry a structure are
   `image_8`, `image_10`, `image_11`, two of them Markush generics.
2. *"`decimer_segmentation.py` differs [from upstream] by three deleted lines, all of
   them the unguarded Zenodo download."* That file also carries the whole
   `DECIMER_BBOX_PAD` branch and a rewritten `_download_weights` with four validation
   checks. The pad branch is precisely the lever under discussion, and it does something
   different from what its name suggests (§5). Worth re-deriving that diff before
   relying on it. (Not verified against an upstream checkout here — only that the local
   file contains substantial additions.)

---

## 9. Files

* per-document JSON (written incrementally, one file per document as it finished):
  `<work>/inkloc/<document>.json` — 20 files (18 primary + 2 tagged
  `extra_corpus`), each carrying per-figure rectangles, placement exactness, the
  3×256 (class, grey) histogram from which the whole threshold sweep is exact, distance
  histograms, the pad simulation and the contamination counts.
* `figure_classification.json` — the by-eye structure/no-structure verdict and reason
  for all 135 figures.
* `figure_index.json` — figure index ↔ contact-sheet caption ↔ path.
* scripts: `measure_inkloc.py`, `aggregate.py`, `final.py`, `composite.py`,
  `composite2.py`, `contact.py`, `classify.py`, `probe_place.py`.
* logs: `run3.log` (the run these numbers come from).
