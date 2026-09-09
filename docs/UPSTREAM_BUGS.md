# Upstream defects found while benchmarking

Written for the C-MAGE / DECIMER-Image-Segmentation maintainers. Every claim below
was measured on this fork, whose stage-2 tree is byte-identical to upstream except
for the vendored `DECIMER_BBOX_PAD` branch and the removed Zenodo download. Line
numbers are from the files as they sit in `cxmolscribe-wd/`.

---

## 1. Red and blue are swapped in every segment PNG

**Where:** `cxmolscribe-wd/DECIMER-Image-Segmentation/pipeline_dis.py:84`

```python
for numeral, img in enumerate(segments):
    img_var = Image.fromarray(img)          # <- img is BGR(A), PIL reads it as RGB(A)
```

**Why:** `decimer_segmentation.py:73` loads a non-PDF input with

```python
images = [cv2.imread(file_path)]            # OpenCV returns BGR
```

so for the image-file path — which is the path C-MAGE always takes, because stage 1
writes PNG figures — the array that reaches `Image.fromarray` is BGR. PIL interprets
it as RGB and writes the file with the red and blue channels exchanged.

The round trip then hides it. Stage 3 reads the segment with
`MolScribe/molscribe/interface.py:154-155`:

```python
image = cv2.imread(path)
image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
```

which faithfully reproduces what the PNG says — so the model sees the swapped
colours, and nothing in the pipeline ever compares a segment back to its source.

**Measured.** Locating each segment inside its source figure by matching on the
GREEN channel only — which an R↔B swap leaves untouched — and then comparing all
three channels at that offset:

| figure | ink px | match as written | match with R,B swapped |
|---|---|---|---|
| PMC11227129_..._image_1 | 3,740 | 2,321 | **3,740 (100.000%)** |
| PMC11227129_..._image_1 (2nd segment) | 1,977 | 84 | **1,977 (100.000%)** |
| PMC13390035_..._image_1 | 378 | 160 | **378 (100.000%)** |
| PMC9185882_..._image_1 | 179 | 12 | **179 (100.000%)** |

Over 1,914 segments from 20 document runs: **1,010 (52.8%) carry colour**
(`|R−B| > 20` on at least one ink pixel), and **21.25% of all segment ink pixels**
(2,465,543 of 11,600,042) are affected. Pure black-on-white line art is unaffected,
which is why this survives on the usual test images.

**Root cause is really an inconsistency two lines apart.** `decimer_segmentation.py`
returns a different channel order depending on the input type:

```python
# 65-71  PDF input   -> pdf2image -> PIL -> np.array(...)   = RGB
# 73     image input -> cv2.imread(...)                     = BGR
```

Everything downstream is correct for exactly one of those.

---

## 2. The Otsu threshold that builds the mask runs on a wrongly-weighted greyscale

**Where:** `cxmolscribe-wd/DECIMER-Image-Segmentation/decimer_segmentation/decimer_segmentation.py:436`

```python
im_gray = cv2.cvtColor(masked_image, cv2.COLOR_RGB2GRAY)
_, im_bw = cv2.threshold(im_gray, 128, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
```

`masked_image` came from the same `cv2.imread` above, so on the image-file path it is
BGR, and `COLOR_RGB2GRAY` applies the red weight (0.299) to the blue channel and the
blue weight (0.114) to the red one. The resulting binary image is what becomes the
alpha channel, so **for any coloured structure the mask boundary is decided by a
luminance that is wrong by construction** — red ink is treated as three times fainter
than it is, blue ink as three times stronger.

This compounds with the fixed binarisation at `complete_structure.py:282`
(`binarize_image(image_array, threshold=0.72)`, overriding the Otsu default at `:25`),
which is already the main driver of ink loss.

---

## 3. `apply_mask` with a bbox pad returns the crop UNMASKED

**Where:** `decimer_segmentation/decimer_segmentation.py:313` (`apply_mask`), the
`DECIMER_BBOX_PAD > 0` branch, which returns `image[y0:y1, x0:x1]` without applying
the mask at all.

This is worth documenting because it makes the two obvious remedies
non-comparable: any positive pad already recovers **100%** of the ink that the mask
would have whitened inside the crop rectangle, so "pad the bbox" and "dilate the
mask" are not two settings of the same dial. Measured on 88 structure-bearing real
figures, mask dilation's entire ceiling is **+2.6 points** of retained ink
(48.0% → 50.6%); `DECIMER_BBOX_PAD=0.15` reaches 58.3%, but 26.8% of the newly
included ink belongs to a *different* segment and most of the remainder is body text.
Higher retention there is not better recognition.

---

## What is NOT a bug, contrary to our own earlier report

We previously measured "stage 2 destroys most real figures — median 29.1% of figure
ink retained, 27% of figures produce zero segments" and traced it to the 0.72
binarisation. That number's denominator was wrong. Classifying all 139 stage-1
figures by eye (twice, independently, agreeing exactly) shows **44 of 139 (32%)
contain no chemistry at all** — body text, data tables, IR spectra, journal
boilerplate. Restricted to the 95 figures that carry a drawn structure:

| | all 139 | structure-bearing 95 |
|---|---|---|
| zero-segment figures | 26.6% | **4.2%** |
| median ink retained | 0.291 | **0.590** |

Segmentation is a good filter: 75% of non-chemistry figures produce no segment and
only 0.9% of non-chemistry ink survives. And on the drawings it does engage with, it
keeps **96.2%–99.8%** of their ink.

The real remaining costs are (1) the colour bugs above, (2) detection — structures it
never engages with, and (3) 11 non-chemistry figures that DO leak 15 false-positive
segments into stage 3. Not the masking.

---

## What the colour swap costs, measured — and why the answer is "not yet known"

Both arms ran stage 3 over the SAME 569 segments from 17 documents. The only
difference is channel order: `stock` is the file as `pipeline_dis.py` wrote it,
`fixed` has R and B exchanged back. 75 of the 569 (13.2%) actually differ; the
other 494 are grey and byte-identical, which makes them a built-in control.

    coloured segments, prediction changed by the fix   30 of 75  (40%)
    grey segments (byte-IDENTICAL input), changed       4 of 494 (0.8%)

That 0.8% is not a bug in the comparison. **CXMolScribe is not deterministic**:
the same file, the same weights, the same device, twice, disagrees about one
prediction in 125. Every A/B on this pipeline has that noise floor, and a
difference of a few structures is not a difference.

The accuracy effect could not be measured on this corpus:

    coloured AND carrying a reference SMILES     44
    of those, prediction changed by the fix      12
    graded-exact GAINED                           0
    graded-exact LOST                             0
    wrong in BOTH arms                           41 of 44

41 of 44 are wrong either way, so there was almost nothing to gain and nothing to
lose. **A null result over a population that is 93% wrong regardless is not
evidence the fix does not help — it is evidence this corpus cannot tell.**

The clearest single case is unscorable: rifampicin in `PMC11771699_macrocycle_drugs`
goes from an unparseable string at confidence 0.574 to a fully stereochemical
CXSMILES at **0.835** once the channels are corrected. That document has no
reference manifest, so it counts for nothing.

### Then it was run, and the answer is a clean null

560 PubChem 2D depictions, 545 of them (97%) carrying colour, every one with an
InChIKey-verified answer. The same images through stage 3 twice — once as they
are, once with red and blue exchanged the way `pipeline_dis.py` writes them:

| arm | strict exact | graded exact |
|---|---|---|
| correct colour | 63/560 = 11.2% | 324/560 = **57.9%** |
| R and B swapped | 69/560 = 12.3% | 331/560 = **59.1%** |

Paired over the 560: **31 images correct only when swapped, 24 correct only when
not.** Net +7 in favour of the wrong colours. Two-sided sign test over the 55
discordant pairs, **p = 0.42**.

**So the swap costs nothing measurable in recognition.** It remains a real defect —
anyone who opens a segment sees the wrong colours, and any downstream consumer of
those PNGs gets them — but it should not be reported as an accuracy bug, and this
document previously implied it might be.

Worth separating: **16.6% of images changed grade between the two arms.** The model
is highly sensitive to its input; it simply has no systematic preference between
the two channel orders. That is not the same claim as "colour does not matter".

One vivid case pointed the other way and was wrong: rifampicin going from an
unparseable string at 0.574 to a full stereochemical CXSMILES at 0.835 when the
channels were corrected. It had no reference SMILES, and a single unscorable
example is an anecdote whichever direction it points.
